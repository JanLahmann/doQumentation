# Tier-4 deep review — Opus rubric (spot-check, NOT the bulk pass)

This is a **deliberately different task** from the Tier-3 Haiku review
(`review-prompt.md` / `review-tier3-rubric.md`). Read this section before
using it, or you will waste Opus tokens duplicating a cheaper pass.

## When this applies — and when it does NOT

- **Tier-3 (Haiku)** is the validated *exhaustive* pass. For the 4-check
  rubric (register / word-salad / verbosity / accuracy) Haiku scored 8/8 vs
  ground truth — Opus adds **no accuracy gain there, only cost**. Do NOT run
  Opus to re-do that checklist.
- **Tier-4 (Opus, this file)** is a *small, random, manually-triggered
  spot-check*. It exists to judge the things a fast checklist rubber-stamps:
  **naturalness, cross-file terminology consistency, subtle semantic drift,
  and pedagogical register**. It is a sampling audit, not full coverage.
- It runs only when there are spare tokens in a window (5h / weekly), driven
  by the `opus-deep-review` workflow. It **annotates** (`review_opus*` keys);
  it NEVER overwrites the Tier-3 `review` verdict. A Haiku-PASS / Opus-FAIL
  disagreement is a *signal*, not an error — it is the whole point.

## Model

**Pin Opus** (`Agent(..., model="opus")`). The justification for Opus here is
NOT the 4-check rubric (Haiku is fine for that) — it is the deep editorial read
below, which a fast model cannot do. If you find yourself only checking the
4 mechanical items, you are using the wrong tier.

## What the agent receives

- One file to read in full: the EN source `docs/<REL>` and the translation
  `i18n/{LOCALE}/docusaurus-plugin-content-docs/current/<REL>`.
- The per-locale register line (substituted into `{REGISTER}`).
- The file's current Tier-3 verdict (`{TIER3_VERDICT}`) — context only; you are
  forming an *independent* opinion, not validating Haiku's.

## Prompt

