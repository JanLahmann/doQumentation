#!/usr/bin/env python3
"""Generate CONTRIBUTING-NOW.md — what the project currently needs.

The two CONTRIBUTING-*.md guides describe a *process* and should change
rarely. Anything with a number in it goes stale silently: CONTRIBUTING-REVIEWS.md
told contributors "`de` is complete" long after de had been reopened, and its
pool-size table was a snapshot from a threshold the project had already moved
past. An agent reading either would have skipped real work.

So the numbers live here instead, regenerated from the same data the sampler
itself reads. Re-run this whenever review rounds land (the daily
check-translations.yml workflow does it automatically):

    python3 translation/scripts/contributing-status.py --write

Eligibility is not reimplemented — it imports build_pool() from
sample-deep-review.py, so a contributor who runs the sampler sees exactly the
numbers this file quotes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parent
OUT = REPO / "CONTRIBUTING-NOW.md"
REVIEWS = REPO / "translation" / "reviews"

# Thresholds the guide quotes, widest-first. A locale is reported at the
# tightest threshold that still leaves it workable, which is the same order a
# round should try them in.
LADDER = [2, 4, 6, 8, 12]

# Below this a locale cannot support a useful round at that threshold.
WORKABLE = 25


def _load_sampler():
    """Import sample-deep-review.py by path (its name is not importable)."""
    spec = importlib.util.spec_from_file_location(
        "sample_deep_review", SCRIPTS / "sample-deep-review.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pools_by_threshold(sdr, status) -> dict[int, dict[str, int]]:
    out = {}
    for leaks in LADDER:
        pool = sdr.build_pool(
            status, sdr.MAIN_LOCALES, min_lines=40,
            max_leaks=leaks, exclude_reviewed=True,
        )
        out[leaks] = {loc: len(files) for loc, files in pool.items()}
    return out


def recent_rounds(limit: int = 6) -> list[tuple[str, int, int]]:
    """[(seed, reviewed, fails)] for the most recent review files."""
    rows = []
    # By mtime, not filename: the early rounds used names like
    # "wave3-drift-..." and "Brereview" that sort above every dated seed.
    files = sorted(REVIEWS.glob("opus-*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for p in files[:limit]:
        try:
            recs = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(recs, list) or not recs:
            continue
        tally = Counter(r.get("verdict") for r in recs)
        rows.append((p.stem.replace("opus-", ""), len(recs), tally.get("FAIL", 0)))
    return rows


def reviewed_counts(status, locales) -> dict[str, tuple[int, int]]:
    """{locale: (reviewed, eligible_total)} — how far each locale has been walked."""
    out = {}
    for loc in locales:
        entries = status.get(loc, {})
        total = sum(1 for e in entries.values() if e.get("validation") == "PASS")
        done = sum(1 for e in entries.values() if e.get("review_opus"))
        out[loc] = (done, total)
    return out


def render(sdr, status) -> str:
    pools = pools_by_threshold(sdr, status)
    done = reviewed_counts(status, sdr.MAIN_LOCALES)
    rounds = recent_rounds()

    # For each locale, the tightest threshold that still leaves a workable pool.
    rec: dict[str, tuple[int, int] | None] = {}
    for loc in sdr.MAIN_LOCALES:
        rec[loc] = None
        for leaks in LADDER:
            n = pools[leaks].get(loc, 0)
            if n >= WORKABLE:
                rec[loc] = (leaks, n)
                break
        if rec[loc] is None:
            widest = LADDER[-1]
            rec[loc] = (widest, pools[widest].get(loc, 0))

    ready = sorted(
        [l for l in sdr.MAIN_LOCALES if rec[l][1] >= WORKABLE],
        key=lambda l: (-rec[l][1], l),
    )
    thin = sorted(
        [l for l in sdr.MAIN_LOCALES if rec[l][1] < WORKABLE],
        key=lambda l: (-rec[l][1], l),
    )

    L = []
    A = L.append
    A("# What we need right now")
    A("")
    A(f"*Auto-generated on {date.today().isoformat()} by "
      "`translation/scripts/contributing-status.py`.*")
    A("*Do not edit by hand — it will be overwritten. Regenerate with:*")
    A("")
    A("```bash")
    A("python3 translation/scripts/contributing-status.py --write")
    A("```")
    A("")
    A("**New here?** Read `CONTRIBUTING-REVIEWS.md` (reviewing existing")
    A("translations) or `CONTRIBUTING-TRANSLATIONS.md` (translating new")
    A("content) for the actual recipe. This file only tells you *which* work")
    A("is worth picking up today, so the recipes never have to carry numbers")
    A("that go stale.")
    A("")
    A("---")
    A("")
    A("## Pick a locale")
    A("")
    A("Every locale below still has unreviewed pages. Claim one with the")
    A("maintainer so two people don't review the same one, then follow")
    A("`CONTRIBUTING-REVIEWS.md`.")
    A("")
    A("`--max-leaks` controls how many capitalized-English leaks a file may")
    A("contain and still be eligible. Tighter is better quality-per-round; the")
    A("value shown is the **tightest threshold that still leaves a workable")
    A(f"pool** (at least {WORKABLE} files). Use it as the starting point.")
    A("")
    if ready:
        A("| Locale | Unreviewed pool | Use | Reviewed so far |")
        A("|---|---|---|---|")
        for loc in ready:
            leaks, n = rec[loc]
            d, tot = done[loc]
            pct = f"{100 * d // tot}%" if tot else "—"
            A(f"| `{loc}` | **{n}** | `--max-leaks {leaks}` | {d}/{tot} ({pct}) |")
        A("")
    if thin:
        A(f"**Nearly exhausted** (fewer than {WORKABLE} eligible even at")
        A(f"`--max-leaks {LADDER[-1]}`) — still worth a short round, but expect")
        A("to widen further or re-sweep files that already carry a verdict:")
        A("")
        for loc in thin:
            leaks, n = rec[loc]
            d, tot = done[loc]
            A(f"- `{loc}` — {n} left at `--max-leaks {leaks}` ({d}/{tot} reviewed)")
        A("")
    A("The 9 German dialects (`aut bad bar bln gsw ksh nds sax swg`) are kept")
    A("but deliberately unmaintained. **Never review or translate them** — they")
    A("hold hundreds of known lint errors and are excluded from every gate.")
    A("")
    A("---")
    A("")
    A("## What recent rounds found")
    A("")
    if rounds:
        A("| Round (seed) | Files | FAIL | Rate |")
        A("|---|---|---|---|")
        for seed, n, f in rounds:
            A(f"| `{seed}` | {n} | {f} | {100 * f / n:.1f}% |")
        A("")
        avg = sum(f for _, _, f in rounds) / max(sum(n for _, n, _ in rounds), 1)
        A(f"Typical FAIL rate is around **{100 * avg:.0f}%**. If your round comes")
        A("in far above that, stop and tell the maintainer before fixing — it")
        A("usually means the rubric drifted, not that the locale collapsed.")
    else:
        A("*(No review files found yet.)*")
    A("")
    A("---")
    A("")
    A("## The highest-value thing you can do")
    A("")
    A("**When two or more locales are flagged for the same sentence, check the")
    A("other fifteen before fixing.**")
    A("")
    A("Sampling finds instances; comparing one span across all locales finds")
    A("the class. A recent round flagged three locales for rendering *\"a")
    A("software development kit (SDK)\"* as *\"a programming language\"* — checking")
    A("that single sentence everywhere turned up **eight** affected locales, so")
    A("sampling had located fewer than half. The same move found a paragraph")
    A("dropped from three locales' `wire-cutting.mdx`.")
    A("")
    A("It cuts both ways, and a negative result is worth just as much: an LHC")
    A("\"27 km circumference\" that became \"diameter\" turned out to be a single")
    A("locale, with the other sixteen correct. Check before you generalize —")
    A("and check before you write a rule, too. A tempting corpus-wide pattern")
    A("for one Czech defect matched 500+ occurrences that were nearly all")
    A("legitimate words in other languages.")
    A("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help=f"write {OUT.name} (default: print to stdout)")
    args = ap.parse_args()

    sdr = _load_sampler()
    status = json.load(open(sdr.STATUS_FILE, encoding="utf-8"))
    text = render(sdr, status)

    if args.write:
        prev = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if prev == text:
            print(f"{OUT.name}: unchanged")
        else:
            OUT.write_text(text, encoding="utf-8")
            print(f"{OUT.name}: written ({len(text.splitlines())} lines)")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
