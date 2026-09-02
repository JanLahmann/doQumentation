#!/usr/bin/env python3
"""Retire baseline passages that English deleted and the translation dropped too.

`baseline-hashes.json` records the English passage hashes a translation was made
from; `validate-translation.py --check-drift` reports every one of them that is
gone from current English. It reports 4210 files / 81714 events, which is too
many to act on — but the entries are NOT bogus. `promote-drafts.py` already
advances the baseline for files it promotes (530 entries carry `commit: null`
from that path), so the backlog is real translation debt: English moved, and the
corpus has since been maintained by *targeted* fixes — review rounds, fix waves,
the survey-paragraph removal in #463, the Accordion migration in #466 — none of
which go through promote and so none of which retire a baseline passage.

This retires the subset that can be *proven* resolved, and nothing else.

The proof
---------
A baseline passage is retired only when all of the following hold:

  1. English deleted it — the hash is in the baseline and absent from current EN.
  2. The deleted passage carried translation-invariant tokens (inline code,
     CamelCase identifiers, numbers) that are absent from the *whole* current
     English file, so they are genuinely gone rather than merely moved.
  3. None of those tokens appear anywhere in the translation.

Together those mean English dropped the passage and the translation dropped it
too — there is nothing left to track, so the baseline entry is noise. A passage
with no distinctive tokens cannot be judged and is kept; so is one whose tokens
still appear in the translation, because that is exactly the stale-content case
worth reporting.

Deletions only, never edits. If English *reworded* a passage, dropping the
baseline entry would silently assert the translation followed the rewording,
which is the mistake that made `source_hash` worthless (see #462). Retiring a
deletion asserts only that both sides removed the same thing.

    python3 translation/scripts/advance-baseline.py            # report
    python3 translation/scripts/advance-baseline.py --apply
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DOCS = REPO / "docs"
I18N = REPO / "i18n"
DOC_SUB = "docusaurus-plugin-content-docs/current"
BASELINE = REPO / "translation" / "baseline-hashes.json"

MAIN_LOCALES = {"ar", "cs", "de", "es", "fr", "he", "id", "it", "ja",
                "ko", "ms", "pl", "pt", "ro", "th", "tl", "uk"}

_spec = importlib.util.spec_from_file_location(
    "passage_units", Path(__file__).resolve().parent / "passage_units.py")
_pu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pu)

# Same token model as check-stale-passages.py: things that survive translation.
TOKEN_RE = re.compile(
    r"`[^`\n]{2,60}`"
    r"|\b[A-Z][a-z]+[A-Z][A-Za-z]*\b"
    r"|\b[A-Z][a-zA-Z]{4,}\b"
    r"|\b\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand)?\b"
)
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


# Retirement needs a STRICTER token model than detection does.
#
# Detection (check-stale-passages.py) can afford a loose model: a false positive
# is noise in a report. Retirement cannot — retiring a passage wrongly deletes
# the evidence that a translation is stale, so the error is silent and
# permanent. And the loose model is wrong here in a specific way: bare
# capitalized words like "Initializing" or "Converting" are *translated*, so
# their absence from an Indonesian file says nothing about whether it tracked
# English's deletion. Only inline code, CamelCase identifiers and numbers
# survive translation intact and can carry the proof.
STRICT_TOKEN_RE = re.compile(
    r"`[^`\n]{2,60}`"                     # `max_shots`
    r"|\b[A-Z][a-z]+[A-Z][A-Za-z]*\b"     # DAGCircuit, TwirlingOptions
    r"|\b\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand)?\b"
)


def tokens(text: str) -> set[str]:
    """Loose model — used only to decide a passage still LIVES in a translation.

    Over-matching here is safe: it keeps a baseline entry that might have been
    retirable, which costs nothing but a stale report line.
    """
    return {t.strip() for t in TOKEN_RE.findall(text)
            if t.strip() not in STOPWORDS and len(t.strip()) >= 3}


def strict_tokens(text: str) -> set[str]:
    """Translation-invariant only — the evidence retirement is allowed to use."""
    return {t.strip() for t in STRICT_TOKEN_RE.findall(text)
            if t.strip() not in STOPWORDS and len(t.strip()) >= 2}


_hist: dict[str, dict[str, str]] = {}
_cur: dict[str, set[str]] = {}
_entext: dict[str, str] = {}


def en_current(rel: str):
    """(unit hashes, full text) of current EN, or (None, None) if absent."""
    if rel not in _cur:
        p = DOCS / rel
        if not p.exists():
            _cur[rel] = None
            _entext[rel] = None
        else:
            t = p.read_text(encoding="utf-8")
            _cur[rel] = set(_pu.hash_units(t, mode="lenient"))
            _entext[rel] = t
    return _cur[rel], _entext[rel]


def en_history(rel: str) -> dict[str, str]:
    """hash -> full unit text, across every past revision of docs/<rel>."""
    if rel in _hist:
        return _hist[rel]
    out: dict[str, str] = {}
    revs = subprocess.run(["git", "log", "--format=%H", "--", f"docs/{rel}"],
                          cwd=REPO, capture_output=True, text=True).stdout.split()
    for c in revs:
        blob = subprocess.run(["git", "show", f"{c}:docs/{rel}"],
                              cwd=REPO, capture_output=True, text=True)
        if blob.returncode:
            continue
        for u in _pu.extract_units(blob.stdout, mode="lenient"):
            out.setdefault(_pu.hash_unit(u), u)
    _hist[rel] = out
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write baseline-hashes.json")
    ap.add_argument("--locale", action="append")
    ap.add_argument("--stale-json", metavar="PATH",
                    help="write the passages proven STILL stale — English "
                         "deleted them and the translation still carries them. "
                         "This is the actionable half of the run: retirement "
                         "only removes settled noise, whereas these are real "
                         "defects a review round can target directly.")
    args = ap.parse_args()

    baselines = json.loads(BASELINE.read_text(encoding="utf-8"))
    want = set(args.locale) if args.locale else MAIN_LOCALES

    stats = Counter()
    changed_files = 0
    stale: list[dict] = []
    for key, sidecar in sorted(baselines.items()):
        loc, rel = key.split("/", 1)
        if loc not in want:
            continue
        cur_hashes, cur_text = en_current(rel)
        if cur_hashes is None:
            continue
        base = sidecar.get("hashes") or []
        removed = [h for h in base if h not in cur_hashes]
        if not removed:
            continue
        tp = I18N / loc / DOC_SUB / rel
        if not tp.exists():
            continue
        tr_text = tp.read_text(encoding="utf-8")
        hist = en_history(rel)
        en_tokens_now = tokens(cur_text)
        en_strict_now = strict_tokens(cur_text)

        retire = []
        for h in removed:
            old = hist.get(h)
            if old is None:
                stats["kept: old text unrecoverable"] += 1
                continue
            # Keep first, on the loose model: any hint the passage still lives
            # in the translation means real drift, and it stays reported.
            live = {t for t in tokens(old) if t not in en_tokens_now}
            if live and any(t in tr_text for t in live):
                stats["kept: translation still carries it (real drift)"] += 1
                stale.append({"locale": loc, "file": rel,
                              "evidence": sorted(t for t in live if t in tr_text)[:6],
                              "deleted_en_passage": old[:400]})
                continue
            # Retire only on the strict model: proof, not absence of evidence.
            gone = {t for t in strict_tokens(old) if t not in en_strict_now}
            if not gone:
                stats["kept: no translation-invariant token (cannot prove)"] += 1
                continue
            if any(t in tr_text for t in gone):
                # Real drift can be caught by EITHER check — the worklist must
                # record both branches or it silently under-reports (it dropped
                # 471 of 1190 when only the first branch appended).
                stats["kept: translation still carries it (real drift)"] += 1
                stale.append({"locale": loc, "file": rel,
                              "evidence": sorted(t for t in gone if t in tr_text)[:6],
                              "deleted_en_passage": old[:400]})
                continue
            retire.append(h)
            stats["RETIRED: EN deleted it and the translation dropped it too"] += 1

        if retire and args.apply:
            sidecar["hashes"] = [h for h in base if h not in retire]
            baselines[key] = sidecar
        if retire:
            changed_files += 1

    total = sum(stats.values())
    print(f"drifted baseline passages examined: {total}\n")
    for k, v in stats.most_common():
        print(f"  {v:>6}  {k}")
    retired = stats["RETIRED: EN deleted it and the translation dropped it too"]
    print(f"\nfiles affected: {changed_files}")
    if args.apply and retired:
        BASELINE.write_text(
            json.dumps(baselines, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
        print(f"wrote {BASELINE.name}: retired {retired} passage(s)")
    elif not args.apply:
        print("(dry run — pass --apply to write)")

    if args.stale_json:
        Path(args.stale_json).write_text(
            json.dumps(stale, ensure_ascii=False, indent=1), encoding="utf-8")
        locs = Counter(s["locale"] for s in stale)
        print(f"\nwrote {args.stale_json}: {len(stale)} passage(s) proven still "
              f"stale across {len({s['file'] for s in stale})} file(s)")
        print(f"  by locale: {dict(sorted(locs.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
