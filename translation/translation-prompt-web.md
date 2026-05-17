# Translation Prompt — Claude Code Web Session

For use in the Claude Code web UI (claude.ai Code tab) with the doQumentation repo.

## Setup (run once at start of session)

```bash
git pull && git submodule update --init && python scripts/sync-content.py
ls docs/tutorials/ docs/guides/ docs/learning/courses/ docs/learning/modules/
```

If any directory is missing, setup failed — do not proceed.

## ⚠ Known web limitation — large `Write` loses work

In Claude Code **web**, the `Write` tool can fail when writing a large
file. The agent finishes translating (tokens spent), the big `Write`
fails, and the whole translation is **lost**. The CLI does not have this
problem. To survive it, web agents must **never write a large file in one
`Write`** — build it incrementally so a failure costs at most one small
section, not the whole file:

1. **Create** the draft with `Write`, containing ONLY the frontmatter +
   `{/* doqumentation-source-hash: {HASH} */}` + the first section.
2. **Append** each subsequent section with a separate `Edit` (old_string
   = the file's current last line or a unique tail anchor; new_string =
   that line + the next translated section). One `Edit` per section,
   ≤~150 lines each.
3. After the last section, do a final `Read` to confirm the file is
   complete (last line matches the source's last line) before reporting
   "Done". If it is truncated, continue appending — do not restart.

This makes the unit-of-loss a single small `Edit`, not the file.

## Prompt template

Replace LANGUAGE and LOCALE, then paste:

```
Translate all untranslated pages to LANGUAGE. Follow instructions in translation/translation-prompt.md, EXCEPT: this is a web session — never write a file in one large Write. Create the draft (frontmatter + source-hash + first section) with Write, then append each following section with a separate Edit (≤150 lines per Edit). Read the file at the end to confirm it is complete before reporting Done. Chunk files over 800 lines into separate agents. Use only 3 parallel agents. One file/chunk per agent; do not assign more work to a single agent.
```

Why 800 (not 350): a Sonnet agent translates ≤800-line files whole
fine — the old 350 cap was a workaround for the large-`Write` failure
above. With incremental writes, 800 is safe in web too; only split
genuinely huge files.

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
