# The Learner's Own Assistant: grounding layer, entry points, and the doQumentation MCP server

> **Status**: Ideation round 3b (2026-09-18) — a deep dive on §3.4 of [`RUNTIME_AI_IDEAS.md`](./RUNTIME_AI_IDEAS.md). Exploration and design, no implementation commitment.
> **The thesis in one line**: the cheapest, best, and most scalable runtime AI for doQumentation is the assistant the learner already has. Our job is not to run a model; it is to be the **best-grounded, easiest-to-attach knowledge source** for every assistant a learner might bring: claude.ai, ChatGPT, NotebookLM, Claude Code, IBM Bob, a local model on a Pi.
> **Budget frame**: unchanged. Build-time work on Max ≈ $0, runtime $0 (static files) or a free edge Worker. No API tokens anywhere.

---

## 0. Why this is the right first move

| Property | In-site runtime AI (Nano, BYOK, nightly routines) | Learner's own assistant |
|---|---|---|
| Model quality | sub-1B, or whatever the learner configures | frontier models, whichever the learner pays for |
| Cost to us | $0 only with heavy constraints | $0, no constraints |
| Scales with traffic | only if precomputed | yes, trivially |
| Privacy | best (nothing leaves) | learner's choice, explicit per action |
| Reach | everyone on the site | everyone with an assistant (which is now most learners) |
| Can execute Qiskit | only through our Jupyter backends | yes, if the assistant has a terminal (Claude Code, Bob, Desktop + local MCP) |
| What we control | everything | **only the grounding and the prompts** |

The last row is the design constraint. We cannot control the assistant, so everything we build is one of three things: **content the assistant can fetch cleanly**, **an entry point that hands it the right content with the right instruction**, or **a tool surface (MCP) that makes fetching, searching, and recommending precise**. Everything below is one of those three.

---

## 1. Layer 1 — The grounding layer: content as data

Nothing else works if an assistant fetching a page gets a React shell, JSX, or a search-index blob. Today a fetch of any page returns rendered Docusaurus HTML: usable, but noisy, and the executable-code cells, admonitions, and notebook outputs arrive as markup. The fix is a set of build-time artifacts, one per locale (every locale is its own build with its own subdomain, so per-locale versions fall out for free).

### 1.1 What to emit

| Artifact | Path | Purpose | Source |
|---|---|---|---|
| **Per-page Markdown** | `<page-path>.md` next to every page (e.g. `/tutorials/hello-world.md`) | The canonical thing an assistant should read. Clean: admonitions → blockquotes, `<ExecutableCode>` → fenced `python`, images absolute, banners and feedback widgets dropped. | The existing `clean_notebook_markdown()` in `scripts/sync-content.py` already does most of this for the Colab copies; reuse it rather than a third-party plugin, so the 17 locales and our custom MDX components are handled identically. |
| **`/llms.txt`** | site root | The curated index per the llmstxt.org convention: title, one-line description, URL per page, grouped by tutorials / guides / courses / addons, with a short site preamble (what it is, execution model, license, unofficial status). | Descriptions come from round-1 idea 2A (page metadata) — this is the first consumer that makes 2A worth generating. Until then, first paragraph. |
| **`/llms-full.txt`** | site root | Everything concatenated. Useful for tools that ingest one file. | Concatenation of the per-page `.md`. |
| **Course knowledge packs** | `/llms/<course-or-section>.txt` | One file per course or guide section, sized to fit a Claude Project, a custom GPT, or a NotebookLM notebook as *knowledge*. This is the piece that lets a learner say "add this course to my Project" instead of pasting pages. | Sidebar structure in `sidebars.ts` defines the packs. |
| **`/api/index.json`** | site root | Machine index: `id, title, description, path, section, locale, notebook_path, executable, upstream_date, word_count, related[], prerequisites[], difficulty` (the last three arrive with 2A). | Generated where `contentMeta.ts` and `upstreamFileMeta.json` are generated today. |
| **Notebooks** | `/notebooks/**.ipynb` | Already published at build. Add them to the index so an assistant with a terminal can pull the exact executable artifact. | Exists (`publish_notebooks_to_static()`). |
| **Transcripts** | `/transcripts/<id>/<locale>.*` | Already published. Index them by the page that embeds the video. | Exists. |
| **`<link rel="alternate" type="text/markdown">`** | every page's `<head>` | Lets fetchers that honor it find the `.md` sibling. Belt and braces with the `.md` suffix convention. | One line in the theme. |

