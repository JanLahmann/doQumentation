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
- Launch at most 3 agents in parallel. Wait for all 3 before the next batch.
- Skip files where severity is `NOOP` — `--auto-fix` will handle them.
- For `MAJOR` severity (>100 lines changed or structural), translate the
  whole file fresh using `translation-prompt.md` instead.
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
3. Read i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{PATH}
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
- Keep byte-identical: code fences and content, math ($...$, $$...$$),
  URLs, image paths, imports, inline code backticks, JSX href=/value=/id=
  /analyticsName=/type=/className=, and other frontmatter keys
  (notebook_path, slug, platform).
- Keep terms: Qubit, Gate, Circuit, Backend, Transpiler, Session, Sampler,
  Estimator, PUB.
- Heading anchors: derive {#anchor} from the ENGLISH heading (lowercase,
  spaces→hyphens, ASCII only — no accents/non-Latin). If the existing
  {LANGUAGE} heading already has {#...}, and the English heading text did
  NOT change in the hunk, keep that exact anchor.
- Use {INFORMAL_FORM} register. Write fluent {LANGUAGE}.

NEVER do these (each caused a real validation failure):
- Do NOT add an `# H1` (or any heading) that is not present in the
  English source. Mirror the EN heading structure exactly — no more, no
  fewer.
- Do NOT leave a heading without its English-derived `{#anchor}`. Every
  heading in the file must carry one, even headings you did not change.
- Do NOT leave frontmatter `title:`/`sidebar_label:` in English when a
  hunk changed them.
- Do NOT translate or alter any code, math, URL, import, or JSX
  non-text attribute.

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

Re-run the agent on any `_finalize_failures.txt` entries (common slips:
missing `{#anchor}`, an added H1 not in EN, untranslated frontmatter
`title:`), then `--finalize` again until the failures file is empty.

## Workflow shape — weekly recipe

| Step | Time | Tool |
|---|---|---|
| `check-translation-freshness` | ~5 s | script |
| `update-translations --auto-fix` (structural) | ~30 s per locale | script |
| Generate workfiles for all 16 main locales | ~5 min | script |
| Sub-agent refresh (sonnet, 3 parallel) | depends on stale count | LLM |
| Re-validate per locale | ~10 s | script |
| Commit + open per-locale PR (or one mega-PR) | ~2 min | gh |

For a typical weekly sync (~30 stale files per locale): ~15 min CPU-time
per locale × 16 locales / 3-parallel batches = ~80 min wall-clock if run
fully sequential, or ~20 min if 4 locale orchestrators run in parallel
(matches the pattern from `translation-prompt.md`).

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
