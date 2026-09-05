export const meta = {
  name: 'translate-locale',
  description: 'Fill the prepared translation batches of one locale: one agent per batch, one read, one write',
  whenToUse: 'After `translate.py --locale X --prepare`. Pass the contents of work/X/manifest.json as args.',
  phases: [{ title: 'Translate', detail: 'one agent per batch, haiku for near-identical fuzzy entries, sonnet for the rest' }],
}

// args = contents of translation/v2/work/<locale>/manifest.json:
//   { locale, instructions, batches: [{ file, out, model, items, words }], concurrency? }
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
// On every locale run (pt, ja, ko, uk, cs, ro, id: 7 runs of 33-39 batches)
// one to three agents replied as if no prompt had reached them ("I don't
// see a task in your message…") and did nothing; once an agent returned
// 118 strings for 120 items. A retry with a slightly different prompt is
// a fresh agent call (the same prompt would replay from cache on resume).
const MAX_ATTEMPTS = (args && args.attempts) || 3
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

// The batch carries no ids and the agent returns a plain list of strings in
// item order: ids, keys and pretty-printing cost more tokens than the
// English itself (a 120-item batch read at ~60% after the change), and
// the id echoed per item was ~9% of the Thai output. translate.py --apply
// pairs the strings with the batch's .ids.json and rejects the whole
// batch on a count mismatch, so a dropped item cannot shift the rest.
function outFile(b) {
  return b.out || b.file.replace(/\.json$/, '.out.json')
}

function prompt(b, attempt) {
  const retry = attempt > 1
    ? `\n\nThis is attempt ${attempt} for this batch: the previous run returned without doing the work, or with the wrong number of strings. Do the task above now. The list must contain exactly ${b.items} strings, one per item, in the batch's order; never merge or skip an item.`
    : ''
  return `You are a technical translator for doQumentation (locale "${locale}").

${RULES}

Do exactly this, in this order, with no other tool calls:
1. Read ${b.file} (once). It is a JSON list of ${b.items} items, one per line.
2. Translate EVERY item's "msgid" following the rules above. If an item is code or a proper name that must stay in English, its translation is the msgid unchanged.
3. Write ${outFile(b)} with ONE Write call: a JSON list of exactly ${b.items} strings, the translation of each item in the same order as the batch, one string per line. Nothing else in the file; no keys, no ids, no comments.
4. Reply with exactly one line and nothing else: done <count>/${b.items}

Do not read any other file, do not run scripts or shell, do not verify by re-reading, do not write partial files. Keep reasoning to a minimum; the translation is the work.${retry}`
}

// A custom agent type registers only at session start and is dropped again
// by a re-login mid-session (2026-09-04: 30 th batches failed in 10 s with
// "agent type 'translator' not found"). Do NOT fall back to general-purpose:
// a 5-agent wave of it cost 3.4M tokens for 3 finished batches. Fail fast so
// the run can be restarted in a fresh session with the cheap agent.
function run(b, attempt) {
  return agent(prompt(b, attempt), {
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
// A sliding pool, not waves: as soon as one agent finishes the next batch
// starts, so CONCURRENCY agents are running at any time (a wave of 15 would
// idle down to 1 while its slowest batch finished).
const done = new Array(batches.length)
let next = 0
async function worker() {
  while (next < batches.length) {
    const i = next++
    const b = batches[i]
    const name = b.file.split('/').pop()
    let res
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      try {
        res = { ...parseDone(await run(b, attempt), b), model: b.model, attempts: attempt }
      } catch (e) {
        if (/is not registered in this session/.test(String(e && e.message || e))) throw e
        res = { file: b.file, filled: 0, total: b.items, model: b.model, failed: true, attempts: attempt, raw: String(e && e.message || e).slice(0, 200) }
      }
      if (!res.failed && res.filled >= res.total) break
      if (attempt < MAX_ATTEMPTS)
        log(`${name}: attempt ${attempt} ${res.failed ? 'did nothing' : `short (${res.filled}/${res.total})`} — retrying`)
    }
    done[i] = res
    const finished = done.filter(Boolean)
    const filled = finished.reduce((s, r) => s + (r.filled || 0), 0)
    const total = finished.reduce((s, r) => s + r.total, 0)
    log(`${finished.length}/${batches.length} batches, ${filled}/${total} items filled`)
  }
}
await Promise.all(Array.from({ length: Math.min(CONCURRENCY, batches.length) }, worker))
const failed = done.filter(r => r.failed || r.filled < r.total)
if (failed.length) log(`${failed.length} batch(es) incomplete: ${failed.map(f => f.file.split('/').pop()).join(', ')} — rerun with resumeFromRunId after fixing`)
return { locale, batches: done, incomplete: failed.map(f => f.file) }
