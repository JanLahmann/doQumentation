# What we need right now

*Auto-generated on 2026-09-08 by `translation/scripts/contributing-status.py`.*
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

## Who is working on what

A claim is one open issue labelled `translation-claim` (template:
*Claim a locale*). Open one before you start and close it when you
stop; it is the only reservation there is. List them any time with
`gh issue list --repo JanLahmann/doQumentation --label translation-claim`.

| Locale | Who | Doing | Since | Issue |
|---|---|---|---|---|
| `cs` | @JanLahmann | review | 2026-09-08 | [#503](https://github.com/JanLahmann/doQumentation/issues/503) |
| `de` | @JanLahmann | review | 2026-09-07 | [#500](https://github.com/JanLahmann/doQumentation/issues/500) |
| `es` | @JanLahmann | review | 2026-09-08 | [#502](https://github.com/JanLahmann/doQumentation/issues/502) |
| `fr` | @JanLahmann | review | 2026-09-08 | [#504](https://github.com/JanLahmann/doQumentation/issues/504) |
| `he` | @JanLahmann | review | 2026-09-07 | [#501](https://github.com/JanLahmann/doQumentation/issues/501) |

---

## Pick a locale

Every locale below still has unreviewed pages. Pick one that is not
claimed above, open your claim issue, then follow
`CONTRIBUTING-REVIEWS.md`.

**`--max-leaks` currently filters nothing, and that is expected.** A
leak is a term the locale's `translation/glossary/<loc>.json` records
as wrongly left in English — *not* any capitalized English word. The
terms the house style keeps in English (Qiskit, Qubit, Gate, Circuit,
Backend, Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum,
QPU) do not count, and no locale currently records anything else, so
every file scores 0. What limits a pool today is pages already
reviewed and stubs under 40 lines, not leakage.

| Locale | Unreviewed pool | Reviewed so far |
|---|---|---|
| `de` | **189** | 171/428 (39%) |
| `th` | **142** | 219/428 (51%) |
| `he` | **130** | 232/428 (54%) |
| `id` | **129** | 233/428 (54%) |
| `ko` | **118** | 245/428 (57%) |
| `cs` | **91** | 270/428 (63%) |
| `ms` | **75** | 286/428 (66%) |
| `ro` | **75** | 289/428 (67%) |
| `pl` | **63** | 297/428 (69%) |

**Nearly exhausted** (fewer than 25 eligible) — still worth
a short round, but expect to re-sweep files that already carry a
verdict, or to accept a round smaller than 25:

- `ja` — 17 left (347/428 reviewed)
- `uk` — 16 left (348/428 reviewed)
- `ar` — 10 left (356/428 reviewed)
- `pt` — 8 left (359/428 reviewed)
- `it` — 7 left (359/428 reviewed)
- `es` — 6 left (360/428 reviewed)
- `fr` — 6 left (361/428 reviewed)
- `tl` — 5 left (362/428 reviewed)

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `2026090801-JanLahmann` | 6 | 0 | 0.0% |
| `2026090802-JanLahmann` | 22 | 3 | 13.6% |
| `2026090803-JanLahmann` | 6 | 0 | 0.0% |
| `2026090702-JanLahmann` | 25 | 4 | 16.0% |
| `2026090701-JanLahmann` | 25 | 2 | 8.0% |
| `20260901` | 136 | 14 | 10.3% |

Typical FAIL rate is around **10%**. If your round comes
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