```
You are a senior native-speaker technical editor for {LOCALE_NAME} ({LOCALE}),
reviewing Qiskit / quantum-computing documentation. A fast automated pass has
ALREADY checked this file for register, word-salad, verbosity, and basic
accuracy — assume those mechanical checks passed. Your job is the deeper
editorial judgment a checklist cannot make. Read the WHOLE file slowly,
comparing the English source to the translation paragraph by paragraph.

Ignore code blocks, math, JSX, URLs, image paths, and heading anchors — those
are validated separately. Judge ONLY the prose.

DEEP CHECKS (this is what Opus is here for — go beyond the surface):

1. NATURALNESS / FLUENCY
   Does this read like a {LOCALE_NAME}-speaking quantum engineer WROTE it, or
   like fluent machine translation? Flag: translationese, calqued English
   syntax, unnatural word order, stiff or robotic phrasing that a native
   technical writer would never use — even when it is grammatically correct.

2. TERMINOLOGY (domain correctness + consistency)
   For the core domain terms — qubit, gate, circuit, observable, expectation
   value, measurement, entanglement, superposition, Hamiltonian, ansatz,
   transpile, backend, shots, primitive (Sampler/Estimator) — judge:
   (a) Is the chosen {LOCALE_NAME} rendering the CORRECT, conventional domain
       term (not a literal but wrong word, not an over-translation of a term
       the field keeps in English)?
   (b) Is it used CONSISTENTLY within this file? (Cross-file consistency is
       reported separately; within-file mixing of the same concept is a flag.)
   A confidently-correct, consistent convention is GOOD — do not nitpick a
   defensible choice. Flag genuinely WRONG or INCONSISTENT terminology.

3. SUBTLE SEMANTIC DRIFT (the dangerous, fluent kind)
   A sentence can be grammatical, natural, and still say something the English
   does NOT. Flag fluent-but-wrong: inverted conditions/negations, a swapped
   quantity, a softened or strengthened claim, an example that no longer
   matches its setup, a dropped caveat. Read for MEANING, not surface match.

4. PEDAGOGICAL REGISTER
   This is teaching material. Does the translation EXPLAIN as clearly as the
   English — same intuition, same emphasis, same "aha"? Flag where nuance has
   flattened, an analogy broke, or an explanatory sentence became a flat
   restatement that no longer teaches.

Also confirm the informal register convention holds: {REGISTER}. (A handful of
formal slips is MINOR, not FAIL — the bulk pass already covers this; only note
it if pervasive.)

NOT defects (never flag): the injected "Post-course survey / Was this page
helpful" note block (`> **Note:** This survey is provided by IBM Quantum …
open a GitHub issue`) — doQumentation injects this in place of IBM's English-
only feedback form. The GitHub-issues / feedback.ibm.com link is expected.

VERDICT (independent of the prior automated verdict; first match wins):
- FAIL  = any semantic drift/mistranslation, wrong domain terminology, ≥3
          within-file term inconsistencies, or prose so unnatural it reads as
          raw MT throughout.
- MINOR_ISSUES = isolated naturalness/terminology/register slips that a native
          editor would smooth but that do not mislead the reader.
- PASS  = reads like native, well-edited technical prose; correct, consistent
          terminology; faithful meaning; teaches as well as the English.

OUTPUT — return EXACTLY this JSON object (one object, this file only):
{
  "locale": "{LOCALE}",
  "file": "{REL}",
  "verdict": "PASS | MINOR_ISSUES | FAIL",
  "issues": <int count of distinct problems>,
  "editor_note": "<1-3 sentences: your overall editorial read of fluency and
     terminology — fill this in EVEN ON PASS; this is the signal a fast pass
     never produces>",
  "examples": [
    {"line_approx":"Line NN","type":"Naturalness|Terminology|Drift|Pedagogy",
     "source":"<EN>","translation":"<TR>","why":"<brief>","suggested":"<fix>"}
  ]
}
The JSON object is the deliverable. Do NOT edit the file. Do NOT touch git or
status.json. After the JSON, reply with ONE line: "<LOCALE>/<REL>: <VERDICT>
(<n> issues)".
```

## Register sections (paste into `{REGISTER}`)

Reuse the per-language register table from `review-prompt.md`. One-liners:

| locale | register |
|--------|----------|
| de | informal "du" — not Sie/Ihnen/Verwenden Sie |
| es | informal "tú" — not usted/consulte/utilice/ejecute |
| fr | informal "tu" — not vous/votre/veuillez |
| it | informal "tu" — not Lei/consulti/utilizzi |
| pt | casual "você" — not o senhor/a senhora/vossa |
| uk | informal "ти" — not Ви/Вам/Ваш |
| pl | informal "ty" — not Pan/Pani/Państwo/proszę uprzejmie |
| cs | informal "ty" — not Vy/Vám/Vás/račte (Chceš-li is fine) |
| ro | informal "tu" — not dumneavoastră/dvs./vă rog |
| ja | polite desu/masu, no keigo — not ございます/いただく/ご覧ください |
| ko | 해요체 — not honorific/humble (하십시오체, 드리) |
| ar | informal anta/anti — not formal antum |
| he | informal — not biblical/over-formal register |
| th | casual — no polite particles ครับ/ค่ะ |
| ms | standard "anda" — casual "kamu" is a MINOR, not FAIL |
| id | "Anda"/"kamu" — not bapak/ibu deferential |
| tl | casual — no po/opo formality |

## How verdicts are recorded

The `opus-deep-review` workflow writes all verdicts to
`translation/reviews/opus-<seed>.json` and prints a `--record-review` recipe.
Recording stores them under **separate** `review_opus`, `review_opus_issues`,
`review_opus_note`, `reviewed_opus` keys in `status.json` — the Tier-3 `review`
field is left untouched. Disagreements (Tier-3 PASS vs Opus FAIL) are listed
explicitly in the workflow's final summary as the actionable output.
