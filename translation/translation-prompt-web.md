# Translation Prompt — Claude Code Web Session

Use with: `Read translation/translation-prompt-web.md. Continue translations to Hebrew.`

The language in the user message determines the target. This prompt is self-contained — do NOT read translation-prompt.md.

## Language Table

| Language | LOCALE | Informal form |
|----------|--------|---------------|
| German | de | "du" not "Sie" |
| Spanish | es | "tú" not "usted" |
| French | fr | "tu" not "vous" |
| Italian | it | "tu" not "Lei" |
| Ukrainian | uk | "ти" not "Ви" |
| Japanese | ja | polite (です/ます) but not overly formal |
| Portuguese | pt | "você" casual |
| Filipino | tl | casual (no po/opo) |
| Arabic | ar | informal register |
| Hebrew | he | informal register |
| Thai | th | casual (no ครับ/ค่ะ) |
| Malay | ms | casual |
| Indonesian | id | casual |

Look up the LOCALE and informal form from this table based on the language the user specified.

## Constraints

- Translate at most 20 files per session. Stop after 20 and report progress.
- Launch at most 3 agents in parallel. Wait for all 3 to finish before the next batch.
- If an agent fails or times out, skip that file and move on.

## Step 1 — Setup

All three commands are required. The docs/ directory is not in git — it is generated:

```bash
git pull && git submodule update --init && python scripts/sync-content.py
ls docs/tutorials/ docs/guides/ docs/learning/courses/ docs/learning/modules/
```

If any directory is missing, stop — setup failed.

Create draft output directories so agents can write directly:
```bash
mkdir -p translation/drafts/{LOCALE}/tutorials translation/drafts/{LOCALE}/guides translation/drafts/{LOCALE}/learning/courses translation/drafts/{LOCALE}/learning/modules
```

## Step 2 — Discover files to translate

```bash
python translation/scripts/translation-status.py --locale LOCALE --backlog --limit 20
```

This prints at most 20 untranslated file paths in priority order (tutorials → guides → courses → modules). These are the files to translate this session.

Source file paths (courses and modules are nested — not top-level):
- Tutorials: `docs/tutorials/{file}.mdx`
- Guides: `docs/guides/{file}.mdx`
- Courses: `docs/learning/courses/{course}/{section}/{file}.mdx`
- Modules: `docs/learning/modules/{module}/{file}.mdx`

Print: "Translating up to 20 of N remaining files."

## Step 3 — Prepare

Before launching agents, for each file from the backlog:
1. Compute its source hash: `python3 -c "import hashlib; print(hashlib.sha256(open('docs/{path}').read().encode()).hexdigest()[:8])"`
2. Create the output directory: `mkdir -p translation/drafts/{LOCALE}/$(dirname {path})`

Do this in a single batch so agents only need to read and write.

## Step 4 — Translate

For each file, launch a Sonnet agent. The agent only needs to read and write — no hash computation, no mkdir. Up to 3 agents in parallel.

Agent prompt (fill in {path}, {LANGUAGE}, {LOCALE}, {HASH}, {INFORMAL_FORM} before launching):

```
You are a {LANGUAGE} translator for doQumentation.

1. Use the Read tool to read `docs/{path}`
2. Translate the content to {LANGUAGE}
3. Use the Write tool to write the translation to `translation/drafts/{LOCALE}/{path}`

Rules:
- Use the Read tool and Write tool. Do NOT use Bash for file operations.
- After frontmatter closing ---, add: {/* doqumentation-source-hash: {HASH} */}
- Translate title/description/sidebar_label in frontmatter only. Keep all other keys.
- Preserve ALL code blocks, math, JSX tags, imports, URLs, images byte-identical.
- Pin headings with anchors: ## Translated Heading {#original-english-anchor}
- Keep terms: Qubit, Gate, Circuit, Backend, Transpiler
- Use {INFORMAL_FORM} register. Write fluent {LANGUAGE}.
- After writing, respond with ONLY "Done" or a brief error if something failed. No summaries, no translation decisions.
```

Files >600 lines: split at `## ` headings into ~400-line chunks BEFORE launching agents. One agent per chunk writing to `{filename}-part{N}.mdx`. Concatenate in order after all finish. Delete part files.

After each batch of 3: `✓ file1, file2, file3 — done/total`

After every 10 files:
```bash
git add translation/drafts/{LOCALE}/
git commit -m "feat(i18n): add {LANGUAGE} translation drafts"
```

## Step 5 — Summary

After finishing or reaching 20 files, print:
- Files translated, skipped, failed
- Files remaining (total from step 2)
