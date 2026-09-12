export const meta = {
  name: 'refute-fails',
  description: 'Refutation gauge for a review round: two independent Opus readers try to refute each FAIL from the cited passages; a third reads only when they disagree. A FAIL stands when the majority cannot refute it.',
  whenToUse: 'After a deep-review round, before its fix wave. Bake the FAILs in with translation/scripts/make-gauge-run.py, then run by scriptPath.',
  phases: [{ title: 'Refute', detail: '2 Opus readers per FAIL, a third on disagreement' }],
}

// ---------------------------------------------------------------------------
// Input: the payload from make-gauge-run.py, i.e.
//   { locale, locale_name, pair_dir, fails: [
//       { file, editor_note, examples: [{ type, source, translation, why, entry }],
//         passages: [{ entry, en, tr }] }, ... ] }
// Baked in as FAILS below (workflow scripts read no files); args wins when given.
//
// Why passages, not files: the previous gauge sent three readers per FAIL to
// Read both full pages — about 1M tokens per FAIL page on 2026-09-12 — to
// overturn roughly half of them. The cited entries with two neighbours on
// each side are what a refuter actually checks; the paired prose file is
// named for the rare case where more context is needed.
// ---------------------------------------------------------------------------

const BAKED = null  // ← replaced by make-gauge-run.py
const input = (args && Array.isArray(args.fails) && args.fails.length) ? args : BAKED
if (!input || !Array.isArray(input.fails) || !input.fails.length) {
  log('ERROR: no FAILs. Bake them with make-gauge-run.py or pass them via args.')
  return { error: 'no fails provided' }
}
const FAILS = input.fails
const LOC = input.locale
const NAME = input.locale_name || LOC
log(`refutation gauge — ${FAILS.length} FAIL(s) on ${LOC}`)

const SCHEMA = { type: 'object', additionalProperties: false, required: ['file', 'refuted', 'reason'],
  properties: { file: { type: 'string' }, refuted: { type: 'boolean' }, reason: { type: 'string', minLength: 20 },
                misleading_examples: { type: 'array', items: { type: 'integer' } } } }

function prompt(f, k) {
  const passages = (f.passages || []).map((p) =>
    `[${p.entry}]${p.cited ? ' (cited)' : ''}\nEN: ${p.en}\n${LOC.toUpperCase()}: ${p.tr}`).join('\n\n')
  return `You are auditing ONE verdict of a ${NAME} translation review for doQumentation (IBM Quantum's Qiskit docs mirrored in ${NAME}). A reviewer marked this page FAIL, meaning at least one passage would MISLEAD a learner (wrong claim, inverted meaning, wrong term that teaches a false concept). Your job is to try to REFUTE that: decide whether the cited passages really mislead.

Page: ${f.file}

Reviewer's note:
${f.editor_note}

Reviewer's examples (index: type | source | translation | why):
${f.examples.map((e, i) => `${i}: ${e.type} | EN: ${e.source} | ${LOC.toUpperCase()}: ${e.translation} | ${e.why}`).join('\n')}

The passages below are the cited entries of the page with their neighbours, as the PO holds them (English, then the ${NAME} as it stands now). They are the evidence; judge from them. Only if a passage genuinely cannot be judged without more of the page, Read ${f.pair || 'the paired prose file named in the passages'} once — otherwise read nothing and run nothing.

${passages}

Rules: A FAIL stands if ANY cited passage genuinely misleads a learner (wrong direction, wrong quantity, inverted instruction, a term that names a different concept). Awkward wording, calques, inconsistency or a dropped nuance that the surrounding text repairs do NOT justify a FAIL. When uncertain, refute (refuted: true). This is reader ${k}; judge independently.

Return the structured object: file="${f.file}", refuted (true if NO cited passage misleads), reason (which passages you checked and why), misleading_examples (indices of examples that DO mislead, empty when refuted).`
}

const QUOTA_RE = /hit your (session|usage|weekly) limit|usage limit reached|resets? \d/i
let aborted = null
const AGENT_TYPE = input.agentType || undefined
function refute(f, k) {
  if (aborted) return Promise.resolve({ file: f.file, refuted: null, reason: 'skipped: ' + aborted, k })
  return agent(prompt(f, k), { label: `refute ${f.file.split('/').pop()} #${k}`, phase: 'Refute', model: 'opus',
                               effort: 'medium', schema: SCHEMA, ...(AGENT_TYPE ? { agentType: AGENT_TYPE } : {}) })
    .then((r) => ({ ...(r || { file: f.file, refuted: null, reason: 'no result' }), k }))
    .catch((e) => {
      const msg = String(e && e.message || e)
      if (QUOTA_RE.test(msg) && !aborted) { aborted = msg.slice(0, 120); log(`⛔ quota: ${aborted}`) }
      return { file: f.file, refuted: null, reason: msg.slice(0, 200), k }
    })
}

phase('Refute')
// Two readers each; the third reads only when the two disagree (or one
// errored). Same majority rule as before — 2 of 3 must uphold for a FAIL to
// stand — at two-thirds the cost when the readers agree, which they mostly do.
const summary = await pipeline(FAILS,
  (f) => parallel([() => refute(f, 1), () => refute(f, 2)]).then((rs) => rs.filter(Boolean)),
  async (rs, f) => {
    const votes = rs.filter((r) => typeof r.refuted === 'boolean')
    const agree = votes.length === 2 && votes[0].refuted === votes[1].refuted
    const all = agree ? rs : [...rs, await refute(f, 3)]
    const upheld = all.filter((r) => r.refuted === false).length
    const refuted = all.filter((r) => r.refuted === true).length
    const idx = {}
    for (const r of all) for (const i of (r.misleading_examples || [])) idx[i] = (idx[i] || 0) + 1
    return { file: f.file, upheld, refuted, errors: all.length - upheld - refuted,
             stands: upheld >= 2 || (upheld === 1 && refuted === 0 && all.length === 1),
             misleading_examples: Object.entries(idx).filter(([, n]) => n >= 2).map(([i]) => +i),
             reasons: all.map((r) => `#${r.k} ${r.refuted === true ? 'REFUTED' : r.refuted === false ? 'UPHELD' : 'ERROR'}: ${r.reason}`) }
  })
const rows = summary.filter(Boolean)
log(`${rows.filter((s) => s.stands).length} of ${rows.length} FAILs stand`)
return { locale: LOC, stands: rows.filter((s) => s.stands).map((s) => s.file), refuted: rows.filter((s) => !s.stands).map((s) => s.file),
         ...(aborted ? { aborted } : {}), summary: rows.map(({ reasons, ...rest }) => rest) }
