# What we need right now

*Auto-generated on 2026-09-30 by `translation/scripts/contributing-status.py`.*
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
| `all` | @JanLahmann | review | 2026-09-29 | [#725](https://github.com/JanLahmann/doQumentation/issues/725) |

---

## Pick a locale

Every locale below has pages waiting for a read: pages never read, or
*delta* pages whose model-written entries no reviewer has seen yet (the
pool table further down). Pick one that is not claimed above, open
your claim issue, then follow `CONTRIBUTING-REVIEWS.md`. When a
locale's pool runs dry, sample with `--order risk`: it re-reads the
pages whose last verdict was FAIL first (the first column here).

| Locale | Last verdict FAIL | Never read | Oldest verdict |
|---|---|---|---|
| `ms` | **9** | 0 | 2026-09-29 |
| `fr` | **8** | 0 | 2026-07-05 |
| `id` | **6** | 0 | 2026-09-12 |
| `it` | **6** | 0 | 2026-09-28 |
| `de` | **4** | 0 | 2026-09-29 |
| `ar` | **2** | 0 | 2026-08-29 |
| `pl` | **1** | 0 | 2026-06-28 |
| `es` | **0** | 0 | 2026-06-26 |
| `pt` | **0** | 0 | 2026-07-05 |
| `ja` | **0** | 0 | 2026-09-28 |
| `ko` | **0** | 0 | 2026-09-28 |
| `uk` | **0** | 0 | 2026-09-29 |
| `tl` | **0** | 0 | 2026-09-29 |
| `he` | **0** | 0 | 2026-09-29 |
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

*Never read* pages have no verdict yet: a full read. *Delta* pages
were reviewed, and entries were written on them after that: almost
always a round's own fix wave (a fix carries the verdict's date, and
only entries stamped before a verdict count as read), sometimes an
English sync. The reviewer judges only those entries. A locale can be
100% reviewed and still have a delta pool.

| Locale | Never read | Delta | Reviewed so far |
|---|---|---|---|
| `he` | **0** | 411 | 449/449 (100%) |
| `ms` | **0** | 397 | 449/449 (100%) |
| `ro` | **0** | 381 | 449/449 (100%) |
| `cs` | **0** | 375 | 449/449 (100%) |
| `de` | **0** | 374 | 449/449 (100%) |
| `ar` | **0** | 373 | 449/449 (100%) |
| `uk` | **0** | 367 | 449/449 (100%) |
| `ko` | **0** | 365 | 449/449 (100%) |
| `th` | **0** | 360 | 449/449 (100%) |
| `it` | **0** | 348 | 449/449 (100%) |
| `fr` | **0** | 347 | 449/449 (100%) |
| `ja` | **0** | 345 | 449/449 (100%) |
| `es` | **0** | 342 | 449/449 (100%) |
| `id` | **0** | 339 | 449/449 (100%) |
| `pt` | **0** | 337 | 449/449 (100%) |
| `tl` | **0** | 303 | 449/449 (100%) |
| `pl` | **0** | 281 | 449/449 (100%) |

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `2026093171-pl-JanLahmann` | 80 | 1 | 1.2% |
| `2026093170-ar-JanLahmann` | 78 | 2 | 2.6% |
| `2026093169-uk-JanLahmann` | 40 | 0 | 0.0% |
| `2026093168-tl-JanLahmann` | 40 | 1 | 2.5% |
| `2026093167-th-JanLahmann` | 40 | 0 | 0.0% |
| `2026093166-ro-JanLahmann` | 40 | 0 | 0.0% |

Typical FAIL rate is around **1%**. If your round comes
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

