# Runtime & Near-time AI: what is possible without an API budget

> **Status**: Ideation round 3 (2026-09-18) — exploration, no implementation commitment.
> **Relationship to the other rounds**: [`AI_FEATURES_BRAINSTORMING.md`](./AI_FEATURES_BRAINSTORMING.md) is the capability layer (search, RAG, metadata, runtime tiers), [`BUILD_TIME_AI_IDEAS.md`](./BUILD_TIME_AI_IDEAS.md) is the build-time product layer (Certification Studio, Compiled Tutor, flywheel). This round asks one question: **what lies beyond build-time AI when the only budgets are a Claude Code Max subscription and 500 Bobcoins/month on IBM Bob, with no Claude API tokens?**
> **Budget frame (new)**: Claude Code Max = interactive sessions + cloud sessions + **Routines** (scheduled / API / GitHub-event triggers) + the Claude Code GitHub Action via OAuth token. IBM Bob Ultra = 500 Bobcoins/month (≈ $250 list value), usable interactively and headless (Bob Shell) in CI. Both are *subscriptions*, not per-request APIs — which is exactly what shapes the answer.

---

## 1. The latency ladder

"Runtime AI" is not one thing. Sort by how long the learner waits:

| Tier | Latency | What it can be paid with | What we already have |
|---|---|---|---|
| **Build-time** | minutes → days, batch | Max (fan-out sessions), Bob | Translation factory, notebook sweep, status bookkeeping |
| **Near-time** | ~2–30 min, asynchronous, *one run serves many* | Max **Routines** (cron ≥ 1 h, HTTP `/fire` endpoint, GitHub PR/release events; daily run cap), Claude Code GitHub Action with `CLAUDE_CODE_OAUTH_TOKEN` (`@claude` in issues/PRs draws on the Max quota), **Bob headless in GitHub Actions** (Bobcoins; Actions cron can go to 5 min) | Weekly/daily CI cadences, pre-filled "Report this error" issue links, feedback widgets → Umami events |
| **Runtime** | < 10 s, synchronous, per learner | **No model budget at all** — so it must come from one of four free sources (§4) | localStorage learner state, thebelab kernel, RasQberry/Docker/Code Engine containers, BYOK settings page |

The honest headline: **true per-request runtime AI is possible, but only from sources we don't pay per call for** — precomputation, the learner's own browser, the deployment's own server where one exists, or the learner's own assistant. Everything that needs *our* model budget lands in the near-time tier, and near-time only scales through batching.

### 1.1 The one hard constraint: a static site cannot hold a secret

The Routines `/fire` endpoint and the Bob/Claude tokens are bearer secrets. They can never ship in the GitHub Pages bundle. Any learner-initiated near-time flow therefore needs one of:

- **GitHub as the intake** (issue forms, Discussions, `@claude` mentions) — free, auditable, but the learner needs a GitHub account.
- **A stateless relay** — a Cloudflare Worker (free tier: 100k req/day) or a Code Engine function that rate-limits, strips PII, and forwards to the routine endpoint. It holds a token, not state; the "no backend" rule is about learner state and accounts, and this violates neither. Round 1 already accepted a $0–5/month Code Engine function on the same grounds.

Everything else in this document is designed so that *nothing* needs a secret in the browser.

---

## 2. Near-time patterns (Claude Routines + Bob headless)

### 2.1 The batched-personalization pattern ← the key enabler

Routines have a **daily run cap** (third-party write-ups cite 15/day on Max; the live number is on claude.ai/code/routines) and a minimum schedule interval of one hour. Per-learner runs therefore cannot scale. Batching can:

> **Queue requests during the day → one nightly run processes all of them → results published as static JSON keyed by a random ID → each learner's page polls its ID.**

One run a day serves an unbounded number of learners. Latency is "by tomorrow morning", which is fine for a *learning plan* and wrong for a *chat*. The queue can be a GitHub issue form (account needed), a Worker KV namespace (free, no account), or a form tool reachable through a connector. The routine writes to a `claude/` branch → CI deploys → JSON goes live. Learners opt in and choose what to include; the profile leaves the browser only on an explicit click.

### 2.2 `@claude` in Issues/Discussions = a free grounded Q&A bot

The Claude Code GitHub Action supports Max via OAuth token. Enabling it on the repo means anyone with a GitHub account can open an issue or Discussion, mention `@claude`, and get an answer grounded in the very repository that *is* the site (docs, notebooks, transcripts, all 17 locales). No RAG index, no runtime cost beyond quota. Cheapest real Q&A we can offer, and the answers accumulate as searchable public threads.

