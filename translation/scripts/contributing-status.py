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

Eligibility is not reimplemented — it imports catalogue() and build_pool()
from sample-deep-review.py, which read the PO files and their headers, so a
contributor who runs the sampler sees exactly the numbers this file quotes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import os
import subprocess
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parent
OUT = REPO / "CONTRIBUTING-NOW.md"
REVIEWS = REPO / "translation" / "reviews"

# Claims: one open GitHub issue per person-and-locale, labelled
# translation-claim (template: .github/ISSUE_TEMPLATE/translation-claim.yml).
# Listing them here answers "who is working on what" without a PR; the
# issue is the reservation, this file is its mirror.
CLAIM_REPO = "JanLahmann/doQumentation"
CLAIM_LABEL = "translation-claim"
CLAIM_TITLE_RE = re.compile(r"claim:\s*([a-z]{2})\b(?:.*?\b(review|translat\w*))?", re.I)

# Thresholds the guide quotes, widest-first. A locale is reported at the
# tightest threshold that still leaves it workable, which is the same order a
# round should try them in.
LADDER = [2, 4, 6, 8, 12]

# Below this a locale cannot support a useful round at that threshold.
WORKABLE = 25


def fetch_claims() -> list[dict] | None:
    """Open claim issues as [{locale, track, who, number, since}], or None when
    neither `gh` nor the public API answered (offline, rate-limited)."""
    raw = None
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--repo", CLAIM_REPO, "--label", CLAIM_LABEL, "--state", "open",
             "--limit", "100", "--json", "number,title,body,assignees,author,createdAt"],
            capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            raw = json.loads(out.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        raw = None
    if raw is None:
        url = f"https://api.github.com/repos/{CLAIM_REPO}/issues?labels={CLAIM_LABEL}&state=open&per_page=100"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "doqumentation-contributing-status"})
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = json.loads(r.read().decode("utf-8"))
        except Exception:
            return None
        raw = [i for i in raw if "pull_request" not in i]
        for i in raw:
            i["createdAt"] = i.get("created_at", "")
            i["author"] = i.get("user") or {}
    claims = []
    for i in raw:
        title = i.get("title") or ""
        body = i.get("body") or ""
        m = CLAIM_TITLE_RE.search(title)
        locale = m.group(1).lower() if m else None
        track = (m.group(2) or "").lower() if m else ""
        # the issue form writes "### Locale\n\nde" / "### What you will do\n\nreview (...)"
        fm = re.search(r"###\s*Locale\s*\n+\s*([a-z]{2})\b", body, re.I)
        if fm:
            locale = fm.group(1).lower()
        ft = re.search(r"###\s*What you will do\s*\n+\s*(review|translate)", body, re.I)
        if ft:
            track = ft.group(1).lower()
        track = "translate" if track.startswith("translat") else ("review" if track else "?")
        who = ", ".join("@" + a["login"] for a in (i.get("assignees") or []) if a.get("login")) \
            or ("@" + (i.get("author") or {}).get("login", "?"))
        claims.append({"locale": locale or "?", "track": track, "who": who,
                       "number": i.get("number"), "since": (i.get("createdAt") or "")[:10]})
    return sorted(claims, key=lambda c: (c["locale"], c["since"]))


def rendered_counts(cats) -> dict[str, int]:
    """{locale: rendered pages on disk}. The rendered pages are derived and
    not in git; a locale that is not rendered has a pool of 0 for the wrong
    reason, and the file must say so instead of printing the 0."""
    return {loc: sum(1 for i in cat.values() if i["rendered"]) for loc, cat in cats.items()}


