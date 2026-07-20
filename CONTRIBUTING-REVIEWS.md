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

You need a **Claude Max subscription** (the review model is Opus) and
`git`, `python3`, and the [`gh` CLI](https://cli.github.com/). You do
**not** need Node, npm, or a site build.

1. Fork <https://github.com/JanLahmann/doQumentation> on GitHub.
2. Clone your fork and `cd` into it.
3. Ask the maintainer which **locale** to take (see the table below), so
   two people don't review the same one.
4. Open Claude Code in the repo and paste:

   > Read `CONTRIBUTING-REVIEWS.md` and run one review round for locale
   > `<LOCALE>`, about `<N>` files. **Use a workflow** for the review and
   > fix waves.

The words **"use a workflow"** matter — they authorize Claude to fan out
parallel sub-agents, which is what makes a round finish in one sitting
rather than ten.

Everything below is addressed to Claude.

---

## Instructions for Claude

You are running a Tier-4 deep review of one locale of a translated
documentation corpus. Work only in the repo root.

### 0. Establish scope before doing anything

Confirm with the user, or take from their prompt:

- **`LOCALE`** — one of `es uk ja fr it pt tl ar he ms id th ko pl ro cs`.
  (`de` is complete. The 9 German dialects — `aut bad bar bln gsw ksh nds
  sax swg` — are never reviewed; skip them without asking.)
- **`N`** — how many files to review this round. Budget ≈ **40k tokens per
  file**, so 25 files ≈ 1M, 60 files ≈ 2.4M. When in doubt pick 25; a small
  round that completes beats a large one that dies.
- **`HANDLE`** — the user's GitHub username. It namespaces their output
  file so concurrent contributors never collide.

Pick a **`SEED`** no one has used: `<YYYYMMDD><two digits of your choosing>`,
e.g. `2026072041`. Check `translation/reviews/` for existing filenames and
avoid a collision.

### 1. Verify setup

```bash
python3 --version                      # 3.10+
git remote -v                          # should show the user's fork
python3 translation/scripts/translation-status.py --locale <LOCALE>
```

If `translation/status.json` is missing, the clone is incomplete — stop and
say so. There is nothing else to install.

### 2. Draw the sample

```bash
python3 translation/scripts/sample-deep-review.py \
  --locale <LOCALE> --per-locale <N> --seed <SEED> \
  --max-leaks 2 --drift-focus --exclude-reviewed \
  --out /tmp/round-<SEED>.json
```

It prints the eligible pool size. `--exclude-reviewed` skips files that
already carry a verdict, so rounds never re-tread ground.

If the pool is smaller than `N`, that locale has drained at `--max-leaks 2`.
Raise it (`--max-leaks 5`, then `10`) to reopen the pool rather than
shrinking the round. Current pool sizes at `--max-leaks 2`:

| Ample (85+) | Thin (20–25) | Drained (<15) |
|---|---|---|
| `tl` 139, `fr` 123, `es` 120, `it` 109, `pt` 105, `ar` 101, `uk` 95, `ja` 87 | `ro` 25, `ko` 23, `pl` 20 | `ms` 10, `id` 9, `he` 4, `th` 3, `cs` 2 |

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

Build a fix spec — a JSON array, one entry per file worth fixing (surviving
FAILs, plus MINORs with concrete line-level examples):

```json
[{"locale": "<LOCALE>", "rel": "guides/foo.mdx", "locale_name": "French",
  "note": "<the reviewer's editor_note>",
  "examples": [{"type": "wrong-term", "line_approx": "~120",
                "source": "<EN>", "translation": "<current>",
                "why": "<what a learner gets wrong>",
                "suggested": "<correction>"}]}]
```

Then:

```bash
python3 translation/scripts/make-fix-run.py \
  --fixes /tmp/fixes-<SEED>.json --out /tmp/fix-<SEED>-wf.js
```

and run it with the `Workflow` tool. Sonnet agents apply one file each.

### 7. Gate the result

All three must pass before you commit:

```bash
python3 translation/scripts/lint-translation.py --locale <LOCALE>
python3 translation/scripts/check-translation-freshness.py --locale <LOCALE>
python3 translation/scripts/check-known-mistranslations.py --locale <LOCALE>
python3 translation/scripts/check-wrong-language.py --locale <LOCALE>
```

Freshness must show **no new stale files**. If a file went stale, a fix
agent edited the `{/* doqumentation-source-hash: … */}` marker — revert
that file and redo it.

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
git add -f i18n/<LOCALE>/          # i18n/ is gitignored — the -f is required
git commit && gh pr create --repo JanLahmann/doQumentation
```

**Do not commit `translation/status.json`.** The maintainer banks your
verdicts into it with `review-translations.py --record-opus` after merge.
This is the whole reason contributor PRs never conflict: you touch only a
brand-new review file and your own locale's subtree.

PR description should state: locale, seed, file count, the verdict tally,
the gauge result, and which files you changed.

### Hard rules

- **Never** edit `translation/status.json` — that's the maintainer's merge step.
- **Never** edit `docs/` — that's the English source of truth.
- **Never** edit a locale other than the one assigned.
- **Never** touch a `{/* doqumentation-source-hash: … */}` marker.
- **Never** touch the 9 German dialects.
- Fix only the identified defect. Do not restyle passages that are already
  correct, and do not touch code blocks, math, JSX, image paths, or heading
  anchors.

### If you run out of budget mid-round

Expected, and safe. Both workflows batch 7 agents at a time, so at most 7
are lost; every completed batch is preserved, and fix-agent edits are
already on disk.

To resume in the **same session**: call `Workflow` again with the same
`scriptPath` plus `resumeFromRunId: "<the runId from the first call>"` —
completed agents replay from cache instantly and only the lost ones re-run.

Across sessions the cache is gone. Recover the completed verdicts from the
workflow's `journal.jsonl` (last-wins per `locale`+`file`), write them to
the reviews file, commit that as a safety net, and either ship the partial
round or draw a fresh sample with `--exclude-reviewed` to pick up the rest.
**Revert any partial edit a killed fix-agent left behind before redoing it.**

A partial round is a perfectly good contribution. Ship what completed.
