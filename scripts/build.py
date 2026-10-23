#!/usr/bin/env python3
"""Merge page-tagged blocks with a translation into the reading artefacts.

Produces, in --out:

  <title>（中文翻译）.md     the translation, keeping every block id and page
  <title>（双语对照）.html   what the Parallel Reader plugin loads

The translation is read from every `zh-*.txt` in --workdir, in sorted filename
order, one block per line, in the same order as `blocks.jsonl`. Ordering is the
whole contract: ids are assigned by position, so they can never drift out of
alignment with the blocks they describe. A count mismatch aborts.

The HTML carries, per the plugin's contract:
  * one `<section data-pr-page="N">` per PDF page, N zero-based, so
    "go to translation" can scroll to the page and "go to original" can read
    the page back from the topmost visible section;
  * a `#parallel-reader-map` JSON element declaring the source PDF's MD5 and
    page count, which is what stops the plugin from silently mis-locating when
    the wrong PDF is open.

Editorial emphasis is configured per paper via --config (see --help); every
configured phrase is asserted to have matched, so a typo aborts instead of
silently dropping an emphasis.
"""
import base64
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from overview import update_html

SEPARATOR = "* * * * *"
FOOTNOTE_RE = re.compile(r"\$\^\{([^}]*)\}\$")
# Journals do not always title the list plainly. "Footnote references" is the
# Economic History Review's own heading; without it the cutoff would silently
# fail and the whole bibliography would be rendered as body text.
# audit.py must use the identical pattern (it is the same editorial judgement).
REFERENCE_HEADING_RE = re.compile(
    r"^(?:(?:footnote|literature|source)\s+)?"
    r"(?:references|bibliography|works cited|参考文献)$", re.I
)
# PaddleOCR-VL returns table content as HTML (`<table>…`). The cells carry the
# paper's numbers, which must survive verbatim, so the markup is passed through
# a strict whitelist instead of being escaped into visible source text.
TABLE_RE = re.compile(r"^<table(?:\s[^>]*)?>", re.I)
TABLE_TAG_RE = re.compile(
    r"</?(?:table|thead|tbody|tfoot|tr|th|td|caption|sup|sub|b|i|em|strong|br)"
    r"(?:\s+(?:rowspan|colspan)\s*=\s*(?:\"[^\"]{0,4}\"|'[^']{0,4}'))*\s*/?>",
    re.I,
)
# A `kind == "footnote"` block can hold several numbered notes; each `$^{n}$`
# opens one. Used when footnotes are hoisted into an end section.
NOTE_SPLIT_RE = re.compile(r"\$\^\{([^}]*)\}\$")


def split_notes(text: str) -> list[tuple[str | None, str]]:
    """Split one footnote block into [(marker_or_None, note_body), ...]."""
    marks = list(NOTE_SPLIT_RE.finditer(text))
    if not marks:
        return [(None, text.strip())]
    out: list[tuple[str | None, str]] = []
    for k, mark in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        body = text[mark.end():end].strip()
        if body:
            out.append((mark.group(1), body))
    return out or [(None, text.strip())]

# Terms are per paper, so the default is empty; supply them via --config.
DEFAULT_TERMS: list[str] = []

DEFAULT_CONFIG = {
    "terms": DEFAULT_TERMS,
    # "all" chips every occurrence, "first" only the one that introduces the
    # term. Use "first" when a term is a common word in the paper's own language
    # and chipping every instance would be noise.
    "termChip": "all",
    "conclusions": {},
    "inferredLabels": {},
    "author": "",
    "source": "",
    "htmlStopBeforeReferences": True,
    # Hoist every `kind == "footnote"` block out of its page section into a single
    # end section, and turn the in-text markers into links to it. Page sections and
    # the 0..pageCount-1 mapping are untouched: the notes section carries no
    # `data-pr-page`, exactly like the overview.
    "footnotesAtEnd": True,
    # Free-text line for staged deliveries of a long source (a book part done in
    # rounds). Shown in the md header and the HTML header. Does not affect the
    # page mapping — unlike `renderPages`, which only knows about this run's
    # blocks and therefore cannot report how much of the source is still missing.
    "scopeNote": "",
}


