# Re-translation Prompt — doQumentation (weekly STALE refresh)

Use with: `Read translation/retranslation-prompt.md. Refresh stale German translations.`

The language in the user message determines the target. Look up LOCALE and informal form from `translation-prompt.md` § Language Table.

> Designed for **stale-only updates**, not first-time translation. For new
> pages, use [`translation-prompt.md`](translation-prompt.md).
> Tool-agnostic contributor guide: [`CONTRIBUTING-TRANSLATIONS.md`](../CONTRIBUTING-TRANSLATIONS.md).

## When to use this prompt

A translation goes STALE whenever its EN source file changes after the
translation was promoted. This prompt updates only the **paragraphs that
changed** — preserving the existing translation's voice, terminology, and
unchanged sections.

Run weekly (or after each upstream sync) for each main locale:

```bash
python translation/scripts/check-translation-freshness.py --locale {LOCALE}
```

If that shows `N stale files`, proceed below.

## Constraints

- Use `model: "sonnet"` for all agents.
- Launch agents in waves of 3 (one file each); wait for each wave. See
  the **Orchestration recipe** below for the full batch→PR loop when
  scaling a backlog — follow it exactly.
- Skip files where severity is `NOOP` — `--auto-fix` will handle them.
- For `MAJOR` severity / `full_retranslation` (no historical EN, or a
  large/structural rewrite), translate the whole file fresh using
  `translation-prompt.md` instead — do not hunk-splice it.
- Do NOT translate the German dialects (aut, bad, bar, bln, gsw, ksh, nds,
  sax, swg) unless explicitly asked.

## Step 1 — Discover and auto-fix

From the repo root:

```bash
# Apply auto-fixes (code blocks, imports, links, images, JSX, source-hash):
python translation/scripts/update-translations.py --locale {LOCALE} --auto-fix

# Generate the workfile that lists per-paragraph updates needed:
python translation/scripts/update-translations.py --locale {LOCALE} --generate-workfile --output /tmp/{LOCALE}-workfile.json
```

The auto-fix pass handles structural drift (code, imports). The workfile
then describes the exact EN change per file: each `update.new_en` is a
unified-diff hunk (old EN → current EN). Files where the EN did not change
(only whitespace/code drift) are NOOP and absent from the workfile —
their source hash is bumped automatically. Files with no historical EN
(new/renamed) or a very large change are listed under `full_retranslation`
— do those with `translation-prompt.md`, not this prompt.

Read the workfile summary:

```bash
python3 -c "
import json
wf = json.load(open('/tmp/{LOCALE}-workfile.json'))
print(f'Files needing hunk-splice: {len(wf[\"files\"])}')
print(f'Full retranslation (use translation-prompt.md): {len(wf.get(\"full_retranslation\", []))}')
for f in wf['files']:
    print(f'  {f[\"severity\"]:<10} {len(f[\"updates\"]):>3} hunk(s)  {f[\"path\"]}')
"
```

If there are more than 50 files, slice to the top N by severity or
hunk-count and do them first.

## Step 2 — Per-file refresh

For each file in the workfile, launch a sub-agent with this prompt:

