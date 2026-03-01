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

## How to Launch Translation Agents

Launch **one agent per file**, up to **3 agents in parallel** per round. Use `model: "sonnet"` and `subagent_type: "general-purpose"` for each agent.

Example: 9 files → 3 rounds of 3 agents each.

**Large files (>400 lines)**: The orchestrator handles chunking — see "Large File Chunking" section below. Do NOT include chunking instructions in the per-agent prompt.

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

## Large File Chunking (>400 lines) — Orchestrator Responsibility

The **orchestrator** (not the sub-agent) handles chunking for large files. Sub-agents always receive a single chunk or a complete small file — they never need to split anything themselves.

### How the orchestrator handles a large file

1. Read the source file and count lines
2. If ≤400 lines → assign to a single agent as normal
3. If >400 lines → split into chunks:
   a. Identify section boundaries (e.g., `## Part I`, `## Step 3`)
   b. Split into chunks of **~400 lines each**, always at a section heading boundary (500 upper limit)
   c. Launch one agent per chunk (up to 3 in parallel), each with this modified prompt:
      - "Translate this **chunk** of `{file}` (lines {start}–{end})"
      - Agent reads the full source file but translates only its assigned line range
      - First chunk agent includes frontmatter; subsequent chunk agents start at their section heading
      - Each agent writes to a temp file: `/tmp/{filename}-part{N}.mdx`
   d. After all chunk agents complete, the orchestrator concatenates temp files with a **blank line between chunks**
   e. The orchestrator writes the final result to `translation/drafts/{LOCALE}/{path}`

### Post-concatenation verification (orchestrator)

4. **Verify integrity**: total line count vs source (should be similar), section heading count, code block count (triple backticks), LaTeX block count (`$$` pairs), last 5 lines of each chunk (truncation is the most common failure)
5. **Verify Unicode** — grep for ASCII digraph patterns (e.g., `koennen`, `fuer` for German) and fix any found

---

## Autonomous Workflow

When NO explicit file list is given, discover files to translate:

### Step 1: Discover untranslated files

1. `Glob docs/**/*.mdx` → all English source files
2. `Glob i18n/{LOCALE}/docusaurus-plugin-content-docs/current/**/*.mdx` → existing promoted translations
3. `Glob translation/drafts/{LOCALE}/**/*.mdx` → existing drafts (in progress)
4. For each English source, check:
   - Draft exists in `translation/drafts/{LOCALE}/{path}` → SKIP (draft in progress)
   - Promoted file exists in `i18n/` and does NOT contain `{/* doqumentation-untranslated-fallback */}` → SKIP (already translated)
   - Promoted file has fallback marker or doesn't exist → needs translation
5. Build the list of files needing translation

### Step 2: Launch parallel agents

Launch up to **3 agents in parallel** per round. Each agent uses `model: "sonnet"`. For files >400 lines, use the chunking workflow from the "Large File Chunking" section above.

Process in this order: tutorials → guides → courses → modules

### Step 3: After all agents complete

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

| Locale | Pages | Status |
|--------|-------|--------|
| DE | 79/387 | 54 guides, 18 tutorials, 5 courses/modules, homepage, 2 indexes + UI strings |
| ES | 55/387 | 43 tutorials, 5 guides, 3 courses, 2 modules, homepage + UI strings |
| UK | 55/387 | 43 tutorials, 5 guides, 3 courses, 2 modules, homepage + UI strings |
| FR | 44/387 | 44 tutorials + UI strings |
| IT | 44/387 | 44 tutorials + UI strings |
| PT | 44/387 | 44 tutorials + UI strings |
| JA | 59/387 | 44 tutorials, 5 guides, 3 courses, 2 modules, homepage, 2 indexes + UI strings |
| TL | 48/387 | 44 tutorials, 1 homepage, 3 index pages + UI strings |
| AR | 44/387 | 44 tutorials + UI strings (RTL) |
| HE | 47/387 | 44 tutorials, 1 homepage, 2 index pages + UI strings (RTL) |
| SWG | 31/387 | 14 tutorials, homepage, 16 indexes + UI strings |
| BAD | 31/387 | 14 tutorials, homepage, 16 indexes + UI strings |
| BAR | 31/387 | 14 tutorials, homepage, 16 indexes + UI strings |
| KSH | 46/387 | 28 tutorials, homepage, 16 indexes, tutorials/index + UI strings |
| NDS | 43/387 | 25 tutorials, homepage, 16 indexes, tutorials/index + UI strings |
| GSW | 42/387 | 24 tutorials, homepage, 16 indexes, tutorials/index + UI strings |
| SAX | 39/387 | 21 tutorials, homepage, 16 indexes, tutorials/index + UI strings |
| BLN | 36/387 | 18 tutorials, homepage, 16 indexes, tutorials/index + UI strings |
| AUT | 34/387 | 16 tutorials, homepage, 16 indexes, tutorials/index + UI strings |

## Agent Configuration Summary

| Setting | Value |
|---------|-------|
| Model | `sonnet` |
| Subagent type | `general-purpose` |
| Unit per agent | 1 file or 1 chunk (orchestrator splits files >400 lines) |
| Parallel agents | 3 per round |
| Rounds for full locale | ~124 rounds (371 files ÷ 3 agents per round) |
