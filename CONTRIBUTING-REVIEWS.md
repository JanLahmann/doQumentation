# Reviewing translations with Claude Code — start here

**doQumentation** ships IBM Quantum's Qiskit docs in 17 languages. The
translations are machine-produced and then reviewed. This file is the
complete, self-contained recipe for running one **review round**: sample
some translated pages, have Claude read them against the English source,
fix what genuinely misleads a learner, and open a PR.

A round is **budget-shaped**: you tell it how many files to review, and it
costs roughly that many × 40k tokens. It's designed to soak up whatever is
left of a weekly Claude Max budget and stop cleanly — nothing breaks if you
run out mid-round.

---

## For the human: how to start

You need a **Claude Max subscription** (the review model is Opus),
`git`, `python3` (3.11+), the [`gh` CLI](https://cli.github.com/), and the
tools that render a locale from its PO files: **po4a ≥ 0.74, GNU gettext
and the `polib` package** (`brew install po4a gettext` or
`apt-get install po4a gettext`, then `pip install polib`). You do **not**
need Node, npm, or a site build.

1. Fork <https://github.com/JanLahmann/doQumentation> on GitHub.
2. Clone your fork and `cd` into it.
3. **Sync your fork with upstream `main` — every time, not just the first.**

   ```bash
   gh repo sync <YOUR-USER>/doQumentation --source JanLahmann/doQumentation --branch main
   git checkout main && git pull
   ```

   This is not housekeeping. Which files are eligible for review is read
   from `translation/status.json`, and every merged round updates it. On a
   fork that is even a few days old, Claude will re-review pages someone
   already did, and your PR will conflict with what has landed since.
   See [`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md) after syncing — it is
   regenerated daily and tells you what is actually left.

4. **Claim a locale.** Look at the open claims
   (`gh issue list --repo JanLahmann/doQumentation --label translation-claim`,
   also listed in [`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md)), pick a
   locale nobody holds, and open an issue with the **Claim a locale**
   template. That issue is the reservation; close it when you stop.
5. Open Claude Code in the repo and say what you want, in your own words:

   > I want to help with reviews. What should I do?

   or, if you already know the locale and how much you can spend:

   > Review the `<LOCALE>` translation, about `<N>` files. Use a workflow.

   The repo's `CLAUDE.md` routes either sentence here. Claude will ask for
   whatever is missing (locale, file count, your GitHub handle) and check
   your fork, the claim and the toolchain before it starts.

If Claude asks whether it may **"use a workflow"**, say yes — that
authorizes it to fan out parallel sub-agents, which is what makes a round
finish in one sitting rather than ten.

Everything below is addressed to Claude.

---

## Instructions for Claude

You are running a Tier-4 deep review of one locale of a translated
documentation corpus. Work only in the repo root.

### 0. Establish scope before doing anything

Confirm with the user, or take from their prompt:

