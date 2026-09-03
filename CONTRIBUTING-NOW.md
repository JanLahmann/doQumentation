# What we need right now

*Auto-generated on 2026-09-03 by `translation/scripts/contributing-status.py`.*
*Do not edit by hand — it will be overwritten. Regenerate with:*

```bash
python3 translation/scripts/contributing-status.py --write
```

> **Sync your fork before you trust any of this.** These counts
> describe upstream `main` on the date above. A fork is stale the
> moment anyone else's round merges, and eligibility is read from
> `translation/status.json` — which every merged round rewrites. Work
> from a behind-fork and `--exclude-reviewed` filters against an old
> verdict set, so you re-review pages that are already done and your
> PR conflicts with what has landed.
>
> ```bash
> gh repo sync <YOUR-USER>/doQumentation \
>   --source JanLahmann/doQumentation --branch main
> git checkout main && git pull
> ```

**New here?** Read `CONTRIBUTING-REVIEWS.md` (reviewing existing
translations) or `CONTRIBUTING-TRANSLATIONS.md` (translating new
content) for the actual recipe. This file only tells you *which* work
is worth picking up today, so the recipes never have to carry numbers
that go stale.

---

## Pick a locale

Every locale below still has unreviewed pages. Claim one with the
maintainer so two people don't review the same one, then follow
`CONTRIBUTING-REVIEWS.md`.

`--max-leaks` controls how many capitalized-English leaks a file may
contain and still be eligible. Tighter is better quality-per-round; the
value shown is the **tightest threshold that still leaves a workable
pool** (at least 25 files). Use it as the starting point.

**Nearly exhausted** (fewer than 25 eligible even at
`--max-leaks 12`) — still worth a short round, but expect
to widen further or re-sweep files that already carry a verdict:

- `ko` — 5 left at `--max-leaks 12` (245/428 reviewed)
- `th` — 5 left at `--max-leaks 12` (219/428 reviewed)
- `he` — 4 left at `--max-leaks 12` (232/428 reviewed)
- `id` — 4 left at `--max-leaks 12` (233/428 reviewed)
- `pl` — 3 left at `--max-leaks 12` (297/428 reviewed)
- `de` — 2 left at `--max-leaks 12` (171/428 reviewed)
- `ms` — 2 left at `--max-leaks 12` (286/428 reviewed)
- `ro` — 2 left at `--max-leaks 12` (289/428 reviewed)
- `cs` — 1 left at `--max-leaks 12` (270/428 reviewed)
- `ar` — 0 left at `--max-leaks 12` (356/428 reviewed)
- `es` — 0 left at `--max-leaks 12` (360/428 reviewed)
- `fr` — 0 left at `--max-leaks 12` (361/428 reviewed)
- `it` — 0 left at `--max-leaks 12` (359/428 reviewed)
- `ja` — 0 left at `--max-leaks 12` (347/428 reviewed)
- `pt` — 0 left at `--max-leaks 12` (359/428 reviewed)
- `tl` — 0 left at `--max-leaks 12` (362/428 reviewed)
- `uk` — 0 left at `--max-leaks 12` (348/428 reviewed)

The 9 German dialects (`aut bad bar bln gsw ksh nds sax swg`) are kept
but deliberately unmaintained. **Never review or translate them** — they
hold hundreds of known lint errors and are excluded from every gate.

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `20260901` | 136 | 14 | 10.3% |
| `20260831` | 126 | 11 | 8.7% |
| `20260830` | 133 | 13 | 9.8% |
| `20260829` | 131 | 12 | 9.2% |
| `20260828` | 134 | 9 | 6.7% |
| `20260827` | 49 | 1 | 2.0% |

Typical FAIL rate is around **8%**. If your round comes
in far above that, stop and tell the maintainer before fixing — it
usually means the rubric drifted, not that the locale collapsed.

---

## The highest-value thing you can do

**When two or more locales are flagged for the same sentence, check the
other fifteen before fixing.**

Sampling finds instances; comparing one span across all locales finds
the class. A recent round flagged three locales for rendering *"a
software development kit (SDK)"* as *"a programming language"* — checking
that single sentence everywhere turned up **eight** affected locales, so
sampling had located fewer than half. The same move found a paragraph
dropped from three locales' `wire-cutting.mdx`.

It cuts both ways, and a negative result is worth just as much: an LHC
"27 km circumference" that became "diameter" turned out to be a single
locale, with the other sixteen correct. Check before you generalize —
and check before you write a rule, too. A tempting corpus-wide pattern
for one Czech defect matched 500+ occurrences that were nearly all
legitimate words in other languages.

