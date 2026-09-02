# Translation pipeline v2 — segments, not files

This directory replaces the file-splicing update pipeline in
`translation/scripts/` with a standard localisation model: the English page is
split into segments, each segment's translation is stored once per locale in a
gettext PO file, and the locale page is rendered from the English skeleton at
build time. Nothing is inferred, located or spliced.

If you are new here, read this file top to bottom once. It is short on purpose;
the reasoning behind the change is in the assessment linked at the end.

## Why v2 exists (one paragraph)

v1 kept 17 complete copies of every MDX page and tried to keep them in step with
English by diffing an old English against a new one and asking a model to edit
the translation in place. That made staleness a whole-file property (any
notebook output change re-staled 17 files), forced a large validator and repair
chain to keep 17 copies of the code byte-identical, and left no record of which
translated paragraph belonged to which English paragraph, so a skipped edit was
invisible. Five disagreeing provenance records grew around that gap. v2 removes
the gap instead of guarding it.

## The model

```
docs/<page>.mdx                       English, the only source of truth (tracked, pinned to an upstream commit)
        │  extract.py  (po4a)
        ▼
translation/v2/pot/<page>.pot         English segments, typed: Plain text, Title, Bullet, Front matter …
        │  bootstrap.py (once, po4a-gettextize)      update.py (after every sync, msgmerge)
        ▼
i18n/<loc>/po/<page>.po               THE translation memory: msgid = English segment, msgstr = translation
        │  render.py  (po4a-translate)
        ▼
i18n/<loc>/docusaurus-plugin-content-docs/current/<page>.mdx     derived; what Docusaurus builds
```

A segment is whatever po4a's Markdown parser yields: a paragraph, a heading, a
list item, a table row, a front-matter value, an admonition body, a JSX line.
Fenced code is extracted by po4a too but **dropped from every PO** (`prune()`):
code is never translated, and po4a-translate renders the English for any entry
that is absent from the PO. Consequently a PO holds prose only, and a change
to notebook output can never make a translation stale.

### What each tool does

| Tool | When | What it does |
|---|---|---|
| `extract.py [--check]` | after every sync, and by bootstrap | `docs/` → `pot/`. `--check` renders each POT untranslated and requires the result to equal the source (modulo blank lines and front-matter quoting). All 424 pages pass. |
| `bootstrap.py --locale X [--verify]` | once per locale, **before** the next English sync | Builds `i18n/X/po/` from the existing translations. `exact` strategy is `po4a-gettextize`; `positional` is our fallback for pages po4a refuses (pairs the type sequences with difflib, adopts matching runs only). Writes `work/bootstrap-X.json`. |
| `update.py --locale X --json …` | after every sync | `msgmerge --previous` every PO against the new POT, then prints the worklist: fuzzy (near-identical English, old msgid kept as `#\| msgid`) and untranslated entries. |
| `translate.py --locale X --prepare` | after update | Writes `work/X/batch-NNN.json` and `instructions.md`. Anything that can fill `msgstr` in JSON can translate: a Claude Code agent, the Anthropic API (`--backend anthropic`, untested here), a human. |
| `translate.py --locale X --apply` | after the batches are filled | Runs `check.py` on every item, writes accepted ones into the PO, lists rejected ones with the reason. Nothing partial is ever written. |
| `render.py --locale X [--out-dir D]` | at build time, or to preview | POT + PO → locale MDX, with the v1 freshness marker so v1 tools keep working during the migration. |
| `check.py` | inside apply and bootstrap | Multiset comparison of everything that must survive translation: inline code, URLs, image paths, math, JSX/HTML tags, `{#anchors}`, MDX comments. |
| `po4a_io.py` | library | Everything above calls into it. Pre-rules, po4a wrappers, PO hygiene. |

### The pre-rules (read `po4a_io.py`'s docstring, they matter)

po4a never sees `docs/` directly. A temporary copy is made with four rewrites,
and the rendered output reverses the ones that must not reach the site:

1. every heading gets an explicit `{#anchor}` from the English text, numbered
   `x`, `x-1`, `x-2` for repeats exactly as Docusaurus does. The anchor is part
   of the msgid, so the translator keeps it, `check.py` verifies it, and
   cross-page links work in every locale;
2. `:::note[Title]` … `:::` becomes `<DoqAdmonition type="note" title="Title">`
   … `</DoqAdmonition>` (po4a cannot parse the bracket form or a fence inside
   the block) and is turned back on render;
3. a blank line is inserted before a fence or heading that follows prose
   directly (same rendering, but po4a pairs entries differently without it);
4. a closing fence carrying a language tag (```` ```json ```` where ```` ``` ````
   was meant, a sync-content artefact on 17 English pages) is made bare for
   po4a and restored on render, so v1's fence-count gates stay green. Those
   pages are genuinely broken upstream of us; the fix belongs in sync-content.

On the translation side only, the v1 marker and stray `{/* c510c407 */}`
comments are removed before alignment.

## Numbers to expect (measured 2026-09-02 on the June-19 English)

| | |
|---|---|
| English pages | 424, all extract, all round-trip, 25,291 translatable entries |
| German bootstrap | 305 pages exact, 117 positional, 0 failed; 26,394 of 26,495 entries paired (99.6%) |
| German render vs the old file | 304 of 422 identical; the rest differ by design (below) |
| German rendered pages passing the v1 MDX lint | 422 of 422 |
| German residual worklist | 225 entries, 6,070 words, on 41 pages |
| Time | extract 2 min, bootstrap 3.5 min per locale |