Every `.md` carries a header block: source page URL, locale, upstream commit and date, CC BY-SA 4.0 attribution to IBM's Qiskit documentation, the "unofficial mirror" line, and the pinned Qiskit version the code was verified against. The license *requires* the attribution; the version line prevents the most common assistant failure mode (explaining Qiskit 1.x API against 2.x code).

### 1.2 Build mechanics

A small Docusaurus plugin in `plugins/` in the style of `plugins/page-dates` (reads the docs tree, writes to the build output in `postBuild`), or a step in `sync-content.py`. Either way: locale-scoped, runs in the same per-locale build, adds seconds. Per-page files add ~433 small files per locale build; trivial against the ~320 MB build.

`robots.txt` already allows all crawlers; keep it that way and do not block assistant fetchers. `max-snippet:-1` is already set. Add the `llms.txt` line to the site footer and `/ai` hub page (§2.4) so humans find it too.

### 1.3 What this alone unlocks (before any MCP)

- Any assistant with web fetch reads the exact page, in the learner's language, with correct code and version context.
- NotebookLM users add `llms-full.txt` or a course pack as a source and get the round-1 NLM-1 audio overview without us building anything.
- Claude Projects and custom GPTs get a course as knowledge in one upload.
- Claude Code and Bob users can `curl` a tutorial into their working directory and run it.

---

## 2. Layer 2 — Zero-infrastructure entry points on the page

The grounding layer is passive. These buttons make the first use a one-click experience and encode *our* pedagogy in the prompt.

### 2.1 "Open in your assistant" (split button in the page header, next to Lab | Colab)

Targets that accept a URL-prefilled prompt: claude.ai (`/new?q=`), ChatGPT (`?q=`), Perplexity, and any others that adopt the convention. *(Verify the exact query parameter for each before shipping; they change.)* Bob and NotebookLM have no prefill URL; for those the button falls back to "Copy prompt".

The prompt is a template chosen by a small menu, localized through `code.json`:

| Menu item | Prompt (abbreviated) |
|---|---|
| Explain this page | Read `<page>.md`. Explain it at the level of someone who has done `<prerequisites>`; keep the code; stop and ask me one question per section. |
| Quiz me | Read `<page>.md`. Ask me 5 questions of increasing difficulty; do not reveal answers until I attempt each. |
| Help me with this error | Read `<page>.md`, cell `<n>`. I got `<ErrorClass>` with this traceback: `<…>`. Qiskit version `<pinned>`. Diagnose, then propose the smallest fix. |
| Explain like I'm 12 / math-first / code-first | The round-2 persona lenses, live and free, for pages that have no precomputed lens. |
| Continue my learning (see §2.3) | Prompt pack. |

Rules baked into every template: *cite the page section you rely on; if the page doesn't cover it, say so before answering from general knowledge; assume the pinned Qiskit version.* We cannot enforce this, but a template that asks for it measurably changes behavior, and it is the only lever we have.

### 2.2 "Copy page as Markdown" / "View as Markdown"

The pattern every AI-friendly docs site has converged on. One button, copies the `.md` content (or opens the sibling URL). Also the fallback for assistants without a prefill URL.

### 2.3 "Copy my learning context" — the prompt pack

Reads what we already store (`dq-visited-pages`, `dq-executed-pages`, `dq-bookmarks`, `dq-recent-pages`; later quiz mastery and mock-exam history from round 2) plus a four-question intent form (goal, background, hours per week, preferred lens), and renders a paste-ready block:

