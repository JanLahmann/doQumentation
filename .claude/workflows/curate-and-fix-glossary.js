export const meta = {
  name: 'curate-and-fix-glossary',
  description: 'Strategy A at scale: per-locale Sonnet agent finalizes the glossary (keep-English vs translate), runs the deterministic leak fixer, and lint+freshness-gates. One agent per locale; each edits only its own i18n subtree.',
  phases: [
    { title: 'Curate+Fix', detail: 'one Sonnet agent per locale', model: 'sonnet' },
  ],
}

// LOCALES baked in by make-glossary-run.py (replaces the declaration below).
// Each entry: { locale, locale_name, register }
const LOCALES = null

const input = (args && Array.isArray(args.locales) && args.locales.length) ? args.locales : LOCALES
if (!input || !Array.isArray(input) || input.length === 0) {
  log('ERROR: no locales. Bake them with make-glossary-run.py or pass args.locales.')
  return { error: 'no locales provided' }
}

log(`Strategy A — curate+fix glossary leaks for ${input.length} locale(s) (Sonnet, lint+freshness-gated)`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['locale', 'status', 'summary'],
  properties: {
    locale: { type: 'string' },
    status: { enum: ['DONE', 'KEEP_ENGLISH_LOCALE', 'COULD_NOT_FIX'] },
    glossary_terms: { type: 'integer' },
    leaks_before: { type: 'integer' },
    leaks_after: { type: 'integer' },
    fixes_applied: { type: 'integer' },
    files_changed: { type: 'integer' },
    summary: { type: 'string', minLength: 40 },
  },
}

function promptFor(f) {
  return `You are a senior ${f.locale_name} technical translator finalizing a terminology glossary and cleaning up English-leakage in the ${f.locale_name} Qiskit docs. Repo root: current working directory. Work ONLY on locale "${f.locale}" — never touch other locales.

GOAL: the dominant translation-quality defect in this corpus is capitalized-English leakage (e.g. "Gate"/"Circuit"/"Qubit" left in English mid-sentence) and within-file term inconsistency. A deterministic detector + fixer exist; your job is to give them a CORRECT per-locale glossary, then run them.

STEP 1 — inspect the scaffold:
  cat translation/glossary/${f.locale}.json   (a scaffold from majority usage — a STARTING POINT, may be wrong)
  python3 translation/scripts/check-glossary-consistency.py --locale ${f.locale} --report   (current leaks/mixes)
Read 2-3 of the most leak-heavy files (from the report) to see how "gate"/"circuit"/"qubit" are actually rendered in real ${f.locale_name} prose.

STEP 2 — DECIDE per concept (gate, circuit) whether ${f.locale_name} technical convention TRANSLATES it or KEEPS it in English:
  - If TRANSLATED (e.g. es puerta/circuito, de Gatter/Schaltkreis): set "preferred" to the canonical ${f.locale_name} term, list any genuine second rendering in "variants", and keep "leaked_en" = the capitalized English forms to fix.
  - If KEPT IN ENGLISH (e.g. French keeps "circuit"; some locales keep "gate"): REMOVE that concept from "translate" entirely — do NOT force a translation. Leaving it out means the fixer won't touch it. This is correct and important: do not invent a non-idiomatic translation.
  - "qubit"/"qubits" go in "keep_lowercase" for EVERY locale (English, but lowercase mid-sentence) UNLESS this locale's script doesn't use Latin case (ja/ko/ar/he/th — then keep_lowercase can be empty, capitalization isn't meaningful).
Write the finalized glossary back to translation/glossary/${f.locale}.json (valid JSON; keep the schema: {"translate":{...},"keep_lowercase":[...]}; you may delete the "_note"/"_counts" scaffold fields).

STEP 3 — run the deterministic fixer (it only does SAFE edits — decapitalize keep_lowercase, translate leaked_en where an agreeing article precedes; it holds back name-patterns/no-determiner and lint-gates each file with rollback):
  python3 translation/scripts/fix-glossary-leaks.py --locale ${f.locale} --all
Then VERIFY:
  python3 translation/scripts/check-glossary-consistency.py --locale ${f.locale} --report   (leaks should drop)
  python3 translation/scripts/check-translation-freshness.py --locale ${f.locale}   (STALE must NOT increase — the fixer never touches the source-hash marker; if STALE rose, something is wrong — investigate/revert)

CONSTRAINTS: edit only translation/glossary/${f.locale}.json and i18n/${f.locale}/** files. NO git. Do NOT touch status.json or other locales. If on inspection ${f.locale_name} keeps BOTH gate and circuit in English (no leakage to fix), set status=KEEP_ENGLISH_LOCALE and explain.

Return the structured object: locale="${f.locale}", status, glossary_terms (count in translate), leaks_before, leaks_after, fixes_applied, files_changed, and a summary naming the canonical terms you set and what you fixed.`
}

phase('Curate+Fix')
const results = await parallel(input.map((f) => () =>
  agent(promptFor(f), {
    label: `glossary:${f.locale}`,
    phase: 'Curate+Fix',
    model: 'sonnet',
    schema: SCHEMA,
  })
))

const ok = results.filter(Boolean)
const done = ok.filter((r) => r.status === 'DONE')
const keepEn = ok.filter((r) => r.status === 'KEEP_ENGLISH_LOCALE')
const failed = ok.filter((r) => r.status === 'COULD_NOT_FIX')

const totalFixes = done.reduce((s, r) => s + (r.fixes_applied || 0), 0)
const totalBefore = ok.reduce((s, r) => s + (r.leaks_before || 0), 0)
const totalAfter = ok.reduce((s, r) => s + (r.leaks_after || 0), 0)

log(`Done. ${done.length} fixed, ${keepEn.length} keep-English, ${failed.length} could-not-fix, ${input.length - ok.length} agent-errored.`)
log(`Total leaks: ${totalBefore} → ${totalAfter} (${totalFixes} fixes applied).`)
for (const r of ok) log(`  ${r.locale} [${r.status}]: ${r.leaks_before ?? '?'}→${r.leaks_after ?? '?'} leaks — ${r.summary}`)

return {
  total: input.length,
  fixed: done.map((r) => r.locale),
  keep_english: keepEn.map((r) => r.locale),
  could_not_fix: failed.map((r) => ({ locale: r.locale, why: r.summary })),
  leaks_before: totalBefore,
  leaks_after: totalAfter,
  fixes_applied: totalFixes,
  records: ok,
}
