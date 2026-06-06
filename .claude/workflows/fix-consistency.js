export const meta = {
  name: 'fix-consistency',
  description: 'Unify within-file terminology inconsistency (the two-pass-merge FAIL class) flagged by the Opus deep-review. One Sonnet agent per file: pick the dominant/correct rendering of each split term and make it consistent. Lint+freshness-gated.',
  phases: [
    { title: 'Fix', detail: 'one Sonnet agent per inconsistent file', model: 'sonnet' },
  ],
}

// FIXES baked in by make-consistency-run.py (it rewrites the declaration below).
// Each: { locale, locale_name, rel, note, examples:[{type,line_approx,source,translation,why,suggested}] }
const FIXES = null

const input = (args && Array.isArray(args.fixes) && args.fixes.length) ? args.fixes : FIXES
if (!input || !Array.isArray(input) || input.length === 0) {
  log('ERROR: no fixes. Bake them with make-consistency-run.py or pass args.fixes.')
  return { error: 'no fixes provided' }
}

log(`Consistency-fix — ${input.length} files with within-file terminology inconsistency (Sonnet, lint+freshness-gated)`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['locale', 'file', 'status', 'summary'],
  properties: {
    locale: { type: 'string' },
    file: { type: 'string' },
    status: { enum: ['FIXED', 'NO_CHANGE_NEEDED', 'COULD_NOT_FIX'] },
    edits_made: { type: 'integer' },
    terms_unified: { type: 'integer' },
    summary: { type: 'string', minLength: 40 },
  },
}

function promptFor(f) {
  const ex = (f.examples || []).map((e, i) =>
    `  ${i + 1}. [${e.type}] ${e.line_approx || ''}\n` +
    `     issue:     ${e.why}\n` +
    `     current:   ${e.translation}\n` +
    `     suggested: ${e.suggested}`).join('\n')
  return `You are a senior ${f.locale_name} technical editor fixing WITHIN-FILE TERMINOLOGY INCONSISTENCY in one Qiskit documentation translation. Repo root: current working directory.

Files:
  English source:  docs/${f.rel}
  ${f.locale_name} translation (EDIT THIS):  i18n/${f.locale}/docusaurus-plugin-content-docs/current/${f.rel}

An expert reviewer found that one or more core domain terms are rendered MULTIPLE different ways within this single file (the "two-pass-merge" defect — different sections translated in different passes, never reconciled). Reviewer's note:
"${f.note}"

Specific inconsistencies:
${ex || '  (no line-level examples — use the note above; read the file and find the terms rendered ≥2 ways.)'}

YOUR TASK — for each inconsistently-rendered term:
- Choose the SINGLE correct/dominant ${f.locale_name} rendering (prefer the one the field conventionally uses AND that the file already uses most; follow the reviewer's "suggested" where given), and make that term consistent THROUGHOUT the file.
- If the reviewer also named a genuine MISTRANSLATION (a wrong term, not just an inconsistent one), correct it to match the English meaning.
- Change ONLY the inconsistent/wrong term renderings. Do NOT restyle correct prose, do NOT touch code blocks, math, JSX, image paths, or heading anchors.
- CRITICAL: do NOT touch the {/* doqumentation-source-hash: ... */} marker — the EN is current; you are unifying the translation's terminology only.

After editing, VERIFY:
  python3 translation/scripts/lint-translation.py --locale ${f.locale} --file i18n/${f.locale}/docusaurus-plugin-content-docs/current/${f.rel}
must pass (returncode 0). If your edit breaks lint, fix or revert it.

Return the structured object: locale="${f.locale}", file="${f.rel}", status (FIXED / NO_CHANGE_NEEDED / COULD_NOT_FIX), edits_made (count), terms_unified (how many distinct terms you made consistent), and a summary naming each term and the rendering you standardized on. Do NOT touch git, status.json, or any other file.`
}

// Each agent edits a DISTINCT file — no worktree isolation needed; all edits
// accumulate in the working tree for one review+commit.
phase('Fix')
const results = await parallel(input.map((f) => () =>
  agent(promptFor(f), {
    label: `consist:${f.locale}/${f.rel.split('/').pop()}`,
    phase: 'Fix',
    model: 'sonnet',
    schema: SCHEMA,
  })
))

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
