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

The auto-fix pass handles structural drift (code, imports, links) without
touching prose. After it runs, the workfile contains only paragraphs that
need real translator attention.

Read the workfile summary:

```bash
python3 -c "
import json
wf = json.load(open('/tmp/{LOCALE}-workfile.json'))
print(f'Total stale files: {len(wf[\"files\"])}')
for f in wf['files']:
    print(f'  {f[\"severity\"]:<10} {len(f[\"updates\"]):>3} updates  {f[\"path\"]}')
"
```

If there are more than 50 files, slice to the top N by severity or
update-count and do them first.

## Step 2 — Per-file refresh

For each file in the workfile, launch a sub-agent with this prompt:

```
You are a {LANGUAGE} translator for doQumentation. Update a STALE translation.

1. Read /path/to/{LOCALE}-workfile.json (above)
2. Find the entry for file path `{PATH}`
3. Read i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{PATH}
4. For each `update` in the workfile entry:
   - Locate the matching `current_translation` in the locale file
   - Replace it with a fresh translation of `new_en`
   - Preserve the surrounding context byte-identically
5. Use the Edit tool (not Write) for each replacement so other paragraphs stay untouched.
6. After all updates, the file's source-hash marker will be auto-bumped by
   the `--auto-fix` pass — don't change it yourself.

Translation rules:
- Match the voice and terminology of `current_translation` where possible
  (the existing translator's style is established; minimise change).
- Translate ONLY: prose paragraphs, headings, list items, blockquotes,
  table cells, admonition text and title= props, <summary>/<details>
  text, JSX label= props.
- Keep byte-identical: code fences and content, math ($...$, $$...$$),
  URLs, image paths, imports, inline code backticks.
- Keep terms: Qubit, Gate, Circuit, Backend, Transpiler, Session, Sampler,
  Estimator, PUB.
- Pin heading anchors: derive from the ENGLISH heading. ASCII slug only —
  no accented characters, no non-Latin characters.
- Use {INFORMAL_FORM} register. Write fluent {LANGUAGE}.

After all edits, respond with ONLY "Done" or a brief error.
```

Fill in `{PATH}`, `{LANGUAGE}`, `{LOCALE}`, `{INFORMAL_FORM}` per the
language table in `translation-prompt.md`.

## Step 3 — Validate + commit

```bash
# Re-validate (drift severity should drop to NOOP for all touched files):
python translation/scripts/check-translation-freshness.py --locale {LOCALE}

# Run the standard validation gate too:
python translation/scripts/validate-translation.py --locale {LOCALE}

# If failures appear, look at translation/scripts/fix-heading-anchors.py
# and translation/scripts/sync-translations.py — both are idempotent.
```

Stage and commit per locale:

```bash
git add -f i18n/{LOCALE}/docusaurus-plugin-content-docs/current/
git add translation/status.json translation/baseline-hashes.json
git commit -m "i18n({LOCALE}): refresh N stale translations after upstream sync"
```

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
