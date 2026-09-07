# Contributing translations — start here

doQumentation ships **17 main locales** of IBM Quantum's Qiskit docs.
English content is synced from upstream; a translation goes **stale**
when its EN source changes after it was last translated. The work is
keeping stale segments in sync — a continuous refresh, not one-time
translation.

Since September 2026 a locale's translation is its PO files under
`i18n/<LOCALE>/po/` (one per page, one entry per paragraph); the pages
Docusaurus builds are rendered from them and are **not in git**. The
pipeline, its tools and the sync procedure are documented in
[`translation/v2/README.md`](translation/v2/README.md) — read it once.

> 👀 **Want to *review* rather than translate?** See
> [`CONTRIBUTING-REVIEWS.md`](CONTRIBUTING-REVIEWS.md) — a self-contained,
> budget-shaped recipe for running a deep review round of one locale with
> Claude Code. Good for spare tokens at the end of a weekly budget.

> **You can use any tool or LLM** (Claude Code, Gemini, manual…). This
> file is the **coordination contract** — read it once. Detailed
> mechanics live in:
> - [`translation/v2/README.md`](translation/v2/README.md) — the pipeline:
>   how a page becomes PO entries, the sync procedure (the exact
>   update → prepare → translate → apply → render loop), the checker's
>   rules and the known agent failure modes.
> - [`translation/translation-prompt.md`](translation/translation-prompt.md)
>   — the **Language Table** (each locale's informal-register rule — the
>   source of truth for register; do not duplicate it). `translate.py
>   --prepare` inlines it into every batch's instructions.
> - [`translation/review-prompt.md`](translation/review-prompt.md) —
>   linguistic review (Haiku is the validated review model).

> ⚠️ **Deprecated:** the older file-based pipelines (`translation/drafts/`
> → `promote-drafts.py`, and the git-diff hunk-splice
> `update-translations.py`) were removed when v2 landed. They are
> recoverable from git history if ever needed.

## Onboarding a new contributor (for maintainers)

Send them this, filling in `<LOCALE>`:

> Fork <https://github.com/JanLahmann/doQumentation>, clone your fork,
> open Claude Code in it and say: **"I want to help translating
> `<LOCALE>`. What should I do?"** The repo's `CLAUDE.md` takes it from
> there: it checks your fork, your claim and your toolchain, then runs
> the sync for that one locale.

For AI-assisted contributors, emphasize verbally that the sub-agent
**scope + no-git** rule is the one that caused the worst incident here
(a 309-file manual recovery) — it is non-negotiable.

**When is there work?** A locale has translation work only after an
upstream English sync lands (a merged "sync: upstream content" PR).
Between syncs every locale is current and `translate.py --prepare` reports
nothing to do; that is the moment to do a review round instead
(`CONTRIBUTING-REVIEWS.md`). `CONTRIBUTING-NOW.md` says which it is today.

## The one rule that prevents all collisions: own whole locales

**Each contributor owns one or more locales, exclusively. Never touch a
locale someone else owns.** Every PR then modifies only a disjoint
`i18n/<your-locale>/po/` subtree → zero merge conflicts, no coordination
beyond claiming.

- **Claim = one open GitHub issue** labelled `translation-claim`, opened
  with the *Claim a locale* template (`gh issue list --repo
  JanLahmann/doQumentation --label translation-claim` lists them; so does
  `CONTRIBUTING-NOW.md`). Close it when you stop.
- No claim = free. The locale's own state (what is translated, what is
  fuzzy) is in its PO files; `update.py --locale X` prints the worklist.

## Setup (once)

```bash
# point at upstream once, so `git pull` can never mean "my own stale fork"
git remote add upstream https://github.com/JanLahmann/doQumentation.git
git worktree add ../doq-<locale> -b i18n/<locale>-wip && cd ../doq-<locale>
# docs/ (the English) is tracked in git; nothing to generate for it.
```
Node 20+, Python 3.11+, and for the v2 pipeline po4a ≥ 0.74, GNU gettext
and the `polib` package (`brew install po4a gettext` / `apt-get install
po4a gettext`, `pip install polib`; see `translation/v2/README.md`,
*Dependencies*). The rendered pages under `i18n/<LOCALE>/…/current/` are
gitignored and derived: commit `i18n/<LOCALE>/po/`, never the rendered MDX.