- **`LOCALE`** — see **[`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md)** for
  which locales still have unreviewed pages and how much is left in each.
  All 17 main locales are in scope (`de es uk ja fr it pt tl ar he ms id
  th ko pl ro cs`); none is finished.
- **`N`** — how many files to review this round. Budget ≈ **40k tokens per
  file**, so 25 files ≈ 1M, 60 files ≈ 2.4M. When in doubt pick 25; a small
  round that completes beats a large one that dies.
- **`HANDLE`** — the user's GitHub username. It namespaces their output
  file so concurrent contributors never collide.
- **The claim.** `gh issue list --repo JanLahmann/doQumentation --label translation-claim`
  must show an open claim for `LOCALE` by this user. If another person
  holds it, stop and say so. If nobody does, open one for the user (the
  *Claim a locale* issue template; title `claim: <LOCALE> (review)`)
  before drawing a sample.

Pick a **`SEED`** no one has used: `<YYYYMMDD><two digits of your choosing>`,
e.g. `2026072041`. Check `translation/reviews/` for existing filenames and
avoid a collision.

### 1. Verify setup

```bash
python3 --version                      # 3.11+
git remote -v                          # should show the user's fork
po4a --version && msgmerge --version | head -1 && python3 -c "import polib"
python3 translation/scripts/translation-status.py --locale <LOCALE>
```

If `translation/status.json` is missing, the clone is incomplete — stop and
say so. If po4a, gettext or polib is missing, stop and tell the user what
to install (see the top of this file); nothing below works without them.

**Then check the fork is current, before drawing any sample:**

```bash
git remote add upstream https://github.com/JanLahmann/doQumentation.git 2>/dev/null
git fetch -q upstream main
git rev-list --count HEAD..upstream/main    # 0 == up to date
```

If that count is not `0`, **stop and sync before continuing**:

```bash
git checkout main && git merge --ff-only upstream/main
```

**Then render the locale.** The pages the review reads live under
`i18n/<LOCALE>/docusaurus-plugin-content-docs/current/`; they are derived
from the PO files at build time and are **not in git**, so on a fresh clone
that directory is empty and the sampler reports no eligible files:

```bash
python3 translation/v2/render.py --locale <LOCALE>     # ~1 min, 433 pages
```

Re-run it after every fix wave, so lint and the gauge read what the PO
files now say.

Do not "work around" a behind-fork by drawing the sample anyway. Eligibility
comes from `status.json`, which every merged round rewrites; on a stale copy
`--exclude-reviewed` silently filters against an old verdict set, so you will
re-review pages that already have verdicts and open a PR that conflicts with
what has landed. Say plainly that the fork was behind and that you synced.

### 2. Draw the sample

```bash
python3 translation/scripts/sample-deep-review.py \
  --locale <LOCALE> --per-locale <N> --seed <SEED> \
  --max-leaks <THRESHOLD> --drift-focus --exclude-reviewed \
  --out /tmp/round-<SEED>.json
```

It prints the eligible pool size. `--exclude-reviewed` skips files that
already carry a verdict, so rounds never re-tread ground.

If the pool is smaller than `N`, that locale is genuinely drained: take the
short round rather than shrinking `N` on a locale that still has work. (The
`--max-leaks` ladder used to reopen a pool here; it no longer does — see the
note below.)

> **A "leak" is what the locale's glossary records, not any English word.**
> Since 2026-09-08 the terms the house style keeps in English — Qiskit,
> Qubit, Gate, Circuit, Backend, Transpiler, Session, Sampler, Estimator,
> PUB, IBM Quantum, QPU (`_common.KEEP_ENGLISH_TERMS`) — are **not** counted.
> They used to be, which held 154 de / 92 he / 70 cs pages out of review for
> following the house style. A locale whose `translation/glossary/<loc>.json`
> records nothing therefore has a leak count of 0 and `--max-leaks` does not
> filter it at all; that is expected, not a broken sampler.

**[`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md) lists the current pool size
per locale.** It is regenerated daily, so
trust it over any number written into this file — pool sizes move every
time a round lands.

#### Or: sweep for misaligned pairings instead

There is a second way to fill a round, aimed at one specific defect:

```bash
python3 translation/scripts/find-positional-drift.py --locale <LOCALE> \
  --out /tmp/drift-<LOCALE>.json
```

`bootstrap` seeded the PO files from the old rendered pages. Where po4a
refused to pair the two files exactly it fell back to matching their po4a
*type* sequences with difflib, and adopted the runs that matched (those
entries carry a `# doq-bootstrap: positional` comment). On a page that is
mostly `Plain text`, difflib has no content to place an insertion or
deletion with, so it puts it at an arbitrary point in the run and every
entry between there and the true position carries its neighbour's
translation.

This is the one defect class that survives every automatic gate we have.
The page renders, the prose is fluent, and `check.py` passes it, because a
well-formed translation of the wrong paragraph breaks no structural
invariant — no code span, URL, tag or math is out of place. Only the
meaning is wrong, which is exactly what a fluent reader is for.

**Treat the output as a list of suspect PAGES, not of suspect entries.**
The detector only fires when a better-fitting neighbour lies within eight
entries and the pair carries enough anchors to score, so it cannot see a
misaligned heading or a run longer than its window. On `it` it found 14
entries; sweeping those pages in full found 26, including seven
consecutive headings in `learning/modules/computer-science/vqe.mdx` each
holding the previous heading's text. Gauge the candidates (step 5) to
decide which pages are really affected, then build the fix spec so the
fixer re-checks **every** entry on those pages, not only the flagged ones.

In the spec, say plainly that a flagged translation belongs to a different
paragraph and must be discarded rather than repaired, or the fixer will
try to polish text that was never about this source.

Two more things this defect is not:

- It is **not** inherited identically across locales. The same pages break
  everywhere, because the fragility is in the English structure, but the
  entries differ: only 2 of ~34 confirmed entries coincided between `de`
  and `pt`. You cannot reuse one locale's entry list for another.
- The correct translation usually **cannot** be recovered from the old
  rendered page by content matching. Tried on `de`: 0 of 11 right, with
  confidence scores of 0.94-1.00 on entirely wrong paragraphs. Anchor-free
  prose gives absolute matching nothing to work with. Retranslate instead.

To choose *which* pages to sweep, run it across every locale:

```bash
python3 translation/scripts/find-positional-drift.py --all --rank-pages --print
```

A slip starts from a dropped entry, and entries are dropped because of
something in the **English** page — so the same page slips in every locale
at once. A page flagged in 16 of 17 locales is not seventeen coincidences;
those pages are where the defect really lives.

