# What we need right now

*Auto-generated on 2026-10-03 by `translation/scripts/contributing-status.py`.*
*Do not edit by hand — it will be overwritten. Regenerate with:*

```bash
python3 translation/scripts/contributing-status.py --write
```

> **Sync your fork before you trust any of this.** These counts
> describe upstream `main` on the date above. A fork is stale the
> moment anyone else's round merges, and eligibility is read from
> the PO files' headers — which every merged round changes. Work
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
| `all` | @JanLahmann | ? | 2026-10-01 | [#918](https://github.com/JanLahmann/doQumentation/issues/918) |

---

## Pick a locale

Nearly every page of every locale now carries a review verdict, so the
work is **re-reading where a read is most likely to find something**.
Sample with `--order risk` (and without `--exclude-reviewed`): it takes
pages whose last verdict was FAIL first (they were fixed but never
re-read), then pages never read, then the oldest verdicts.
`translation/v2/round.py start --order risk` does this for you.

| Locale | Last verdict FAIL | Never read | Oldest verdict |
|---|---|---|---|
| `fr` | **1** | 0 | 2026-07-05 |
| `ar` | **1** | 0 | 2026-08-29 |
| `de` | **1** | 0 | 2026-09-29 |
| `es` | **0** | 0 | 2026-06-26 |
| `pl` | **0** | 0 | 2026-06-28 |
| `pt` | **0** | 0 | 2026-07-05 |
| `id` | **0** | 0 | 2026-09-12 |
| `ja` | **0** | 0 | 2026-09-28 |
| `it` | **0** | 0 | 2026-09-28 |
| `ko` | **0** | 0 | 2026-09-28 |
| `uk` | **0** | 0 | 2026-09-29 |
| `tl` | **0** | 0 | 2026-09-29 |
| `he` | **0** | 0 | 2026-09-29 |
| `ms` | **0** | 0 | 2026-09-29 |
| `th` | **0** | 0 | 2026-09-29 |
| `ro` | **0** | 0 | 2026-09-29 |
| `cs` | **0** | 0 | 2026-09-29 |

**`--max-leaks` currently filters nothing, and that is expected.** A
leak is a term the locale's `translation/glossary/<loc>.json` records
as wrongly left in English — *not* any capitalized English word. The
terms the house style keeps in English (Qiskit, Qubit, Gate, Circuit, Backend, Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum, QPU, IBM Quantum Platform, Qiskit Runtime, Qiskit Functions, Circuit functions, Application functions, Catalog Functions, Custom Functions, job mode, session mode, batch mode)
do not count, and no locale currently records anything else, so
every file scores 0. What limits a pool today is pages already
reviewed with nothing written since, not leakage.

**Nearly exhausted** (fewer than 25 eligible) — still worth
a short round, but expect to re-sweep files that already carry a
verdict, or to accept a round smaller than 25:

- `ar` — 0 never read, 0 delta (449/449 reviewed)
- `cs` — 0 never read, 0 delta (449/449 reviewed)
- `de` — 0 never read, 0 delta (449/449 reviewed)
- `es` — 0 never read, 0 delta (449/449 reviewed)
- `fr` — 0 never read, 0 delta (449/449 reviewed)
- `he` — 0 never read, 0 delta (449/449 reviewed)
- `id` — 0 never read, 0 delta (449/449 reviewed)
- `it` — 0 never read, 0 delta (449/449 reviewed)
- `ja` — 0 never read, 0 delta (449/449 reviewed)
- `ko` — 0 never read, 0 delta (449/449 reviewed)
- `ms` — 0 never read, 0 delta (449/449 reviewed)
- `pl` — 0 never read, 0 delta (449/449 reviewed)
- `pt` — 0 never read, 0 delta (449/449 reviewed)
- `ro` — 0 never read, 0 delta (449/449 reviewed)
- `th` — 0 never read, 0 delta (449/449 reviewed)
- `tl` — 0 never read, 0 delta (449/449 reviewed)
- `uk` — 0 never read, 0 delta (449/449 reviewed)

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `2026100104-uk-JanLahmann` | 3 | 0 | 0.0% |
| `2026100104-tl-JanLahmann` | 3 | 0 | 0.0% |
| `2026100104-th-JanLahmann` | 3 | 0 | 0.0% |
| `2026100104-ro-JanLahmann` | 3 | 0 | 0.0% |
| `2026100104-pt-JanLahmann` | 3 | 0 | 0.0% |
| `2026100104-pl-JanLahmann` | 3 | 0 | 0.0% |

Typical FAIL rate is around **0%**. If your round comes
in far above that, stop and tell the maintainer before fixing — it
usually means the rubric drifted, not that the locale collapsed.

---

## The highest-value thing you can do

**If you read one of these languages fluently: spot-check pages as a
human.** Model review is close to saturation: most reads come back
MINOR_ISSUES, mostly style. A fluent reader going through 10-20 pages
catches what the model reviewers miss, and tells us whether their
Naturalness notes matter to a real reader. Open an issue with what you
found (page, sentence, what it should say); you do not need the
pipeline for this. The locales with the most FAIL history in the table
above benefit most.

**Otherwise, when two or more locales are flagged for the same sentence,
check the other fifteen before fixing.**

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

