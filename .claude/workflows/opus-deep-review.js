export const meta = {
  name: 'opus-deep-review',
  description: 'Tier-4 deep-review spot-check: Opus reads a seeded random sample of translations for fluency, terminology, subtle drift, and pedagogy. Annotates review_opus*; never overwrites the Tier-3 Haiku verdict.',
  whenToUse: 'Run manually when there are spare tokens in a window (5h/weekly). Feed it the output of translation/scripts/sample-deep-review.py via args. Rotate the seed each run to walk a fresh random sample.',
  phases: [
    { title: 'Deep review', detail: 'one Opus agent per sampled file', model: 'opus' },
  ],
}

// ---------------------------------------------------------------------------
// args: the JSON payload from sample-deep-review.py, i.e.
//   { seed, per_locale, eligible_total, sample_size, files: [
//       { locale, rel, section, lines, locale_name, register, tier3_verdict }, ... ] }
// Produce it first:
//   python3 translation/scripts/sample-deep-review.py --per-locale 5 --seed <S> --out /tmp/opus-sample.json
//   then pass the file's parsed contents as args.
// ---------------------------------------------------------------------------

if (!args || !Array.isArray(args.files) || args.files.length === 0) {
  log('ERROR: args.files is empty. Run sample-deep-review.py and pass its JSON as args.')
  return { error: 'no sample provided', expected: 'args = output of sample-deep-review.py' }
}

const files = args.files
const seed = args.seed ?? 'unseeded'
log(`Tier-4 Opus deep-review — ${files.length} file(s), seed=${seed}, pool=${args.eligible_total ?? '?'}`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['locale', 'file', 'verdict', 'issues', 'editor_note'],
  properties: {
    locale: { type: 'string' },
    file: { type: 'string' },
    verdict: { enum: ['PASS', 'MINOR_ISSUES', 'FAIL'] },
    issues: { type: 'integer' },
    editor_note: { type: 'string' },
    examples: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          line_approx: { type: 'string' },
          type: { enum: ['Naturalness', 'Terminology', 'Drift', 'Pedagogy', 'Register'] },
          source: { type: 'string' },
          translation: { type: 'string' },
          why: { type: 'string' },
          suggested: { type: 'string' },
        },
      },
    },
  },
}

function promptFor(f) {
  return `You are a senior native-speaker technical editor for ${f.locale_name} (${f.locale}), reviewing Qiskit / quantum-computing documentation in the doQumentation repo (root: the current working directory).

Read BOTH files in full:
  English source:  docs/${f.rel}
  ${f.locale_name} translation:  i18n/${f.locale}/docusaurus-plugin-content-docs/current/${f.rel}

A fast automated pass already checked register, word-salad, verbosity, and basic accuracy — assume those mechanical checks passed (its verdict was: ${f.tier3_verdict}). Your job is the DEEPER editorial judgment a checklist cannot make. Compare paragraph by paragraph. Ignore code blocks, math, JSX, URLs, image paths, and heading anchors — judge ONLY the prose.

DEEP CHECKS (this is why you, Opus, are here — go beyond the surface):
1. NATURALNESS / FLUENCY — does it read like a ${f.locale_name}-speaking quantum engineer WROTE it, or like fluent machine translation? Flag translationese, calqued English syntax, stiff/robotic phrasing a native technical writer would never use — even when grammatically correct.
2. TERMINOLOGY — for core domain terms (qubit, gate, circuit, observable, expectation value, measurement, entanglement, superposition, Hamiltonian, ansatz, transpile, backend, shots, Sampler/Estimator): is the chosen rendering the CORRECT conventional ${f.locale_name} domain term (not a literal-but-wrong word, not an over-translation of a term the field keeps in English), and is it used CONSISTENTLY within this file? A confidently-correct, consistent convention is GOOD — do not nitpick a defensible choice.
3. SUBTLE SEMANTIC DRIFT — a sentence can be grammatical, natural, and STILL say something the English does not: inverted condition/negation, swapped quantity, softened/strengthened claim, an example that no longer matches its setup, a dropped caveat. Read for MEANING.
4. PEDAGOGICAL REGISTER — this is teaching material. Does the translation EXPLAIN as clearly as the English (same intuition, same emphasis)? Flag where nuance flattened or an analogy broke.
Also confirm the informal register convention holds: ${f.register}. A few formal slips is MINOR, not FAIL.

NOT a defect (never flag): the injected "Post-course survey / Was this page helpful" note block ("> **Note:** This survey is provided by IBM Quantum … open a GitHub issue") — doQumentation injects this in place of IBM's English-only feedback form.

VERDICT (independent of the prior automated verdict; first match wins):
- FAIL = any semantic drift/mistranslation, wrong domain terminology, ≥3 within-file term inconsistencies, or prose that reads as raw MT throughout.
- MINOR_ISSUES = isolated naturalness/terminology/register slips that do not mislead.
- PASS = native, well-edited technical prose; correct consistent terminology; faithful meaning; teaches as well as the English.

Return the structured object: locale="${f.locale}", file="${f.rel}", your verdict, an integer issue count, an editor_note of 1-3 sentences on fluency+terminology (FILL THIS IN EVEN ON PASS — it is the signal a fast pass never produces), and up to a few concrete examples. Do NOT edit any file. Do NOT touch git or status.json.`
}

// One Opus agent per file, all concurrent (capped by the runtime). Each returns
// a validated verdict object; a skipped/errored agent yields null.
phase('Deep review')
const verdicts = await parallel(files.map((f) => () =>
  agent(promptFor(f), {
    label: `opus:${f.locale}/${f.rel.split('/').pop()}`,
    phase: 'Deep review',
    model: 'opus',
    schema: SCHEMA,
  }).then((v) => (v ? { ...v, _tier3: f.tier3_verdict } : null))
))

const results = verdicts.filter(Boolean)

// Summarize: verdict tally + the actionable disagreements (Opus harsher than Tier-3).
const rank = { PASS: 0, MINOR_ISSUES: 1, FIXED: 1, FAIL: 2 }
const tally = {}
const disagreements = []
const fails = []
for (const r of results) {
  tally[r.verdict] = (tally[r.verdict] || 0) + 1
  if (r.verdict === 'FAIL') fails.push(`${r.locale}/${r.file}`)
  const t3 = r._tier3
  if (t3 in rank && r.verdict in rank && rank[r.verdict] > rank[t3]) {
    disagreements.push(`${r.locale}/${r.file}: tier3=${t3} → opus=${r.verdict}`)
  }
}

log(`Done. ${results.length}/${files.length} reviewed — ` +
  Object.entries(tally).map(([k, v]) => `${k}=${v}`).join(', '))
if (disagreements.length) {
  log(`⚠ ${disagreements.length} disagreement(s) where Opus is harsher than Tier-3 (the actionable signal):`)
  disagreements.forEach((d) => log(`   ${d}`))
}

// Strip the internal _tier3 marker from the records the user will persist.
const records = results.map(({ _tier3, ...rest }) => rest)

return {
  seed,
  reviewed: results.length,
  requested: files.length,
  tally,
  fails,
  disagreements,
  // Persist this array, then record it:
  //   write to translation/reviews/opus-<seed>.json, then
  //   python3 translation/scripts/review-translations.py --record-opus --from-json translation/reviews/opus-<seed>.json
  records,
}
