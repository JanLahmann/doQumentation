# Translation Prompt — doQumentation

> For a tool-agnostic contributor guide (any LLM, no Claude Code required), see [`CONTRIBUTING-TRANSLATIONS.md`](../CONTRIBUTING-TRANSLATIONS.md) in the repo root.

Translates English MDX content to other languages using Claude Code CLI with parallel Sonnet Task agents.

**Model**: Sonnet (always — via `model: "sonnet"` in Task calls)
**Batch size**: 1 file or chunk per agent
**Parallelism**: 3 agents per round

---

## Prompt Templates

Paste one of these into Claude Code:

```
Read translation/translation-prompt.md. Translate all untranslated pages to French (fr).
```

```
Read translation/translation-prompt.md. Translate all remaining guide pages to German (de). Skip already-translated files.
```

```
Read translation/translation-prompt.md. Translate these files to Spanish (es): guides/install-qiskit.mdx, guides/hello-world.mdx
```

---

## Source File Paths — IMPORTANT

Content files are NOT all at the top level of `docs/`. The four sections have different directory structures:

| Section | English source path | Example file |
|---------|-------------------|--------------|
| Tutorials | `docs/tutorials/{file}.mdx` | `docs/tutorials/hello-world.mdx` |
| Guides | `docs/guides/{file}.mdx` | `docs/guides/install-qiskit.mdx` |
| Courses | `docs/learning/courses/{course}/{section}/{file}.mdx` | `docs/learning/courses/basics-of-quantum-information/single-systems/introduction.mdx` |
| Modules | `docs/learning/modules/{module}/{file}.mdx` | `docs/learning/modules/computer-science/deutsch-jozsa.mdx` |

**Courses are nested**: each course is a directory under `docs/learning/courses/` containing an `index.mdx`, optional `exam.mdx`, and section subdirectories with lesson files. There are 13 courses with ~154 pages total.

**Modules are flat**: each module is a directory under `docs/learning/modules/` containing an `index.mdx` and lesson files. There are 2 modules with ~14 pages total.

**Translation output paths mirror the source paths** relative to `docs/`:
- Source: `docs/learning/courses/basics-of-quantum-information/single-systems/introduction.mdx`
- Draft: `translation/drafts/{LOCALE}/learning/courses/basics-of-quantum-information/single-systems/introduction.mdx`
- Promoted: `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/learning/courses/basics-of-quantum-information/single-systems/introduction.mdx`

---

## How to Launch Translation Agents

Launch **one agent per file**, up to **3 agents in parallel** per round. Use `model: "sonnet"` and `subagent_type: "general-purpose"` for each agent.

Example: 9 files → 3 rounds of 3 agents each.

**Large files (>400 lines)**: The orchestrator MUST handle chunking — see "Large File Chunking" section below. Do NOT assign files >400 lines to a single agent. Do NOT include chunking instructions in the per-agent prompt. Do NOT ask agents to "handle chunking themselves."

Each agent gets this prompt (with variables filled in):

