# Contributing translations — start here

doQumentation ships **17 main locales** of IBM Quantum's Qiskit docs.
English content is synced from upstream; a translation goes **stale**
when its EN source changes after it was last translated. The work is
keeping stale files in sync — a continuous refresh, not one-time
translation.

> **You can use any tool or LLM** (Claude Code, Gemini, manual…). This
> file is the **coordination contract** — read it once. Detailed
> mechanics live in:
> - [`translation/retranslation-prompt.md`](translation/retranslation-prompt.md)
>   — the stale-refresh path you'll use 95% of the time, incl. the
>   **Orchestration recipe** (the exact batch→PR loop) and the
>   sub-agent prompt.
> - [`translation/translation-prompt.md`](translation/translation-prompt.md)
>   — whole-file / from-scratch path, incl. the **Language Table**
>   (each locale's informal-register rule — the source of truth for
>   register; do not duplicate it).
> - [`translation/review-prompt.md`](translation/review-prompt.md) —
>   linguistic review (Haiku is the validated review model).

> ⚠️ **Deprecated:** the old `translation/drafts/` → `promote-drafts.py`
> workflow is no longer used. The current pipeline edits `i18n/`
> directly via git-diff hunk-splice (below). Old flow is recoverable
> from git history if ever needed.

## Onboarding a new contributor (for maintainers)

Assign each person one or more **locales** (the unit of ownership).
Send them this message verbatim, filling in `<LOCALE>`:

> You're translating the **`<LOCALE>`** locale of doQumentation. It's
> yours exclusively — no one else will touch it, so you cannot cause
> merge conflicts.
>
> 1. In your worktree of the repo, read **`CONTRIBUTING-TRANSLATIONS.md`**
>    (repo root) — it is the whole contract: setup, the batch→PR loop,
>    and the hard rules.
> 2. Follow the **Orchestration recipe** in
>    `translation/retranslation-prompt.md` exactly. Use
>    `--locale <LOCALE>` everywhere.
> 3. Add yourself to the ownership table at the bottom of
>    `CONTRIBUTING-TRANSLATIONS.md` in your first PR.
>
> Do not translate any locale other than `<LOCALE>`. Do not run git or
> the pipeline scripts from inside a translation sub-agent. One branch →
> one PR per ~20-file batch.

Suggested split of the unclaimed locales (~240–360 stale files each;
hand out 1–3 per person by fluency/interest):

| Highest backlog | Mid | Lower |
|---|---|---|
| tl, th, he, id | ms, ja, ro, ar | cs, pt, pl, ko |

For AI-assisted contributors, emphasize verbally that the sub-agent
**scope + no-git** rule is the one that caused the worst incident here
(a 309-file manual recovery) — it is non-negotiable.

## The one rule that prevents all collisions: own whole locales

**Each contributor owns one or more locales, exclusively. Never touch a
locale someone else owns.** Every PR then modifies only a disjoint
`i18n/<your-locale>/` subtree → zero merge conflicts, no coordination
beyond claiming.

- Claim by adding yourself to the table at the bottom in your first PR.
- `translation/manifests/<locale>.json` is the source of truth for what
  is already finalized in a locale. No manifest = not started = free.
- **Owned / in progress:** `de` (complete), `es`, `fr`, `it`, `uk`.
  **Free to claim** (~240–360 stale files each): `ja, pt, ko, pl, cs,
  ro, tl, he, th, id, ms, ar`.
- The 9 German dialects (aut, bad, bar, bln, gsw, ksh, nds, sax, swg)
  are auto-handled — do **not** translate them unless asked.

## Setup (once)

```bash
git worktree add ../doq-<locale> -b i18n/<locale>-wip && cd ../doq-<locale>
python3 scripts/sync-content.py        # populates docs/ (EN, gitignored) if empty
```
Node 20+, Python 3.11+. No extra deps for the translation scripts.
`i18n/` and `docs/` are gitignored — stage with `git add -f`.

## The loop (per batch — one branch → one PR)

Follow the **Orchestration recipe** in
[`translation/retranslation-prompt.md`](translation/retranslation-prompt.md)
exactly. Per ~15–30-file batch:

```bash
LOC=<your-locale>
git checkout main && git pull && git checkout -b i18n/$LOC-batchN
python translation/scripts/update-translations.py --locale $LOC --auto-fix
python translation/scripts/update-translations.py --locale $LOC \
  --generate-workfile --output /tmp/$LOC-wf.json \
  --exclude-open-prs --skip-manifest-done          # parallel-safe + resumable
# → translate the workfile hunks: see retranslation-prompt.md §Step 2.
#   (each update.new_en is a unified diff; mirror it into the TR region.
#   update.current_translation, when non-empty, is the pre-located TR
#   region — edit THAT, don't read the whole file.)
python translation/scripts/update-translations.py --locale $LOC \
  --finalize --output /tmp/$LOC-wf.json            # the gate
# commit ONLY files that passed --finalize → open one PR
```

`--finalize` is the gate: a file is hash-bumped & committable only when
it passes **structural + content + MDX-fatal** checks. Failures stay
stale and are safely retried next batch — the manifest makes the whole
backlog resumable across people and sessions.

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

Add yourself here in your first PR so others see the locale is taken.

| Locale | Owner | Status |
|--------|-------|--------|
| de | core | complete |
| es, fr, it, uk | core | in progress |
| ja, pt, ko, pl, cs, ro, tl, he, th, id, ms, ar | *unclaimed* | not started |