### 3. Run the review wave

Bake the sample into a runnable workflow, then execute it:

```bash
python3 translation/scripts/make-opus-run.py \
  --sample /tmp/round-<SEED>.json --out /tmp/round-<SEED>-wf.js
```

Then call the `Workflow` tool with `{scriptPath: "/tmp/round-<SEED>-wf.js"}`.
It runs Opus agents in batches of 7 and returns a `records` array.

**Copy the baked `.js` and the sample somewhere outside `/tmp` first** —
`/tmp` gets reaped, and you will want them if you have to resume.

### 4. The rubric (know it, so you can sanity-check the output)

The prompt asks each agent exactly one question: **would this mislead a
learner?**

- **FAIL** — yes. Semantic drift or inversion, a hallucinated claim, a term
  rendered so wrongly it teaches a false concept, or raw-MT prose
  throughout. One misleading sentence is a FAIL.
- **MINOR_ISSUES** — no, but a native technical editor would still change
  something: a calque, stiff phrasing, an imperfect-but-recognizable term,
  inconsistent terminology within the file, a dropped qualifier.
- **PASS** — no, and nothing an editor would change.

Expect roughly **1–3% FAIL** and a large MINOR share. If a round comes back
with 15%+ FAIL, the rubric is being misread — stop and report it rather
than launching a large fix wave. (This exact failure happened once; see
`.claude/PROJECT_HANDOFF.md`.)

**PASS means "screened, no misleading defect found" — not "certified
clean."** Don't describe it as clean in your summary.

### 5. Gauge before fixing

Do not fix on trust. For each FAIL, spawn 3 short sub-agents prompted to
**refute** the finding (default to "refuted" when uncertain), and keep the
finding only if a majority fail to refute it. With ≤3 FAILs, do this
inline; with more, add it as a workflow stage.

Report the gauge result to the user. Findings are usually real even when
the severity label is too harsh — remediate on the **finding**, not the
label.

### 6. Run the fix wave

Fixes go through the **PO files**, never into a rendered page (a rendered
page is regenerated from the PO at the next build, so an edit there is
lost). The path reuses the translation pipeline: one batch per page, the
same `translate-locale` workflow, the same checker gate.

Build a fix spec — a JSON array, one entry per file worth fixing (surviving
FAILs, plus MINORs with concrete line-level examples). The raw `records`
from step 3 are accepted as-is (PASS records are skipped), or write the
trimmed form:

```json
[{"rel": "guides/foo.mdx",
  "note": "<the reviewer's editor_note>",
  "examples": [{"type": "wrong-term",
                "source": "<EN quote>", "translation": "<current>",
                "why": "<what a learner gets wrong>",
                "suggested": "<correction>"}]}]
```

Then:

```bash
python3 translation/v2/fix.py --locale <LOCALE> \
  --fixes translation/v2/work/fixes-<SEED>.json --prepare
```

It writes `translation/v2/work/<LOCALE>/fix-NNN-sonnet.json` (every
translated entry of the page, with a `review` field on the entries the
examples point at) and `manifest-fix.json`.

> **`--prepare` wipes the work directory first.** It deletes every
> `fix-*.json` under `work/<LOCALE>/` before writing new ones, so running it
> while a wave is still filling destroys the batches that wave is reading.
> The agents then find nothing and return empty — on `ro` this cost 11
> batches and 33 agent runs. Finish and `--apply` the outstanding wave
> before preparing anything else for the same locale.

> **If you write your own instruction text, build it ON
> `fix_instructions(locale)` — do not replace it.** That function
> interpolates the locale's register from `language_info()`, among other
> things. Hand-writing the text and omitting a field is silent: on `ro` the
> `Register:` line went missing and a wave came back addressing the reader
> as *dumneavoastră* instead of *tu*. Nothing checks register — not
> `check.py`, not lint, not `mdxcheck` — so it renders perfectly and reads
> wrong. Append your extra guidance to `fix_instructions(locale)` instead.

Fill the batches with the `Workflow` tool:

```
Workflow({ scriptPath: ".claude/workflows/translate-locale.js",
           args: <the parsed contents of translation/v2/work/<LOCALE>/manifest-fix.json,
                  plus "agentType": "translator"> })
```

One Sonnet agent per page corrects the flagged entries and copies the rest
back verbatim. Then write the results into the PO files, through the gate:

```bash
python3 translation/v2/fix.py --locale <LOCALE> --apply
python3 translation/v2/render.py --locale <LOCALE>
```