def load_translation(workdir: Path) -> list[str]:
    files = sorted(workdir.glob("zh-*.txt"))
    if not files:
        raise SystemExit(f"no zh-*.txt translation files in {workdir}")
    out: list[str] = []
    for path in files:
        for line in path.read_text().splitlines():
            if line.strip():
                out.append(line)
    return out


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html_fragment(text: str) -> str:
    """Escape a table block, letting only whitelisted table markup through."""
    out, pos = [], 0
    for match in TABLE_TAG_RE.finditer(text):
        out.append(esc(text[pos:match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(esc(text[pos:]))
    return "".join(out)


class Emphasis:
    def __init__(self, config: dict):
        self.terms = config.get("terms") or []
        self.chip_all = config.get("termChip", "all") != "first"
        self.conclusions = config.get("conclusions") or {}
        self.introduced: set[str] = set()
        self.matched = 0
        self.expected = 0
        # note numbers that will get an anchor in the end section: markers for
        # these become links, the rest stay plain superscripts
        self.footnote_links: set[str] = set()
        self.linked: set[str] = set()

    def render_footnote_marker(self, match: re.Match[str]) -> str:
        num = match.group(1)
        if num not in self.footnote_links or num in self.linked:
            return f"<sup>{num}</sup>"
        self.linked.add(num)
        return (
            f'<a class="pr-fnref" href="#pr-note-{num}" id="pr-fnref-{num}">'
            f"<sup>{num}</sup></a>"
        )

    def mark_terms(self, text: str) -> str:
        for term in sorted(self.terms, key=len, reverse=True):
            pattern = re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])")

            def chip(match: re.Match[str], term: str = term) -> str:
                if term in self.introduced:
                    return (
                        f'<span class="pr-term">{match.group(0)}</span>'
                        if self.chip_all
                        else match.group(0)
                    )
                self.introduced.add(term)
                return (
                    f'<span class="pr-term pr-term-first">{match.group(0)}'
                    '<i class="pr-term-tag">术语首见</i></span>'
                )

            text = pattern.sub(chip, text)
        return text

    def mark_conclusions(self, text: str, block_id: str) -> str:
        for phrase in self.conclusions.get(block_id, []):
            self.expected += 1
            if phrase not in text:
                raise SystemExit(
                    f"conclusion phrase not found in {block_id}: {phrase!r}"
                )
            self.matched += 1
            text = text.replace(
                phrase, f'<span class="pr-conclusion">{phrase}</span>', 1
            )
        return text

    def render(self, text: str, block_id: str) -> str:
        # Conclusions first: a conclusion containing a term would otherwise have
        # that term's markup inserted into it and the exact match would fail.
        handler = self.render_footnote_marker if self.footnote_links else None
        out = FOOTNOTE_RE.sub(handler or r"<sup>\1</sup>", esc(text))
        out = self.mark_conclusions(out, block_id)
        return self.mark_terms(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True, help="source PDF (hashed into the map)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="per-paper JSON config")
    args = parser.parse_args()

    config = dict(DEFAULT_CONFIG)
    if args.config:
        config.update(json.loads(args.config.read_text()))

    blocks = [
        json.loads(line)
        for line in (args.workdir / "blocks.jsonl").read_text().splitlines()
        if line.strip()
    ]
    zh = load_translation(args.workdir)

    block_pages = sorted({b["page"] for b in blocks})
    derived_count = max(block_pages) + 1 if block_pages else 0
    configured_count = config.get("pageCount")
    page_count = int(configured_count) if configured_count else derived_count
    if page_count < derived_count:
        raise SystemExit(
            f"pageCount {page_count} is below the highest block page "
            f"{derived_count - 1}; sections would be lost"
        )
    # Every page in 0..pageCount-1 gets a section, including pages that carry no
    # block at all (blank leaves, plates). A missing section is a page the
    # plugin could never locate.
    pages = list(range(page_count))

    # Optional staged delivery: only blocks on pages inside `renderPages`
    # (inclusive zero-based file page range) are rendered and translated. Every
    # other page becomes an empty anchor, which keeps the 0..pageCount-1 mapping
    # intact so a later round can fill in the rest without rebuilding the map.
    render_range = config.get("renderPages")
    if render_range:
        lo, hi = int(render_range[0]), int(render_range[1])
        selected = [i for i, b in enumerate(blocks) if lo <= b["page"] <= hi]
    else:
        selected = list(range(len(blocks)))

    if len(zh) != len(selected):
        raise SystemExit(
            f"translation lines {len(zh)} != rendered block count {len(selected)}; "
            "the translation must cover every rendered block, in order"
        )
    text_by_index = dict(zip(selected, zh))

    md5 = hashlib.md5(args.pdf.read_bytes()).hexdigest()
    inferred = {int(k): v for k, v in (config.get("inferredLabels") or {}).items()}
    printed_by_page = {b["page"]: b["printed"] for b in blocks}

    def label(page: int, printed: str | None) -> str:
        valid_printed = printed if printed and re.fullmatch(r"\d{1,4}", str(printed)) and int(printed) > 0 else None
        return valid_printed or inferred.get(page) or str(page + 1)

    def label_first(page: int) -> str:
        return label(page, printed_by_page.get(page))

    emphasis = Emphasis(config)

    reference_start = None
    if config.get("htmlStopBeforeReferences", True):
        reference_start = next(
            (i for i, b in enumerate(blocks) if REFERENCE_HEADING_RE.fullmatch(b["text"].strip())),
            None,
        )

    if config.get("footnotesAtEnd") is not True:
        raise SystemExit("footnotesAtEnd must be true")
    omitted = set(config.get("htmlOmitBlockIds", []))
    overrides = config.get("htmlBlockText", {})
    crops = config.get("pdfCrops", {})
    known = {b["id"] for b in blocks}
    if (omitted | set(overrides) | set(crops)) - known:
        raise SystemExit("HTML configuration refers to unknown block IDs")
    if omitted & set(crops):
        raise SystemExit("A crop block cannot also be omitted")
    footnotes_at_end = True
    in_scope = [i for i in selected if reference_start is None or i < reference_start]
    if footnotes_at_end:
        note_idx = [i for i in in_scope if blocks[i]["kind"] == "footnote"]
        page_idx = [i for i in in_scope if blocks[i]["kind"] != "footnote"]
        emphasis.footnote_links = {
            num
            for i in note_idx
            for num, _ in split_notes(text_by_index[i])
            if num is not None
        }
    else:
        note_idx, page_idx = [], in_scope

    # ---- Markdown ----
    md = [
        f"# {args.title}（中文翻译）",
        "",
        f"> 页码映射：pdfPageIndex 0–{page_count - 1}，共 {page_count} 页；源 PDF md5 `{md5}`",
        "",
    ]
    if footnotes_at_end and note_idx:
        md += [f"> 脚注（{len(note_idx)} 个 block）统一后置于文末。", ""]
    if config.get("scopeNote"):
        md += [f"> {config['scopeNote']}", ""]
    if render_range and not config.get("scopeNote"):
        md += [
            f"> 本轮仅渲染 pdfPageIndex {int(render_range[0])}–{int(render_range[1])}"
            f"（印刷页 {label_first(int(render_range[0]))}–{label_first(int(render_range[1]))}）；"
            f"其余 {len(blocks) - len(selected)} 个 block 尚未翻译。",
            "",
        ]
    md.append("")
    for page in pages:
        rows = [i for i in page_idx if blocks[i]["page"] == page]
        if not rows:
            continue
        md.append(f"## 第 {page + 1} 页 · 印刷页 {label_first(page)}")
        md.append("")
        for i in rows:
            b = blocks[i]
            text = text_by_index[i]
            md.append(
                f"<!-- {b['id']} · pdfPageIndex={b['page']} · "
                f"printed={label_first(page)} -->"
            )
            md.append(FOOTNOTE_RE.sub(r"<sup>\1</sup>", text))
            md.append("")
    if note_idx:
        md += ["## 脚注（Notes）", ""]
        for i in note_idx:
            b, text = blocks[i], text_by_index[i]
            md.append(
                f"<!-- {b['id']} · pdfPageIndex={b['page']} · "
                f"printed={label_first(b['page'])} -->"
            )
            md.append(
                f"（源：PDF 第 {b['page'] + 1} 页 · 印刷页 {label_first(b['page'])}）"
                f" {FOOTNOTE_RE.sub(r'<sup>\1</sup>', text)}"
            )
            md.append("")

    # Apply presentation filtering only after writing the archival Markdown.
    page_idx = [i for i in page_idx if blocks[i]["id"] not in omitted]
    note_idx = [i for i in note_idx if blocks[i]["id"] not in omitted]
    crop_images = {}
    visible_ids = {blocks[i]["id"] for i in page_idx}
    if set(crops) & visible_ids:
        import fitz
        with fitz.open(args.pdf) as pdf:
            for b in blocks:
                if b["id"] not in crops or b["id"] not in visible_ids:
                    continue
                crop = crops[b["id"]]
                if crop["page"] != b["page"]:
                    raise SystemExit("Crop page does not match block page")
                page = pdf[crop["page"]]
                rect = fitz.Rect(crop["bbox"])
                if rect.is_empty or rect.is_infinite or not page.rect.contains(rect):
                    raise SystemExit("Invalid or out-of-page crop rectangle")
                png = page.get_pixmap(clip=rect, dpi=180, alpha=False).tobytes("png")
                crop_images[b["id"]] = base64.b64encode(png).decode("ascii")

    # ---- HTML ----
    body: list[str] = []
    for page in pages:
        page_label = esc(label_first(page))
        visible = [
            (i, blocks[i], text_by_index[i])
            for i in page_idx
            if blocks[i]["page"] == page
        ]
        if not visible:
            body.append(
                f'<section class="pr-page pr-page-omitted" data-pr-page="{page}" '
                f'data-pr-label="{page_label}" aria-hidden="true"></section>'
            )
            continue
        body.append(
            f'<section class="pr-page" data-pr-page="{page}" '
            f'data-pr-label="{page_label}">'
        )
        body.append(
            f'<div class="pr-page-mark"><span>PDF 第 {page + 1} 页'
            f" · 印刷页 {page_label}</span></div>"
        )
        for _, b, text in visible:
            cls = "pr-block"
            attrs = f'data-pr-id="{b["id"]}" data-pr-page-ref="{b["page"]}"'
            text = overrides.get(b["id"], text)
            if b["id"] in crop_images:
                body.append(f'<div class="pr-block pr-figure" {attrs}>'
                            f'<img src="data:image/png;base64,{crop_images[b["id"]]}" '
                            f'alt="原 PDF 图表" style="max-width:100%;height:auto"></div>')
            elif text.strip() == SEPARATOR or (SEPARATOR in text and len(text) < 30):
                body.append(f'<div class="pr-sep" {attrs}>* * * * *</div>')
            elif TABLE_RE.match(text.strip()):
                raise SystemExit(f"Table {b['id']} requires a pdfCrops entry")
            elif b["level"] == 2:
                body.append(
                    f'<h2 class="{cls}" {attrs}>{emphasis.render(text, b["id"])}</h2>'
                )
            else:
                body.append(
                    f'<p class="{cls}" {attrs}>{emphasis.render(text, b["id"])}</p>'
                )
        body.append("</section>")

    if note_idx:
        body.append('<section class="pr-notes" id="pr-notes">')
        body.append(
            '<div class="pr-page-mark"><span>脚注 · Notes</span></div>'
        )
        for i in note_idx:
            b, text = blocks[i], text_by_index[i]
            src = f"PDF 第 {b['page'] + 1} 页 · 印刷页 {label_first(b['page'])}"
            body.append(
                f'<div class="pr-block pr-note" data-pr-id="{b["id"]}" '
                f'data-pr-page-ref="{b["page"]}">'
            )
            for num, note_body in split_notes(text):
                anchor = f' id="pr-note-{num}"' if num else ""
                back = (
                    f'<a class="pr-fnback" href="#pr-fnref-{num}" '
                    f'title="回到正文">↑</a>'
                    if num in emphasis.linked
                    else ""
                )
                marker = num if num else "※"
                body.append(
                    f'<p class="pr-note-item"{anchor}>'
                    f'<span class="pr-note-num">{esc(marker)}</span>'
                    f"{emphasis.render(note_body, b['id'])}{back}"
                    f'<span class="pr-note-src">{esc(src)}</span></p>'
                )
            body.append("</div>")
        body.append("</section>")

    dom_order = page_idx + note_idx
    rendered = [i for i in dom_order]
    page_map = json.dumps(
        {
            "schema": "parallel-reader-pages-v1",
            "source": {"md5": md5, "pageCount": page_count},
            "content": {
                "referencesOmitted": reference_start is not None,
                "renderedPages": (
                    [int(render_range[0]), int(render_range[1])] if render_range else None
                ),
                "lastRenderedBlock": (
                    blocks[rendered[-1]]["id"] if rendered else None
                ),
                "footnotesAtEnd": footnotes_at_end,
            },
        },
        ensure_ascii=False,
    )

    style = (Path(__file__).parent / "assets" / "reading.css").read_text()
    meta = config.get("author") or ""
    # The legend has to describe the mode actually in use: under termChip
    # "first" there is no plain grey chip for later occurrences.
    term_legend = (
        "标记关键术语首次出现，其后的出现处为普通灰底；"
        if emphasis.chip_all
        else "仅标记关键术语的首次出现；"
    )
    note_legend = (
        "全部脚注已移至文末，正文中的脚注序号可点击跳转；"
        if footnotes_at_end and note_idx
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(args.title)}（中文翻译）</title>
<style>
{style}</style>
</head>
<body>
<header class="pr-doc-head">
  <h1>{esc(args.title)}</h1>
  {f'<p class="pr-meta">{esc(meta)}</p>' if meta else ""}
  {f'<p class="pr-meta">{esc(config["scopeNote"])}</p>' if config.get("scopeNote") else ""}
  <p class="pr-legend">
    <b>阅读标记</b>（全部为黑白灰，不影响原文）：
    <span class="pr-term pr-term-first">术语<i class="pr-term-tag">术语首见</i></span>
    {term_legend}
    <span class="pr-conclusion">灰色下划线</span> 标记论文的关键结论句。
    {note_legend}
  </p>
</header>
{chr(10).join(body)}
<script type="application/json" id="parallel-reader-map">{page_map}</script>
</body>
</html>
"""

    html = update_html(html, config)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.title}（中文翻译）.md").write_text("\n".join(md))
    (args.out / f"{args.title}（双语对照）.html").write_text(html)

    html_blocks = len(rendered)
    print(f"pages={page_count} blocks={len(blocks)} translation={len(zh)} htmlBlocks={html_blocks}")
    if reference_start is None and config.get("htmlStopBeforeReferences", True):
        print("  NOTE: no reference heading found — HTML cutoff was not applied.", file=sys.stderr)
    elif reference_start is not None:
        print(f"references omitted from HTML starting at {blocks[reference_start]['id']}")
    print(
        f"terms introduced={len(emphasis.introduced)}/{len(emphasis.terms)}: "
        f"{sorted(emphasis.introduced)}"
    )
    print(f"conclusions matched={emphasis.matched}/{emphasis.expected}")
    print(f"md5={md5} out={args.out}")
    if not emphasis.terms:
        print("  NOTE: no terms configured — term emphasis skipped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
