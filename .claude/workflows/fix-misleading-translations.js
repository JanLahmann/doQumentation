export const meta = {
  name: 'fix-misleading-translations',
  description: 'Strategy B: targeted per-file fixes for the genuinely-misleading translation errors found by the Opus deep-review (semantic inversions, wrong terms, injected content). One Sonnet agent per file, lint+freshness-gated.',
  phases: [
    { title: 'Fix', detail: 'one Sonnet agent per misleading file', model: 'sonnet' },
  ],
}

// FIXES is baked in by make-fix-run.py (it rewrites the declaration below).
// Each entry: { locale, rel, locale_name, note,
//   examples:[{type,line_approx,source,translation,why,suggested}] }
const FIXES = null

const input = (args && Array.isArray(args.fixes) && args.fixes.length) ? args.fixes : FIXES
if (!input || !Array.isArray(input) || input.length === 0) {
  log('ERROR: no fixes. Bake them with make-fix-run.py or pass args.fixes.')
  return { error: 'no fixes provided' }
}

log(`Strategy B — ${input.length} targeted misleading-error fixes (Sonnet, lint+freshness-gated)`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['locale', 'file', 'status', 'summary'],
  properties: {
    locale: { type: 'string' },
    file: { type: 'string' },
    status: { enum: ['FIXED', 'NO_CHANGE_NEEDED', 'COULD_NOT_FIX'] },
    edits_made: { type: 'integer' },
    summary: { type: 'string', minLength: 40 },
  },
}

function promptFor(f) {
  const ex = (f.examples || []).map((e, i) =>
    `  ${i + 1}. [${e.type}] ${e.line_approx || ''}\n` +
    `     EN source:   ${e.source}\n` +
    `     current TR:  ${e.translation}\n` +
    `     problem:     ${e.why}\n` +
    `     suggested:   ${e.suggested}`).join('\n')
  return `You are a senior ${f.locale_name} technical translator fixing a SPECIFIC, already-identified defect in one Qiskit documentation translation. Repo root: current working directory.

Files:
  English source:  docs/${f.rel}
  ${f.locale_name} translation (EDIT THIS):  i18n/${f.locale}/docusaurus-plugin-content-docs/current/${f.rel}

An expert reviewer found genuinely MISLEADING content in the translation — content a learner would get WRONG. Reviewer's overall note:
"${f.note}"

Specific issues to fix:
${ex || '  (no line-level examples — use the reviewer note above; read both files and find the misleading passage it describes.)'}

YOUR TASK — fix ONLY these identified defects and any direct duplicate of the same defect elsewhere in the file:
- Apply the semantic correction so the ${f.locale_name} matches the English MEANING (fix inversions, swapped labels, wrong terms, injected/hallucinated sentences, dropped content).
- For a within-file terminology inconsistency, pick the CORRECT conventional ${f.locale_name} term and make it consistent throughout the file.
- Preserve everything else: do NOT rewrite passages that are already correct, do NOT restyle, do NOT touch code blocks, math, JSX, image paths, or heading anchors.
- CRITICAL: do NOT touch the {/* doqumentation-source-hash: ... */} marker — leave it exactly as is (the file's EN is current; you are fixing the translation prose only).

After editing, VERIFY your work:
  python3 translation/scripts/lint-translation.py --locale ${f.locale} --file i18n/${f.locale}/docusaurus-plugin-content-docs/current/${f.rel}
must pass (returncode 0). If your edit breaks lint, fix it or revert that edit.

Return the structured object: locale="${f.locale}", file="${f.rel}", status (FIXED if you corrected it, NO_CHANGE_NEEDED if on inspection it was already fine, COULD_NOT_FIX if you couldn't safely fix it), edits_made (count), and a summary of exactly what you changed (name the corrected term/passage). Do NOT touch git or status.json or any other file.`
}

// No worktree isolation: each agent edits a DISTINCT file (verified — no two
// fixes target the same path), so concurrent edits don't race on the working
// copy, and all fixes accumulate in the main tree for one review+commit.
phase('Fix')
// Throttle to <=7 concurrent agents (user-tuned 2026-07-17: 7->10->5->7). The 5h
// session limit can hit mid-run; with a small in-flight batch only those <=7
// are lost on a hit, and every completed
// batch is preserved in `results` (vs. submitting all at once and losing the lot).
const BATCH = 7
const results = []
for (let i = 0; i < input.length; i += BATCH) {
  const slice = input.slice(i, i + BATCH)
  log(`Fix batch ${Math.floor(i / BATCH) + 1}: files ${i + 1}-${i + slice.length} of ${input.length}`)
  const r = await parallel(slice.map((f) => () =>
    agent(promptFor(f), {
      label: `fix:${f.locale}/${f.rel.split('/').pop()}`,
      phase: 'Fix',
      model: 'sonnet',
      schema: SCHEMA,
    })
  ))
  results.push(...r)
}

const ok = results.filter(Boolean)
const fixed = ok.filter((r) => r.status === 'FIXED')
const noChange = ok.filter((r) => r.status === 'NO_CHANGE_NEEDED')
const failed = ok.filter((r) => r.status === 'COULD_NOT_FIX')

log(`Done. ${fixed.length} fixed, ${noChange.length} no-change, ${failed.length} could-not-fix, ${input.length - ok.length} agent-errored.`)
for (const r of fixed) log(`  ✓ ${r.locale}/${r.file}: ${r.summary}`)
for (const r of failed) log(`  ✗ ${r.locale}/${r.file}: ${r.summary}`)

return {
  total: input.length,
  fixed: fixed.map((r) => `${r.locale}/${r.file}`),
  no_change: noChange.map((r) => `${r.locale}/${r.file}`),
  could_not_fix: failed.map((r) => ({ f: `${r.locale}/${r.file}`, why: r.summary })),
  records: ok,
}
