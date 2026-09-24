# Reviewing translations with Claude Code — start here

**doQumentation** ships IBM Quantum's Qiskit docs in 17 languages. The
translations are machine-produced and then reviewed. This file is the
complete, self-contained recipe for running one **review round**: sample
some translated pages, have Claude read them against the English source,
fix what genuinely misleads a learner, and open a PR.

A round is **budget-shaped**: you tell it how many pages to review (40 is
the default for a first round), and it stops cleanly if you run out of
usage mid-round — nothing breaks, and it resumes where it stopped.

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

   This is not housekeeping. Which pages are still unreviewed is read from
   the PO files themselves (each reviewed page carries its verdict in its
   PO header), and every merged round changes them. On a fork that is even
   a few days old, Claude will re-review pages someone already did, and
   your PR will conflict with what has landed since.
   See [`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md) after syncing — it is
   regenerated daily and tells you what is actually left.

4. **Claim a locale.** Look at the open claims
   (`gh issue list --repo JanLahmann/doQumentation --label translation-claim`,
   also listed in [`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md)), pick a
   locale nobody holds, and open an issue with the **Claim a locale**
   template. That issue is the reservation; close it when you stop.
5. Open a **new** Claude Code session in the repo (after pulling — the
   review agent it needs is read at session start) and say, in any
   language:

   > Help with translation reviews on doQumentation, locale `<LOCALE>`.

   That is the whole prompt. The repo's `CLAUDE.md` routes it here; Claude
   checks your fork, the toolchain and the claim (and opens the claim if
   you have not), runs a 40-page round, explains each step to you in your
   language and asks before anything this recipe does not cover.

If Claude asks whether it may **"use a workflow"**, say yes — that
authorizes it to fan out parallel sub-agents, which is what makes a round
finish in one sitting rather than ten.

Everything below is addressed to Claude.

---

## Instructions for Claude

You are running a Tier-4 deep review of one locale of a translated
documentation corpus. Work only in the repo root.

**Talk to the user in the language they wrote in.** Say briefly what each
step does before running it and what it found after; report token use at
the end of each workflow. Follow this recipe as written and **ask before
doing anything it does not describe** — a contributor cannot judge an
improvised step, and every past surprise came from one.

### 0. Establish scope before doing anything

Confirm with the user, or take from their prompt:

