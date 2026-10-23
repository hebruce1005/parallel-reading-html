#!/usr/bin/env python3
"""Alternative to extract.py: build page-tagged blocks from a PaddleOCR-VL result.

Use this when the user already supplies a PaddleOCR-VL JSON (`*_by_PaddleOCR-VL-*.json`)
and MinerU must NOT be run — the page ids still come from a page-per-record parser, so
the plugin contract holds. Output is byte-compatible with extract.py: blocks.jsonl
({id, page, printed, level, kind, text}) plus pages.json.

Input shape (one list entry per PDF page, in file order):

    [{"prunedResult": {"parsing_res_list": [
        {"block_label": "header|number|doc_title|paragraph_title|text|abstract|
                         footnote|reference_content|footer|aside_text",
         "block_content": "..."}, ...]}, ...}, ...]

Label handling mirrors extract.py's intent:
  * header / footer / aside_text  -> dropped (running heads, download stamps)
  * number                        -> the printed folio (not a constant offset)
  * doc_title / paragraph_title   -> headings, level 2, leading '#' stripped
  * footnote                      -> kind="footnote" (kept; rendered as a note)
  * everything else               -> body text, in document order
"""
import argparse
import json
import re
from pathlib import Path

DROP = {"header", "footer", "aside_text"}
# PaddleOCR wraps folios in brackets ("[35]"), and on some pages the folio is
# emitted as a `header` block instead of a `number` block, so both are inspected.
# Must not swallow things like "[I. Satanic Mill]" — digits only, no other words.
FOLIO = re.compile(r"^[\[\(]?\s*(\d{1,4})\s*[\]\)]?\.?$")
FOOTNOTE_REF = re.compile(r"\$\s*\^\{([^}]*)\}\s*\$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="PaddleOCR-VL JSON file")
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument(
        "--pages", type=int, nargs=2, metavar=("LO", "HI"),
        help="keep only blocks on pdfPageIndex LO..HI inclusive (staged delivery: "
             "pair with renderPages in the paper config so every page still gets an "
             "anchor)",
    )
    args = ap.parse_args()
    lo, hi = (args.pages if args.pages else (None, None))

    pages = json.loads(args.source.read_text(encoding="utf-8-sig"))
    blocks: list[dict] = []
    printed: dict[int, str] = {}

    for page_no, page in enumerate(pages):
        if lo is not None and not (lo <= page_no <= hi):
            continue
        pruned = page.get("prunedResult") or page
        for item in pruned.get("parsing_res_list", []):
            label = item.get("block_label")
            text = (item.get("block_content") or "").strip()
            if not text:
                continue
            if label in ("number", "header"):
                folio = FOLIO.match(text)
                if folio and int(folio.group(1)) > 0:
                    printed.setdefault(page_no, folio.group(1))
                continue
            if label in DROP:
                continue
            if label in ("doc_title", "paragraph_title"):
                text = re.sub(r"^#+\s*", "", text)
                level = 2
            else:
                level = None
            # Footnote markers carry a space inside the delimiters in PaddleOCR
            # output ("$ ^{1} $"); build.py only recognises "$^{1}$".
            text = FOOTNOTE_REF.sub(r"$^{\1}$", text)
            text = re.sub(r"[ \t]+", " ", text).strip()
            blocks.append({
                "id": f"block-{len(blocks) + 1:04d}",
                "page": page_no,
                "printed": printed.get(page_no),
                "level": level,
                "kind": "footnote" if label == "footnote" else "text",
                "text": text,
            })

    args.workdir.mkdir(parents=True, exist_ok=True)
    with (args.workdir / "blocks.jsonl").open("w", encoding="utf-8") as fh:
        for b in blocks:
            fh.write(json.dumps(b, ensure_ascii=False) + "\n")
    (args.workdir / "pages.json").write_text(
        json.dumps({str(p): {"printed": printed.get(p)} for p in range(len(pages))},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"blocks={len(blocks)} chars={sum(len(b['text']) for b in blocks)} "
          f"pages={len(pages)}")
    for p in range(len(pages)):
        rows = [b for b in blocks if b["page"] == p]
        print(f"  page {p:3d} printed={printed.get(p)!s:>6} blocks={len(rows):3d} "
              f"chars={sum(len(b['text']) for b in rows)}")
    if not printed:
        print("  NOTE: no folio found — page labels fall back to file page numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
