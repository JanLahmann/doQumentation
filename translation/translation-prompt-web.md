# Translation Prompt — Claude Code Web Session

For use in the Claude Code web UI (claude.ai Code tab) with the doQumentation repo.

## Setup (run once at start of session)

```bash
git pull && git submodule update --init && python scripts/sync-content.py
ls docs/tutorials/ docs/guides/ docs/learning/courses/ docs/learning/modules/
```

If any directory is missing, setup failed — do not proceed.

## Prompt template

Replace LANGUAGE and LOCALE, then paste:

```
Translate all untranslated pages to LANGUAGE. Follow instructions in translation/translation-prompt.md. Chunk files over 350 lines. Assign one chunk per agent. Use only 3 parallel agents. Do not assign more work to a single agent.
```

To limit scope: `Translate all untranslated tutorials and guides to LANGUAGE.`

## Language reference

| Language | LOCALE |
|----------|--------|
| German | de |
| Spanish | es |
| French | fr |
| Italian | it |
| Ukrainian | uk |
| Japanese | ja |
| Portuguese | pt |
| Filipino | tl |
| Arabic | ar |
| Hebrew | he |
| Thai | th |
| Malay | ms |
| Indonesian | id |
| Korean | ko |
| Polish | pl |
| Romanian | ro |
| Czech | cs |
