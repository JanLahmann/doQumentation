# What we need right now

*Auto-generated on 2026-09-26 by `translation/scripts/contributing-status.py`.*
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

*Never read* pages have no verdict yet: a full read. *Delta* pages
were reviewed, and a sync has since written new entries on them: the
reviewer judges only those entries. A locale can be 100% reviewed and
still have a delta pool.

| Locale | Never read | Delta | Reviewed so far |
|---|---|---|---|
| `de` | **88** | 220 | 355/443 (80%) |
| `he` | **87** | 194 | 356/443 (80%) |
| `th` | **17** | 252 | 416/433 (96%) |
| `cs` | **181** | 76 | 262/443 (59%) |
| `id` | **17** | 224 | 416/433 (96%) |
| `pl` | **176** | 62 | 257/433 (59%) |
| `ro` | **184** | 46 | 249/433 (57%) |
| `tl` | **60** | 158 | 373/433 (86%) |
| `ms` | **179** | 38 | 254/433 (58%) |
| `ja` | **131** | 74 | 302/433 (69%) |
| `ko` | **17** | 186 | 416/433 (96%) |
| `ar` | **134** | 65 | 309/443 (69%) |
| `uk` | **131** | 57 | 302/433 (69%) |
| `it` | **120** | 51 | 313/433 (72%) |
| `es` | **124** | 44 | 319/443 (72%) |
| `fr` | **123** | 35 | 320/443 (72%) |
| `pt` | **120** | 38 | 313/433 (72%) |

---

## What recent rounds found

| Round (seed) | Files | FAIL | Rate |
|---|---|---|---|
| `2026091103-JanLahmann` | 28 | 0 | 0.0% |
| `2026091102-JanLahmann` | 264 | 4 | 1.5% |
| `2026091101-JanLahmann` | 309 | 16 | 5.2% |
| `2026091003-JanLahmann` | 250 | 11 | 4.4% |
| `2026091002-JanLahmann` | 149 | 27 | 18.1% |
| `2026091001-JanLahmann` | 158 | 12 | 7.6% |

Typical FAIL rate is around **6%**. If your round comes
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