Where a rendered page differs from the old translation, the bootstrap report
says why. Three classes, all intended:

- **translation-only content dropped.** The old file carried a paragraph the
  English does not have (a doQumentation note whose subject was removed, a
  bullet upstream deleted, a stale sentence). Rendering from the English
  skeleton removes it. This is the stale-content class v1 could not detect;
  read the report before assuming the drop is wrong.
- **unpaired segments render in English.** The positional strategy could not
  pair a run; the entry is empty and lands on the worklist.
- **entries dropped for tag mismatch.** An inherited translation had lost or
  moved a JSX/HTML tag (64 in German, mostly `<Accordion>` blocks from the v1
  migration). Rendering it would break the page, so it is emptied, annotated
  `doq-bootstrap: dropped …` in the PO, and lands on the worklist.

## Running a sync (the whole procedure)

```bash
# 0. Bootstrap every locale you have not bootstrapped yet — BEFORE merging the sync.
python3 translation/v2/bootstrap.py --locale fr --verify

# 1. Merge the "sync: upstream content" PR. docs/ now has the new English.
python3 translation/v2/extract.py --check

# 2. Per locale: merge, worklist, batches.
python3 translation/v2/update.py --locale fr --json translation/v2/work/worklist-fr.json
python3 translation/v2/translate.py --locale fr --prepare
#    fill work/fr/batch-*.json (agent, API, or human), following work/fr/instructions.md
python3 translation/v2/translate.py --locale fr --apply       # rejects go back on the worklist

# 3. Render, lint, build, commit the PO files (never the rendered MDX by hand).
python3 translation/v2/render.py --locale fr
python3 translation/scripts/lint-translation.py --locale fr
git add i18n/fr/po translation/v2/pot && git commit
```

Order matters in step 0: `po4a-gettextize` aligns a translation with the
English it was made from. Bootstrapping after the sync would pair the old
German with new English and fail on every changed page.

## Hard rules

- **Only `translate.py --apply` writes a `msgstr`.** No script, hook or agent
  edits a PO by other means. The PO is the provenance record; v1 lost its
  provenance because a validator wrote to it as a side effect.
- **Never hand-edit a rendered MDX.** It is derived. Fix the PO and render.
- **Do not add a check to a tool to work around a page.** If a page needs a
  rule, it goes into `pre_source()` with a test in `tests/`, or into
  sync-content where the English is produced.
- **The 9 German dialects** (swg bad bar ksh nds gsw sax bln aut) are not
  bootstrapped or translated. `MAIN_LOCALES` is the list.

## Migration state and what is still v1

- Rendered MDX under `i18n/<loc>/…/current/` is still tracked and still what
  CI builds; `render.py` writes the v1 marker so `check-translation-freshness`
  reports rendered pages as fresh. Once every locale is bootstrapped and one
  sync has gone through v2, the rendered files leave git and `render.py` runs
  in the build workflows where `populate-locale` runs today.
- v1 scripts to delete at that point: `update-translations.py`,
  `sync-translations.py`, `check-translation-freshness.py`,
  `bootstrap-passage-hashes.py`, `update-en-passage-hashes.py`,
  `advance-baseline.py`, `promote-drafts.py`, `check-stale-passages.py`,
  `remove-stale-paragraph.py`, `fix-heading-anchors.py`,
  `migrate-details-to-accordion.py`; records `baseline-hashes.json`,
  `en-passage-hashes.json`, `translation/manifests/`, the `source_hash` and
  `validated_against` fields in `status.json`.
- Keep: `lint-translation.py` (on rendered output), `check-known-mistranslations.py`
  and `check-wrong-language.py` (to be folded into `check.py`), the glossaries,
  the Opus review rubric (to be applied per entry; verdicts then live in the
  PO as translator comments), `build-locales-pr.yml`.
- Review verdicts from `status.json` were copied into each PO header
  (`X-Doq-Review-Tier3`, `X-Doq-Review-Opus`) at bootstrap so they are not lost.

## Dependencies

`po4a` ≥ 0.74 and GNU gettext (`msgmerge`, `msgattrib`) on PATH; Python
`polib`. macOS: `brew install po4a gettext`; Debian/Ubuntu: `apt-get install
po4a gettext`. Tests: `python3 -m pytest translation/v2/tests -q` (po4a tests
skip when it is missing).

## Known limitations

- po4a merges a JSX closing tag and the paragraph that follows it into one
  entry when no blank line separates them (`</Accordion>\nText…`). Harmless,
  but such entries carry tags the translator must keep; `check.py` enforces it.
- A bare JSX line such as `<OpenInLabBanner … />` is an entry too. It is not
  translatable and is skipped by `translatable()`; it stays in the PO so
  entry indices are stable.
- Duplicate paragraphs on one page share one entry (gettext semantics). Two
  different translations of the same English sentence on one page are not
  possible; at bootstrap the first one is kept and the entry is annotated.
- `translate.py --backend anthropic` has not been run in the environment this
  was written in (no API key). The batch-file path has.

## Where the reasoning lives

The assessment that led to this design, with the measurements and the tests of
po4a, mdpo, translate-toolkit, Weblate and Crowdin against this corpus:
https://claude.ai/code/artifact/2a1289ff-d77d-45e9-b08c-d8746b73b94e