```
You are a {LANGUAGE} translator for doQumentation. Update a STALE translation.

The workfile gives you the EXACT English diff — old EN vs current EN — for
this file. Your job: mirror that same change into the {LANGUAGE} file.

1. Read /path/to/{LOCALE}-workfile.json
2. Find the entry for file path `{PATH}`
3. TOKEN-EFFICIENT READING (do this, it matters):
   - If every `update` for this file has a non-empty
     `current_translation`, that field already contains the exact
     translated region (±~18 lines) around where the hunk applies. Use
     it to make a **targeted `Read` with offset/limit of just that
     region** and Edit there. Do NOT read the whole locale file.
   - Only if an `update.current_translation` is empty (region not
     pre-located) do you read more of
     `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{PATH}` —
     and even then read just enough to find that hunk's region (use
     offset/limit around its context anchors), not the entire file.
   - Whole-file reads are the single biggest token cost; avoid them.
4. Each `update.new_en` is a unified-diff HUNK of the English source:
   - `@@ -a,b +c,d @@` header — ignore, just positional
   - lines starting `-` were REMOVED from the old English
   - lines starting `+` were ADDED in the current English
   - unchanged context lines start with a space
   For each hunk:
   a. The `-` lines are the OLD English. Find the {LANGUAGE} text in the
      locale file that is the translation of those old English lines
      (use the surrounding context lines to locate the region precisely).
   b. Rewrite that {LANGUAGE} region so it is a faithful translation of
      the `+` lines (the new English), keeping every unchanged context
      line's translation as-is.
   c. If the hunk only adds lines (no `-`), insert the {LANGUAGE}
      translation of the `+` lines at the matching position.
   d. If the hunk only removes lines, delete the corresponding
      {LANGUAGE} text.
   e. IMAGE / COMPONENT REMOVAL: if a `-` line is an image
      (`![...](...)`) or an `<Image .../>`, `<Figure .../>`, etc., that
      removal is REAL — DELETE the corresponding image line in the
      {LANGUAGE} file. Do NOT keep it just because images are otherwise
      "byte-identical": byte-identical applies to images that STAY, not
      to ones the diff removes. Likewise an added `-`→`+` image swap
      (e.g. `foo.avif` → `foo.svg`) must be applied. Mismatched image
      counts vs EN fail validation, so the EN image count must end up
      exactly mirrored.
5. Use the Edit tool (not Write) per hunk so untouched regions stay byte-
   identical. Do NOT touch the {/* doqumentation-source-hash: ... */}
   marker — it is bumped by the finalize step.

Translation rules:
- Preserve the existing translator's voice/terminology in unchanged text;
  only the diffed region changes.
- Structural changes in the hunk are REAL: if `+` lines add a <CardGroup>,
  a heading, an <Admonition>, or a `:::note` block (or remove one),
  reproduce that structure in {LANGUAGE} exactly — same components, same
  nesting, same count. This is why we diff: the change may be structural,
  not just prose.
- Translate: prose, headings, list items, blockquotes, table cells,
  admonition text and title= props, <summary>/<details> text, JSX label=
  and description= and title= props, AND frontmatter `title:` and
  `sidebar_label:` (these ARE translatable — if a hunk changes them,
  translate the new value into {LANGUAGE}; do not leave them in English).
- Keep byte-identical (for elements that REMAIN — this does not block
  applying a hunk that removes/changes one): code fences and content,
  math ($...$, $$...$$), URLs, image paths, imports, inline code
  backticks, JSX href=/value=/id=/analyticsName=/type=/className=, and
  other frontmatter keys (notebook_path, slug, platform). "Byte-identical"
  means: don't translate or reword them — NOT "never delete one the diff
  deletes." A removed/swapped image, URL, or import in the diff must be
  removed/swapped in the translation too.
- Keep terms: Qubit, Gate, Circuit, Backend, Transpiler, Session, Sampler,
  Estimator, PUB.
- Heading anchors: derive {#anchor} from the ENGLISH heading (lowercase,
  spaces→hyphens, ASCII only — no accents/non-Latin). If the existing
  {LANGUAGE} heading already has {#...}, and the English heading text did
  NOT change in the hunk, keep that exact anchor.
- Use {INFORMAL_FORM} register. Write fluent {LANGUAGE}.

NEVER do these (each caused a real validation failure):
- HARD SCOPE: edit ONLY the exact files in your assigned list. Do NOT
  read-then-edit, auto-fix, "while I'm here" touch, or batch-process ANY
  file outside that list — not even other stale files in the same
  locale. Your list is exhaustive; the orchestrator owns everything else.
- NO GIT, NO TOOLS BEYOND Read/Edit: never run `git` (no add, commit,
  branch, checkout, reset, stash), never run the pipeline scripts
  (`update-translations.py`, `fix-tutorialfeedback-import.py`,
  `--auto-fix`, `--finalize`), never run shell. You ONLY Read and Edit
  the assigned `.mdx` files. Committing and finalizing are exclusively
  the orchestrator's job, AFTER the dual-gate. An agent that commits or
  runs scripts corrupts the batch (this happened: an agent re-translated
  309 files and `git commit`-ed onto main — full manual recovery).
- Do NOT add an `# H1` (or any heading) that is not present in the
  English source. Mirror the EN heading structure exactly — no more, no
  fewer.
- Do NOT leave a heading without its English-derived `{#anchor}`. Every
  heading in the file must carry one, even headings you did not change.
- Do NOT leave frontmatter `title:`/`sidebar_label:` in English when a
  hunk changed them.
- Do NOT translate or alter any code, math, URL, import, or JSX
  non-text attribute.
- Do NOT skip an image (or `<Image/>`/`<Figure/>`) that a `-` hunk
  removes, or a `foo.avif`→`foo.svg`-style image swap. The translation's
  image count and paths must end up exactly matching current EN —
  un-applied image-removal hunks are a recurring "Image paths count
  mismatch" validation failure.

Conservative no-op: if a hunk's English change is purely cosmetic
(capitalization, punctuation moved, whitespace, a link's trailing
period repositioned) and the existing {LANGUAGE} text is already a
correct translation, make NO edit for that hunk and note it briefly.
Minimise change is the goal — never rewrite a correct paragraph for a
cosmetic English-only delta.

After all edits, respond with ONLY "Done", or "Done — no-op: <reason>"
when every hunk was cosmetic, or a brief error.
```

Fill in `{PATH}`, `{LANGUAGE}`, `{LOCALE}`, `{INFORMAL_FORM}` per the
language table in `translation-prompt.md`.

## Step 3 — Finalize + commit

One command does the whole gate per file: pin English-derived heading
anchors → validate → bump the source hash **only if validation passes**.
Files that fail are written to `_finalize_failures.txt` (next to the
workfile) for rework — they are NOT hash-bumped, so they stay flagged
STALE until fixed instead of silently shipping broken.

```bash
python translation/scripts/update-translations.py --locale {LOCALE} --finalize \
  --output /tmp/{LOCALE}-workfile.json -v
