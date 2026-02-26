# Translation Prompt — doQumentation

Translates English MDX content to other languages using Claude Code CLI with parallel Sonnet Task agents.

**Model**: Sonnet (always — via `model: "sonnet"` in Task calls)
**Batch size**: 1 file per agent
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

Launch **one agent per file**, all simultaneously using parallel Task tool calls in a single message. Use `model: "sonnet"` and `subagent_type: "general-purpose"` for each agent.

Example: 20 files → 20 agents → all 20 launched in one message.

Each agent gets this prompt (with variables filled in):

```
You are a {LANGUAGE} translator for doQumentation (Docusaurus site for Qiskit quantum computing tutorials).

Translate this English MDX file to {LANGUAGE}:

File (path relative to docs/): {file}

1. Read the English source from `docs/{path}`
2. Translate following the rules below
3. Write the translation to `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{path}`

Rules:
- Use the Read tool to read files and the Write tool to write files. Do NOT use Bash for file operations.
- If the target file exists and contains `{/* doqumentation-untranslated-fallback */}`, it's a fallback — overwrite it completely
- If the target file exists WITHOUT that marker, it's already translated — SKIP it
- Preserve ALL frontmatter keys exactly — translate ONLY values of `title`, `description`, `sidebar_label`
- Preserve ALL code blocks (` ```python `, ` ```bash `, ` ```text `, etc.) completely unchanged
- Preserve ALL math/LaTeX (`$...$`, `$$...$$`) completely unchanged
- Preserve ALL JSX components, imports, and HTML tags unchanged (e.g., `<Admonition>`, `<Tabs>`, `<OpenInLabBanner>`)
- Preserve ALL URLs/links and image paths unchanged
- Preserve ALL inline code backticks unchanged (e.g., `Statevector`, `QuantumCircuit`, `numpy`)
- Translate ONLY prose: paragraphs, headings, list items, admonition text content
- **Heading anchors**: When translating headings, pin the original English anchor using Docusaurus syntax: `## Translated Heading {#original-english-anchor}`. This ensures internal `#anchor` links keep working. Example: `## Change ordering in Qiskit` → `## Reihenfolge in Qiskit ändern {#change-ordering-in-qiskit}`
- Keep standard quantum computing terms (Qubit, Gate, Circuit, Backend, Transpiler)
- Use {FORMAL_FORM}
- Write natural, fluent {LANGUAGE} — not word-for-word translation
- **Use proper Unicode characters** — NEVER use ASCII digraph substitutes. For German: use ä ö ü Ä Ö Ü ß directly, NEVER ae oe ue ss. For other languages: use the native script characters, never romanized approximations.

### Large file chunking (>400 lines)

Files over ~400 lines should be **split into chunks** for translation to avoid output token limits:

1. Read the source file and identify section boundaries (e.g., `## Part I`, `## Step 3`)
2. Split into chunks of **~400 lines each**, always at a section heading boundary (500 upper limit)
3. Translate each chunk in a **separate parallel agent** — write to temp files (`/tmp/{filename}-part1.mdx`, etc.)
4. First chunk includes frontmatter; subsequent chunks start at their section heading
5. After all chunks complete, concatenate with a **blank line between chunks**
6. **Verify integrity**: total line count vs source (should match), section heading count, code block count (triple backticks), LaTeX block count (`$$` pairs), last 5 lines of each chunk (truncation is the most common failure)
7. **Verify Unicode** — grep for ASCII digraph patterns (e.g., `koennen`, `fuer` for German) and fix any found

Files under 400 lines: translate in a single pass.
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

Launch one agent per file, all in a **single message** (all parallel). Each agent uses `model: "sonnet"`.

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

| Variable | DE | JA | UK | ES | FR | IT | PT | TL | TH | AR | HE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LOCALE | de | ja | uk | es | fr | it | pt | tl | th | ar | he |
| LANGUAGE | German | Japanese | Ukrainian | Spanish | French | Italian | Portuguese | Tagalog/Filipino | Thai | Arabic | Hebrew |
| FORMAL_FORM | formal ("Sie" not "du") | polite (です/ます form) | formal ("Ви" not "ти") | formal ("usted" not "tú") | formal ("vous" not "tu") | formal ("Lei" not "tu") | formal ("você" formal) | formal ("po/opo" forms) | polite (ครับ/ค่ะ forms) | formal (فصحى) | professional register |

**New locales**: Before using `populate-locale` for a new locale, ensure its banner template exists in `BANNER_TEMPLATES` dict in `scripts/translate-content.py`. Currently defined: de, ja, uk, es, fr, it, pt, tl, th, ar, he.

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
| DE | 79/387 | 54 guides, 18 tutorials, 5 courses/modules, homepage, 2 indexes + UI strings |
| ES | 55/387 | 43 tutorials, 5 guides, 3 courses, 2 modules, homepage + UI strings |
| UK | 55/387 | 43 tutorials, 5 guides, 3 courses, 2 modules, homepage + UI strings |
| FR | 44/387 | 44 tutorials + UI strings |
| IT | 44/387 | 44 tutorials + UI strings |
| PT | 44/387 | 44 tutorials + UI strings |
| JA | 59/387 | 44 tutorials, 5 guides, 3 courses, 2 modules, homepage, 2 indexes + UI strings |
| TL | 8/387 | 8 tutorials + UI strings |
| AR | 44/387 | 44 tutorials + UI strings (RTL) |
| HE | 9/387 | 9 tutorials + UI strings (RTL) |

## Agent Configuration Summary

| Setting | Value |
|---------|-------|
| Model | `sonnet` |
| Subagent type | `general-purpose` |
| Files per agent | 1 (use chunking for files >400 lines) |
| Parallel agents | 20+ per round |
| Rounds for full locale | ~19 rounds (371 files ÷ 20 agents per round) |