`--apply` writes only the entries that changed and pass `check.py` (code
spans, URLs, math, tags, anchors, length), stamps each with
`doq: fixed after review <date>`, and rejects the rest with a reason. A
rejected entry is redone in a second, smaller wave or left with its verdict
on record; never hand-edit the PO to force it.

Two things to check before you go on, neither of which any tool reports:

**Count the applied entries against the flagged ones.** `--apply` prints
how many it accepted. If that is fewer than you flagged, some flags did not
reach the fixer or the fixer declined them; if it is more, the fixer
changed entries nobody reviewed. Both happen, and both matter.

**Diff every applied change against your flagged set, not just the flagged
ones.** Confirming your flagged entries landed is a *different* check from
confirming nothing else moved, and only the second one catches a bad
unflagged change. Twice a fix wave replaced a translated `<IBMVideo
title="…">` caption with the English original — invisible to every gate,
because `title=` is the one attribute `check.py` does not compare
byte-for-byte (it must change under translation) and lint reads an English
caption as prose that may legitimately be English. Both were found only by
this diff.

Unflagged changes are not automatically wrong: on a drift round the fixer
reading a whole page often repairs more of a shifted run than the detector
saw, which is the point. Read them and decide; do not assume either way.

A batch that returns one translation too few is discarded whole by
`--apply` — correctly, since a dropped item shifts every later one and
would manufacture the very defect you are fixing. Expect this: it happened
on 2 of ~24 batches. Redo those in a second wave. Note that
`translate-locale.js` will still report such a batch as fully filled, since
it parses the agent's own count and has no filesystem access to check.

### 7. Gate the result

All three must pass before you commit:

```bash
python3 translation/scripts/lint-translation.py --locale <LOCALE>
python3 translation/scripts/check-known-mistranslations.py --locale <LOCALE>
python3 translation/scripts/check-wrong-language.py --locale <LOCALE>
```

> The rendered pages under `i18n/<LOCALE>/…/current/` are derived from
> the PO files and are not in git (`translation/v2/README.md`). Run the
> gate on a fresh `render.py` output, and if anything edited a rendered
> page directly, discard it: the PO files are the only thing that ships.

`lint-translation.py` has one known false positive: "unmatched code fence"
on a line like `` ```from scipy.optimize import minimize``` `` that opens
and closes on itself. Before treating any lint failure as a regression,
check whether the English source at `docs/<same path>` fails identically —
if it does, it is not your bug, and you must **not** "fix" it by diverging
from English.

### 8. Ship it

Write the verdicts to a **new, handle-namespaced file** — never edit an
existing one:

```
translation/reviews/opus-<SEED>-<HANDLE>.json
```

That's the raw `records` array from step 3, verbatim.

```bash
git checkout -b review/<LOCALE>-<SEED>
git add translation/reviews/opus-<SEED>-<HANDLE>.json
git add i18n/<LOCALE>/po           # the PO files only; nothing under …/current/
git status --short                 # exactly those two paths, nothing else
git commit && gh pr create --repo JanLahmann/doQumentation
```

**Do not commit `translation/status.json`.** The maintainer banks your
verdicts into it with `review-translations.py --record-opus` after merge.
This is the whole reason contributor PRs never conflict: you touch only a
brand-new review file and your own locale's PO tree.

PR description should state: locale, seed, file count, the verdict tally,
the gauge result, and which files you changed.

### Hard rules

- **Never** edit `translation/status.json` — that's the maintainer's merge step.
- **Never** edit `docs/` — that's the English source of truth.
- **Never** edit a locale other than the one assigned.
- **Never** hand-edit a rendered page or a `.po` file; `fix.py --apply`
  is the only way a fix reaches the translation.
- Fix only the identified defect. Do not restyle passages that are already
  correct, and do not touch code blocks, math, JSX, image paths, or heading
  anchors.

### If you run out of budget mid-round

Expected, and safe. The review workflow batches 7 agents at a time and
the fix workflow runs a sliding pool of 5, so at most a handful are lost;
every completed review record and every filled `fix-*.out.json` is
preserved on disk, and nothing reaches a PO file until `fix.py --apply`.

To resume in the **same session**: call `Workflow` again with the same
`scriptPath` plus `resumeFromRunId: "<the runId from the first call>"` —
completed agents replay from cache instantly and only the lost ones re-run.

Across sessions the cache is gone. Recover the completed verdicts from the
workflow's `journal.jsonl` (last-wins per `locale`+`file`), write them to
the reviews file, commit that as a safety net, and either ship the partial
round or draw a fresh sample with `--exclude-reviewed` to pick up the rest.
A killed fix agent leaves at most an incomplete `fix-*.out.json`, which
`--apply` rejects as a whole (count mismatch); delete it and rerun that
batch.

A partial round is a perfectly good contribution. Ship what completed.