Concrete site hook: the existing "Report this error" links pre-fill an issue. Add a sibling **"Ask about this error"** that pre-fills an issue with page, cell index, error class, Qiskit version, and an `@claude` mention. Guardrail: a repo-committed prompt/skill that pins Claude to answering from the docs, linking pages, never inventing API.

### 2.3 "Report a translation problem → fixed by tomorrow"

`TranslationFeedback` currently emits an Umami event and stops. Upgrade it to an issue form (locale, page, quoted sentence, suggested fix). A nightly routine reads open `translation-feedback` issues, applies fixes **only through `translation/v2/fix.py --apply`** (so every entry passes `check.py`), opens a PR, and comments on the issue. Human merge stays the gate. This gives 17 locale communities a 24-hour fix loop without giving anyone commit access — the Adopt-a-Locale idea from round 2, made bidirectional.

### 2.4 Error report → reproduce in the harness → PR with an inline hint

Round 2 proposed a *Misconception Miner* over anonymous error-class counts. Near-time makes it concrete per report: a routine picks up an "Ask about this error" issue, re-runs the cell in the pinned image (`ci/00_patch_runtime.py` fake-backend harness), and either answers ("works on 2.3-xl; your kernel is stale, click Restart") or opens a PR adding an inline error hint for that `ErrorClass × page`. The open TODO "Qiskit execution error hints" then fills itself from real reports.

### 2.5 Workshop-day live triage (the Bob slot)

During a workshop, Code Engine logs and Umami "Run Code" errors spike in real time. A GitHub Actions cron every 10–15 min running **Bob headless** (Bob Shell `bob run …` with a fixed prompt) reads the last window of errors and posts a short "top 3 errors right now + suggested fix" digest for the organizer. Claude Routines can't go below one hour; Actions cron can, and Bobcoins are the budget that is otherwise idle. Scope it to workshop days only (`workshop-start.yml` enables it, `workshop-close.yml` disables it).

### 2.6 Search-miss → answered by tomorrow

Log zero-result search queries as an Umami event (query string only). A nightly routine reads the Umami API, clusters new misses, and writes synonym-map entries plus compiled Q&A pairs (round 2 §5.4) → PR → deploy. Cohort-level personalization: the site learns what *today's* learners couldn't find and answers it *tomorrow*.

---

## 3. Runtime patterns (synchronous, $0 per request)

### 3.1 Source A — precomputation (the Compiled Tutor)

Unchanged from round 2 §5: enumerate learner states at build time, ship a decision table, select client-side. For **recommendations** this is not the fallback, it is the *best* tool: deterministic, explainable, instant, offline on the Pi, no privacy exposure. Every other layer below should *frame* its output, not replace it.

### 3.2 Source B — the learner's browser

**Granite 4.0 Nano via WebGPU (transformers.js).** IBM ships browser demos of the 350M and 1B Nano models; the handoff already lists "Offline AI tutor (Granite 4.0 Nano)" as a future idea. Realistic jobs for a model that small, all **page-scoped** (context = the current page only, so no vector index is needed and hallucination surface is small):

- *Explain this cell* — code + surrounding prose → plain-language explanation
- *Simplify this paragraph* / *ELI12 this* — a live persona lens for pages that have no precomputed lens
- *Explain this error* — traceback + cell → likely cause, in the page's language
- *Phrase my recommendation* — turn the Compiled Tutor's row into two friendly sentences

Reality checks: first-load download (hundreds of MB, cached), WebGPU coverage, slow on phones, quality ceiling of a sub-1B model. Strictly a progressive enhancement behind a toggle, never the primary path.

**Chrome built-in AI (Prompt / Summarizer / Translator APIs, Gemini Nano).** A free on-device model for a growing share of users, no download on our side. Same page-scoped jobs. Needs an availability check per API before we rely on it; degrade to "not available in this browser".

### 3.3 Source C — the deployment's own server, where one exists

GitHub Pages has no server. But two of our three deployments already run a container:

| Deployment | Server we already own | Runtime AI option |
|---|---|---|
| **RasQberry** | Pi 5 (8 GB), local Jupyter | `llama-server` (llama.cpp) + Granite 4.0 Nano 350M/1B GGUF, CPU. **Fully offline tutor at exhibits** — the single strongest runtime-AI story we have. |
| **Docker** | `jupyter-local` container | Same, optional service in `docker-compose.yml` |
| **Code Engine** | `jupyter-codeengine` (min 0 / max 1, 1 vCPU / 2 GB) | Same sidecar; 350M runs on 1 vCPU, costs free-tier hours only while a learner is active. Keep it **out of the Binder image** (size, federation). |

