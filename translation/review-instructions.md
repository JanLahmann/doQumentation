# Translation Review Instructions

> **Moved.** The canonical, multi-language review instructions now live in
> [`translation/review-prompt.md`](review-prompt.md). This file used to hold a
> Spanish-only copy that drifted out of sync — it has been collapsed to this
> pointer to avoid two conflicting sources of truth.

## How a full linguistic review works

1. **Render first** — the pages under `i18n/<LOCALE>/…/current/` are derived
   from the PO files and not in git:
   ```bash
   python3 translation/v2/render.py --locale <LOCALE>
   ```
   Only review a locale whose `translation/v2/update.py --locale <LOCALE>`
   reports 0 fuzzy and 0 untranslated (see `translation/v2/README.md`).
2. **Tier 1 — structural validation** (heading count, code blocks, image paths):
   ```bash
   python translation/scripts/validate-translation.py --locale <LOCALE> --record
   ```
3. **Tier 2 — MDX lint** (build-breaking syntax: anchors, fences, missing imports):
   ```bash
   python translation/scripts/lint-translation.py --locale <LOCALE> --record
   ```
4. **Tier 3 — linguistic review** (register, word salad/hallucination, verbosity,
   accuracy). Use the prompt and per-language register table in
   [`review-prompt.md`](review-prompt.md). Haiku is the validated review model.

## Orchestration

The whole flow is driven by
[`translation/scripts/review-translations.py`](scripts/review-translations.py):

```bash
python translation/scripts/review-translations.py --auto-check          # Tiers 1+2
python translation/scripts/review-translations.py --progress            # dashboard
python translation/scripts/review-translations.py --next-chunk          # fresh files only
python translation/scripts/review-translations.py --record-review ...   # save verdicts
```

`--next-chunk` skips STALE/UNKNOWN files by default (pass `--include-stale` to
override). Verdicts are tracked per file in `translation/status.json`.
