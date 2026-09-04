export const meta = {
  name: 'translate-locale',
  description: 'Fill the prepared translation batches of one locale: one agent per batch, one read, one write',
  whenToUse: 'After `translate.py --locale X --prepare`. Pass the contents of work/X/manifest.json as args.',
  phases: [{ title: 'Translate', detail: 'one agent per batch, haiku for near-identical fuzzy entries, sonnet for the rest' }],
}

// args = contents of translation/v2/work/<locale>/manifest.json:
//   { locale, instructions, batches: [{ file, model, items, words }], concurrency? }
//
// Why this shape: the German run cost ~150k tokens per 4,000-word batch when
// agents read, verified, re-read and wrote in 5-34 tool calls. Each turn
// re-sends the whole context. This script gives every agent a prompt that
// allows exactly three turns: read the batch, write it back, return a count.
// Workflow scripts have no filesystem access, so batches stay on disk and
// the results stay out of the orchestrator's context; apply happens
// afterwards with `translate.py --locale X --apply`.

const { locale, instructions, instructions_text, batches } = args
const CONCURRENCY = (args && args.concurrency) || 5
// .claude/agents/translator.md (Read + Write only) is the cheaper agent type,
// but custom agents register at session start; pass agentType in args once
// a session that knows it is running. general-purpose always works.
const AGENT_TYPE = (args && args.agentType) || 'general-purpose'
// The instructions travel inside the prompt (manifest.json carries them as
// instructions_text) so an agent needs no Read for them: with a fixed cost
// of roughly 15k tokens per turn, one turn less per batch matters more than
// anything in the prompt text.
const RULES = instructions_text || `Follow the rules in ${instructions} (read it once first).`

// No output schema: a StructuredOutput call is one more turn per agent, and a
// turn costs ~15k tokens of fixed context. The agent's final text is parsed.
function parseDone(text, b) {
  const m = /done\s+(\d+)\s*\/\s*(\d+)/i.exec(String(text || ''))
  return m ? { file: b.file, filled: +m[1], total: +m[2] } : { file: b.file, filled: 0, total: b.items, failed: true, raw: String(text || '').slice(0, 200) }
}

function prompt(b) {
  return `You are a technical translator for doQumentation (locale "${locale}").

${RULES}

Do exactly this, in this order, with no other tool calls:
1. Read ${b.file} (once). It is a JSON list of ${b.items} items.
2. For EVERY item write the translation of "msgid" into "msgstr", following the rules above. Leave every other field untouched; do not add, remove or reorder items. If an item is code or a proper name that must stay in English, copy msgid into msgstr unchanged.
3. Write the result to ${b.file} with ONE Write call: a JSON list of objects with exactly two keys, "id" (copied from the item) and "msgstr" (your translation), one per item, in order. Nothing else in the file.
4. Reply with exactly one line and nothing else: done <filled>/${b.items}

Do not read any other file, do not run scripts or shell, do not verify by re-reading, do not write partial files. Keep reasoning to a minimum; the translation is the work.`
}

// A custom agent type registers only at session start and is dropped again
// by a re-login mid-session (2026-09-04: 30 th batches failed in 10 s with
// "agent type 'translator' not found"). Do NOT fall back to general-purpose:
// a 5-agent wave of it cost 3.4M tokens for 3 finished batches. Fail fast so
// the run can be restarted in a fresh session with the cheap agent.
function run(b) {
  return agent(prompt(b), {
    label: `${b.model} ${b.file.split('/').pop()} (${b.items} items)`,
    phase: 'Translate',
    model: b.model,
    effort: b.model === 'haiku' ? 'low' : 'medium',
    agentType: AGENT_TYPE,
  }).catch(e => {
    if (/agent type .* not found/i.test(String(e && e.message || e)))
      throw new Error(`agent type '${AGENT_TYPE}' is not registered in this session (custom agents register at startup and a /login drops them). Start a new session and rerun; nothing was translated.`)
    throw e
  })
}

phase('Translate')
const done = []
for (let i = 0; i < batches.length; i += CONCURRENCY) {
  const chunk = batches.slice(i, i + CONCURRENCY)
  const out = await parallel(chunk.map(b => () => run(b).then(text => parseDone(text, b))))
  chunk.forEach((b, k) => done.push(out[k] ? { ...out[k], model: b.model } : { file: b.file, filled: 0, total: b.items, model: b.model, failed: true }))
  const filled = done.reduce((s, r) => s + (r.filled || 0), 0)
  const total = done.reduce((s, r) => s + r.total, 0)
  log(`${done.length}/${batches.length} batches, ${filled}/${total} items filled`)
}
const failed = done.filter(r => r.failed || r.filled < r.total)
if (failed.length) log(`${failed.length} batch(es) incomplete: ${failed.map(f => f.file.split('/').pop()).join(', ')} — rerun with resumeFromRunId after fixing`)
return { locale, batches: done, incomplete: failed.map(f => f.file) }
