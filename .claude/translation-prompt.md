# Translation Prompt — doQumentation

Translates English MDX content to other languages using Claude Code CLI with parallel Sonnet Task agents.

**Model**: Sonnet (always — via `model: "sonnet"` in Task calls)
**Batch size**: 2 files per agent (max 3 for short files)
**Parallelism**: 10+ agents per round (launch as many as possible in a single message)

---

## Prompt Templates

Paste one of these into Claude Code:

```
Read .claude/translation-prompt.md. Translate all untranslated pages to French (fr).
```

```
Read .claude/translation-prompt.md. Translate all remaining guide pages to German (de). Skip already-translated files.
```

```
Read .claude/translation-prompt.md. Translate these files to Spanish (es): guides/install-qiskit.mdx, guides/hello-world.mdx
```

---

## How to Launch Translation Agents

When you have a list of files to translate, split them into groups of 2 and launch **all groups simultaneously** using parallel Task tool calls in a single message. Use `model: "sonnet"` and `subagent_type: "general-purpose"` for each agent.

Example: 20 files → 10 agents of 2 files each → all 10 launched in one message.

Each agent gets this prompt (with variables filled in):

```
You are a {LANGUAGE} translator for doQumentation (Docusaurus site for Qiskit quantum computing tutorials).

Translate these English MDX files to {LANGUAGE}:

Files (paths relative to docs/):
- {file1}
- {file2}

For EACH file:
1. Read the English source from `docs/{path}`
2. Translate following the rules below
3. Write the translation to `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{path}`

Rules:
- Preserve ALL frontmatter keys exactly — translate ONLY values of `title`, `description`, `sidebar_label`
- Preserve ALL code blocks, math/LaTeX, JSX components, imports, HTML tags, URLs, image paths, inline code backticks UNCHANGED
- Translate ONLY prose: paragraphs, headings, list items, admonition text content
- **Heading anchors**: When translating headings that are linked to within the same page, pin the original English anchor using Docusaurus syntax: `## Translated Heading {#original-english-anchor}`. This ensures internal `#anchor` links keep working. Example: `## Change ordering in Qiskit` → `## Reihenfolge in Qiskit ändern {#change-ordering-in-qiskit}`
- Keep standard quantum computing terms (Qubit, Gate, Circuit, Backend, Transpiler)
- Use {FORMAL_FORM}
- Write natural, fluent {LANGUAGE} — not word-for-word translation
- If the target file exists and contains `{/* doqumentation-untranslated-fallback */}`, it's a fallback — overwrite it completely
- If the target file exists WITHOUT that marker, it's already translated — SKIP it
```

---

## Autonomous Workflow

When NO explicit file list is given, discover files to translate:

### Step 1: Discover untranslated files

1. `Glob docs/**/*.mdx` → all English source files
2. `Glob i18n/{LOCALE}/docusaurus-plugin-content-docs/current/**/*.mdx` → existing locale files
3. For each existing locale file, Read and check:
   - Contains `{/* doqumentation-untranslated-fallback */}` → needs translation
   - Does NOT contain the marker → genuine translation, SKIP
   - File doesn't exist → needs translation
4. Build the list of files needing translation

### Step 2: Launch parallel agents

Split the file list into groups of 2. Launch 10+ Task agents in a **single message** (all parallel). Each agent uses `model: "sonnet"`.

Process in this order: tutorials → guides → courses → modules

### Step 3: After all agents complete

Report summary:
- Total files translated
- Files skipped (already translated)
- Any errors

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

## Adding a New Language — Checklist

When adding a new locale (e.g., `fr`), these files need translation beyond the MDX content pages:

### 1. Sidebar categories — `current.json`
`i18n/{LOCALE}/docusaurus-plugin-content-docs/current.json` — ~60 sidebar category/link labels. Generated with `npm run write-translations -- --locale {LOCALE}`, then translate all `"message"` values. Keep brand names (Qiskit, IBM Quantum, OpenQASM) and abbreviations (SQD, OBP, etc.) unchanged. Use `i18n/de/.../current.json` as reference.

### 2. UI strings — `code.json`
`i18n/{LOCALE}/code.json` — buttons, search placeholder, "Next"/"Previous", custom component text. Generated with `npm run write-translations -- --locale {LOCALE}`.

### 3. Navbar — `navbar.json`
`i18n/{LOCALE}/docusaurus-theme-classic/navbar.json` — navbar item labels.

### 4. Footer — `footer.json`
`i18n/{LOCALE}/docusaurus-theme-classic/footer.json` — footer column headers and links.

### 5. Banner template
Add a `{LOCALE}` entry to `BANNER_TEMPLATES` in `scripts/translate-content.py` (admonition with "not yet translated" message in the target language).

### 6. Config
Add locale to `locales` array and `localeConfigs` in `docusaurus.config.ts`. Add `language` entry in search plugin config (if `lunr-languages` supports it).

### 7. Git tracking
`current.json` is tracked normally. MDX content translations must be force-added: `git add -f i18n/{LOCALE}/docusaurus-plugin-content-docs/current/`.

## Current Translation State

| Locale | Pages | Status |
|--------|-------|--------|
| DE | 75/387 | 54 guides, 14 tutorials, 5 courses/modules, homepage, 2 indexes + UI strings |
| ES | 15/387 | 4 tutorials, 5 guides, 3 courses, 2 modules, homepage + UI strings |
| UK | 15/387 | Same pages as ES + UI strings |
| JA | 15/387 | Same pages as ES. **Disabled** (no UI strings). Not in `locales` array. |

## Agent Configuration Summary

| Setting | Value |
|---------|-------|
| Model | `sonnet` |
| Subagent type | `general-purpose` |
| Files per agent | 2 (max 3 for short files) |
| Parallel agents | 10+ per round |
| Rounds for full locale | ~19 rounds (371 files ÷ 2 per agent ÷ 10 agents) |
