export const meta = {
  name: 'opus-deep-review',
  description: 'Tier-4 deep-review spot-check: Opus reads a seeded random sample of translations for fluency, terminology, subtle drift, and pedagogy. Annotates review_opus*; never overwrites the Tier-3 Haiku verdict.',
  whenToUse: 'Run manually when there are spare tokens in a window (5h/weekly). Feed it the output of translation/scripts/sample-deep-review.py via args. Rotate the seed each run to walk a fresh random sample.',
  phases: [
    { title: 'Deep review', detail: 'one Opus agent per sampled file', model: 'opus' },
  ],
}

// ---------------------------------------------------------------------------
// Sample input: the JSON payload from sample-deep-review.py, i.e.
//   { seed, per_locale, eligible_total, sample_size, files: [
//       { locale, rel, section, lines, locale_name, register, tier3_verdict }, ... ] }
//
// Two ways to supply it:
//  (A) via args — Workflow({ name:"opus-deep-review", args: <parsed JSON> }).
//  (B) via an embedded SAMPLE constant — set SAMPLE below to the parsed JSON.
//      Use this when invoking by scriptPath, where large args may not pass
//      through. The make-opus-run.py helper bakes the sample in for you:
//        python3 translation/scripts/make-opus-run.py --sample /tmp/opus-sample.json \
//            --out /tmp/opus-run.js   # then run that file via scriptPath
// ---------------------------------------------------------------------------

const SAMPLE = null  // ← replaced by make-opus-run.py, or leave null and use args

const input = (args && Array.isArray(args.files) && args.files.length) ? args : SAMPLE

if (!input || !Array.isArray(input.files) || input.files.length === 0) {
  log('ERROR: no sample. Pass it via args, or bake it into SAMPLE (see make-opus-run.py).')
  return { error: 'no sample provided', expected: 'args = output of sample-deep-review.py' }
}

