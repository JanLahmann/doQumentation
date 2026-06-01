# Tier-3 linguistic review — agent rubric (externalized)

This is the **single source of truth** for the prompt given to a Tier-3 review
agent. The orchestrator (`review-build-batches.py`) points each agent at this
file plus a per-batch file list, instead of re-embedding the rubric in every
prompt. Keep it parametric: the orchestrator substitutes `{LOCALE}`,
`{LOCALE_NAME}`, and `{REGISTER}`.

## Model

**Run the review agents on Haiku.** Haiku is the validated production review
model (re-validated 2026-05-17: 8/8 vs ground truth across de/ja/ar, matching
Sonnet/Opus, zero false-FAILs). Do **not** run review on Opus — no accuracy
gain, just cost. Escalate to Sonnet only a *contested* file (a verdict you and a
re-check disagree on), never the bulk pass.

## What the agent receives

- A batch file `batch.json`: `[{"file": "<REL>", "hints": ["FLAG", ...]}, ...]`.
  `hints` are from the deterministic pre-filter — "look here" pointers, **not**
  verdicts. Confirm or dismiss each; never record a verdict from a hint alone.
- An output path `out.json` to write verdicts to.

## Prompt

```
You are a Tier-3 linguistic reviewer for {LOCALE_NAME} ({LOCALE}) Qiskit docs.
Repo root: /home/user/doQumentation. For each file in batch.json, compare the
English source docs/<REL> against the translation
i18n/{LOCALE}/docusaurus-plugin-content-docs/current/<REL>.

Use the per-file `hints` as starting points (the pre-filter already ran cheap
structural/lexical checks) — confirm or dismiss each, then do your own pass.

CHECKS (prose only — ignore code/math/JSX/URLs/anchors):
1. REGISTER — {REGISTER}. Register problems are MINOR (fix in place), not FAIL,
   unless pervasive (>2 distinct formal slips in a single short doc).
2. WORD SALAD / HALLUCINATION — match each prose paragraph to its EN paragraph.
   Flag gibberish/repetition, and fluent-but-fabricated/substituted content not
   in the source. Scrutinize the last 40% of long files.
3. VERBOSITY — sentences materially longer/redundant vs source.
4. ACCURACY — meaning drift, dropped detail, added info, negation inversions,
   wrong-term (e.g. single-qubit→single-bit, gates→circuits, observables→X),
   dropped trailing sentence/paragraph/References, added/dropped table rows,
   fabricated links.

INCONSISTENT-GLOSSARY RULE (apply uniformly — this removes reviewer guesswork):
- A file that renders a concept CONSISTENTLY — always the capitalized English
  term, OR always the target-language word — is acceptable: PASS on that axis.
- A file that MIXES them for the SAME concept (e.g. both "litar" and "Circuit",
  or both lowercase "qubit" and capitalized "Qubit", in prose) is inconsistent
  leakage. If ≥3 such mixed hits: FAIL. If 1–2 isolated: fix in place (MINOR).

FIX POLICY — fix only safe MINOR issues in place (register→informal/standard,
clear typos, isolated leaked words, foreign-language leaks, leaked survey-note
blocks). After any edit the file MUST pass
  python3 translation/scripts/lint-translation.py --locale {LOCALE} --file <ABS>
and  python3 translation/scripts/check-translation-freshness.py --locale {LOCALE}
must NOT increase STALE (never touch the {/* doqumentation-source-hash */}
marker). Do NOT fix word-salad / hallucination / accuracy / dropped-content /
pervasive-leak — record FAIL with a precise note instead.

VERDICT (first match wins): FAIL = any word salad, hallucination, accuracy/
dropped/added-content error, inconsistent-glossary ≥3, >2 register, or >3
verbosity. MINOR_ISSUES = 1–2 isolated register/leak/verbosity (fixed or noted),
no serious issue. PASS = clean (a consistent glossary convention is clean).

OUTPUT — write a JSON array to out.json, exactly one object per file:
  {"locale":"{LOCALE}","file":"<REL>","verdict":"PASS|MINOR_ISSUES|FAIL",
   "issues":<int>,"notes":"<brief: confirmed/dismissed hints, fixes, FAIL reason>"}
This array is the deliverable. Then reply with ONE LINE only: the tally, e.g.
  "b3: 10 PASS, 3 MINOR(fixed), 2 FAIL — out.json written". Do NOT paste a table.

HARD CONSTRAINTS: NO git. Do NOT edit translation/status.json. Edit only the
{LOCALE} files in your batch. No other locales/dialects.
```

## Register sections (paste into `{REGISTER}`)

| locale | register |
|--------|----------|
| es | informal "tú" — flag usted/consulte/utilice/ejecute |
| de | informal "du" — flag Sie/Ihnen/Verwenden Sie |
| fr | informal "tu" — flag vous/votre/veuillez |
| it | informal "tu" — flag Lei/consulti/utilizzi |
| pt | casual "você" — flag o senhor/a senhora/vossa |
| uk | informal "ти" — flag Ви/Вам/Ваш |
| pl | informal "ty" — flag Pan/Pani/Państwo/proszę uprzejmie |
| cs | informal "ty" — flag Vy/Vám/Vás/Chcete-li/naleznete/račte (Chceš-li is fine) |
| ja | polite desu/masu, no keigo — flag ございます/いただく/ご覧ください |
| ms | standard "anda" — "kamu"/casual is a MINOR fix, not FAIL |
| ko | 해요체 — flag honorific/humble (하십시오체, 시, 드리) |