def _load_sampler():
    """Import sample-deep-review.py by path (its name is not importable)."""
    spec = importlib.util.spec_from_file_location(
        "sample_deep_review", SCRIPTS / "sample-deep-review.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pools_by_threshold(sdr, cats) -> dict[int, dict[str, int]]:
    out = {}
    for leaks in LADDER:
        pool = sdr.build_pool(
            cats, min_lines=1,
            max_leaks=leaks, exclude_reviewed=True,
        )
        out[leaks] = {loc: len(files) for loc, files in pool.items()}
    return out


def recent_rounds(limit: int = 6) -> list[tuple[str, int, int]]:
    """[(seed, reviewed, fails)] for the most recent review files."""
    rows = []
    # Order by the YYYYMMDD embedded in the seed, NOT by filename and NOT by
    # mtime. Plain filename sort puts the early rounds ("wave3-drift-...",
    # "Brereview") above every dated seed; mtime looks right locally but is
    # useless in CI, where a fresh checkout stamps every file with the same
    # time — which is exactly how the legacy names reappeared in the first
    # generated copy of this table. Undated legacy seeds sort last.
    def seed_key(f: Path):
        m = re.search(r"(20\d{6})", f.stem)
        return (1, m.group(1)) if m else (0, f.stem)

    files = sorted(REVIEWS.glob("opus-*.json"), key=seed_key, reverse=True)
    for p in files:
        if len(rows) >= limit:
            break
        try:
            recs = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(recs, list) or not recs:
            continue
        tally = Counter(r.get("verdict") for r in recs)
        if tally.get("FIXED"):
            continue   # a repair round (drift/gauge/sync fixes): nobody read pages for meaning
        rows.append((p.stem.replace("opus-", ""), len(recs), tally.get("FAIL", 0)))
    return rows


def reviewed_counts(cats, min_lines: int = 1) -> dict[str, tuple[int, int]]:
    """{locale: (reviewed, reviewable)} — how far each locale has been walked.
    Reviewable = rendered, not an English fallback, not a stub; a page that is
    mid-update (fuzzy entries) still counts here, it is only held back from
    the pool until its sync lands."""
    out = {}
    for loc, cat in cats.items():
        pages = [i for i in cat.values()
                 if i["rendered"] and not i["fallback"] and i["lines"] >= min_lines]
        out[loc] = (sum(1 for i in pages if i["verdict"]), len(pages))
    return out


def render(sdr, cats, claims: list[dict] | None = None) -> str:
    pools = pools_by_threshold(sdr, cats)
    done = reviewed_counts(cats)
    rounds = recent_rounds()
    rendered = rendered_counts(cats)
    unrendered = [l for l in sdr.MAIN_LOCALES if not sdr.is_rendered(cats[l])]

    # Does the leak filter still bind anywhere? A leak is what a locale's
    # glossary records, minus the terms the house style keeps in English, so
    # with no glossary entries every file scores 0 and --max-leaks is inert.
    # Advertising a threshold then is worse than saying nothing: it reads as a
    # quality knob that does something.
    leaky = any(sdr._leak_terms(loc) for loc in sdr.MAIN_LOCALES)

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
        [l for l in sdr.MAIN_LOCALES if rec[l][1] >= WORKABLE and l not in unrendered],
        key=lambda l: (-rec[l][1], l),
    )
    thin = sorted(
        [l for l in sdr.MAIN_LOCALES if rec[l][1] < WORKABLE and l not in unrendered],
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
    A("> **Sync your fork before you trust any of this.** These counts")
    A("> describe upstream `main` on the date above. A fork is stale the")
    A("> moment anyone else's round merges, and eligibility is read from")
    A("> the PO files' headers — which every merged round changes. Work")
    A("> from a behind-fork and `--exclude-reviewed` filters against an old")
    A("> verdict set, so you re-review pages that are already done and your")
    A("> PR conflicts with what has landed.")
    A(">")
    A("> ```bash")
    A("> gh repo sync <YOUR-USER>/doQumentation \\")
    A(">   --source JanLahmann/doQumentation --branch main")
    A("> git checkout main && git pull")
    A("> ```")
    A("")
    A("**New here?** Read `CONTRIBUTING-REVIEWS.md` (reviewing existing")
    A("translations) or `CONTRIBUTING-TRANSLATIONS.md` (translating new")
    A("content) for the actual recipe. This file only tells you *which* work")
    A("is worth picking up today, so the recipes never have to carry numbers")
    A("that go stale.")
    A("")
    A("---")
    A("")
    A("## Who is working on what")
    A("")
    A("A claim is one open issue labelled `translation-claim` (template:")
    A("*Claim a locale*). Open one before you start and close it when you")
    A("stop; it is the only reservation there is. List them any time with")
    A("`gh issue list --repo JanLahmann/doQumentation --label translation-claim`.")
    A("")
    if claims is None:
        A("*(Could not reach GitHub while generating this file — check the")
        A(f"[open claims](https://github.com/{CLAIM_REPO}/issues?q=is%3Aissue+is%3Aopen+label%3A{CLAIM_LABEL}) directly.)*")
    elif not claims:
        A("*No open claims right now — every locale is free.*")
    else:
        A("| Locale | Who | Doing | Since | Issue |")
        A("|---|---|---|---|---|")
        for c in claims:
            A(f"| `{c['locale']}` | {c['who']} | {c['track']} | {c['since']} | "
              f"[#{c['number']}](https://github.com/{CLAIM_REPO}/issues/{c['number']}) |")
    A("")
    A("---")
    A("")
    A("## Pick a locale")
    A("")
    A("Every locale below still has unreviewed pages. Pick one that is not")
    A("claimed above, open your claim issue, then follow")
    A("`CONTRIBUTING-REVIEWS.md`.")
    A("")
    if unrendered:
        A(f"> ⚠ {len(unrendered)} locale(s) were not rendered when this file was")
        A("> generated, so their pools are unknown here (not zero):")
        A(f"> `{'`, `'.join(unrendered)}`. Render one with")
        A("> `python3 translation/v2/render.py --locale <locale>` and run the")
        A("> sampler yourself. The daily CI run renders all of them.")
        A("")
    if leaky:
        A("`--max-leaks` controls how many recorded glossary leaks a file may")
        A("contain and still be eligible. Tighter is better quality-per-round;")
        A("the value shown is the **tightest threshold that still leaves a")
        A(f"workable pool** (at least {WORKABLE} files). Use it as a start.")
    else:
        A("**`--max-leaks` currently filters nothing, and that is expected.** A")
        A("leak is a term the locale's `translation/glossary/<loc>.json` records")
        A("as wrongly left in English — *not* any capitalized English word. The")
        A("terms the house style keeps in English (Qiskit, Qubit, Gate, Circuit,")
        A("Backend, Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum,")
        A("QPU) do not count, and no locale currently records anything else, so")
        A("every file scores 0. What limits a pool today is pages already")
        A("reviewed with nothing written since, not leakage.")
    A("")
    if ready:
        A("| Locale | Unreviewed pool | Reviewed so far |" if not leaky
          else "| Locale | Unreviewed pool | Use | Reviewed so far |")
        A("|---|---|---|" if not leaky else "|---|---|---|---|")
        for loc in ready:
            leaks, n = rec[loc]
            d, tot = done[loc]
            pct = f"{100 * d // tot}%" if tot else "—"
            A(f"| `{loc}` | **{n}** | {d}/{tot} ({pct}) |" if not leaky
              else f"| `{loc}` | **{n}** | `--max-leaks {leaks}` | {d}/{tot} ({pct}) |")
        A("")
    if thin:
        A(f"**Nearly exhausted** (fewer than {WORKABLE} eligible) — still worth")
        A("a short round, but expect to re-sweep files that already carry a")
        A("verdict, or to accept a round smaller than 25:")
        A("")
        for loc in thin:
            _leaks, n = rec[loc]
            d, tot = done[loc]
            A(f"- `{loc}` — {n} left ({d}/{tot} reviewed)")
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
    ap.add_argument("--no-claims", action="store_true",
                    help="skip the GitHub lookup of open claim issues (offline runs)")
    args = ap.parse_args()

    sdr = _load_sampler()
    cats = {loc: sdr.catalogue(loc) for loc in sdr.MAIN_LOCALES}
    claims = None if args.no_claims else fetch_claims()
    text = render(sdr, cats, claims)

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