```
You are my Qiskit tutor. Site: https://doqumentation.org (fetch any page as <path>.md).
Goal: pass the Qiskit developer certification in ~8 weeks. Background: linear algebra yes, QM no. Time: 3 h/week.
Done (executed code): Hello World, Basics of quantum information §1–2, Primitives guide.
Visited but not executed: Transpiler intro, Error mitigation.
Bookmarked: Grover's algorithm tutorial.
Course structure: https://doqumentation.org/llms.txt
Ask me two diagnostic questions, then propose the next 3 pages with one-sentence reasons, and a plan for this week. Cite pages.
```

The learner sees the block in a textarea before copying; nothing is sent anywhere. This is the L1 layer of the recommendation design in `RUNTIME_AI_IDEAS.md` §4, and it exists after one component and one settings-page section.

### 2.4 The `/ai` hub page

One page, translated: what the grounding files are, the recipes per assistant (Claude Project + course pack; custom GPT; NotebookLM sources; Claude Desktop one-click bundle; Claude Code plugin; Bob `.bob/mcp.json`; claude.ai custom connector URL), the privacy statement, and the honest caveats (assistants can still be wrong; the site is the source of truth; unofficial). It is also where the "add doQumentation to your assistant" story lives for talks and workshops.

---

## 3. Layer 3 — The doQumentation MCP server

### 3.1 What it is and is not

An MCP server is the difference between "the assistant can fetch a URL if it thinks of it" and "the assistant has `search`, `get_page`, `next_steps`, and a quiz prompt as first-class tools it reaches for". It does **not** add intelligence; it adds precision, discoverability, and our pedagogy as tool descriptions and prompt templates.

Design principles, each mapped to a constraint we already live with:

1. **Stateless.** The MCP spec revision 2026-07-28 removed the initialization handshake and protocol sessions; list results are cacheable and deterministic. That fits a static-content server perfectly: no Durable Objects, no session store, hostable on a free edge Worker or a laptop identically.
2. **Content-free.** The server holds no content. It fetches `/api/index.json` and the `.md` files from the site (edge-cached), so a deploy of the site is a deploy of the server's knowledge. The same binary serves English or any locale by parameter, and serves a RasQberry's local copy by pointing at `http://rasqberry.local`.
3. **Read-only.** No tool writes anywhere. That is what makes authless hosting acceptable and keeps the abuse surface to "someone downloads our public docs quickly".
4. **One codebase, two transports.** stdio for local clients, Streamable HTTP for remote. TypeScript, because Claude Desktop bundles a Node runtime (so a `.mcpb` bundle works out of the box) and Cloudflare Workers are TypeScript-native.

### 3.2 The tool surface (v1)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `search` | `query, locale?, section?, limit?` | ranked `{id, title, path, snippet, section}` | In-process BM25/MiniSearch over `index.json` descriptions and headings; optionally the domain synonym map from round 1 (idea 1C) so "entangle" finds "Bell state". Zero-hit queries are the best search-miss signal we will ever get (§6). |
| `get_page` | `path, locale?, section_heading?` | Markdown, or one section of it | Section slicing keeps context small; the assistant asks for "## Build the circuit" rather than 6,000 words. |
| `get_notebook` | `path, as: "ipynb" \| "python"` | the executable artifact | For assistants with a terminal. |
| `get_toc` | `section \| course` | ordered list with prerequisites and difficulty (2A) | The structure an assistant needs to plan. |
| `next_steps` | `progress{visited[], executed[], mastery{}}, goal?` | ordered recommendations with reasons | **The Compiled Tutor decision table, exposed as a tool.** Same engine, same JSON as the site's L0 layer; the assistant adds the conversation around a deterministic core. |
| `get_transcript` | `video_id \| page, locale` | text | 55 videos × 18 languages already exist. |
| `environment` | — | pinned package list, image tags, Binder/Colab/CE URLs for a page | Lets a local assistant reproduce our environment exactly (`binder/jupyter-requirements.txt`, QuBins tag), so its results match the site. |
| `error_hint` | `error_class, page?` | known cause and fix | Backed by the inline error-hint table once the flywheel (round 2 §6) produces it. |

