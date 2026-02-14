# Translation Prompt — doQumentation

Translates English MDX content to other languages. Works with:
- **Claude Code CLI** — parallel Task agents (Sonnet), 7 files per agent, 3 agents per round
- **Claude Code Web** (claude.ai/code) — autonomous file discovery, sequential processing

---

## Prompt Templates

Paste one of these into Claude Code (CLI or Web):

```
Read .claude/translation-prompt.md. Translate all untranslated pages to French (fr). Use parallel Task agents if available.
```

```
Read .claude/translation-prompt.md. Translate all remaining guide pages to German (de). Skip already-translated files.
```

```
Read .claude/translation-prompt.md. Translate these files to Spanish (es): guides/install-qiskit.mdx, guides/hello-world.mdx
```

---

## Translation Agent Instructions

You are a {LANGUAGE} translator for the doQumentation project (Docusaurus site for Qiskit quantum computing tutorials).

Your task: Translate English MDX files to {LANGUAGE}. For EACH file:
1. Read the English source from `docs/{path}`
2. Write the {LANGUAGE} translation to `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{path}`

### Critical Rules

- Use the Read tool to read files and the Write tool to write files. Do NOT use Bash for file operations.
- The target directory may already contain a file with English content and a `{/* doqumentation-untranslated-fallback */}` marker — these are FALLBACKS, not translations. Overwrite them completely.
- Preserve ALL frontmatter keys exactly — translate ONLY the values of `title`, `description`, and `sidebar_label`
- Preserve ALL code blocks (` ```python `, ` ```bash `, ` ```text `, etc.) completely unchanged
- Preserve ALL math/LaTeX (`$...$`, `$$...$$`) completely unchanged
- Preserve ALL JSX components, imports, and HTML tags unchanged (e.g., `<Admonition>`, `<Tabs>`, `<OpenInLabBanner>`)
- Preserve ALL URLs/links unchanged
- Preserve ALL image paths unchanged
- Preserve ALL inline code backticks unchanged (e.g., `Statevector`, `QuantumCircuit`, `numpy`)
- Translate ONLY the prose/explanatory text: markdown paragraphs, headings, list items, admonition text content
- Keep technical terms that are standard in {LANGUAGE} quantum computing (e.g., Qubit, Gate, Circuit, Backend, Transpiler)
- Use {FORMAL_FORM}
- Write natural, fluent {LANGUAGE} — not word-for-word translation

### When a file list is provided

```
Files to translate (paths relative to docs/):
{FILE_LIST}
```

Process each file one at a time: Read English → Write {LANGUAGE} translation. Do all files.

---

## Autonomous Workflow (Claude Code Web)

When running in Claude Code Web with NO explicit file list, follow this workflow:

### Step 1: Discover untranslated files

```
1. Glob docs/**/*.mdx → all English source files
2. Glob i18n/{LOCALE}/docusaurus-plugin-content-docs/current/**/*.mdx → existing locale files
3. For each existing locale file, Read it and check:
   - If it does NOT contain "{/* doqumentation-untranslated-fallback */}" → genuine translation, SKIP
   - If it contains the marker OR doesn't exist → needs translation
4. Build the list of files needing translation
```

### Step 2: Translate

Process files in this order: tutorials → guides → courses → modules

For each file:
1. Read the English source from `docs/{path}`
2. Translate following the Critical Rules above
3. Write to `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{path}`
4. Report progress: "Translated X/Y: {path}"

### Step 3: Use parallel agents if available

If Task agents are available (Claude Code CLI), split the file list into groups of 7 and launch 3 parallel agents per round. Each agent gets a subset of files and these same instructions.

If Task agents are NOT available (Claude Code Web), process files sequentially.

### Step 4: After translation

Report summary:
- Total files translated
- Files skipped (already translated)
- Any files that could not be translated (errors)

Remind the user to run:
```bash
python scripts/translate-content.py populate-locale --locale {LOCALE}
git add -f i18n/{LOCALE}/docusaurus-plugin-content-docs/current/
```

---

## Variable Reference

| Variable | DE | JA | UK | ES | FR | IT | PT | TL | TH |
|---|---|---|---|---|---|---|---|---|---|
| LOCALE | de | ja | uk | es | fr | it | pt | tl | th |
| LANGUAGE | German | Japanese | Ukrainian | Spanish | French | Italian | Portuguese | Tagalog/Filipino | Thai |
| FORMAL_FORM | formal ("Sie" not "du") | polite (です/ます form) | formal ("Ви" not "ти") | formal ("usted" not "tú") | formal ("vous" not "tu") | formal ("Lei" not "tu") | formal ("você" formal) | formal ("po/opo" forms) | polite (ครับ/ค่ะ forms) |

**New locales**: Before using `populate-locale` for a new locale, ensure its banner template exists in `BANNER_TEMPLATES` dict in `scripts/translate-content.py`. Currently defined: de, ja, uk, es, fr, it, pt, tl, th.

## Current Translation State

| Locale | Pages | Status |
|--------|-------|--------|
| DE | 75/387 | 54 guides, 14 tutorials, 5 courses/modules, homepage, 2 indexes + UI strings |
| ES | 15/387 | 4 tutorials, 5 guides, 3 courses, 2 modules, homepage + UI strings |
| UK | 15/387 | Same pages as ES + UI strings |
| JA | 15/387 | Same pages as ES. **Disabled** (no UI strings). Not in `locales` array. |

## Batch Size (CLI Task Agents)

- 7 files per agent (20 was too large for context window)
- 3 parallel agents per round
- ~53 rounds for full site (~371 remaining pages per locale)