- **`LOCALE`** — see **[`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md)** for
  which locales still have unreviewed pages and how much is left in each.
  All 17 locales are in scope (`de es uk ja fr it pt tl ar he ms id th ko
  pl ro cs`); none is finished.
- **`N`** — how many pages to review this round. **Default 40** unless the
  user names a number. Measured all-in (read, gauge, fix wave; most of it
  cached context) at roughly 0.3–0.4M tokens per page, so 40 pages ≈ 15M,
  which fits in one usage window. A small round that completes beats a
  large one that dies; a partial round is a complete contribution.
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
ls i18n/<LOCALE>/po | head -3          # the locale's translation: one PO per page
```

If `i18n/<LOCALE>/po/` is missing, the clone is incomplete — stop and say
so. If po4a, gettext or polib is missing, install them if you can (`brew
install po4a gettext` / `apt-get install po4a gettext`, `pip install
polib`), otherwise tell the user what to install; nothing below works
without them.

**The po4a version must be 0.74 or newer** — check the number `po4a
--version` printed. Older releases render some pages differently, and every
gate after that reports noise. Linux distributions often ship an older
one: then install the current release from CPAN (`cpanm Locale::Po4a`) or
from <https://github.com/mquinson/po4a/releases>, and check again.

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

Do not "work around" a behind-fork by drawing the sample anyway. A page's
verdict is in its PO header, and every merged round writes new ones; on a
stale copy `--exclude-reviewed` filters against an old verdict set, so you
will re-review pages that already have verdicts and open a PR that
conflicts with what has landed. Say plainly that the fork was behind and
that you synced.

**Then render the locale.** The pages the review reads live under
`i18n/<LOCALE>/docusaurus-plugin-content-docs/current/`; they are derived
from the PO files at build time and are **not in git**, so on a fresh clone
that directory is empty and the sampler reports no eligible pages:

```bash
python3 translation/v2/render.py --locale <LOCALE>     # ~1 min, 433 pages
python3 translation/scripts/review-translations.py --progress --locale <LOCALE>
```

Re-run the render after every fix wave, so lint reads what the PO files
now say.

### 2. Draw the sample

```bash
python3 translation/scripts/sample-deep-review.py \
  --locale <LOCALE> --per-locale <N> --seed <SEED> \
  --drift-focus --exclude-reviewed \
  --out /tmp/round-<SEED>.json
```

It prints the eligible pool size and how many sampled pages are **delta**
reads; tell the user both numbers (full reads and delta reads) before
running anything. A page is eligible when it is rendered,
is not an English fallback, and has no entry left fuzzy or empty by an
English sync (the page would render English there). With
`--exclude-reviewed` it enters the sample in one of two modes:

- **full** — no verdict yet: the reviewer reads the whole page.
- **delta** — a verdict stands, but a model has written entries since it (a
  fix wave's repairs, a sync's retranslations) that no reviewer has read.
  The reviewer gets the page for context and those entries to judge; the
  sample row carries them as `delta_entries`. This is how every repair and
  every retranslation gets an Opus read, at a fraction of a full page.

A page whose verdict stands with nothing written since is skipped, so rounds
never re-tread ground. There is no minimum page length any more: the short
index and landing pages are where the Card captions live.

For every sampled page the sampler also writes a **paired prose file** under
`translation/v2/work/review/<LOCALE>/<page>.md`: every prose entry of the
PO, numbered `[n]` by its index, English then translation, with code, math
and outputs left out because they are never translated. That file is what
the reader reads — one Read instead of two full pages — and the number is
what the reader cites, which pins a fix to the exact entry. The sample row
carries its path as `pair`.

If the pool is smaller than `N`, that locale is genuinely drained: take the
short round rather than shrinking `N` on a locale that still has work.

> **`--max-leaks` filters nothing today, and that is expected.** A leak is
> a term the locale's `translation/glossary/<loc>.json` records as wrongly
> left in English — not any English word. The terms the house style keeps
> in English (Qiskit, Qubit, Gate, Circuit, Backend, Transpiler, Session,
> Sampler, Estimator, PUB, IBM Quantum, QPU; `_common.KEEP_ENGLISH_TERMS`)
> never count, and no locale currently records anything else.

**[`CONTRIBUTING-NOW.md`](CONTRIBUTING-NOW.md) lists the current pool size
per locale.** It is regenerated daily from the same PO headers, so trust it
over any number written into this file.

> **Other instruments exist, and they are not this recipe.** The
> deterministic completeness sieve, the model gauge and the positional-drift
> detector (`translation/v2/README.md`, *The meaning-and-completeness
> layer*) select *entries* rather than pages and have been run over every
> locale by the maintainer. What they cannot see — a fluent, complete,
> plausible mistranslation — is exactly what a page read is for. Stay on
> the page read.

### 3. Run the review wave

Bake the sample into a runnable workflow, then execute it:

```bash
python3 translation/scripts/make-opus-run.py \
  --sample /tmp/round-<SEED>.json --out /tmp/round-<SEED>-wf.js
```

The readers run as the `reviewer` agent (`.claude/agents/reviewer.md`: Read
only, Opus), the default of both bakers. It is registered when the session
starts, so a session opened before the file existed does not have it: the
workflow then stops at once with `aborted: agent type 'reviewer' is not
available`. Tell the user to start a new session and resume there; do not
switch to another agent type.

Then call the `Workflow` tool with `{scriptPath: "/tmp/round-<SEED>-wf.js"}`.
It runs Opus agents in batches of 7 and returns only the tally, the FAIL
list and the run id. The records themselves stay in the run's journal —
returning them inflated the orchestrator's context by ~11k characters per
shard for nothing — so collect them from there:

```bash
python3 translation/scripts/collect-opus-run.py --run <runId> [--run <runId> …] \
  --sample /tmp/round-<SEED>.json --out translation/reviews/opus-<SEED>-<HANDLE>.json
```

(last verdict per page wins; `--sample` adds each page's `mode` and delta
entries). Commit that file at once as a safety net.

**Copy the baked `.js` and the sample somewhere outside `/tmp` first** —
`/tmp` gets reaped, and you will want them if you have to resume.

If a reader dies on a **quota error** ("You've hit your session limit ·
resets …"), the workflow stops starting readers and says so in its result
(`aborted`). Nothing is retried into the wall. Stop there, give the user
the run IDs and the paths of the baked `.js` files, and resume with
`resumeFromRunId` once the window has reset — only the unread pages run.
The fix workflow and the gauge do the same.

A sample of ~300 pages is best run as several shards (split the sample's
`files` and bake each): the harness runs about four agents per workflow,
so parallelism comes from workflows, not from a bigger batch.

### 4. The rubric (know it, so you can sanity-check the output)

The prompt asks each agent exactly one question: **would this mislead a
learner?**

- **FAIL** — yes. Semantic drift or inversion, a hallucinated claim, a term
  rendered so wrongly it teaches a false concept, or raw-MT prose
  throughout. One misleading sentence is a FAIL.
- **MINOR_ISSUES** — no, but a native technical editor would still change
  something: a calque, stiff phrasing, an imperfect-but-recognizable term,
  inconsistent terminology within the page, a dropped qualifier.
- **PASS** — no, and nothing an editor would change.

Expect roughly **1.5–8% FAIL** (measured 1.5–7.6% across the de, ko, th and
id rounds) and a large MINOR share. If a round comes back with 15%+ FAIL,
the rubric is being misread — stop and report it rather than launching a
large fix wave. (This exact failure happened once: a he round came back at
18% because the rubric was misread, not because the translation was worse;
see `.claude/PROJECT_HANDOFF.md`.)

**PASS means "screened, no misleading defect found" — not "certified
clean."** Don't describe it as clean in your summary.

### 5. Gauge before fixing

Do not fix on trust. Bake the round's FAILs into the refutation workflow
and run it:

```bash
python3 translation/scripts/make-gauge-run.py \
  --records translation/reviews/opus-<SEED>-<HANDLE>.json --locale <LOCALE> \
  --out /tmp/gauge-<SEED>-wf.js
```

Then `Workflow({scriptPath: "/tmp/gauge-<SEED>-wf.js"})`. Two independent
Opus readers per FAIL try to **refute** it (default "refuted" when
uncertain) from the cited entries with two neighbours on each side, inline
in the prompt — not from the full pages; a third reads only when the two
disagree. A FAIL stands when the majority cannot refute it. The result
lists `stands` and `refuted`; on 2026-09-12 it reproduced the three-reader
gauge's verdicts on id at a third of the cost.

Report the gauge result to the user. Findings are usually real even when
the severity label is too harsh — remediate on the **finding**, not the
label.

**When two or more pages are flagged for the same sentence, check the
same sentence in the other locales before fixing.** Sampling finds
instances; comparing one span everywhere finds the class (a "software
development kit" rendered as "a programming language" turned out to be
eight locales, not three). Report it; the maintainer runs the cross-locale
sweep, since your PR touches one locale.

### 6. Run the fix wave

Fixes go through the **PO files**, never into a rendered page (a rendered
page is regenerated from the PO at the next build, so an edit there is
lost). The path reuses the translation pipeline: one batch per page, the
same `translate-locale` workflow, the same checker gate.

Build a fix spec — a JSON array, one entry per page worth fixing (surviving
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

It writes `translation/v2/work/<LOCALE>/fix-NNN-sonnet.json` and
`manifest-fix.json`. What travels per page is the `--mode`:

- **`targeted`** (default): a page with a FAIL verdict goes whole; any other
  page sends the entries the examples pin plus every entry that contains a
  word the reviewer's Terminology/Register corrections removed — the wrong
  term or pronoun that recurs across a page. Measured on th and id
  (2026-09-12): a whole-page wave copied 93% of its entries back unchanged,
  and this mode keeps 73–90% of the changes made outside the pinned entries
  at 23–40% of the entries (th: 3,489 entries in 98 batches instead of
  15,438 in 328). Small pages are packed together, each note prefixed with
  its page.
- **`page`**: every translated entry of every flagged page, the fixer
  copies the rest back verbatim. Use it when a locale's FAIL rate is high.
- **`flagged`**: the pinned entries alone, packed across pages, for
  entry-local defects with many flags (untranslated entries, reversions).

Every entry carries a `review` field saying why it is there.

> **`--prepare` wipes the work directory first.** It deletes every
> `fix-*.json` under `work/<LOCALE>/` before writing new ones, so running it
> while a wave is still filling destroys the batches that wave is reading.
> Finish and `--apply` the outstanding wave before preparing anything else
> for the same locale.

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
on record; never hand-edit the PO to force it. A batch that returns one
translation too few is discarded whole — correctly, since a dropped item
shifts every later one; redo it.

Read what `--apply` prints before going on:

- **The accepted count against the flagged count.** Fewer means flags did
  not reach the fixer or it declined them; more means it changed entries
  nobody reviewed. On a whole-page wave the second is often the fixer
  repairing more of a defect than the reviewer quoted; read them and decide.
- **Every `REPLACED BY ENGLISH` warning.** A fix wave sometimes overwrites a
  translated string with its English source, and it does so where no
  structural check can object: headings, `title=`, `description=` and
  `alt=` captions and table cells. `--apply` names each such entry and
  writes them all as a ready fix spec,
  `translation/v2/work/<LOCALE>/reversions.json`, pinned by entry with the
  previous translation as the suggestion. A filename or a citation
  *should* equal its source — delete those from the spec; everything else
  is a regression (ko 10, th 38, id 25: every one), so restore it:

  ```bash
  python3 translation/v2/fix.py --locale <LOCALE> \
    --fixes translation/v2/work/<LOCALE>/reversions.json --prepare --mode flagged
  # fill with the Workflow tool as above, then --apply again
  ```

### 7. Gate the result

All of these must pass before you commit:

```bash
python3 translation/scripts/lint-translation.py --locale <LOCALE>
python3 translation/scripts/check-known-mistranslations.py --locale <LOCALE>
python3 translation/scripts/check-wrong-language.py --locale <LOCALE>
python3 translation/scripts/audit-check-py.py --locale <LOCALE>
python3 translation/scripts/check-completeness.py --locale <LOCALE> --limit 0 \
  --baseline translation/eval/completeness-baseline.json
```

The last one, the **completeness ratchet**, fails on any finding that is
not in the baseline. Read each one it prints, against the entry's English:

- **A real loss** — a sentence the fix wave dropped, a question turned into
  an instruction, a caption back in English: repair it through `fix.py`
  (a spec with that entry and the previous translation as `suggested`,
  `--mode flagged`), apply, re-render, run the gates again.
- **A false alarm** — a line re-wrapped, a number the translation writes
  differently, a gloss the sieve miscounted: accept it into the baseline,
  then run the ratchet once more; it must say "no new findings".

```bash
python3 translation/scripts/check-completeness.py --all \
  --write-baseline translation/eval/completeness-baseline.json
```

Tell the user which findings you accepted and why. In the rounds of
2026-09-11/12 each locale had two or three: about half real.

The rendered pages under `i18n/<LOCALE>/…/current/` are derived from the
PO files and not in git. Run the gate on a fresh `render.py` output, and if
anything edited a rendered page directly, discard it: the PO files are the
only thing that ships.

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

That's the file `collect-opus-run.py` wrote in step 3. Then record the
verdicts where eligibility reads them — each reviewed page's PO header:

```bash
python3 translation/scripts/review-translations.py --record-opus \
  --from-json translation/reviews/opus-<SEED>-<HANDLE>.json --locale <LOCALE>
```

It writes `X-Doq-Review-Opus: <VERDICT> <date>` into the header of every
page the round read (PASS, MINOR_ISSUES or FAIL alike) and refuses records
for any other locale. It also marks every model-written entry stamped
*before* the round's date as verified — the reader saw it. The repairs your
own fix wave just wrote are stamped with today's date and stay pending, so
the next round on this locale picks those pages up in delta mode and reads
the repairs. The header change ships in your PR with the fixes; there is no
maintainer step after merge.

```bash
git checkout -b review/<LOCALE>-<SEED>
git add translation/reviews/opus-<SEED>-<HANDLE>.json
git add i18n/<LOCALE>/po           # the PO files only; nothing under …/current/
git status --short                 # exactly those paths, nothing else
git commit && gh pr create --repo JanLahmann/doQumentation
```

Show the user the `git status --short` output before committing. If the
completeness ratchet in step 7 needed `--write-baseline` for re-wrapped
lines, `translation/eval/completeness-baseline.json` is staged too; nothing
else ever is. Never `git add -f i18n/`.

When the user stops contributing to this locale — not after every round if
they plan another — close their claim issue, so the locale shows as free.

This is the whole reason contributor PRs never conflict: you touch only a
brand-new review file and your own locale's PO tree.

PR description should state: locale, seed, page count, the verdict tally,
the gauge result, and which pages you changed.

### Hard rules

- **Never** edit `docs/` — that's the English source of truth.
- **Never** edit a locale other than the one assigned.
- **Never** hand-edit a rendered page or a `.po` file; `fix.py --apply`
  writes translations and `review-translations.py --record-opus` writes
  verdicts. Nothing else touches a PO.
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

Across sessions the cache is gone. Recover the completed verdicts with
`collect-opus-run.py --run <runId>` (it reads the journal, last-wins per
`locale`+`file`), commit the reviews file as a safety net, and either ship
the partial round or draw a fresh sample with `--exclude-reviewed` to pick
up the rest.
A killed fix agent leaves at most an incomplete `fix-*.out.json`, which
`--apply` rejects as a whole (count mismatch); delete it and rerun that
batch.

A partial round is a perfectly good contribution. Ship what completed.