const files = input.files
const seed = input.seed ?? 'unseeded'
log(`Tier-4 Opus deep-review — ${files.length} file(s), seed=${seed}, pool=${input.eligible_total ?? '?'}`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['locale', 'file', 'verdict', 'issues', 'editor_note'],
  properties: {
    locale: { type: 'string' },
    file: { type: 'string' },
    verdict: { enum: ['PASS', 'MINOR_ISSUES', 'FAIL'] },
    issues: { type: 'integer' },
    // minLength catches one-word placeholders; a concise PASS proof-of-read
    // sentence clears 40 while keeping the 80%-PASS output (and status.json /
    // notification) small. FAIL/MINOR carry the detail in the note + examples.
    editor_note: { type: 'string', minLength: 40 },
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
  // In "drift" mode the sample is pre-filtered to be low-leakage (0 leaks under
  // --leak-clean, or <=N under --max-leaks — a couple of kept-English terms that
  // a separate deterministic sweep handles), so the irreducible question is:
  // does it MISLEAD? Sharpen the agent onto semantic drift + hallucination and
  // tell it not to spend the read re-confirming cosmetic polish or leaks.
  const driftFocus = f.focus === 'drift' ? `

FOCUS FOR THIS RUN: this file was PRE-FILTERED to be low-leakage — any
capitalized-English kept terms (e.g. Gate/Circuit/Qubit) are handled by a
separate deterministic sweep, so do NOT hunt for leaks. Spend your read on
MEANING: whether the translation would MISLEAD a learner — semantic drift
(inverted condition/negation, swapped quantity, softened/strengthened claim,
example that no longer matches its setup, dropped caveat) or hallucination
(a fluent sentence asserting something NOT in the source). Read slowly,
paragraph against paragraph, especially the last 40%. Naturalness and
terminology-consistency slips are still worth reporting, but in this mode they
are MINOR_ISSUES at most — they must never drive a FAIL on their own. Apply the
VERDICT rubric below exactly as written; this focus note does not override it.` : ''
  return `You are a senior native-speaker technical editor for ${f.locale_name} (${f.locale}), reviewing Qiskit / quantum-computing documentation in the doQumentation repo (root: the current working directory).${driftFocus}

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

VERDICT — apply ONE discriminator, in this order; first match wins. The single
question is: WOULD THIS MISLEAD A LEARNER?
- FAIL = yes, it would mislead. Semantic drift (inverted condition/negation,
  swapped quantity, softened/strengthened claim, example that no longer matches
  its setup, dropped caveat), a hallucinated claim, a domain term rendered so
  wrongly it teaches a FALSE concept (e.g. "variational" rendered as
  "permutational"), or prose that reads as raw MT throughout. Judge the DEFECT,
  not the count: one misleading sentence IS a FAIL.
- MINOR_ISSUES = no, it does not mislead, but a native technical editor would
  still change something: a calque or stiff/robotic phrasing, an imperfect but
  recognizable term, the same term rendered inconsistently within the file, a
  dropped qualifier, a formal-register slip.
- PASS = no, it does not mislead, AND there is nothing a native technical editor
  would change: faithful meaning, correct and consistent terminology, teaches as
  well as the English.

CALIBRATION (these bind — do not silently re-scale them):
- A single imperfect-but-recognizable term is MINOR, never FAIL. A term rendered
  so wrongly the learner would form a false belief is FAIL.
- Within-file term inconsistency is MINOR, however many times it occurs — UNLESS
  the split makes the concept unidentifiable, which is FAIL.
- Stiffness, calques and translationese are MINOR, never FAIL on their own.
- Style/word-choice preferences where the existing rendering is defensible are
  NOT a defect at all: PASS. Do not nitpick a defensible choice.

Return the structured object: locale="${f.locale}", file="${f.rel}", your verdict, an integer issue count, an editor_note, and up to a few concrete examples. Do NOT edit any file. Do NOT touch git or status.json.

editor_note REQUIREMENTS (it must stand alone; length scales with the verdict):
- On PASS: ONE concise sentence that NAMES a concrete specific from the file — an actual rendered term or passage — to prove you read it (e.g. "Faithful and native; core terms correct/consistent (qubit→كيوبت, transpile→...)."). Keep it short — do NOT write a paragraph of praise; we don't act on PASS notes.
- On FAIL/MINOR: 2-4 sentences stating exactly WHAT is wrong (e.g. "‘Hamiltonian’ is rendered three ways: X, Y, Z"), naming the actual terms/passages, alongside the concrete examples below. This is the deliverable we act on — make it specific and self-contained.
- FORBIDDEN: placeholder or filler text. Never return "x", "placeholder", "duplicate", "n/a", "see examples", "ok", or an empty/one-word note. Such a note is a failed deliverable — write the real summary instead.`
}

// A note is a "placeholder" if it's filler rather than a real editorial read.
// The schema minLength catches short ones; this catches longer filler the
// model might still emit.
const PLACEHOLDER_RE = /^(x+|placeholder|duplicate|n\/?a|ok|tbd|see examples?|none|todo)\.?$/i
function isPlaceholderNote(note) {
  const n = (note || '').trim()
  return n.length < 80 || PLACEHOLDER_RE.test(n)
}

// One Opus agent per file, all concurrent (capped by the runtime). Each returns
// a validated verdict object; a skipped/errored agent yields null.
phase('Deep review')
// Throttle to <=7 concurrent agents. The 5h session limit can hit mid-run; with
// a small in-flight batch only those <=7 are lost on a hit, and every completed
// batch is preserved (resume re-runs only the failures). Opus reads are large,
// so a big fan-out exhausts the window fast — keep the live set small.
const BATCH = 7
const verdicts = []
for (let i = 0; i < files.length; i += BATCH) {
  const slice = files.slice(i, i + BATCH)
  log(`Deep-review batch ${Math.floor(i / BATCH) + 1}: files ${i + 1}-${i + slice.length} of ${files.length}`)
  const v = await parallel(slice.map((f) => () =>
    agent(promptFor(f), {
      label: `opus:${f.locale}/${f.rel.split('/').pop()}`,
      phase: 'Deep review',
      model: 'opus',
      schema: SCHEMA,
    }).then((v) => (v ? { ...v, _tier3: f.tier3_verdict } : null))
  ))
  verdicts.push(...v)
}

let results = verdicts.filter(Boolean)

// Backstop: re-run any agent whose editor_note is a placeholder that slipped
// past the schema. The verdict/examples were real; only the summary failed —
// so re-ask for THIS file with an explicit correction, once.
const byKey = (r) => `${r.locale}/${r.file}`
const needNote = results.filter((r) => isPlaceholderNote(r.editor_note))
if (needNote.length) {
  log(`⟳ ${needNote.length} file(s) returned a placeholder editor_note — re-running for a real summary.`)
  const fileByKey = new Map(files.map((f) => [`${f.locale}/${f.rel}`, f]))
  const redone = await parallel(needNote.map((r) => () => {
    const f = fileByKey.get(byKey(r))
    if (!f) return Promise.resolve(null)
    const prompt = promptFor(f) +
      `\n\nIMPORTANT: a prior attempt returned a placeholder editor_note ("${r.editor_note}"). That is a failed deliverable. Re-read the file and return your real verdict with a full 2-4 sentence editor_note that names the specific terms and passages.`
    return agent(prompt, {
      label: `opus-redo:${f.locale}/${f.rel.split('/').pop()}`,
      phase: 'Deep review',
      model: 'opus',
      schema: SCHEMA,
    }).then((v) => (v ? { ...v, _tier3: f.tier3_verdict } : null))
  }))
  // Replace originals with any successful redo that now has a real note.
  const fixedByKey = new Map()
  for (const r of redone.filter(Boolean)) {
    if (!isPlaceholderNote(r.editor_note)) fixedByKey.set(byKey(r), r)
  }
  if (fixedByKey.size) {
    results = results.map((r) => fixedByKey.get(byKey(r)) || r)
    log(`  ✓ ${fixedByKey.size} placeholder note(s) replaced with a real summary.`)
  }
  const stillBad = results.filter((r) => isPlaceholderNote(r.editor_note)).length
  if (stillBad) log(`  ⚠ ${stillBad} note(s) still thin after retry — examples[] still carry the findings.`)
}

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
