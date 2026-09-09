# What we need right now

*Auto-generated on 2026-09-09 by `translation/scripts/contributing-status.py`.*
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
| `?` | @JanLahmann | ? | 2026-09-09 | [#522](https://github.com/JanLahmann/doQumentation/issues/522) |

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
| `th` | **145** | 219/428 (51%) |
| `de` | **139** | 224/428 (52%) |
| `id` | **131** | 233/428 (54%) |
| `ko` | **120** | 245/428 (57%) |
| `he` | **108** | 257/428 (60%) |
| `ms` | **78** | 286/428 (66%) |
| `ro` | **77** | 289/428 (67%) |
| `cs` | **72** | 292/428 (68%) |
| `pl` | **66** | 297/428 (69%) |

**Nearly exhausted** (fewer than 25 eligible) — still worth
a short round, but expect to re-sweep files that already carry a
verdict, or to accept a round smaller than 25:

- `uk` — 19 left (348/428 reviewed)
- `ja` — 18 left (347/428 reviewed)
- `ar` — 11 left (356/428 reviewed)
- `it` — 8 left (359/428 reviewed)
- `pt` — 8 left (359/428 reviewed)
- `tl` — 5 left (362/428 reviewed)
- `es` — 0 left (366/428 reviewed)
- `fr` — 0 left (367/428 reviewed)

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `2026090906-JanLahmann` | 9 | 0 | 0.0% |
| `2026090903-JanLahmann` | 21 | 0 | 0.0% |
| `2026090905-JanLahmann` | 14 | 0 | 0.0% |
| `2026090904-JanLahmann` | 10 | 0 | 0.0% |
| `2026090901-JanLahmann` | 18 | 0 | 0.0% |
| `2026090907-JanLahmann` | 4 | 0 | 0.0% |

Typical FAIL rate is around **0%**. If your round comes
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

