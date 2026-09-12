# What we need right now

*Auto-generated on 2026-09-12 by `translation/scripts/contributing-status.py`.*
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

*No open claims right now — every locale is free.*

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
reviewed with nothing written since, not leakage.

| Locale | Unreviewed pool | Reviewed so far |
|---|---|---|
| `th` | **309** | 198/433 (45%) |
| `de` | **291** | 372/433 (85%) |
| `he` | **266** | 373/433 (86%) |
| `id` | **264** | 213/433 (49%) |
| `ko` | **250** | 237/433 (54%) |
| `cs` | **240** | 272/433 (62%) |
| `pl` | **232** | 267/433 (61%) |
| `ro` | **222** | 258/433 (59%) |
| `ms` | **211** | 263/433 (60%) |
| `tl` | **211** | 384/433 (88%) |
| `ja` | **198** | 312/433 (72%) |
| `uk` | **181** | 311/433 (71%) |
| `ar` | **180** | 319/433 (73%) |
| `it` | **163** | 323/433 (74%) |
| `pt` | **149** | 323/433 (74%) |
| `es` | **148** | 330/433 (76%) |
| `fr` | **139** | 331/433 (76%) |

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `2026091001-JanLahmann` | 158 | 12 | 7.6% |
| `2026091002-JanLahmann` | 149 | 27 | 18.1% |
| `2026090802-JanLahmann` | 22 | 3 | 13.6% |
| `2026090801-JanLahmann` | 6 | 0 | 0.0% |
| `2026090803-JanLahmann` | 6 | 0 | 0.0% |
| `2026090804-JanLahmann` | 25 | 3 | 12.0% |

Typical FAIL rate is around **12%**. If your round comes
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

