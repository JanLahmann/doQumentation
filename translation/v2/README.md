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
| `translate.py --locale X --prepare` | after update | Sorts the worklist into tiers: **copy** (pure math, code, images: msgid copied, no model), **mechanical** (English changed only punctuation placement or emphasis markers: the same edit applied to the previous translation, checker-verified, no model), **haiku** (fuzzy, similarity ≥ 0.9) and **sonnet** (the rest). The model tiers become `work/X/batch-NNN-<model>.json` (≤ 120 items, ≤ 4,000 English words and ≤ 18k estimated tokens as the Read tool presents it; one id-less item per line, with a word diff and the previous translation for real fuzzy matches) plus a `.ids.json` sidecar per batch and `manifest.json`, which also carries the instructions text for inlining into prompts. |
| `.claude/workflows/translate-locale.js` | to fill the batches | One agent per batch from a sliding pool (`concurrency` in the args, default 5; the Polish run used 15), each allowed exactly one Read, one Write (`batch-NNN-<model>.out.json`: a list of strings in item order) and a one-line reply. Run with `Workflow({scriptPath, args: <manifest.json contents>})`; add `"agentType": "translator"` to the args in a session started after `.claude/agents/translator.md` existed (custom agents register at startup). Incomplete batches are listed and rerun with `resumeFromRunId`. |
| `translate.py --locale X --apply` | after the batches are filled | Pairs each `.out.json` with its `.ids.json` by position (a count mismatch rejects that batch), runs `check.py` on every item, writes accepted ones into the PO, lists rejected ones with the reason. Nothing partial is ever written. |
| `render.py --locale X [--out-dir D]` | at build time, or to preview | POT + PO → locale MDX, with the v1 freshness marker so v1 tools keep working during the migration. |
| `check.py` | inside apply and bootstrap | Everything that must survive translation, per entry: inline code, URLs, image paths, inline math (one merge/split tolerated), display math (delimiter count and normalised block content), JSX/HTML tags, table rows, fence lines, `{#anchors}`, MDX comments, and a length ratio that catches fragments. |
| `mdxcheck.mjs` | after render, before commit | Compiles every rendered page with MDX 3 + math + GFM + directives the way Docusaurus does (front matter stripped, heading anchors escaped) and lists the pages acorn rejects. The only check that asks the real parser; the German run needed it twice. |
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
| English pages | 424, all extract, all round-trip, 25,451 translatable entries |
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
python3 translation/v2/translate.py --locale fr --prepare      # tiers; prints how many need a model
#    fill work/fr/batch-*.json: Workflow translate-locale.js with work/fr/manifest.json as args
#    (or any agent/API/human that fills "msgstr" in the JSON)
python3 translation/v2/translate.py --locale fr --apply       # rejects go back on the worklist

