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

If the pool is smaller than `N`, that locale has drained at the threshold
you picked. Raise it (`--max-leaks 4`, then `6`, `8`, `12`) to reopen the
pool rather than shrinking the round.

**[`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md) lists the current pool size
per locale and the threshold to start from.** It is regenerated daily, so
trust it over any number written into this file — pool sizes move every
time a round lands.

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
examples point at) and `manifest-fix.json`. Fill the batches with the
`Workflow` tool:

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