Wire it like the Jupyter endpoint: an `aiEndpoint` resolved by the existing runtime detection (GitHub Pages → none/WebGPU, localhost/Docker/Pi → local, CE → sidecar) and overridable on `/jupyter-settings`. One codebase, three deployments — the pattern the project is built on.

### 3.4 Source D — the learner's own assistant ("BYO-assistant")

The cheapest runtime AI is the one the learner already pays for. Make doQumentation the best *grounding source* for it:

- **`llms.txt` + `llms-full.txt` + per-page Markdown/`.ipynb`** — the notebooks are already published under `static/notebooks/`; add page-level Markdown and an index so any assistant can fetch clean content. (The config already sets `max-snippet:-1` "for AI search"; this finishes the thought.)
- **"Open in Claude / ChatGPT / Bob" buttons** on each page with a pre-filled prompt ("Read this page and quiz me on it"). Zero cost, works today.
- **A doQumentation MCP server** — a small package exposing `search_pages`, `get_page`, `get_notebook`, `list_course`, `import_progress` over the static index. Learners add it to Claude Desktop, Bob, or any MCP client and get a tutor that knows the site. Ships from the same build that produces the search index.
- **Prompt-pack export** — extend the round-2 *Quantum CV* export: one click produces a paste-ready prompt with the learner's progress, goals, and links. Any assistant turns it into a study plan. This is *individual learning recommendations for $0 in one afternoon*.

### 3.5 BYOK stays the premium tier

The approved strategy (Granite in-browser default, BYOK watsonx.ai, BYOK Anthropic) is untouched; §3.3–3.4 just add two more free rungs below it.

---

## 4. Individual learning recommendations — a layered design

Inputs are what we already track (visited, executed, bookmarks, recent; plus quiz mastery and mock-exam history once round 2 ships) and a **four-question intent form** (goal: cert / research / teaching / curiosity; background; hours per week; preferred lens). Output is **one plan schema** — ordered pages with a reason each, a "this week" cut, and a weakest-topic remediation — rendered by one component, wherever it was produced:

| Layer | Produced by | Latency | Cost | When it's used |
|---|---|---|---|---|
| **L0** | Compiled Tutor decision table | instant | $0 | Always. Default for everyone, offline on the Pi. |
| **L1** | Learner's own assistant via prompt pack / MCP | seconds | $0 | Learner clicks "Refine with my assistant". |
| **L2** | Nightly batched routine (§2.1) | by next morning | Max quota, 1 run/day | Learner opts into "Get a personal plan by tomorrow"; result at `/plan/<id>`. |
| **L3** | In-browser or on-Pi Granite Nano (§3.2–3.3) | seconds | $0 | Rephrases L0 conversationally; explains "why this page next". Optional. |

Guiding rule: **L0 must be good enough that L1–L3 are luxuries.** If the decision table can't recommend well, no model at any tier will fix that; the content graph (round 1 idea 2A) remains the prerequisite.

Privacy line to publish: "Nothing about your progress leaves your browser unless you click a button that says it will."

---

## 5. What else near-time and runtime AI could do here

- **"Is this notebook fresh?" badge** — nightly routine compares each notebook's last sweep result against the current pinned image; page shows *verified on 2.3-xl, 2 days ago*. Trust signal, no learner data involved.
- **Release explainer, delivered** — the round-2 "what changed for learners" draft, but posted as a Discussion the same day the weekly bump merges, with `@claude` answering follow-ups.
- **Per-locale weekly digest** — one routine drafts "new/changed pages in your language" for each locale's community channel; the translation factory already knows the diff.
- **Event QR → live puzzle** — at a booth, the Qoffee/Barista challenge (round 2 §4.2) checks answers client-side; a Bob cron posts a leaderboard digest every 15 min from the anonymous "stamp claimed" events.
- **Accessibility on demand** — page-scoped Nano/Chrome AI generating alt text or a summary for images the build hasn't covered yet; build-time sweep remains the real fix.
- **Docent mode, spoken** — on RasQberry, the local model plus the browser's speech APIs turn the round-2 docent script into a question-answering exhibit voice, offline.

---

## 6. What 500 Bobcoins a month are good for

Bob is a subscription coding agent with multi-model routing, Bob Shell for headless runs, and MCP integration; tasks consume Bobcoins by complexity (≈ $0.50/coin at list). *Caveat: bob.ibm.com docs were unreachable from this session; metering details come from secondary write-ups and should be confirmed on the account page.*