## The loop (per batch — one branch → one PR)

Follow **Running a sync** in
[`translation/v2/README.md`](translation/v2/README.md) exactly. A locale is
one branch → one PR:

```bash
LOC=<your-locale>
# Sync from UPSTREAM, not origin: on a fork `git pull` fetches your own copy,
# which is stale the moment anyone else's batch merges. Branch from that and
# you will re-translate segments already done and hit conflicts at PR time.
git checkout main && git fetch upstream main && git merge --ff-only upstream/main
git push origin main                     # keep the fork's main current too
git checkout -b i18n/$LOC-sync
python3 translation/v2/update.py --locale $LOC --init-missing \
  --json translation/v2/work/worklist-$LOC.json   # msgmerge; seed new pages
python3 translation/v2/translate.py --locale $LOC --sweep        # once per locale
python3 translation/v2/update.py --locale $LOC --json translation/v2/work/worklist-$LOC.json
python3 translation/v2/translate.py --locale $LOC --prepare      # tiers + batches
# → fill work/$LOC/batch-*.out.json: the translate-locale workflow
#   (.claude/workflows/translate-locale.js, args = work/$LOC/manifest.json),
#   or any agent/API/human that writes a JSON list of strings per batch
python3 translation/v2/translate.py --locale $LOC --apply        # the gate
python3 translation/v2/render.py --locale $LOC
find i18n/$LOC/docusaurus-plugin-content-docs/current -name '*.mdx' -print0 \
  | xargs -0 node translation/v2/mdxcheck.mjs
python3 translation/scripts/lint-translation.py --locale $LOC
git add i18n/$LOC/po && git commit                               # PO files only
```

`--apply` is the gate: an entry is written only when it passes every
check in `translation/v2/check.py` (code spans, URLs, math, tags, anchors,
length); rejected entries go back on the worklist and are redone in a
second round or by hand. Nothing partial is ever written.

## Hard rules — each maps to a real incident; do not relitigate

- **Byte-identical to EN:** code, code comments, anything inside a
  ` ``` ` fence, math, URLs, imports, image paths, inline-code, JSX
  non-text attrs. Never translate them. The validator enforces it.
- **Translation sub-agents only Read/Edit their explicitly assigned
  files.** Never run `git`, the pipeline scripts, or shell from a
  sub-agent; never touch an unassigned file ("while I'm here"). Commit
  & `--finalize` are the orchestrator's job. *(An agent that
  `git commit`-ed once forced a 309-file manual recovery.)*
- **MDX is strict and aborts the whole locale build on:** an
  `import`/`export` directly adjacent to a `{...}`/`<...>` line (need a
  blank line after the import); a bare Python-style `import numpy` at
  document level. `--finalize` now gates both.
- **Stage exactly your intended set.** Write file lists
  NUL-terminated, stage via `xargs -0` (a `while read` loop drops the
  last path), and assert staged-set == intended-set before every
  commit.
- **Mirror EN structure exactly:** same headings (every one carries an
  English-derived `{#anchor}`), same image count/paths, no extra `# H1`
  the EN lacks.
- **Informal register** per your locale — see the Language Table in
  `translation/translation-prompt.md` (don't restate it here; it drifts).
- **One locale per contributor.** This is what makes parallel work
  conflict-free.

## Quality bar

Every finalized file passes `validate-translation.py` (structural
parity vs EN) **and** the `--finalize` content + MDX-fatal gates. For
linguistic spot-checks use
[`translation/review-prompt.md`](translation/review-prompt.md).

## Contributor / locale ownership

Ownership is not recorded in this file (a table here went stale within
weeks and told people `de` was complete while it was 38% reviewed). The
open claim issues are the record; `CONTRIBUTING-NOW.md` mirrors them
daily.
