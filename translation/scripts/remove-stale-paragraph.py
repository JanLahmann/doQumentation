#!/usr/bin/env python3
"""Remove a paragraph from translations after English deleted it.

When upstream drops a paragraph, translations keep it until someone notices.
`guides/job-limits.mdx` kept a replaced one in six locales for months; the
pre-course survey paragraph outlived its English original in 188 files across
all seventeen locales, leaving readers clicking a dead IBM feedback form.

This removes such a paragraph wherever the *translation* still has it and that
file's *own* English counterpart no longer does. The per-file comparison is the
safety property: English still carries pre-course surveys in 30 files, so a
blanket delete would strip legitimate content.

An "anchor" identifies the paragraph across languages — a URL, an identifier,
anything that survives translation. Prose cannot be matched cross-language, so
only anchor-identifiable paragraphs are in scope; that covers link-bearing
boilerplate, which is most of what upstream retires.

    python3 translation/scripts/remove-stale-paragraph.py \
        --anchor 'your\\.feedback\\.ibm\\.com' --dry-run
    python3 translation/scripts/remove-stale-paragraph.py \
        --anchor 'your\\.feedback\\.ibm\\.com' --apply

Refuses to touch a paragraph inside a fenced code block, and never rewrites the
`doqumentation-source-hash` marker line.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DOCS = REPO / "docs"
I18N = REPO / "i18n"
DOC_SUB = "docusaurus-plugin-content-docs/current"

# The 17 maintained locales.
MAIN_LOCALES = ["ar", "cs", "de", "es", "fr", "he", "id", "it", "ja",
                "ko", "ms", "pl", "pt", "ro", "th", "tl", "uk"]

HASH_MARKER = "doqumentation-source-hash"


def fenced_lines(lines: list[str]) -> set[int]:
    """Indices that sit inside a ``` fence — never edit these."""
    inside, out, fence = False, set(), None
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*(`{3,}|~{3,})", ln)
        if m:
            tok = m.group(1)[0]
            if not inside:
                inside, fence = True, tok
            elif fence == tok:
                inside = False
            out.add(i)
            continue
        if inside:
            out.add(i)
    return out


def strip_paragraph(text: str, anchor: re.Pattern) -> tuple[str, int]:
    """Drop each paragraph matching `anchor`. Returns (new_text, n_removed)."""
    lines = text.split("\n")
    fenced = fenced_lines(lines)
    keep = [True] * len(lines)
    removed = 0

    i = 0
    while i < len(lines):
        if not lines[i].strip() or i in fenced:
            i += 1
            continue
        start = i
        while i < len(lines) and lines[i].strip():
            i += 1
        end = i                                    # exclusive
        block = "\n".join(lines[start:end])
        if anchor.search(block) and not any(j in fenced for j in range(start, end)) \
                and HASH_MARKER not in block:
            for j in range(start, end):
                keep[j] = False
            # take one trailing blank line so paragraph spacing stays correct
            if end < len(lines) and not lines[end].strip():
                keep[end] = False
            removed += 1

    return "\n".join(l for l, k in zip(lines, keep) if k), removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anchor", required=True,
                    help="regex identifying the paragraph (e.g. a URL)")
    ap.add_argument("--locale", action="append", help="restrict to locale (repeatable)")
    ap.add_argument("--require-absent", metavar="REGEX",
                    help="only remove where REGEX is absent from the file. For "
                         "paragraphs that exist to support other content: the "
                         "note 'This survey is provided by IBM Quantum...' is "
                         "doQumentation's own and appears in no EN file, so the "
                         "EN-counterpart test cannot judge it — but it is "
                         "meaningless once the survey it refers to is gone. "
                         "Pass the survey URL here to strip only the orphans.")
    ap.add_argument("--ignore-en", action="store_true",
                    help="skip the 'EN no longer has it' test. Only valid for "
                         "paragraphs EN never had (doQumentation additions); "
                         "pair it with --require-absent.")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--dry-run", action="store_true", help="explicit no-op default")
    args = ap.parse_args()

    anchor = re.compile(args.anchor)
    require_absent = re.compile(args.require_absent) if args.require_absent else None
    locales = args.locale or MAIN_LOCALES

    # Which EN files still contain the anchor? Those are legitimate — skip them.
    en_has: dict[str, bool] = {}
    for p in DOCS.rglob("*.mdx"):
        en_has[str(p.relative_to(DOCS))] = bool(anchor.search(p.read_text(encoding="utf-8")))
    print(f"EN files still containing the anchor (left alone): "
          f"{sum(en_has.values())}")

    touched = para = 0
    skipped_en = skipped_paired = 0
    for loc in locales:
        root = I18N / loc / DOC_SUB
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.mdx")):
            rel = str(p.relative_to(root))
            if rel not in en_has:
                continue
            text = p.read_text(encoding="utf-8")
            if not anchor.search(text):
                continue
            if not args.ignore_en and en_has[rel]:
                skipped_en += 1          # EN still has it → not stale
                continue
            if require_absent is not None and require_absent.search(text):
                skipped_paired += 1      # the content it supports is still here
                continue
            new, n = strip_paragraph(text, anchor)
            if n == 0 or new == text:
                continue
            touched += 1
            para += n
            print(f"  {'REMOVE' if args.apply else 'would remove'} {n} para  {loc}/{rel}")
            if args.apply:
                p.write_text(new, encoding="utf-8")

    print(f"\n{'applied' if args.apply else 'DRY RUN'}: "
          f"{para} paragraph(s) in {touched} file(s); "
          f"{skipped_en} left alone because their EN still has it; "
          f"{skipped_paired} left alone because the content it supports is still present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
