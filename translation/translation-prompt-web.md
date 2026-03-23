# Translation Prompt — Claude Code Web Session

Paste into the Claude Code web UI (claude.ai Code tab) with the doQumentation repo connected.
Change `{LANGUAGE}` and `{LOCALE}` to your target language before pasting.

See [`translation-prompt.md`](translation-prompt.md) for the full CLI prompt with parallel Sonnet agents.

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

SETUP (must complete before translating):
  git pull
  git submodule update --init
  python scripts/sync-content.py

This populates docs/tutorials/, docs/guides/, and docs/learning/ (courses + modules) — all are gitignored and generated from upstream via the submodule.

Then read translation/translation-prompt.md. Translate all untranslated pages to the language above.

Run: python translation/scripts/translation-status.py --locale {LOCALE} --backlog

Source file paths (IMPORTANT — courses and modules are nested under docs/learning/):
- Tutorials: docs/tutorials/{file}.mdx
- Guides: docs/guides/{file}.mdx
- Courses: docs/learning/courses/{course}/{section}/{file}.mdx
- Modules: docs/learning/modules/{module}/{file}.mdx

Translate ALL four sections in order: tutorials → guides → courses → modules.
```
