#!/usr/bin/env python3
"""Deterministic bilingual-profile audit for a Parallel Reader work directory."""
import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

WORD = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
HAN = re.compile(r"[\u3400-\u9fff]")
SPAN = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*(?:[^\u3400-\u9fffA-Za-z]+[A-Za-z]+(?:['’\-][A-Za-z]+)*)*")
# Must stay in sync with build.py's REFERENCE_HEADING_RE: a translated heading
# ("参考文献") stops the HTML render, so it must also stop the audit denominator.
# "Footnote references" is the Economic History Review's own list heading.
REFERENCE_HEADING = re.compile(
    r"^(?:(?:footnote|literature|source)\s+)?"
    r"(?:references|bibliography|works cited|参考文献)$", re.I
)
METADATA = re.compile(r"(?:https?://|www\.|doi\s*:|orcid|article reuse guidelines)", re.I)


def load_translation(workdir: Path) -> list[str]:
    lines = []
    for path in sorted(workdir.glob("zh-*.txt")):
        lines.extend(x for x in path.read_text().splitlines() if x.strip())
    return lines


def classify(blocks: list[dict]) -> list[str]:
    roles, in_refs = [], False
    for block in blocks:
        text = block["text"].strip()
        if REFERENCE_HEADING.fullmatch(text):
            in_refs = True
            roles.append("reference")
        elif in_refs:
            roles.append("reference")
        elif METADATA.search(text) or (len(text) < 160 and not HAN.search(text) and
                                       ("©" in text or text.count("|") >= 2)):
            roles.append("metadata")
        else:
            roles.append("prose")
    return roles


def pct(n: int, d: int) -> float:
    return round(100 * n / d, 2) if d else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    blocks = [json.loads(x) for x in (args.workdir / "blocks.jsonl").read_text().splitlines() if x.strip()]
    zh = load_translation(args.workdir)
    if len(blocks) != len(zh):
        raise SystemExit(f"translation lines {len(zh)} != block count {len(blocks)}")
    roles = classify(blocks)
    source = "\n".join(b["text"] for b, role in zip(blocks, roles) if role == "prose")
    target = "\n".join(t for t, role in zip(zh, roles) if role == "prose")
    source_words = WORD.findall(source)
    target_words = WORD.findall(target)
    han = HAN.findall(target)
    spans = []
    for match in SPAN.finditer(target):
        words = WORD.findall(match.group())
        if words:
            spans.append(words)
    lengths = [len(x) for x in spans]
    single = sum(n == 1 for n in lengths)
    multi_tokens = sum(n for n in lengths if n > 1)
    transitions = len(re.findall(r"(?<=[\u3400-\u9fff])\s*(?=[A-Za-z])|(?<=[A-Za-z])\s*(?=[\u3400-\u9fff])", target))
    candidates = Counter(" ".join(x) for x in spans if 2 <= len(x) <= 6)
    outliers = []
    for b, t, role in zip(blocks, zh, roles):
        if role != "prose":
            continue
        sw, tw = len(WORD.findall(b["text"])), len(WORD.findall(t))
        ratio = tw / sw if sw else 0
        if sw >= 30 and (ratio < 0.45 or ratio > 0.75):
            outliers.append({"id": b["id"], "sourceWords": sw, "retainedWords": tw, "retention": round(ratio, 3)})
    report = {
        "scope": {"blocks": len(blocks), "proseBlocks": roles.count("prose"), "excludedReferenceBlocks": roles.count("reference"), "excludedMetadataBlocks": roles.count("metadata")},
        "retention": {"sourceEnglishTokens": len(source_words), "retainedEnglishTokens": len(target_words), "percent": pct(len(target_words), len(source_words))},
        "displayUnitHeuristic": {"englishTokens": len(target_words), "hanCharacters": len(han), "englishPercent": pct(len(target_words), len(target_words) + len(han))},
        "transitions": {"boundaries": transitions, "per100SourceWords": round(100 * transitions / len(source_words), 2) if source_words else 0},
        "rawSpans": {"count": len(spans), "meanWords": round(statistics.mean(lengths), 2) if lengths else 0, "medianWords": statistics.median(lengths) if lengths else 0, "lengthDistribution": dict(sorted(Counter(lengths).items())), "singleWord": {"count": single, "spanPercent": pct(single, len(spans)), "englishTokenPercent": pct(single, len(target_words))}, "multiWord": {"count": len(spans) - single, "spanPercent": pct(len(spans) - single, len(spans)), "englishTokenPercent": pct(multi_tokens, len(target_words))}},
        "candidateLearningUnits": [{"unit": unit, "occurrences": count} for unit, count in candidates.most_common(40)],
        "candidateLearningUnitNote": "Proxy only; actual novelty requires the user's KNOWN/LEARNING/UNKNOWN vocabulary data.",
        "outlierBlocks": outliers,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
