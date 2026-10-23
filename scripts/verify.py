#!/usr/bin/env python3
"""Check a generated bilingual HTML against the plugin's contract.

Structural checks only. Whether the buttons actually locate cannot be checked
here — that depends on which PDF the user opens, because the plugin compares the
open file's md5 against the map's.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SECTIONS = 'data-pr-page="'
BLOCKS = re.compile(r"data-pr-id=")
MAP = re.compile(r'id="parallel-reader-map">(.*?)</script>', re.S)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    args = parser.parse_args()

    text = args.html.read_text()
    match = MAP.search(text)
    if not match:
        raise SystemExit("FAIL: no #parallel-reader-map element")
    page_map = json.loads(match.group(1))
    page_count = page_map["source"]["pageCount"]
    md5 = page_map["source"]["md5"]

    sections = text.count(SECTIONS)
    blocks = len(BLOCKS.findall(text))
    leftover = text.count("$^{")
    terms = text.count('class="pr-term')
    conclusions = text.count('class="pr-conclusion"')
    content = page_map.get("content") or {}
    references_omitted = bool(content.get("referencesOmitted"))
    omitted_anchors = text.count('class="pr-page pr-page-omitted"')

    print(f"file          {args.html.name}")
    print(f"map           md5={md5} pageCount={page_count}")
    print(f"sections      {sections} (expected {page_count})")
    print(f"blocks        {blocks}")
    print(f"footnote refs {leftover} left as $^{{  (must be 0)")
    print(f"terms         {terms}")
    print(f"conclusions   {conclusions}")
    print(f"references    {'omitted' if references_omitted else 'included/not detected'}")
    print(f"empty anchors {omitted_anchors}")

    problems = []
    if sections != page_count:
        problems.append(f"sections {sections} != pageCount {page_count}")
    if leftover:
        problems.append(f"{leftover} unconverted footnote markers")
    if not re.fullmatch(r"[a-f0-9]{32}", md5):
        problems.append(f"md5 is not 32-char lowercase hex: {md5!r}")
    pages = sorted(int(m) for m in re.findall(r'data-pr-page="(\d+)"', text))
    if pages and pages != list(range(page_count)):
        problems.append(f"page sections not contiguous: {pages}")
    if references_omitted and "lastRenderedBlock" not in content:
        problems.append("reference cutoff lacks lastRenderedBlock metadata")

    if problems:
        print("\nFAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    print("\nOK — structure matches the contract")
    print("Note: confirm in Zotero that the user opens the exact PDF whose md5 is above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
