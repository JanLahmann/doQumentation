#!/usr/bin/env python3
"""Find translations carrying content English has since deleted.

The gap this closes
-------------------
A translation can be *stale in content* while every existing gate says it is
fresh. `guides/job-limits.mdx` sat wrong in six locales for months: upstream
replaced

    "...for Sampler jobs (Estimator jobs can be split into smaller sub-jobs,
     so this limit doesn't apply)."
with
    "...for Sampler jobs due to output size."

but es/he/id/ja/ko/th still told readers Estimator jobs were exempt from a
documented service limit. All seventeen locales carried the *current* source
hash `73803dd4` and `validation: PASS`, because a `--stamp` records which EN
revision a file was compared against, not whether anyone re-translated the
paragraphs that moved.

Why not the existing drift check
--------------------------------
`validate-translation.py --check-drift` already compares each translation's
stored EN passage baseline against current EN, and it *does* fire here — but it
fires on 4210 files / 81714 events, because `baseline-hashes.json` is never
refreshed when a file is correctly re-translated. Every fixed file keeps
reporting drift forever, so the true hits are indistinguishable from the noise.
That check answers "did EN move since the baseline?"; this one answers the
narrower, actionable question: **is the translation still asserting something
English no longer says?**

Passage alignment was tried first and abandoned: translations legitimately
split and merge paragraphs, so unit counts diverge (15-20 against EN's 18 for
job-limits) and index-based pairing is meaningless. This works at file level
instead, which needs no alignment.

How it works
------------
For each EN file, walk its git history and collect *translation-invariant*
tokens — inline-code spans, CamelCase/brand identifiers, numbers — that some
earlier revision contained and the current revision does not. Those are things
English deleted. A translation is flagged when it still contains one.

Invariant tokens are the point: `Estimator`, `max_shots`, `10 million` survive
translation intact, so their presence is comparable across languages without
parsing any of them. Ordinary prose is ignored precisely because it does not
survive.

Precision — read this before wiring it into CI
----------------------------------------------
This is an investigative tool, NOT a gate, and the measured numbers say why.
Corpus-wide it flags 760 findings across 67 files; `--partial 12` cuts that to
95 (file, token) pairs across 49 files, of which only a small minority are real.
The residue is dominated by ordinary English words that translations keep inside
tables and headings — `Hello`, `Median`, `Circuit`, `Matrix` — which EN happened
to drop from prose during a restructure. Those are leakage, not staleness.

It is precise when you already know what changed and are asking who failed to
track it. That is the job-limits shape: `--file guides/job-limits.mdx` separated
the six stale locales from the eleven clean ones exactly, 17/17.

Do not gate on it until the token model distinguishes product identifiers from
ordinary capitalized prose. The structural fix for the underlying blind spot is
elsewhere: `baseline-hashes.json` is written only by bootstrap-passage-hashes.py
and never advanced when a translation is genuinely refreshed, which is why
`--check-drift` reports 81714 events and gets ignored. Advance the baseline in
the same code path that stamps a refreshed file and drift becomes a real signal.

Usage
-----
    python3 translation/scripts/check-stale-passages.py --file guides/job-limits.mdx
    python3 translation/scripts/check-stale-passages.py --since <sync-commit> --partial 12
    python3 translation/scripts/check-stale-passages.py --locale es --partial 12
    python3 translation/scripts/check-stale-passages.py --json report.json

Exit code 1 if anything is flagged.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Shared prose extractor — same units the drift check and the lint use, so a
# passage this script ignores is ignored consistently everywhere.
_spec = importlib.util.spec_from_file_location(
    "passage_units", Path(__file__).resolve().parent / "passage_units.py")
_passage_units = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_passage_units)
DOCS = REPO / "docs"
I18N = REPO / "i18n"
DOC_SUB = "docusaurus-plugin-content-docs/current"

# The 17 maintained locales. The 9 German dialects are kept but deliberately
# unmaintained and are excluded from every gate — see CONTRIBUTING-NOW.md.
MAIN_LOCALES = ["ar", "cs", "de", "es", "fr", "he", "id", "it", "ja",
                "ko", "ms", "pl", "pt", "ro", "th", "tl", "uk"]

# Tokens that survive translation: inline code, CamelCase/brand identifiers,
# and numbers. Deliberately NOT ordinary capitalized words — a sentence-initial
# "The" is not evidence of anything.
TOKEN_RE = re.compile(
    r"`[^`\n]{2,60}`"                     # `max_shots`, `backend.configuration()`
    r"|\b[A-Z][a-z]+[A-Z][A-Za-z]*\b"     # CamelCase: DAGCircuit, TwirlingOptions
    r"|\b[A-Z][a-zA-Z]{4,}\b"             # Estimator, Sampler, Hadamard
    r"|\b\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand)?\b"
)

# Words that are capitalized in English prose but carry no identity — flagging
# these would fire on ordinary sentence rewording rather than deleted facts.
STOPWORDS = {
    "This", "That", "These", "Those", "There", "Their", "Then", "Thus",
    "When", "Where", "Which", "While", "With", "Without", "Would", "Could",
    "Should", "Because", "Before", "After", "Above", "Below", "Also",
    "However", "Therefore", "Although", "Since", "Using", "Note", "Notes",
    "First", "Second", "Third", "Next", "Following", "Example", "Examples",
    "For", "From", "Into", "Only", "Other", "Same", "Such", "Than", "They",
    "Here", "Each", "Every", "Both", "More", "Most", "Some", "Your", "You",
    "English", "Qiskit", "IBM", "Quantum",
}


def tokens(text: str) -> set[str]:
    """Translation-invariant tokens in the PROSE of an MDX file.

    Prose only, via passage_units.extract_units — the first version of this
    scanned raw file text and produced 874 findings, nearly all of them
    notebook output values and Pauli strings (`0.99`, `IIIIZI`) that EN
    regenerates on every run while translations keep the values they were
    promoted with. That is expected divergence, not stale content, and it
    buried the real hits exactly the way the drift check does.
    """
    out = set()
    for unit in _passage_units.extract_units(text, mode="lenient"):
        for t in TOKEN_RE.findall(unit):
            t = t.strip()
            if t in STOPWORDS or len(t) < 3:
                continue
            out.add(t)
    return out


def git_revisions(rel: str) -> list[str]:
    """Commits that touched docs/<rel>, oldest first."""
    r = subprocess.run(
        ["git", "log", "--format=%H", "--", f"docs/{rel}"],
        cwd=REPO, capture_output=True, text=True,
    )
    return list(reversed(r.stdout.split()))


def blob_at(commit: str, rel: str) -> str | None:
    r = subprocess.run(
        ["git", "show", f"{commit}:docs/{rel}"],
        cwd=REPO, capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else None


def deleted_tokens(rel: str, since: str | None = None) -> set[str]:
    """Invariant prose tokens EN used to have and no longer does.

    A token counts as deleted only if it is absent from the *entire* current
    file, so a paragraph that merely moved is correctly ignored.

    `since` is the accuracy knob, and it matters more than anything else here.
    Without it, the comparison is against the union of every past revision,
    which sweeps in each historical restructure and buries the signal (760
    findings corpus-wide, mostly English words some locales leave untranslated
    in tables). Scoped to one upstream sync it answers the question the sync
    actually raises: which locales failed to track *this* set of EN edits.

    That is also where the blind spot is created — EN moves, files get
    `--stamp`ed as compared-against-the-new-revision, and whichever
    translations were not genuinely refreshed keep asserting the old text
    under a current hash. So run it against the sync commit, over the files
    that sync touched.
    """
    cur_path = DOCS / rel
    if not cur_path.exists():
        return set()
    current = tokens(cur_path.read_text(encoding="utf-8"))

    if since:
        blob = blob_at(f"{since}^", rel) or blob_at(since, rel)
        return (tokens(blob) - current) if blob else set()

    revs = git_revisions(rel)
    if len(revs) < 2:
        return set()
    past: set[str] = set()
    for c in revs[:-1]:                      # every revision but the newest
        blob = blob_at(c, rel)
        if blob:
            past |= tokens(blob)
    return past - current


def files_touched_by(commit: str) -> list[str]:
    """EN-relative paths that `commit` modified under docs/."""
    r = subprocess.run(
        ["git", "show", "--name-only", "--format=", commit, "--", "docs/"],
        cwd=REPO, capture_output=True, text=True,
    )
    out = []
    for line in r.stdout.split("\n"):
        line = line.strip()
        if line.startswith("docs/") and line.endswith(".mdx"):
            out.append(line[len("docs/"):])
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", action="append",
                    help="restrict to this locale (repeatable)")
    ap.add_argument("--file", help="restrict to one EN-relative path")
    ap.add_argument("--since", metavar="COMMIT",
                    help="compare EN against COMMIT^ and scan only the files "
                         "COMMIT touched — the intended mode, run after an "
                         "upstream sync")
    ap.add_argument("--partial", type=int, metavar="N", default=None,
                    help="only report a token when at most N locales carry it. "
                         "A genuine missed EN edit is partial by nature — some "
                         "locales tracked the change and some did not (the "
                         "job-limits case split 6 of 17). A token every locale "
                         "carries is almost always an English word left "
                         "untranslated in a table, not stale content. "
                         "Try --partial 12.")
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--quiet", action="store_true",
                    help="only print the summary line")
    args = ap.parse_args()

    locales = args.locale or MAIN_LOCALES
    if args.file:
        rels = [args.file]
    elif args.since:
        rels = files_touched_by(args.since)
        print(f"{args.since} touched {len(rels)} EN file(s)\n")
    else:
        rels = sorted(str(p.relative_to(DOCS)) for p in DOCS.rglob("*.mdx"))

    findings: list[dict] = []
    scanned = 0
    for rel in rels:
        gone = deleted_tokens(rel, since=args.since)
        if not gone:
            continue
        for loc in locales:
            p = I18N / loc / DOC_SUB / rel
            if not p.exists():
                continue
            scanned += 1
            text = p.read_text(encoding="utf-8")
            hits = sorted(t for t in gone if t in text)
            if hits:
                findings.append({"locale": loc, "file": rel, "stale_tokens": hits})

    if args.partial is not None:
        carriers: dict[tuple[str, str], set[str]] = {}
        for f in findings:
            for t in f["stale_tokens"]:
                carriers.setdefault((f["file"], t), set()).add(f["locale"])
        kept = []
        for f in findings:
            toks = [t for t in f["stale_tokens"]
                    if len(carriers[(f["file"], t)]) <= args.partial]
            if toks:
                kept.append({**f, "stale_tokens": toks})
        dropped = len(findings) - len(kept)
        findings = kept
        print(f"--partial {args.partial}: dropped {dropped} finding(s) whose "
              f"tokens every locale carries\n")

    if not args.quiet:
        for f in findings:
            print(f"STALE  {f['locale']}/{f['file']}")
            print(f"       still contains, but current EN does not: "
                  f"{', '.join(f['stale_tokens'][:8])}")

    print(f"\n{len(findings)} flagged / {scanned} translation files compared "
          f"across {len(locales)} locale(s)")

    if args.json:
        Path(args.json).write_text(
            json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {args.json}")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