1. **Measure before allocating.** Run five representative tasks (one translation-review batch, one notebook-breakage triage, one headless cron digest, one issue triage, one code change) and log coins per task. Everything below depends on that number.
2. **Model diversity for the review factory.** The refutation gauge and Opus deep review are all one model family. A Bob-routed *second* reader is a genuinely independent opinion on FAILs — the cheapest quality gain available.
3. **Headless CI slots below one hour.** Claude Routines floor at 1 h; Actions cron + Bob covers workshop-day triage (§2.5) and anything else that needs 10–15 min cadence, keeping the Claude daily run cap for the batch jobs.
4. **Qiskit-specific triage on the weekly bump.** The sweep finds breakage; Bob (with Granite Code in the mix) drafts the fix list and PRs for the mechanical ones.
5. **Issue/PR hygiene via GitHub MCP.** Labeling, duplicate detection, first-response — low coin cost per task, frees Max for content work.
6. **The IBM-facing narrative.** "Reviewed with IBM Bob, executed on IBM Code Engine, grounded in IBM Quantum docs" is a slide that writes itself for IBM audiences.

---

## 7. Limits and risks

| Risk | Mitigation |
|---|---|
| Routine daily cap and 1 h floor | Batch (§2.1); use Actions + Bob for sub-hour |
| Max quota shared with interactive work | Nightly routines run off-hours; monitor at claude.ai/settings/usage |
| Secrets in a static site | GitHub as intake, or a stateless relay (§1.1); never a token in the bundle |
| Public relay abuse | Rate limit per IP, size cap, no free-text pass-through beyond the schema |
| Tiny-model quality (Nano, Chrome AI) | Page-scoped only, labeled "experimental", never authoritative; L0 stays deterministic |
| Privacy / GDPR | Opt-in per action, learner sees the payload before it leaves; issue forms are public by nature — say so |
| `@claude` answering wrong things in public | Repo-committed answering skill: cite pages, admit gaps, no invented API |
| Terms of use for subscription automation | OAuth-token GitHub Action is an Anthropic-supported path; Routines are a first-party feature; Bob headless is IBM-documented. Re-check if plans change. |

---

## 8. Sequencing proposal

**Phase A — zero infrastructure (weeks):** `llms.txt` + per-page Markdown → "Open in assistant" buttons → prompt-pack export from the progress panel → enable the Claude GitHub Action with OAuth and the "Ask about this error" link. Individual recommendations exist after this phase (L1), and the site becomes a grounding source for any assistant.

**Phase B — nightly routines (one relay, one branch pattern):** translation-feedback fixer (§2.3) → search-miss compiler (§2.6) → error-report reproducer (§2.4) → batched learning plans (§2.1, L2). Each is the same shape: intake → routine → `claude/` branch → PR/deploy → static JSON.

**Phase C — on-device and on-server models:** Granite Nano sidecar for RasQberry and Docker (§3.3) → Code Engine sidecar → WebGPU/Chrome-AI fallback on GitHub Pages (§3.2) → page-scoped explain/error/lens features → L3 phrasing of recommendations.

**Continuous:** Bob for review diversity and workshop-day triage; coin measurement first.

---

## 9. Open questions

1. **Intake channel for non-GitHub learners**: accept a free Worker relay, or keep everything GitHub-gated (simpler, public, account required)?
2. **L2 at all?** A nightly plan is a nice demo; is it worth a relay and a daily run when L0 + L1 cover most of the value?
3. **Nano in the Code Engine image**: image size vs. cold start — measure before deciding; Pi and Docker first.
4. **Chrome built-in AI**: confirm which APIs are GA for the open web in current Chrome before promising anything.
5. **Bob coin economics**: run the five-task measurement; decide whether the review-diversity slot or the workshop-triage slot gets the budget.
6. **Public answering posture**: do we want `@claude` answering learners in public issues under the maintainer's account, or a dedicated bot identity?

---

## Sources consulted (2026-09-18)

- Claude Code Routines docs: https://code.claude.com/docs/en/routines (triggers, `/fire` endpoint, 1 h minimum, daily run cap, connectors)
- Claude Code GitHub Actions (OAuth for Pro/Max): https://code.claude.com/docs/en/github-actions
- IBM Bob GA / pricing coverage: https://www.theregister.com/software/2026/04/28/ibms-ai-coding-partner-bob-hits-general-availability/5226774 , https://venturebeat.com/orchestration/ibm-launches-bob-with-multi-model-routing-and-human-checkpoints-to-turn-ai-coding-into-a-secure-production-system , https://www.nicklitten.com/ibm-bob-pricing-explained-free-trial-bobcoins-and-pro-plans-on-ibm-i/
- Bob headless / Actions examples: https://github.com/BrUn3y/IBM_Bob_Harness , https://heidloff.net/article/ibm-bob-shell/
- Granite 4.0 Nano in the browser: https://huggingface.co/spaces/ibm-granite/Granite-4.0-Nano-WebGPU , https://github.com/huggingface/transformers.js/