```
You are a {LANGUAGE} translator for doQumentation (Docusaurus site for Qiskit quantum computing tutorials).

Translate this English MDX file to {LANGUAGE}:

File (path relative to docs/): {file}

1. Read the English source from `docs/{path}`
2. Translate following the rules below
3. Write the translation to `translation/drafts/{LOCALE}/{path}`

Rules:
- Use the Read tool to read files and the Write tool to write files. Do NOT use Bash for file operations.
- If `translation/drafts/{LOCALE}/{path}` already exists — SKIP it (draft already in progress)
- If `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{path}` exists and does NOT contain `{/* doqumentation-untranslated-fallback */}` — SKIP it (already promoted)
- Preserve ALL frontmatter keys exactly — translate ONLY values of `title`, `description`, `sidebar_label`
- **Source hash**: After the frontmatter closing `---`, add a source hash comment: `{/* doqumentation-source-hash: XXXX */}` where XXXX is the first 8 hex chars of SHA-256 of the EN source file content. Compute with: `python3 -c "import hashlib; print(hashlib.sha256(open('docs/{path}').read().encode()).hexdigest()[:8])"`. This lets the freshness checker detect when the EN source changes.
- Preserve ALL code blocks (` ```python `, ` ```bash `, ` ```text `, etc.) completely unchanged
- Preserve ALL math/LaTeX (`$...$`, `$$...$$`) completely unchanged
- Preserve ALL JSX/HTML tag names, imports, and structural attributes unchanged (e.g., `<Admonition>`, `<Tabs>`, `<OpenInLabBanner>`)
- Preserve ALL URLs/links and image paths unchanged
- Preserve ALL inline code backticks unchanged (e.g., `Statevector`, `QuantumCircuit`, `numpy`)
- Translate prose: paragraphs, headings, list items, admonition text content
- **Also translate display text inside HTML/JSX attributes**: `title="..."` on `<Admonition>`, text inside `<summary>`/`<details>`/`<b>` blocks. These contain readable prose even though they're inside tags.
- **Heading anchors**: When translating headings, pin the original English anchor using Docusaurus syntax: `## Translated Heading {#original-english-anchor}`. This ensures internal `#anchor` links keep working. Example: `## Change ordering in Qiskit` → `## Reihenfolge in Qiskit ändern {#change-ordering-in-qiskit}`
- Keep standard quantum computing terms (Qubit, Gate, Circuit, Backend, Transpiler)
- Use {INFORMAL_FORM}
- Write natural, fluent {LANGUAGE} — not word-for-word translation
- **Use proper Unicode characters** — NEVER use ASCII digraph substitutes. For German: use ä ö ü Ä Ö Ü ß directly, NEVER ae oe ue ss. For other languages: use the native script characters, never romanized approximations.
```


---

## Large File Chunking (>400 lines) — Orchestrator MUST Do This

**CRITICAL**: The orchestrator (you) MUST handle chunking. Sub-agents always receive a single chunk or a complete small file — they NEVER split files themselves. Do NOT assign a file >400 lines to a single agent. Do NOT tell an agent "if the file is large, chunk it." YOU do the chunking.

### Step-by-step procedure for EVERY file

Before assigning any file to an agent:

1. **Read the file** yourself: `Read docs/{path}` — note the total line count
2. **If ≤400 lines** → assign to one agent as normal (use the standard prompt above)
3. **If >400 lines** → YOU must chunk it. Follow steps 3a–3e below:

   **3a. Find section boundaries**: Scan the file for `## ` headings (level 2). Note each heading's line number.

   **3b. Plan chunks**: Group consecutive sections into chunks of ~300–400 lines each. Never exceed 500 lines per chunk. Always split at a `## ` heading boundary. Write down: chunk 1 = lines 1–N, chunk 2 = lines (N+1)–M, etc.

   **3c. Launch chunk agents** (up to 3 in parallel). Each chunk agent gets this prompt:

   ```
   You are a {LANGUAGE} translator for doQumentation.

   Translate ONLY lines {START}–{END} of this file to {LANGUAGE}:

   File: docs/{path}

   Instructions:
   1. Read `docs/{path}` (the full file)
   2. Translate ONLY lines {START} through {END}
   3. Write ONLY the translated chunk to `/tmp/{filename}-part{N}.mdx`

   [FIRST CHUNK ONLY: Include the frontmatter block. Add source hash after `---`.]
   [SUBSEQUENT CHUNKS: Start directly at the section heading on line {START}. No frontmatter.]

   Translation rules: [same rules as the standard prompt above]
   ```

   **3d. Concatenate**: After ALL chunk agents finish, read each `/tmp/{filename}-part{N}.mdx` in order. Concatenate them with a blank line between chunks. Write the result to `translation/drafts/{LOCALE}/{path}`.

   **3e. Verify integrity**: Check the concatenated file:
   - Total line count is within ±20% of source
   - Count `## ` headings — must match source exactly
   - Count triple backtick fences (` ``` `) — must match source exactly
   - Count `$$` pairs — must match source exactly
   - Read the last 5 lines — verify no truncation
   - For German: grep for ASCII digraphs (`koennen`, `fuer`, `ue`, `ae`, `oe`) and fix if found

### Common mistakes to AVOID

- **DO NOT** assign a 600-line file to one agent and say "translate this file"
- **DO NOT** tell an agent "if the file is too large, split it into chunks"
- **DO NOT** tell an agent "handle chunking as needed"
- **DO** read the file yourself first, count the lines, plan the chunks, then launch chunk agents

---

## Autonomous Workflow

When NO explicit file list is given, discover files to translate:

### Step 1: Discover untranslated files

Use the status script for an accurate count (it checks both drafts and promoted files):

```bash
python translation/scripts/translation-status.py --locale {LOCALE} --backlog
```

If the status script is unavailable or you prefer manual discovery, follow these steps:

1. **Glob ALL four source directories** (not just `docs/*.mdx` — courses and modules are nested):
   ```
   Glob docs/tutorials/**/*.mdx
   Glob docs/guides/**/*.mdx
   Glob docs/learning/courses/**/*.mdx
   Glob docs/learning/modules/**/*.mdx
   Glob docs/index.mdx
   ```

2. **Glob existing translations** (both promoted AND drafts):
   ```
   Glob i18n/{LOCALE}/docusaurus-plugin-content-docs/current/**/*.mdx
   Glob translation/drafts/{LOCALE}/**/*.mdx
   ```

3. **For each English source file**, derive the relative path (strip `docs/` prefix) and check:
   - Draft exists at `translation/drafts/{LOCALE}/{path}` → **SKIP** (draft in progress)
   - Promoted file exists at `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{path}` AND does NOT contain `{/* doqumentation-untranslated-fallback */}` → **SKIP** (already translated)
   - Otherwise → **needs translation**

4. **Report the count** before starting: "Found N files to translate: X tutorials, Y guides, Z course pages, W module pages"

### Step 2: Check file sizes and plan chunking

**Before launching any agents**, read each file to translate and note its line count. Group them into:
- **Small files** (≤400 lines): assign one agent per file
- **Large files** (>400 lines): plan chunks per the "Large File Chunking" section above

### Step 3: Launch parallel agents

Launch up to **3 agents in parallel** per round. Each agent uses `model: "sonnet"`.

Process in this order: tutorials → guides → courses → modules

For large files, each chunk counts as one agent slot (a 900-line file split into 3 chunks uses all 3 parallel slots for that round).

### Step 4: After all agents complete

Report summary:
- Total files translated (written to `translation/drafts/`)
- Files skipped (already translated or draft exists)
- Any errors

Remind the user to validate, fix, and promote:
```bash
# Validate drafts
python translation/scripts/validate-translation.py --locale {LOCALE} --dir translation/drafts

# Fix heading anchors in drafts
python translation/scripts/fix-heading-anchors.py --locale {LOCALE} --dir translation/drafts --apply

# Generate feedback report (optional — for contributor review)
python translation/scripts/validate-translation.py --locale {LOCALE} --dir translation/drafts --report

# Promote passing drafts to i18n/
python translation/scripts/promote-drafts.py --locale {LOCALE}

# Populate English fallbacks for remaining untranslated pages
python translation/scripts/translate-content.py populate-locale --locale {LOCALE}

# Stage promoted translations
git add -f i18n/{LOCALE}/docusaurus-plugin-content-docs/current/
```

---

## Variable Reference

| Variable | DE | JA | UK | ES | FR | IT | PT | TL | TH | AR | HE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LOCALE | de | ja | uk | es | fr | it | pt | tl | th | ar | he |
| LANGUAGE | German | Japanese | Ukrainian | Spanish | French | Italian | Portuguese | Tagalog/Filipino | Thai | Arabic | Hebrew |
| INFORMAL_FORM | informal ("du" not "Sie") | polite (です/ます) but not overly formal | informal ("ти" not "Ви") | informal ("tú" not "usted") | informal ("tu" not "vous") | informal ("tu" not "Lei") | informal ("você" casual) | casual (no po/opo) | casual (no ครับ/ค่ะ) | informal register | informal register |

**New locales**: Before using `populate-locale` for a new locale, ensure its banner template exists in `BANNER_TEMPLATES` dict in `translation/scripts/translate-content.py`. Currently defined: de, ja, uk, es, fr, it, pt, tl, th, ar, he.

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
Add a `{LOCALE}` entry to `BANNER_TEMPLATES` in `translation/scripts/translate-content.py` (admonition with "not yet translated" message in the target language).

### 6. Config
Add locale to `locales` array and `localeConfigs` in `docusaurus.config.ts`. Add `language` entry in search plugin config (if `lunr-languages` supports it).

### 7. Git tracking
`current.json` is tracked normally. MDX content translations must be force-added: `git add -f i18n/{LOCALE}/docusaurus-plugin-content-docs/current/`.

## Current Translation State

Run `python translation/scripts/translation-status.py` for live counts, or see `translation/STATUS.md`.

## Agent Configuration Summary

| Setting | Value |
|---------|-------|
| Model | `sonnet` |
| Subagent type | `general-purpose` |
| Unit per agent | 1 file or 1 chunk (orchestrator splits files >400 lines) |
| Parallel agents | 3 per round |
| Rounds for full locale | ~124 rounds (371 files ÷ 3 agents per round) |
