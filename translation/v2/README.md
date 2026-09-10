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
| `update.py --locale X --json …` | after every sync | `msgmerge --previous` every PO against the new POT, then prints the worklist: fuzzy (near-identical English, old msgid kept as `#\| msgid`) and untranslated entries. A new entry whose English was one line of a paragraph upstream split apart (an intro sentence and its bullets becoming separate entries — 121 of the 127 new de entries on the first real sync) gets that line of the dropped block's translation as a `split-block` hint. |
| `translate.py --locale X --prepare` | after update | Sorts the worklist into tiers: **copy** (pure math, code, images: msgid copied, no model), **split-block** (the hint above, written when it passes the checker, no model), **mechanical** (English changed only punctuation placement or emphasis markers: the same edit applied to the previous translation, checker-verified, no model), **haiku** (fuzzy, similarity ≥ 0.9) and **sonnet** (the rest). The model tiers become `work/X/batch-NNN-<model>.json` (≤ 120 items, ≤ 4,000 English words and ≤ 18k estimated tokens as the Read tool presents it; one id-less item per line, with a word diff and the previous translation for real fuzzy matches) plus a `.ids.json` sidecar per batch and `manifest.json`, which also carries the instructions text for inlining into prompts. |
| `.claude/workflows/translate-locale.js` | to fill the batches | One agent per batch from a sliding pool (`concurrency` in the args, default 5 — but **the harness caps one workflow at ~4 agents in flight whatever you ask for**; measured 2026-09-09 with 20 requested. For real parallelism split the manifest into shards of ~15-40 batches and launch several workflows at once: 6 shards ran 21 agents where one ran 4; at 14 shards the API 429'd about half of all agent turns, so ~8 is the useful ceiling — and a batch reported "failed" after a rate-limited *final* turn has usually already written its `.out.json`, so check the output files before re-running anything), each allowed exactly one Read, one Write (`batch-NNN-<model>.out.json`: a list of strings in item order) and a one-line reply. Run with `Workflow({scriptPath, args: <manifest.json contents>})`; add `"agentType": "translator"` to the args in a session started after `.claude/agents/translator.md` existed (custom agents register at startup). Incomplete batches are listed and rerun with `resumeFromRunId`. |
| `fix.py --locale X --fixes F --prepare` / `--apply` | after a review round | The review fix path. Takes the round's records (or a trimmed fix spec), builds one batch per flagged page — every translated entry as `{msgid, prev_msgstr}`, a `review` field on the entries the reviewer quoted — and `manifest-fix.json` (`task: "fix"`), which the same `translate-locale.js` fills: the agent corrects the flagged entries and copies the rest back. `--apply` is `translate.apply(prefix="fix")`: only entries that changed and pass `check.py` are written, stamped `doq: fixed after review <date>`. A fuzzy entry copied back unchanged by a fix agent **keeps** its fuzzy flag (`apply` infers `confirm_fuzzy=False` from the `fix` prefix): the fix prompt says to copy unflagged entries back verbatim, so an unchanged string is not a confirmation, and clearing the flag would publish a translation of the previous English. |
| `fix.py --locale X --leaks [--case-only] [--write]` | rarely; needs a curated glossary | Deterministic, no model (the v1 page-editing fixer it replaced was deleted 2026-09-10): decapitalises a wrongly-capitalised common noun (`keep_lowercase`) and, without `--case-only`, applies the glossary `translate` rules after a safe determiner. Dry-run unless `--write`; every change goes through `check.py`. Skips fuzzy entries and `Title` entries, and protects link text, emphasis, table cells, proper names (`IBM Circuit`) and acronym expansions (`CLOPS (Circuit Layer Operations Per Second)`) — each of those was a real false positive from the page-based version. **Review its output before `--write`:** the residue still contains title-like strings, and the glossary `translate` rules currently disagree with the "keep these terms in English" list in `translate.py`. |
| `translate.py --locale X --apply` | after the batches are filled | Pairs each `.out.json` with its `.ids.json` by position (a count mismatch rejects that batch), runs `check.py` on every item, writes accepted ones into the PO, lists rejected ones with the reason. Nothing partial is ever written. A page on which the translate path wrote an entry msgmerge had marked fuzzy or empty — retranslated, new, or the old wording confirmed against changed English — loses its `X-Doq-Review-Opus` verdict (kept as `…-Prior`): nobody has read that prose against the English it now faces, so the page is eligible for review again. Copy, split-block and mechanical carry-overs, and review fixes, leave the verdict standing. |
| `render.py --locale X [--out-dir D]` | at build time, or to preview | POT + PO → locale MDX, with the v1 freshness marker so v1 tools keep working during the migration. |
| `check.py` | inside apply and bootstrap | Everything that must survive translation, per entry: inline code, URLs, image paths, inline math (one merge/split tolerated), display math (delimiter count and normalised block content), JSX/HTML tags, table rows, fence lines, `{#anchors}`, MDX comments, and a length ratio that catches fragments. |
| `mdxcheck.mjs` | after render, before commit | Compiles every rendered page with MDX 3 + math + GFM + directives the way Docusaurus does (front matter stripped, heading anchors escaped) and lists the pages acorn rejects. The only check that asks the real parser; the German run needed it twice. |
| `po4a_io.py` | library | Everything above calls into it. Pre-rules, po4a wrappers, PO hygiene. |
| `translation/scripts/check-completeness.py` | any time; free | The **meaning sieve**. Deterministic, whole-corpus, no model: line-shape, number preservation, list-item count, untranslated `title=` captions, a question that became a statement (or the reverse), a translation far shorter than the locale's norm, and a msgstr duplicated onto a neighbouring entry. Scored against the labelled set below: 70.1% recall on known drift defects at 1.32% on known-faithful ones; 5,539 findings corpus-wide (1.23% of 451,652 translated entries). |
| `translation/scripts/gauge-completeness.py` | after the sieve | The **meaning gauge**, layer 2. `--prepare` builds batches of `{msgid, msgstr}` under `work/gauge/<locale>/`; `translate-locale.js` with `task: "gauge"` fills them with a verdict per entry (COMPLETE / MISSING / EXTRA / DIFFERENT / UNSURE); `--collect` reports, `--emit-fixes` writes a `fix.py --fixes` file. **Read-only** — it never writes a msgstr; repairs go through `fix.py` like every other review fix. |
| `translation/scripts/build-eval-set.py` | once per review branch | Turns a finished review round into a labelled set: every msgstr that changed is a known defect, every msgstr an agent read and copied back is known-faithful. This is what makes a completeness check measurable instead of a hunch. Committed, not regenerated — after the branch merges, the diff that produced it is empty. |

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

## Agent failure modes and what the tooling does about them

Measured over the seven locale runs of 2026-09-05 (pt, ja, ko, uk, cs, ro,
id; 33 to 39 batches each). Every item below cost a manual intervention on
every locale until it was folded in; the residue that still needs a hand is
listed last.

| What happens | How often | What handles it now |
|---|---|---|
| An agent replies as if no prompt reached it ("I don't see a task…") and writes nothing | 1–3 batches per locale | `translate-locale.js` retries the batch up to `attempts` (default 3) times with a slightly different prompt, so the retry is a fresh call rather than a cache replay. |
| An agent returns 118 strings for 120 items | once in 7 locales | `--apply` rejects the whole batch (a shift would misplace every later item); the script retries a short batch like a failed one. |
| An agent replies `done 120/120` without writing the file | once in 7 locales | Only `--apply` can see it (the script has no filesystem): the batch shows as *unfilled*; rerun it with the workflow or a direct agent. |
| Unescaped quotes inside a one-line JSON list (Polish „…", Romanian „…", before a comma) | 2 batches per Slavic/Romance locale | `parse_string_lines` escapes the quote the parser trips on, for both parser messages, then falls back to line-by-line. |
| A code span tidied by the agent: `RuntimeJobV2 ` losing its trailing space, the upstream typo `[NoiseLearnerV3` corrected, or a bare product name backticked (`qiskit-ibm-runtime`, `Executor`) | 3–5 entries per locale | `repair_code_spans` restores the source span or drops the added backticks, deterministically, and the entry is accepted only if it then passes the checker. A *translated* span matches neither rule and stays rejected. |
| A sentence with a ``double-backtick`` span could not be translated at all: the checker paired its second backtick with the next single-backtick span and reported the prose between as code | 2 entries per locale | `check.py` parses code spans by backtick runs (CommonMark), so ``x`` and `y` are two spans and the sentence may be reordered. |
| A bare URL inside a code span captured its closing backtick, so any particle attached after the span failed the URL check | 1–2 entries per locale | The bare-URL regex stops at a backtick. |
| A bullet carrying a 60–130 KB base64 `<img>` became a one-item batch the Read tool refused | 2 entries, once per locale | `--prepare` replaces `data:…;base64,…` with `data:DOQ-BASE64-n` in the batch; `--apply` expands it back from the msgid. |
| The English changed only a tag attribute (a Card `href`), or lost a leading `</AccordionItem></Accordion>` when a blank line was inserted upstream; agents kept the old value from the hint | 3–4 entries per locale | Two more mechanical transfers: attribute values (never `title=`) substituted in the previous translation; the same closing tags dropped from its front. No model. |

Still by hand, in order of frequency: a code span the agent translated
(`第二量子化` for `second quantization`), a math span dropped in a long
paragraph, and an upstream `{/* */}` comment moved. Expect two to six
entries per locale after the redo round; the batch files show exactly which.

## The meaning-and-completeness layer

Everything else in this pipeline checks **markup**. `check.py` compares code
spans, math, URLs, tags, anchors, table rows and fence lines byte-for-byte and
bounds length at 0.3x–2.5x; lint, mdxcheck, `check-wrong-language` and
`check-known-mistranslations` work at the same level. None of them asks whether
a translation says what its source says — and a fluent translation of the
*wrong* paragraph breaks none of the structural invariants.

The size of that hole, measured rather than guessed: against the 314 defects
the nine positional-drift review rounds repaired, `check.py` flags **2**.

Two layers close it, cheap first:

1. **The sieve** (`check-completeness.py`) — deterministic, free, corpus-wide.
   Seven subchecks, each scored against the labelled set before it was allowed
   in. It selects entries worth reading; it does not judge them. The two
   newest (`question-mark`, `length-outlier`) were found by scoring candidates
   against the labelled defects the first five missed — the gauge rounds'
   repairs, useless for measuring the sieve, are exactly the right material
   for extending it.
2. **The gauge** (`gauge-completeness.py`) — a model reads `(msgid, msgstr)`
   and returns one verdict. It is the only thing here that can actually read
   for meaning, so the sieve exists to keep its input small. Measured against
   the labelled set with `--eval-set` (both msgstrs of every entry, shuffled
   and unlabelled): **88.9% sensitivity, 0.3% false alarm**. It discriminates
   rather than agreeing with what it is shown — which is what makes any
   calibration number from it worth quoting.

Repairs then go through `fix.py --fixes` → `translate-locale.js` → `--apply`,
the same path as any review round, so they still pass `check.py` and still land
with a provenance comment.

**What the corpus actually looks like** (6,797 entries, 400 per locale,
measured 2026-09-09). Every sampled entry was scored by *both* the sieve and
the gauge, so one sample yields the whole table:

| | gauge: defective | gauge: fine |
|---|---|---|
| **sieve flags** | 11 | 81 |
| **sieve passes** | 22 | 6,683 |

- corpus defect rate **0.49%** [0.35%, 0.68%] → **~2,200 entries**
- sieve precision **12.0%** [6.8%, 20.2%]
- sieve recall **33.3%** [19.8%, 50.4%]

Gauging all 5,507 sieve flags across the 17 locales then found **748 real
defects — 13.6% precision** [12.7%, 14.5%], inside the interval this sample
predicted. The 70.1% recall measured on the labelled eval set (53.8% before the
two subchecks added 2026-09-09) overstates: every positive there is
drift-class, the sieve's best case.

> **A correction, recorded because the wrong numbers were quoted for half a
> day.** An earlier calibration passed no `--findings`, so the "unflagged
> sample" was in fact drawn from *all* entries — making 0.49% the overall
> defect rate, not the miss rate. A "sieve reaches 45%" figure was then derived
> from a 30.8% precision measured on `ro` alone. Both were wrong. Pass
> `--findings` when you want the miss rate, and prefer the 2×2: one sample,
> both numbers, nothing to combine.

Three things worth knowing before you trust a number from this layer:

- **The gauge is blind on purpose.** Batch items carry only `msgid` and
  `msgstr` — never which subcheck fired, never whether the entry was flagged at
  all. `--sample N` mixes in entries the sieve passed. Tell the gauge what the
  sieve thought and it will agree with it, and both the sieve's precision and
  its miss rate stop meaning anything.
- **Recall on the eval set is not recall on the corpus.** The labelled
  positives are defects a *previous* method already found, which is a much
  friendlier question than "what is wrong out there". The calibration sample is
  the honest estimate.
- **A gauge round's repairs cannot score the sieve.** The set is extended
  after every merged review PR (`build-eval-set.py --extend`, 1,147 positives
  and 64,149 negatives as of #524), but a round that read the sieve's own
  flags finds only what the sieve flagged: 82% "recall" on those rows means
  nothing. `--selection sieve` records this in the set, and the scorer counts
  recall on the 314 independently selected rows only. What those rows are good
  for is the next check: one with different blind spots can be scored on the
  whole set.
- **Neither layer sees a fluent, complete, plausible mistranslation.** Right
  shape, right numbers, right length, wrong claim. That still needs a
  domain-competent reader.

Gauge batches live in `work/gauge/<locale>/`, deliberately not in
`work/<locale>/`: `fix.py --prepare` deletes `fix-*.json` there and would take
an outstanding gauge run with it.

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

## Migration state

Every one of the 17 main locales has been through one v2 sync (English
`723fc910`, 2026-09-05/06), and since then:

- **The rendered MDX is derived and not in git.** `i18n/<loc>/…/current/`
  is gitignored; a locale's translation is its `i18n/<loc>/po/` tree. The
  build workflows (`deploy-locales.yml`, `build-locales-pr.yml`) and the
  daily `check-translations.yml` run `render.py` right after the content
  sync, then `populate-locale` for the pages that have no PO; the composite
  action `.github/actions/setup-po4a` installs po4a 0.74 and gettext.
- **To preview a locale locally**: `python3 translation/v2/render.py --locale de`
  then `npx docusaurus start --locale de`. Never edit a rendered page: the
  next render overwrites it. Fix the PO (through `translate.py --apply`) and
  render again.
- **A PR that changes a PO** is linted in `ci.yml` by rendering that page
  from the PR's PO; `build-locales-pr.yml` builds the locale.
- **Staleness** is reported daily by `check-translations.yml`: `msgmerge`
  against the current English, one line per locale (fuzzy, untranslated,
  pages without a PO), an issue when any is non-zero. The merged POs are
  discarded there; the sync procedure above is what commits them.
- **Deleted with this**: `update-translations.py`, `sync-translations.py`,
  `check-translation-freshness.py`, `bootstrap-passage-hashes.py`,
  `update-en-passage-hashes.py`, `advance-baseline.py`, `promote-drafts.py`,
  `check-stale-passages.py`, `remove-stale-paragraph.py`,
  `fix-heading-anchors.py`, `migrate-details-to-accordion.py`, the
  `--check-drift` mode of `validate-translation.py`, `retranslation-prompt.md`,
  and the records `baseline-hashes.json` and `en-passage-hashes.json`. The
  hash helpers the review scripts used from the freshness checker live in
  `translation/scripts/_common.py`.
- **Still v1, deliberately**: `lint-translation.py` and
  `validate-translation.py` work on the rendered pages; they keep working
  because the workflows render before they run. The v1 `translation/status.json`
  was deleted on 2026-09-10 once its last readers (the page-dates plugin, the
  sync PR's freshness report, `STATUS.md`) were moved to the PO files or
  dropped.   *Fixing* a rendered page in place does not work any more: such an edit
  is lost at the next render. The v1 page-editing workflows and fixers were
  deleted on 2026-09-10; every fix goes through `fix.py` (`--fixes` for a
  review finding, `--leaks` for the deterministic glossary pass). The review
  side moved on 2026-09-10: a page's deep-review verdict is the
  `X-Doq-Review-Opus` field of its PO header (below).
- **A page's review verdict lives in its PO header.** `X-Doq-Review-Opus:
  PASS 2026-07-05` is written by `translation/scripts/review-translations.py
  --record-opus` when a review round ships, so the verdict lands in the same
  PR as the fixes and there is no banking step after merge.
  `sample-deep-review.py` (eligibility) and `contributing-status.py`
  (CONTRIBUTING-NOW.md) read the same headers; a page is eligible when it is
  rendered, not a stub, has no fuzzy or empty entry, and — with
  `--exclude-reviewed` — carries no verdict. Only page reads (PASS,
  MINOR_ISSUES, FAIL) are recorded; a repair round's FIXED records are not.
  `X-Doq-Review-Tier3` is the v1 Haiku verdict copied at bootstrap, context only.

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
