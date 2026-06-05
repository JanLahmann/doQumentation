#!/usr/bin/env python3
"""
Detect duplicated prose: a paragraph (or near-identical paragraph) rendered
twice within a single translated file — a two-pass-merge artifact the Opus
deep-review repeatedly flagged (ms/vqe, id/deutsch-jozsa, tl/index, ...).

Deterministic and locale-agnostic: normalizes prose paragraphs (lowercase,
collapse whitespace, drop punctuation) and flags pairs that are identical or
near-identical (token Jaccard ≥ --threshold). Compares against the EN source's
own duplication so a paragraph that is ALSO repeated in English (legitimately,
e.g. a repeated callout) is NOT flagged — only translation-introduced
duplication.

Prose only (reuses check-glossary-consistency.to_prose) so repeated code/output
blocks are ignored. Short paragraphs (< --min-words) are skipped to avoid
flagging boilerplate one-liners.

Usage:
    python3 translation/scripts/check-duplication.py --locale ms \
        --file learning/courses/quantum-diagonalization-algorithms/vqe.mdx
    python3 translation/scripts/check-duplication.py --locale id --report
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DOCS_DIR = REPO_ROOT / "docs"


def _imp(name, fn):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / fn)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_chk = _imp("glossary_check", "check-glossary-consistency.py")


def _is_structural(raw: str) -> bool:
    """Headings, list-marker-only lines, table rows, and admonition markers are
    legitimately repeatable (e.g. four '### Check your understanding' sections) —
    never flag them as duplication."""
    s = raw.lstrip()
    return (s.startswith("#") or s.startswith("|") or s.startswith(":::")
            or s.startswith(">") or re.match(r"^[-*+]\s", s) is not None
            or re.match(r"^\d+\.\s", s) is not None)


def _paragraphs(text: str):
    """Yield (start_line, normalized, raw) prose paragraphs (headings/structural
    lines excluded — they're legitimately repeatable)."""
    prose = _chk.to_prose(text)
    lines = prose.splitlines()
    buf, start = [], None
    paras = []
    for i, line in enumerate(lines, 1):
        if line.strip() and not _is_structural(line):
            if start is None:
                start = i
            buf.append(line.strip())
        else:
            if buf:
                paras.append((start, " ".join(buf)))
                buf, start = [], None
    if buf:
        paras.append((start, " ".join(buf)))
    out = []
    for start, raw in paras:
        norm = re.sub(r"[^\w\s]", "", raw.lower())
        norm = re.sub(r"\s+", " ", norm).strip()
        out.append((start, norm, raw))
    return out


def _tokens(norm: str):
    return set(norm.split())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_duplication(text: str, en_text: str | None,
                     threshold: float, min_words: int,
                     max_gap: int | None = None):
    """Return list of {line_a, line_b, similarity, preview} duplicate pairs
    not also present in the EN source.

    max_gap: if set, only flag pairs whose paragraphs are within this many lines
    of each other — the back-to-back signature of a real two-pass-merge dup,
    which excludes legitimately-scattered repeated boilerplate (quiz/survey
    instructions repeated once per section). Strongly recommended: without it,
    duplication is dominated by legitimate repeats (~50 files/locale, mostly
    'Check your understanding' widget boilerplate the EN renders as a component)."""
    paras = [(s, n, r) for (s, n, r) in _paragraphs(text)
             if len(n.split()) >= min_words]

    # EN's own duplicate signatures (so we don't flag legit EN repeats)
    en_dupe_sigs = set()
    if en_text:
        en_paras = [n for (_s, n, _r) in _paragraphs(en_text)
                    if len(n.split()) >= min_words]
        seen = set()
        for n in en_paras:
            if n in seen:
                en_dupe_sigs.add(n)
            seen.add(n)

    dupes = []
    for i in range(len(paras)):
        for j in range(i + 1, len(paras)):
            si, ni, ri = paras[i]
            sj, nj, rj = paras[j]
            if ni in en_dupe_sigs:  # legit EN repeat — skip
                continue
            if max_gap is not None and (sj - si) > max_gap:
                continue  # far-apart repeat — almost always legit boilerplate
            if ni == nj:
                sim = 1.0
            else:
                sim = _jaccard(_tokens(ni), _tokens(nj))
                if sim < threshold:
                    continue
            dupes.append({
                "line_a": si, "line_b": sj, "similarity": round(sim, 2),
                "preview": ri[:90],
            })
    return dupes


def iter_files(locale):
    base = _chk.locale_current_dir(locale)
    if base.exists():
        for p in sorted(base.rglob("*.mdx")):
            yield p.relative_to(base).as_posix(), p


def main():
    ap = argparse.ArgumentParser(description="Detect duplicated prose paragraphs")
    ap.add_argument("--locale", required=True)
    ap.add_argument("--file")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.85,
                    help="token-Jaccard similarity to flag (default 0.85)")
    ap.add_argument("--min-words", type=int, default=12,
                    help="skip paragraphs shorter than this (default 12)")
    ap.add_argument("--max-gap", type=int, default=8,
                    help="only flag pairs within N lines (back-to-back dup "
                         "signature); default 8. Use 0/negative to disable "
                         "(WARNING: floods with legit boilerplate repeats).")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    max_gap = args.max_gap if args.max_gap > 0 else None

    def en_for(rel):
        p = DOCS_DIR / rel
        return p.read_text(encoding="utf-8") if p.exists() else None

    if args.file:
        p = _chk.locale_current_dir(args.locale) / args.file
        if not p.exists():
            print(f"not found: {p}", file=sys.stderr); sys.exit(2)
        d = find_duplication(p.read_text(encoding="utf-8"), en_for(args.file),
                             args.threshold, args.min_words, max_gap)
        if args.json:
            import json
            print(json.dumps({"file": args.file, "duplicates": d},
                             ensure_ascii=False, indent=2))
        elif d:
            print(f"{args.file}: {len(d)} duplicated paragraph(s)")
            for x in d:
                print(f"  L{x['line_a']} ≈ L{x['line_b']} (sim {x['similarity']}): "
                      f"{x['preview']}…")
        else:
            print(f"{args.file}: no duplication")
        return

    if args.report:
        rows = []
        for rel, p in iter_files(args.locale):
            d = find_duplication(p.read_text(encoding="utf-8"), en_for(rel),
                                 args.threshold, args.min_words, max_gap)
            if d:
                rows.append((rel, d))
        if args.json:
            import json
            print(json.dumps([{"file": r, "duplicates": d} for r, d in rows],
                             ensure_ascii=False, indent=2))
            return
        print(f"{args.locale}: {len(rows)} file(s) with duplicated prose\n")
        for rel, d in rows:
            print(f"  {rel}  ({len(d)} pair(s); first: L{d[0]['line_a']}≈L{d[0]['line_b']})")
        return

    ap.error("--file or --report required")


if __name__ == "__main__":
    main()
