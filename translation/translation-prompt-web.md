# Translation Prompt — Claude Code Web Session

Paste into the Claude Code web UI (claude.ai Code tab) with the doQumentation repo connected.
Change `{LANGUAGE}` and `{LOCALE}` to your target language before pasting.

See [`translation-prompt.md`](translation-prompt.md) for the full CLI prompt (CLI with parallel Task agents).

---

## Variable Reference

| Language | LOCALE | LANGUAGE |
|----------|--------|----------|
| German | de | German |
| Spanish | es | Spanish |
| French | fr | French |
| Italian | it | Italian |
| Ukrainian | uk | Ukrainian |
| Japanese | ja | Japanese |
| Portuguese | pt | Portuguese |
| Tagalog | tl | Tagalog/Filipino |
| Arabic | ar | Arabic |
| Hebrew | he | Hebrew |
| Malay | ms | Malay |
| Indonesian | id | Indonesian |
| Thai | th | Thai |

---

## Prompt

```
Language: {LANGUAGE} ({LOCALE})

SETUP (run these first):
  git pull
  git submodule update --init
  python scripts/sync-content.py

This generates docs/tutorials/, docs/guides/, and docs/learning/ (all gitignored).
Verify: ls docs/tutorials/ docs/guides/ docs/learning/courses/ docs/learning/modules/

DISCOVER what needs translating:
  python translation/scripts/translation-status.py --locale {LOCALE} --backlog

Source file paths (courses and modules are nested under docs/learning/):
- Tutorials: docs/tutorials/{file}.mdx
- Guides: docs/guides/{file}.mdx
- Courses: docs/learning/courses/{course}/{section}/{file}.mdx
- Modules: docs/learning/modules/{module}/{file}.mdx

TRANSLATE using Sonnet agents — one file per agent, up to 3 in parallel.
Use model: "sonnet" for each agent. Each agent gets this prompt:

---
Translate docs/{path} from English to {LANGUAGE}.

1. Read docs/{path}
2. Compute source hash: python3 -c "import hashlib; print(hashlib.sha256(open('docs/{path}').read().encode()).hexdigest()[:8])"
3. Write translation to translation/drafts/{LOCALE}/{path}

Rules:
- After frontmatter closing ---, add: {/* doqumentation-source-hash: XXXX */}
- Translate frontmatter title/description/sidebar_label only. Keep all other keys.
- Preserve ALL code blocks (``` fences) byte-identical — same count, same content
- Preserve ALL math ($...$, $$...$$), JSX tags, imports, URLs, image paths unchanged
- Translate headings with anchor: ## Translated Heading {#original-english-anchor}
- Keep technical terms: Qubit, Gate, Circuit, Backend, Transpiler
- Write natural, fluent {LANGUAGE}
---

For files >600 lines: YOU (the orchestrator) must chunk at ## headings into ~400-line pieces. Launch one agent per chunk writing to translation/drafts/{LOCALE}/{filename}-part{N}.mdx. After all finish, concatenate and write to the final path. Delete part files.

Skip files already in translation/drafts/{LOCALE}/ or genuinely translated in i18n/{LOCALE}/docusaurus-plugin-content-docs/current/ (no {/* doqumentation-untranslated-fallback */} marker).

Work in order: tutorials → guides → courses → modules.
Before starting, print: "Starting: {N} files to translate ({X} tutorials, Y guides, Z courses, W modules)"
After each agent completes, print: "✓ {path} — {done}/{total} ({percent}%)"
After every 10 files, commit: git add translation/drafts/ && git commit -m "feat(i18n): add {LANGUAGE} translation drafts"
```