```

Then commit ONLY the files that passed (never force-add gitignored
binaries — stage the `.mdx` paths explicitly):

```bash
# inspect failures, if any:
cat /tmp/_finalize_failures.txt 2>/dev/null   # <rel-path>\t<reason>

# stage exactly the passed .mdx files (example: all changed mdx under the locale)
git add -f $(git status --short \
  i18n/{LOCALE}/docusaurus-plugin-content-docs/current/ \
  | awk '/^ M / && /\.mdx$/ {print $2}')
git commit -m "i18n({LOCALE}): refresh N stale translations via git-diff pipeline"
```

`--finalize` gates on **two** things, not just structure:
- **Structural** validation (validate-translation): heading/JSX/code/link
  parity with EN.
- **Content** (the zero-edit guard): for every non-cosmetic removed-EN
  line in the diff, that exact old English must NOT still be present in
  the translation. An agent can answer "Done" yet silently skip a hunk
  (fail to locate the region); the file then passes structurally but is
  still STALE — bumping its hash would lock the staleness in forever.
  Such files are rejected as `CONTENT: old EN still present (hunk not
  applied)` and NOT hash-bumped.

Re-run the agent on any `_finalize_failures.txt` entries (common slips:
missing `{#anchor}`, an added H1 not in EN, untranslated frontmatter
`title:`, or a `CONTENT:` row = a hunk the agent claimed done but never
applied), then `--finalize` again until the failures file is empty. A
file is only committed once it passes BOTH gates.

## Orchestration recipe (scaling a backlog)

Battle-tested on a ~300-file backlog. Follow this exactly — every rule
below maps to a real failure that happened without it.

**Per batch (one branch → one PR):**

1. **Branch from fresh `main`.** `git checkout main && git pull && git
   checkout -b i18n/{LOCALE}-refresh-N`. Each batch is its own branch/PR.
2. **Pick ~25–30 files.** Bigger batches make review and conflict
   recovery harder.
3. **Build the workfiles** with `--auto-fix` then `--generate-workfile`
   per file, **with `--exclude-open-prs --skip-manifest-done`**. This is
   not optional: an unmerged PR's files still read STALE (freshness
   checks `i18n/` on disk), so without the exclusion you re-translate
   files already in another open PR and get rebase conflicts (this
   happened — batch had to be rebased with `git checkout --theirs` on
   the dup files). The manifest skip makes multi-session scaling
   resumable.
4. **Skip MAJOR / `full_retranslation`.** Those are whole-file jobs for
   `translation-prompt.md`, not hunk-splice. Note them; don't mix.
5. **Dispatch sub-agents in waves of 3** (Sonnet, one file each). Wait
   for each wave before the next. Larger fan-out works but 3 keeps
   failures isolated and reviewable.
6. **`--finalize`** the batch (Step 3). It anchors + dual-gates +
   hash-bumps + writes the manifest and `_finalize_failures.txt`.
7. **Commit ONLY passing `.mdx`** (the Step-3 `git add` one-liner —
   never `git add -f` a whole directory; that force-adds gitignored
   binaries, which happened and had to be reverted).
8. **One PR per batch.** Don't wait for merge to start the next batch —
   `--exclude-open-prs` makes parallel batches safe.
9. **Rework the failures file**, re-`--finalize`, until empty, before
   the PR is considered done (or split failures into a follow-up PR and
   note it).

**Timing:** ~30 stale files/locale typical weekly sync. One batch ≈
10–15 min wall-clock (3-wide waves). 16 locales is mechanical and
resumable via the manifest — it does not need to be one sitting.

**Merge-order gotcha:** batches branched from different `main` states
that force-add overlapping `i18n/` paths can rebase-conflict on shared
files. Resolve with `git checkout --theirs <dup>` (take the
already-merged version — they're equivalent translations of the same EN
diff) then `git rebase --continue`. `--exclude-open-prs` prevents this
when used from the start.

## What to do for severity = MAJOR

If a file's diff is >100 lines or structural (added/removed sections,
component changes), `update-translations.py` flags it MAJOR. For those:

1. Don't try to patch paragraph-by-paragraph.
2. Translate the whole file fresh using `translation-prompt.md`.
3. Promote via `promote-drafts.py` as usual.

A small batch of MAJOR-severity files per sync is normal. Don't let it
accumulate — they're the highest-impact pages.

## Skipping the German dialects

The 9 German dialects (aut, bad, bar, bln, gsw, ksh, nds, sax, swg) are
intentionally not refreshed weekly. Their fallback EN content is updated
automatically on every locale build via `populate-locale`.

If you do want to refresh a dialect (e.g. for a release milestone), use
this same prompt with the dialect's locale code.