**Resources**: `doq://<locale>/<path>` for every page (so Claude Desktop users can "attach" a page), `doq://<locale>/index`, `doq://<locale>/toc/<section>`.

**Prompts** (parameterized templates, the MCP primitive most servers ignore and the one that carries our pedagogy): `quiz_me(page, n)`, `explain(page, lens)`, `study_plan(progress, goal, hours_per_week)`, `debug_cell(page, cell, traceback)`, `cert_drill(objective)` (once the round-2 question bank exists). Tool descriptions and prompt texts are generated and iterated at build time on Max, and evaluated (§5).

Deliberately **not** in v1: `run_code` (the assistant's own terminal or our Jupyter backends do that; an execution tool would need a backend budget), any write tool (issue filing, feedback), and anything that needs learner identity.

### 3.3 Distribution: how each assistant attaches it

| Client | Mechanism | Auth | Plan needed | Effort for the learner |
|---|---|---|---|---|
| **Claude Desktop** | `.mcpb` bundle from the `/ai` page (Node runtime ships with the app) | none | any | download, double-click |
| **Claude Code** | plugin marketplace in this repo: `/plugin marketplace add JanLahmann/doQumentation` → `/plugin install doqumentation` installs the MCP server **and** a `qiskit-tutor` skill together (§4) | none | any | two commands |
| **IBM Bob** | `.bob/mcp.json` snippet (project) or `~/.bob/mcp_settings.json` (global); ship a Bob skill that writes it | none | any | paste a snippet |
| **claude.ai web / mobile** | custom connector pointing at the remote URL; authless servers are supported, Streamable HTTP required | none | custom connectors are a paid-plan feature (verify current tiers) | paste a URL |
| **ChatGPT** | developer-mode connector at the remote URL | sources disagree on whether no-auth is accepted or OAuth 2.1 + dynamic client registration is mandatory; **verify before promising** | paid plan | paste a URL |
| **Any MCP client** (Cursor, Zed, VS Code, local-model UIs) | `npx @doqumentation/mcp` stdio, or the remote URL | none | — | one config line |
| **RasQberry / offline** | the same stdio server with `--site http://rasqberry.local` | none | — | pre-installed on the Pi image |

Aspiration, later: submit to the **Claude Connector Directory** so claude.ai users find "doQumentation" in the connector list without pasting anything. The submission requirements are public; a read-only, authless, well-annotated server is the easy case.

### 3.4 Hosting the remote endpoint

| Option | Cost | Fit |
|---|---|---|
| **Cloudflare Worker** with the stateless MCP handler (the SDK's stateful `McpAgent` is deprecated; the stateless handler needs no Durable Objects, so the free plan's 100k requests/day suffices) | $0 | Best. Edge-cached fetches of our static files; also the natural home for the one stateless relay from `RUNTIME_AI_IDEAS.md` §1.1, so one Worker serves both. |
| **IBM Code Engine** app | free-tier hours | The IBM-native story; cold starts and min-instance settings matter for an interactive tool. Worth having as a second deployment target of the same code, not the primary. |
| **GitHub Pages** | — | Cannot: MCP over HTTP needs POST handling. |

A remote server sees tool calls but never learner identity; log tool name, query text for `search`, locale, and a coarse timestamp, nothing else, and say so on `/ai`.

---

## 4. The executable tutor: Claude Code and Bob as the runtime

The strongest form of "the learner's own assistant" is one that has a terminal. Then the assistant can *run* the tutorial, not just read it. Package that as a skill, shipped in the same plugin as the MCP server:

**`qiskit-tutor` skill (Claude Code plugin; Bob skill twin):**
1. Create a venv from `environment` (our pinned requirements, same as Binder and Code Engine), so results match the site.
2. `get_notebook` the chosen tutorial; run it cell by cell; explain each output in the learner's words; stop at checkpoints and ask.
3. Encourage modification: "change the angle and re-run"; compare outputs; explain the difference.
4. Quiz at the end via the `quiz_me` prompt; record mastery in a local `progress.json` the site can import (§7).
5. On error: `error_hint` first, then reasoning; never silently pin a different Qiskit version.

Notably, this skill is the same thing our notebook sweep does mechanically, with pedagogy on top. It also creates a **"bring your own agent" workshop track**: participants with Claude Code or Bob install the plugin and work through a tutorial with an executing tutor, no Binder queue, no Code Engine pool. For Bob users this is an IBM-tool-on-IBM-content demo that sells itself.

---

## 5. Build-time work on Max (where the effort actually goes)

- **Page descriptions and metadata (2A)** — first real consumer is `llms.txt` and `search`.
- **Prompt and tool-description authoring** — tool descriptions are prompts; a poor `search` description means the assistant never calls it. Write, then test.
- **An assistant eval as a CI job** — 50–100 learner questions ("how do I run on a real device with the free plan?", "why does my Estimator return negative expectation values?", in several locales) run through the MCP by a Claude Code session, graded on: did it call the tools, did it cite the right page, did it use the pinned API, did it admit gaps. Regressions block a deploy of the server. This is the same adversarial-verification reflex as the translation review factory, aimed at the tool surface.
- **Course packs and per-section prompts** — generated from the sidebar structure and regenerated on every sync.
- **Localization** of prompt templates through the existing translation factory: they are content.

---

## 6. What flows back (the flywheel, assistant edition)

We cannot see what assistants do with a fetched `.md` (GitHub Pages has no logs). Three signals we *can* collect, all anonymous:

| Signal | Where | Feeds |
|---|---|---|
| Clicks on "Open in assistant", "Copy as Markdown", "Copy context" and which template | Umami events (browser) | Which entry points and pedagogies learners actually use |
| `search` queries with zero hits on the remote MCP | Worker log | The search-miss compiler in `RUNTIME_AI_IDEAS.md` §2.6 — the highest-signal misses we will ever get, because they are phrased by a model trying to help a real learner |
| `get_page` frequency per page vs. site page views | Worker log vs. Umami | Pages that assistants reach for disproportionately are candidates for better metadata or bridge pages |

---

## 7. The progress bridge: localStorage ↔ assistant ↔ site

Three flows, one contract (the plan schema from `RUNTIME_AI_IDEAS.md` §4):

1. **Out, by paste**: the prompt pack (§2.3). Works everywhere, today.
2. **Out, by file**: "Export progress" writes `progress.json` (the round-2 import/export, UX-15). The local MCP server reads `~/.doqumentation/progress.json` if present, so `next_steps` and `study_plan` know the learner without pasting.
3. **In, by import**: an assistant produces a plan in the shared schema; the learner pastes or imports it; the site renders it with the same component as the L0 compiled plan and the L2 nightly plan. The assistant's plan becomes a first-class site object, still with no backend.

---

## 8. Risks and honest limits

| Risk | Mitigation |
|---|---|
| The assistant answers from memory instead of fetching | Templates demand citations; the MCP makes fetching cheaper than guessing; nothing can force it. Say so on `/ai`. |
| Wrong Qiskit version in answers | Version line in every `.md` header and in every prompt; `environment` tool. |
| Platform churn: MCP spec just moved to 2026-07-28, connector rules and prefill URLs change | Thin server on the official SDK; a CI eval that fails loudly; verify the per-client table before each release. |
| Free-Worker abuse | Read-only, rate-limited per IP, response size caps; worst case someone mirrors public docs. |
| License and trademark | CC BY-SA attribution in every artifact; "unofficial, not affiliated with IBM" in `llms.txt` preamble and `/ai`. |
| Learner data | Nothing leaves the browser without a click that says so; remote server logs no identity; local server reads a file the learner created. |
| Maintenance load | Everything regenerates from the existing sync; the server has no content of its own; the eval catches drift. |

---

## 9. Sequencing

**Step 1 — grounding (one focused session + review):** per-page `.md` reusing `clean_notebook_markdown()`, `llms.txt`, `llms-full.txt`, `index.json`, `<link rel="alternate">`, header block with license and version. Ship for English, then all locales ride the same build.

**Step 2 — entry points (frontend week):** "Open in assistant" split button with the template menu, "Copy as Markdown", the prompt pack in the progress panel, the `/ai` hub page, Umami events. Individual recommendations via the learner's assistant exist after this step.

**Step 3 — MCP v1 (two sessions + a Worker deploy):** TypeScript package, stdio + Streamable HTTP, `search` / `get_page` / `get_notebook` / `get_toc` / `environment`, resources, `quiz_me` / `explain` / `debug_cell` prompts. `.mcpb` bundle, Claude Code plugin marketplace with the `qiskit-tutor` skill, Bob snippet. CI eval.

**Step 4 — course packs, `next_steps`, `error_hint`, progress file:** as 2A metadata, the compiled tutor, and the flywheel land. Connector Directory submission when the server has been stable for a month.

**Cost:** build-time on Max; runtime $0 (static) + a free Worker. The only new operational surface is the Worker.

---

## 10. Open questions

1. **Own build step vs. a community `llms.txt` plugin?** Own step is recommended: we already have the MDX cleaning code, 17 locales, and custom components the plugins don't know about.
2. **TypeScript for the MCP server** (Node ships with Claude Desktop; Workers-native) vs. Python (matches the pipeline). Recommendation: TypeScript.
3. **Worker vs. Code Engine as the primary remote host.** Recommendation: Worker primary, Code Engine as a documented second target for the IBM story.
4. **Do we want to be in the Claude Connector Directory** under the maintainer's name, or wait for the org migration (`ORG_MIGRATION_PLAN.md`)?
5. **Prefill URL parameters and ChatGPT auth rules** must be verified at implementation time; both changed within the last year.
6. **How much pedagogy goes into prompts vs. the skill?** Prompts travel to every client; the skill only to Claude Code and Bob. Recommendation: pedagogy in prompts, execution mechanics in the skill.

---

## Sources consulted (2026-09-18)

- MCP specification 2026-07-28 changelog (stateless model, cacheable lists, no protocol sessions): https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx
- Cloudflare Agents SDK 0.20 / stateless MCP handler and `McpAgent` deprecation: https://developers.cloudflare.com/changelog/post/2026-07-27-agents-sdk-v0.20.0-mcp-sdk-v2/ , https://bex.co/blog/2026/09/13/cloudflare-agents-sdk-stateless-mcp-handler
- Claude custom connectors (remote MCP, authless supported, Streamable HTTP): https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp , https://sunpeak.ai/blogs/what-are-claude-connectors/ , directory submission: https://sunpeak.ai/blogs/claude-connector-directory-submission/
- MCP Bundles (`.mcpb`) for Claude Desktop, Node runtime bundled: https://github.com/modelcontextprotocol/mcpb
- Claude Code plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces
- IBM Bob MCP configuration (`.bob/mcp.json`, `~/.bob/mcp_settings.json`): https://bob.ibm.com/docs/ide/configuration/mcp/mcp-in-bob , https://bob.ibm.com/docs/shell/configuration/mcp/mcp-bobshell
- ChatGPT developer mode and connector requirements (conflicting on auth; verify): https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt , https://peliqan.io/blog/chatgpt-mcp/
- Docusaurus `llms.txt` plugins for comparison: https://www.npmjs.com/package/@signalwire/docusaurus-plugin-llms-txt , https://www.npmjs.com/package/docusaurus-plugin-llms