# 3. Render, gate, commit the PO files (never the rendered MDX by hand).
python3 translation/v2/render.py --locale fr
find i18n/fr/docusaurus-plugin-content-docs/current -name '*.mdx' -print0 | xargs -0 node translation/v2/mdxcheck.mjs
python3 translation/scripts/lint-translation.py --locale fr
git add i18n/fr/po translation/v2/pot && git commit
```

Order matters in step 0: `po4a-gettextize` aligns a translation with the
English it was made from. Bootstrapping after the sync would pair the old
German with new English and fail on every changed page.

## Token cost, and why the batches look the way they do

The German run cost about 6.2 M tokens for 4,471 entries: roughly 150k per
4,000-word batch, ten times what one turn of translation needs, because
agents read, verified, re-read and wrote in 5 to 34 tool calls, each turn
re-sending the whole context. The orchestrator's own turns (about sixty
launch-and-notify cycles on a large context) cost at least as much again.
What changed after that run, in order of effect:

1. the workflow script runs a locale in one call and allows each agent
   exactly one read and one write;
2. batches carry only id, type, msgid and, for real fuzzy matches, the
   previous pair; no page context;
3. entries that need no model (pure math, code, images; punctuation-only or
   emphasis-only English changes) never reach one;
4. near-identical fuzzy entries go to Haiku, the rest to Sonnet;
5. batches stop at 120 items or 6,000 words, five run concurrently, and
   agents write back only `{id, msgstr}`, so the 64k output cap stays far
   away even for the largest batch.

The first Thai run (26 batches, `translator` agent) showed where the rest
went, per batch measured from the agents' transcripts: a clean batch was
3 turns, ~50k fresh + ~47k cached input, ~16k output; but the three Haiku
batches, sized by English words while carrying the previous English and
Thai as well, were 59k tokens as the Read tool presents them (it refuses
above 25k), so each agent read in 5 to 7 slices over 13 to 20 turns and
spent 0.6 to 0.8 M tokens, more than the other 23 batches together. And of
a clean batch's read, the English was about a third: ids, keys, JSON
escapes, indentation and the line number the Read tool adds to every line
were the rest. Hence, after that run:

6. batches are sized by an estimate of the tokens the Read tool will
   present (fitted on the 21 recorded reads, within 6% there and up to 20%
   under on the compact format; `estimate_tokens` in translate.py), capped
   at 18k;
7. a batch item is one line: msgid, `type` only when not plain text, and
   for a fuzzy match the previous translation plus a word diff of the
   English change rather than the whole previous English; no id (the
   order is kept in a `.ids.json` sidecar), no empty placeholder;
8. the agent writes a list of strings in item order to `.out.json`; the
   id echoed per item had been ~9% of the output, the most expensive
   tokens. `--apply` rejects a batch whose count differs.

One more measured effect: a Write of 30k output tokens takes longer than
the prompt cache lives, so the final turn re-sends the whole context fresh
(59k tokens on the 120-item, 5,874-word residual batch versus 25k on a
34-item one). Hence a fourth cap, 4,000 English words per batch, which
keeps the output near 20k tokens.

The Polish run (35 batches, 3,336 items, 99.5k words, 15 agents in a
sliding pool, under 15 minutes of translation) then measured, on the same
transcript basis as the Thai run: 791 fresh + 795 cached input tokens per
item against 1,096 + 1,117 for Thai, 28% less, with no batch read in
slices. Two shapes of agent output that `--apply` now tolerates showed
up there: an unescaped quote inside a string (Polish „warstwie" quotes;
repaired at the position the parser reports, however the file is laid
out) and one agent returning 119 strings for 120 items (the batch is
rejected as a whole and redone, which is the point of the count check).

Spanish (34 batches, 3,133 items) came in at 772 fresh + 717 cached per
item and surfaced one more rule: a previous translation that fails the
checker against its own English (a translated code span, typically from
v1) is not offered as a hint, because the agent reuses its wording and
the same rejection then repeats on every retry (three entries, twice).

Measured on a throwaway locale (21 items, 588 words, two batches): about
50k tokens per agent whether it took four tool calls or two, and whether
the rules were read from a file or inlined. The fixed cost is the
general-purpose agent's own context (every tool schema), not the turns.
That is why batches are large, and why `.claude/agents/translator.md` exists:
an agent type with only Read and Write. It could not be measured in the
session that created it (custom agents register at startup); measure it in
the next one before running a full locale. Expected cost for a locale of
the German run's size: roughly 60 batches at 60 to 80k each, 4 to 5 M
tokens with the general-purpose agent, and well under 1 M of the
orchestrator's own turns instead of sixty launch cycles.

## Hard rules

- **Only `translate.py --apply` writes a `msgstr`.** No script, hook or agent
  edits a PO by other means. The PO is the provenance record; v1 lost its
  provenance because a validator wrote to it as a side effect.
- **Never hand-edit a rendered MDX.** It is derived. Fix the PO and render.
- **Do not add a check to a tool to work around a page.** If a page needs a
  rule, it goes into `pre_source()` with a test in `tests/`, or into
  sync-content where the English is produced.
- `MAIN_LOCALES` is the list of locales; the 9 German dialect locales were
  removed from the repository on 2026-09-06.

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
`polib`; for `mdxcheck.mjs` the repository's `node_modules` (`npm ci`). macOS: `brew install po4a gettext`; Debian/Ubuntu: `apt-get install
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
