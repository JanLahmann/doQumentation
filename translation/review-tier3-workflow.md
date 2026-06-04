# Tier-3 linguistic review — efficient workflow

Distilled from a 14-wave / ~1,035-file run across pl, cs, ms. Goal: same review
coverage at a fraction of the tokens, with consistent verdicts.

## Pipeline

```
prefilter (gate + hints)  →  build-batches (line-balanced)  →  N Haiku agents
        →  merge verdict JSONs  →  --record-review --from-json  →  commit once/wave
```

1. **Triage (free, deterministic).**
   `python translation/scripts/review-prefilter.py --locale <L> --unreviewed-only --json /tmp/<L>_triage.json`
   - Hard-gates STALE/UNKNOWN and validation/lint-failing files (`SKIP_*`) so no
     tokens are wasted on un-reviewable files.
   - Attaches per-file **hint flags** and marks `priority` files (structural
     content drift). Hints are pointers, **not verdicts** — see "What it is not".

2. **Build balanced batches.**
   `python translation/scripts/review-build-batches.py --triage /tmp/<L>_triage.json --agents 5 --max-lines 1800`
   - Bin-packs by line count (not file count) → even agent runtime, no 760k
     outliers, less session-limit risk.
   - Priority files first; writes `/tmp/review/<L>_<wave>_b<N>.json` and prints a
     launch recipe.

3. **Launch agents — explicitly on Haiku.**
   Each agent gets `review-tier3-rubric.md` + its batch file. **Pin the model:
   `Agent(..., model="haiku")`.** Do not rely on the default — an un-pinned
   `general-purpose` agent inherits the *parent's* model (Opus), which is what
   the first run accidentally did. Haiku is the validated review model (8/8 vs
   ground truth); Opus adds cost, not accuracy.

4. **Agents return a one-line tally only**; verdicts go to `*_verdicts.json`.
   (The full per-file table is not needed in the orchestrator's context — the
   JSON is the deliverable. This alone saved the bulk of orchestration tokens.)

5. **Merge + record once per wave** (single writer — avoids status.json races):
   `cat /tmp/review/<L>_<wave>_b*_verdicts.json` → merge to one array →
   `review-translations.py --record-review --from-json -`. Commit once.

## What the pre-filter is — and is NOT (validated on ms, 422 files)

It is a **gate + prioritizer + hint provider**, not a classifier:
- Per-flag precision for "is this a FAIL?" was 17%–67%; `INCONSISTENT_GLOSSARY`
  fired on ~46% of files at 29% precision. So it **never auto-records a verdict
  and never skips a fresh file.**
- Its wins are real but bounded: (a) reliable freshness/validation/lint gating,
  (b) hints that make the Haiku pass faster and more targeted, (c) a single
  scripted inconsistent-glossary definition the agents apply uniformly (this is
  what removes the reviewer-to-reviewer verdict drift we saw on ms).
- `SAMPLE` (stub/index) files were ~78% PASS — low-stakes but *not* zero-risk,
  so review a sample, don't blanket-skip.

## Where the token savings actually come from

| change | mechanism |
|--------|-----------|
| Haiku, pinned | review on Haiku not inherited-Opus — biggest per-token win |
| one-line tally | stops verbose agent tables flowing into orchestrator context |
| externalized rubric | 3-line agent prompt vs re-embedding a ~600-token rubric ×5 ×N |
| line-balanced batches | even runtime; fewer session-limit stalls/retries |
| prefilter gate | zero tokens spent on STALE/lint-failing/un-reviewable files |
| sample SAMPLE tier | don't exhaustively review stubs |
| commit once/wave | fewer push round-trips |

## Consistency / fixes

- **Inconsistent-glossary** is now a precise rule (rubric): consistent term use
  = PASS; mixing target word + capitalized English for the *same* concept ≥3×
  = FAIL; 1–2 isolated = MINOR fix. No more per-agent guessing.
- **MINOR auto-fixes**: agents fix isolated register/typos/leaks in place
  (lint + freshness gated). A blanket scripted register pass (e.g. ms
  `kamu`→`anda`) was deliberately *not* automated — `\bkamu\b` is safe-ish but
  context (code, quotes, proper nouns like "kamus"=dictionary) makes a blind
  regex edit risky. Detection is in the prefilter (`REGISTER_*` flags); the edit
  stays with a reviewer.

## Sampling strategy

After ~2 waves per locale the defect classes repeat (same upstream MT). Beyond
that, exhaustive review has diminishing returns: review a representative sample
per (locale × section), characterize the classes, and let the prefilter's
structural flags catch the rest. The first wave or two per locale is where the
value is.

## Per-locale notes

- **pl / cs**: course content has systematic dropped-trailing-content and
  (cs especially) pervasive leaked-English; many FAILs are shared upstream
  defects → candidates for retranslation, not line-level review.
- **ms**: cleaner; dominant issues are `kamu` register and inconsistent
  litar/Circuit leakage. Cross-language (Indonesian) contamination appears.
- **de / es (next)**: their 33 unreviewed files are **validation=PASS but
  lint not yet recorded** — they just need a lint run, then they enter the
  review queue. Not STALE, not a re-stamp. Run:
  `python translation/scripts/lint-translation.py --locale de` (then es),
  re-run the prefilter, and they move from `SKIP_LINT` → `REVIEW`.

## Tier-4 — Opus deep-review spot-check (manual, optional)

Tier-3 (Haiku) is the exhaustive pass. **Tier-4 is a small, seeded-random,
manually-triggered Opus audit on top of it** — for the quality a fast checklist
rubber-stamps: naturalness/fluency, cross-file terminology correctness, subtle
fluent-but-wrong drift, pedagogical register. Rubric:
[`review-tier4-opus-prompt.md`](review-tier4-opus-prompt.md). Run it only when a
window has spare tokens (5h / weekly).

It **annotates, never overwrites**: verdicts land in separate `review_opus*`
keys in `status.json`; the Tier-3 `review` field is untouched. A Tier-3-PASS /
Opus-FAIL disagreement is the *signal*, surfaced explicitly by both the workflow
and `review-translations.py --progress`.

Run it in three steps:

```bash
# 1. Draw a reproducible stratified sample (uniform over fresh, non-stub files;
#    round-robin across the 17 main locales × sections). Rotate --seed each run.
python3 translation/scripts/sample-deep-review.py \
    --per-locale 5 --seed 20260604 --out /tmp/opus-sample.json

# 2. Run the workflow, passing the sample JSON as args (Opus agents, one/file):
#    Workflow({ name: "opus-deep-review", args: <parsed contents of /tmp/opus-sample.json> })
#    It returns a verdict tally + the actionable Opus-harsher-than-Tier-3 list,
#    and a `records` array to persist.

# 3. Save records to translation/reviews/opus-<seed>.json, then record them:
python3 translation/scripts/review-translations.py \
    --record-opus --from-json translation/reviews/opus-20260604.json
```

`--per-locale` controls cost: 2 ≈ 34 files (quick, ~one 5h window), 5 ≈ 85
(standard), 10 ≈ 170 (deep). A fresh `--seed` walks a new random sample, so
repeated runs accumulate deep coverage without ever needing an exhaustive Opus
pass. **Note**: Opus here is justified ONLY by the deeper task — for the Tier-3
4-check rubric, Haiku scored 8/8 vs ground truth and Opus adds cost, not
accuracy. Don't use Tier-4 to re-run Tier-3.
