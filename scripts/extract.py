#!/usr/bin/env python3
"""Turn MinerU output into page-tagged blocks ready for translation.

Reads the `content_list.json` from a MinerU result directory (or the file
itself) and writes, into --workdir:

  blocks.jsonl  one JSON object per translatable block, in document order:
                {id, page, printed, level, kind, text}
  pages.json    {page: {printed}} — the printed folio found on each PDF page

Running heads, running feet and the JSTOR download stamp are dropped; body text
and footnotes are kept. `page_idx` is the zero-based *file* page index and is
what the plugin locates on, so it is preserved verbatim.

The printed folio is taken from MinerU's `page_number` items, which is the only
reliable source — it is NOT a constant offset from the file page index, because
covers and front matter break that.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DROP_FOOTER = re.compile(
    r"This content downloaded from|^JSTOR$|^J$|^The International History Review,",
)


def find_content_list(source: Path) -> Path:
    if source.is_file():
        return source
    # Prefer the v1 file: it carries `page_idx`, which v2 does not.
    candidates = sorted(
        p
        for p in source.rglob("*content_list*.json")
        if "v2" not in p.name
    )
    if not candidates:
        raise SystemExit(f"no content_list*.json found under {source}")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="MinerU result dir or content_list.json")
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()

    items = json.loads(find_content_list(args.source).read_text())

    by_page: dict[int, list[dict]] = defaultdict(list)
    printed: dict[int, str] = {}
    for it in items:
        page = it.get("page_idx")
        kind = it.get("type")
        text = (it.get("text") or "").strip()
        if page is None or not text:
            continue
        if kind == "page_number":
            # A folio must look like a page number. Some scans carry a
            # decorative placeholder (e.g. "000") where the folio should be;
            # keeping it would stamp "printed=000" onto every page section.
            if re.fullmatch(r"\d{1,4}", text) and int(text) > 0:
                printed[page] = text
            continue
        if kind == "footer" and DROP_FOOTER.search(text):
            continue
        # Running heads repeat the author/title; they carry no content.
        if kind == "header":
            continue
        by_page[page].append(it)

    blocks = []
    for page in sorted(by_page):
        for it in by_page[page]:
            blocks.append(
                {
                    "id": f"block-{len(blocks) + 1:04d}",
                    "page": page,
                    "printed": printed.get(page),
                    "level": it.get("text_level"),
                    "kind": "footnote"
                    if it.get("type") == "page_footnote"
                    else "text",
                    "text": re.sub(r"\s+", " ", (it.get("text") or "").strip()),
                }
            )

    args.workdir.mkdir(parents=True, exist_ok=True)
    with (args.workdir / "blocks.jsonl").open("w") as fh:
        for b in blocks:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")
    (args.workdir / "pages.json").write_text(
        json.dumps(
            {str(p): {"printed": printed.get(p)} for p in sorted(by_page)},
            ensure_ascii=False,
            indent=1,
        )
    )

    total = sum(len(b["text"]) for b in blocks)
    print(f"blocks={len(blocks)} chars={total} pages={len(by_page)}")
    for p in sorted(by_page):
        n = sum(1 for b in blocks if b["page"] == p)
        c = sum(len(b["text"]) for b in blocks if b["page"] == p)
        print(f"  page {p:3d} printed={printed.get(p)!s:>6} blocks={n:3d} chars={c}")
    if not printed:
        print(
            "  NOTE: no page_number found — printed labels will fall back to "
            "file page numbers.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())