# AI Features Brainstorming: doQumentation

> **Status**: Ideation / brainstorming — exploring possibilities, not committing to implementation yet.
> **Budget constraint**: Very limited monthly cost. Use existing Claude Code Max subscription for build-time AI work. For any runtime AI, use IBM public cloud, IBM Code Engine, or IBM serverless (Granite models on watsonx.ai Lite/Essentials plan).
> **Priority features**: Smart Search & Navigation, Adaptive Learning Paths
> **Deferred for now**: Interactive Quantum Circuit Debugger
> **Note**: Single canonical AI-ideation doc. The older `AI_INTEGRATION_IDEAS.md` (2026-03-08) was merged into the section at the bottom of this file on 2026-05-17 and deleted (original in git history).

---

## What We Have Today

| Aspect | Current State |
|--------|--------------|
| **Site** | Docusaurus 3.7.0, fully static, no backend |
| **Content** | 381 pages: 42 tutorials, 171 guides, 154 course pages, 14 modules |
| **Search** | `@easyops-cn/docusaurus-search-local` — keyword-only, client-side, 10 languages |
| **User tracking** | localStorage/cookies: visited pages, executed pages, bookmarks, recent pages (anonymous, no backend) |
| **Learning structure** | Sidebar ordering implies sequence, but no formal prerequisites, difficulty tags, or content graph |
| **Navigation** | No "Related Topics", no "Next Steps", no cross-references between content silos |

---

## Feature 1: Smart Search & Navigation

### The Problem
- Keyword search can't handle conceptual queries ("How do I entangle two qubits?" won't find "Bell state" or "CNOT gate" pages)
- 381 pages across 4 content types (tutorials, guides, courses, modules) with no bridges between them
- Pages end abruptly — no "Related Topics" or "You might also like..." (UX-20, UX-39)
- No search facets or filters (UX-40)

### Idea Space

**A. Semantic search via build-time embeddings**
- Generate vector embeddings for all 381 pages at build time (using Claude Code Max or IBM Granite embedding model)
- Ship as a static index (~5-10MB) with the site
- Client-side vector similarity search — user types a natural-language question, gets ranked results
- Works offline, zero runtime cost
- *Question*: Is 5-10MB acceptable for static site bundle? Could lazy-load the index.

**B. AI-generated "Related Pages" metadata**
- Use Claude to analyze all pages and generate `related: [page1, page2, page3]` for each
- Render as "Related Topics" cards at the bottom of every page
- One-time generation cost, re-run when content changes
- Could also generate a full content graph (which pages reference which concepts)
- *This alone would be a big UX win even without changing search.*

**C. Quantum computing synonym/concept map**
- Build a domain-specific thesaurus: "entangle" ↔ "Bell state" ↔ "CNOT" ↔ "EPR pair"
- Use it to expand search queries before hitting the existing keyword search
- Zero infrastructure change, just a static JSON map
- Could be AI-generated and human-curated
- *Lowest effort, highest bang-for-buck improvement to existing search.*

**D. Hybrid: static search + optional "Ask AI" button**
- Combine A or C for instant results
- Add an "Ask AI" button that sends query + top 3 page excerpts to IBM Code Engine serverless function
- Function calls Granite (free tier) or Claude to synthesize an answer with citations
- Scales to zero, pay-per-use
- *Progressive enhancement: search works without AI, AI makes it better.*

**E. Search with facets**
- Add content-type filters (Tutorial / Guide / Course / Module) to search results
- Add difficulty filter (once we have difficulty metadata from Feature 2)
- Could be done with the existing search plugin + client-side filtering
- *Complements any of the above approaches.*

### Interesting Combinations
- **C + B**: Synonym-enhanced keyword search + AI-generated Related Pages. Zero cost, significant UX improvement.
- **A + B + E**: Full semantic search with related pages and facets. Zero runtime cost but more build-time effort.
- **A + D**: Semantic search with optional AI synthesis. Near-zero cost at low traffic.

### IBM Angle
- **IBM Granite embedding models** on watsonx.ai could generate embeddings at build time
- **IBM Code Engine** (serverless) for the optional "Ask AI" endpoint — scales to zero
- **Granite free tier**: 1M tokens/month on IBM Cloud — likely sufficient for low-traffic Q&A

---

## Feature 2: Adaptive Learning Paths

### The Problem
- 381 pages with no difficulty indicators (UX-45) — newcomers hit advanced material unknowingly
- No prerequisites — users don't know what to study first (UX-41, UX-30)
- Progress tracking exists (visited/executed) but measures *exposure*, not *comprehension* (UX-33). Currently `dq-visited-pages` and `dq-executed-pages` are based just on "page visited" — may need a user self-assessment like "understood the concepts" to make adaptive learning meaningful.
- No personalized recommendations — everyone sees the same sidebar order
- Content silos (Tutorials, Guides, Courses, Modules) don't connect to each other

### Idea Space

**A. AI-generated content metadata (the foundation)**
- Use Claude (via Max subscription) to analyze all 381 pages and tag each with:
  - `difficulty: beginner | intermediate | advanced`
  - `prerequisites: ["/path/to/page1", "/path/to/page2"]`
  - `leads_to: ["/path/to/next1", "/path/to/next2"]`
  - `topics: ["quantum-gates", "entanglement", "error-correction", ...]`
  - `estimated_time: "15 min"`
- Store as frontmatter or a separate static JSON manifest
- *This metadata enables everything else — difficulty badges, prerequisite chains, recommendations, the content graph for search.*

**B. Difficulty badges in sidebar and page headers**
- Visual indicators: color-coded tags (green/yellow/red or Beginner/Intermediate/Advanced)
- Show in sidebar items and at the top of each page
- Simple CSS + frontmatter, no runtime AI
- *High UX value, low effort once metadata exists.*

**C. Prerequisite breadcrumbs**
- Above page content: "Before this: [Intro to Qubits] → **This Page** → Next: [Entanglement]"
- Visual learning path context that helps users navigate intentionally
- Built from `prerequisites` and `leads_to` metadata
- *Addresses UX-41 directly.*

**D. Client-side recommendation engine**
- Use visited/executed pages (already tracked!) + content graph (from A) to suggest next steps
- Simple rules: "You've completed 3/4 prerequisites for page X → Recommended next"
- Show as a "Suggested Next" widget on homepage and/or page footer
- Could also power a "Learning Dashboard" showing progress through a visual content map
- *Zero runtime cost, leverages existing infrastructure.*

**E. Knowledge assessment quiz**
- AI-generate a short quiz (5-10 questions) per course section at build time
- Store as static JSON, render client-side
- Score determines starting recommendation: "Skip ahead to Section 3" or "Start from the beginning"
- Also serves as a comprehension check (addresses UX-33)
- *Adds interactivity, helps newcomers find their level.*

**F. "Where should I start?" AI advisor**
- Serverless function on Code Engine that takes: visited pages + self-assessment ("I know basic linear algebra but not quantum mechanics")
- Returns a personalized learning path with reasoning
- Uses the content graph as context
- *Per-call cost but infrequent usage (once per session). Could use Granite free tier.*

**G-bis. Self-Assessment: "I understood this" button**
- Add a lightweight self-assessment at the bottom of each page: "Did you understand the concepts?" (Yes / Partially / No)
- Store as `dq-understood-pages` in localStorage alongside visited/executed
- The recommendation engine (D) could use this signal: pages marked "Partially" or "No" get suggested for revisit; pages marked "Yes" unlock downstream prerequisites
- Bridges the gap between *exposure tracking* (current) and *comprehension tracking* (needed for true adaptive learning)
- *Zero runtime cost, simple UI, meaningful signal for personalization*

**G. Visual content map / knowledge graph**
- Interactive visualization showing all 381 pages as nodes, connected by prerequisites
- Color-coded by visited/unvisited/executed
- Users can see their progress and discover unexplored areas
- Could be a dedicated page or an overlay
- *High effort but very cool. D3.js or similar.*

### Interesting Combinations
- **A + B + C**: Metadata + difficulty badges + prerequisite breadcrumbs. Foundation-level, zero runtime cost, big UX improvement.
- **A + B + C + D**: Add client-side recommendations. "You've done 80% of the entanglement prerequisites — try this next."
- **A + E + D**: Metadata + quizzes + recommendations. Full adaptive experience, still zero runtime cost.
- **A + B + C + D + G**: The full vision — metadata, badges, breadcrumbs, recommendations, and a visual knowledge graph.

### What We Can Build On
- `dq-visited-pages` and `dq-executed-pages` already track user progress per page
- `dq-recent-pages` stores last 10 visited with timestamps
- Sidebar already shows per-category visit counts ("3/10 visited")
- `src/config/preferences.ts` has `getProgressStats()` returning visited/executed by category
- Course structure in `sidebar-courses.json` already implies ordering
- `src/theme/DocSidebarItem/` already renders progress indicators (visited/executed icons)

---

## The Shared Foundation: Build-Time AI Enrichment

Both features benefit from the same foundation: **AI-generated content metadata**.

A single build-time process could analyze all 381 pages and produce:

| Output | Used By |
|--------|---------|
| `related: [...]` per page | Smart Search (Related Pages) |
| `topics: [...]` per page | Smart Search (facets, synonym map), Learning Paths (content graph) |
| `difficulty: ...` per page | Learning Paths (badges, filtering) |
| `prerequisites: [...]` per page | Learning Paths (breadcrumbs, recommendations) |
| `leads_to: [...]` per page | Learning Paths (breadcrumbs, recommendations) |
| `estimated_time: ...` per page | Learning Paths (session planning) |
| Vector embeddings per page | Smart Search (semantic search) |
| Synonym/concept map | Smart Search (query expansion) |

This could run as a script using Claude Code Max — zero additional cost beyond the existing subscription.

---

## Cost Thinking

| What | Monthly Cost | Notes |
|------|-------------|-------|
| Build-time metadata generation | **$0** | Claude Code Max (existing) |
| Static assets (embeddings, JSON) | **$0** | Shipped with site |
| Client-side search + recommendations | **$0** | Runs in browser |
| "Ask AI" on Code Engine (optional) | **~$0-5/mo** | Scales to zero, Granite free tier |
| "Where should I start?" advisor (optional) | **~$0-2/mo** | Infrequent calls, Granite free tier |

**Strategy**: Maximize build-time AI, minimize runtime AI. Progressive enhancement — everything works without a backend, AI just makes it better.

---

## IBM Cloud & Granite: RAG Possibilities

### What's Available

| Service | What It Does | Free Tier | Fit |
|---------|-------------|-----------|-----|
| **Granite models on watsonx.ai** | LLM inference (chat, generation) | Lite plan: ~25K tokens/month | Good for low-traffic Q&A |
| **Granite embedding models** | `granite-embedding-125m` (768d), `granite-embedding-30m` (384d) | Included in Lite plan | Good for embedding 381 pages |
| **IBM Code Engine** | Serverless containers/functions | 100K vCPU-sec + 200K GB-sec/month free | Perfect for API endpoints |
| **watsonx Assistant** | Managed chatbot + search integration | Lite: 1,000 MAUs/month free | Could be the "Ask AI" frontend |
| **watsonx Discovery** | Document ingestion + semantic search | 30-day trial only (~$500+/mo after) | Too expensive |

### RAG Architecture Ideas

**Idea R1: Fully Static RAG (zero runtime cost)**
- Pre-compute Granite embeddings for all 381 pages (one-time, via watsonx.ai API)
- Ship embeddings as a static file — at 381 vectors this is only **~300KB gzipped** (not 5-10MB as initially feared)
- Client-side cosine similarity in JavaScript — at 381 vectors, brute-force takes <1ms, no HNSW/FAISS needed
- Could even embed the query client-side using a small ONNX model in the browser
- No backend needed, works offline
- *Limitation*: No synthesized answers — just better page ranking. But great as a foundation.

**Idea R2: Client-side search + Code Engine LLM synthesis**
- **Split architecture**: Vector search happens client-side (instant, free), only the LLM call goes to Code Engine
- User types question → browser does cosine similarity over 381 embeddings → finds top 3 pages → sends question + page excerpts to Code Engine function → function calls LLM → returns synthesized answer with citations
- This halves the cold-start problem (search is instant, only "thinking" takes time)
- Also saves token budget (Code Engine only receives the relevant chunks, not the full index)
- *This is the most promising pattern for our constraints*

**Idea R3: watsonx Assistant as the "AI Tutor"**
- Managed chatbot with "conversational search" (synthesizes answers from documents with citations)
- Web chat widget (single script tag, works on Docusaurus), 13+ languages, custom extensions
- **Cost reality check**: Lite plan only covers **140 MAUs** (too small). Plus plan: **~$140/month** (over budget).
- *Verdict*: Too expensive. Could prototype on Lite (140 users fine for testing), but not viable for production.
- *Better path*: Build lightweight RAG ourselves (R2) at $0-5/month

**Idea R4: Hybrid static + on-demand**
- Client-side semantic search (R1) for instant ranked results — no "Ask AI" button needed for basic search
- "Ask AI" button only appears when user wants a synthesized answer — triggers R2
- Most queries answered by client-side search alone, LLM called rarely
- *Best cost/value ratio*: Bulk of queries free, AI synthesis only when explicitly requested

**Idea R5: WebLLM / fully client-side LLM**
- Run Granite 2B or Phi-3 Mini entirely in the browser via WebGPU — no backend at all, zero cost
- *Reality check*: 1-3GB model download on first visit (cacheable), requires WebGPU-capable browser (~70% of users), slow on phones (~10-20 tok/s on good GPUs)
- *Best as*: An "offline mode" toggle or progressive enhancement, not the primary experience

### Which LLM for the Code Engine Function?

| Model | Cost at 100 queries/mo | Quality | Ecosystem |
|-------|----------------------|---------|-----------|
| **Granite 3.1 8B** on watsonx.ai | $0 (Lite: ~25K tok/mo free) | Good for factual Q&A | IBM native |
| **Claude Haiku 3.5** via API | **~$0.04/month** | Excellent reasoning | External API |
| **Claude Sonnet** via API | **~$0.50/month** | Best quality | External API |
| **Self-hosted Granite 2B** on CE | $0 (if fits free tier) | Lower quality | IBM, no API limits |

**Surprise finding**: Claude Haiku via API is incredibly cheap at this traffic level (~$0.04/month for 100 queries). It's far more capable than Granite Lite for quantum-specific questions. The trade-off is using an external API vs. staying in the IBM ecosystem.

### Code Engine Specifics

- **Function type**: Code Engine **Functions** (not Apps) — short-lived request/response, scale to zero, Python runtime
- **Free tier**: 100K vCPU-seconds/month — more than enough for 100-500 queries
- **Cold start**: 2-5 seconds for Python function. Mitigations:
  - Keep container image minimal (<100MB)
  - Pre-warm with a cron ping every 15 min (almost free)
  - Use client-side search (R1/R2) so the delay feels like "AI is thinking" not "page is loading"
- **Vector index in container**: Bundle the `.npy` embeddings file directly in the container image (~200KB). No external DB needed at this scale.

### RAG Patterns for Education (Nice Ideas)

- **Source citations**: Append `[Source: Tutorial - Bell States](/tutorials/bell-states)` to each answer. Trivial and high-value.
- **Code snippets**: Include Qiskit code blocks from matched chunks verbatim in the answer
- **Adaptive complexity**: Classify query sophistication and adjust the system prompt: "Explain for a beginner" vs. "Assume familiarity with quantum circuits"
- **Circuit diagrams**: Store image paths in chunk metadata; render as `![diagram](url)` in markdown answers. Not truly multi-modal, but effective.
- **"Learn more" links**: Append top-3 related pages from vector search, beyond the ones used for the answer
- **"I didn't find what you need"**: If confidence is low, suggest the user try the keyword search or browse a specific section

### The Sweet Spot

The most promising architecture for our budget:

```
User types question
    ↓
Browser: cosine similarity over 381 pre-computed embeddings (~300KB static file)
    ↓
Instant: show top 5 ranked pages (free, works offline)
    ↓
Optional "Ask AI" button
    ↓
Code Engine Function: receives question + top 3 page excerpts
    ↓
Calls Granite (free) or Claude Haiku (~$0.04/mo)
    ↓
Returns synthesized answer with citations + code snippets + "Learn more" links
```

**Total estimated cost: $0-1/month** at 100-500 users. Most interactions never hit the backend.

---

## Beyond Search: More Granite + IBM Cloud Ideas

### Content & Translation

**T1. AI-Assisted Translation with Granite**
- 19 locales configured, most <20% translated
- Granite models support multilingual generation — could draft translations at build time
- Human reviewers (native speakers) review and approve
- Could dramatically accelerate translation velocity for the ~300 untranslated pages per locale
- *Also listed under "Additional AI ideas" in the merged section below; Granite makes it more cost-effective*

**T2. Content Gap Analysis**
- Use Granite to analyze all 381 pages and identify: missing explanations, assumed knowledge not covered elsewhere, orphan pages with no inbound references, outdated Qiskit API references
- Output a "content health report" as a build artifact
- *Helps maintainers prioritize what to write or update next*

**T3. Auto-Generated Summaries / TL;DR**
- Generate a 2-3 sentence summary for each page at build time
- Show as a collapsible "TL;DR" at the top of long tutorials
- **Must be marked with "Summary created by doQumentation"** to indicate AI-generated content
- Also useful as search result snippets and social media preview cards
- *Zero runtime cost, improves scannability*

### Code & Debugging (using Granite Code models)

**D1. Granite Code for Qiskit Analysis**
- IBM's Granite Code models are specifically trained on code understanding
- Could analyze Qiskit code cells in tutorials to: validate they still work with current Qiskit versions, identify deprecated API usage, suggest simpler alternatives
- Run as a CI check: "These 5 code cells use deprecated `execute()` API"
- *Build-time only, zero runtime cost*

**D2. "Explain This Code" with RAG context**
- When a user clicks "Explain" on a code cell, send the code + surrounding tutorial text to a Code Engine function
- Granite generates a plain-language explanation grounded in the tutorial's context
- Different from a generic code explainer because it knows *what the tutorial is teaching*
- *Could combine with the error debugger feature — same endpoint, different prompt*

### Learning & Engagement

**L1. AI-Generated Practice Exercises**
- Use Granite to generate practice problems from tutorial content at build time
- "Based on this section on quantum entanglement, here are 3 exercises..."
- Store as static JSON, render as interactive cards at the end of each page
- Could include hints and solutions (also AI-generated)
- *Addresses UX-33 (no comprehension checks) at zero runtime cost*

**L2. Personalized Study Reminders**
- If we add an optional email/notification opt-in (lightweight, no full auth needed)
- Code Engine cron job that sends: "You were studying quantum error correction — ready to continue?"
- Uses the content graph to suggest the next page
- *Very lightweight backend, but requires user contact info — privacy considerations*

**L3. "Quantum Concept of the Day"**
- AI-generate a daily quantum concept explanation from the docs
- Display as a rotating banner or card on the homepage
- Pre-generate 365 concepts at build time, cycle through them
- *Zero runtime cost, adds engagement and discoverability*

### RAG Architecture Variations

**RAG-1. Multi-Turn Conversational RAG**
- Not just single-question search, but a chat sidebar where users can have a conversation
- "What's a Bell state?" → answer → "How is that different from a GHZ state?" → answer referencing previous context
- Requires session state (conversation history) — could be client-side
- Code Engine function handles the RAG + Granite generation
- *More engaging than single-shot search, but higher per-session cost*

**RAG-2. Code-Aware RAG**
- Combine documentation RAG with code execution context
- When a user gets an error, the RAG system searches both: (a) the error pattern database and (b) relevant tutorial pages explaining the concept
- "Your TranspilerError happened because... Here's the tutorial that explains this: [link]"
- *Bridges the debugger and search features — they become one system*

**RAG-3. RAG for Workshop Instructors**
- Workshop organizers using the admin panel could ask: "Which tutorials should I assign for a 2-hour intro to quantum gates?"
- RAG searches the content, considers difficulty + estimated time, and suggests a curriculum
- *Niche but high-value for the workshop/classroom use case*

### IBM Cloud Infrastructure Ideas

**I1. IBM Cloud Object Storage for AI Artifacts**
- Store pre-computed embeddings, content graphs, error databases, etc.
- Serve as static assets via CDN (IBM Cloud Internet Services)
- Cheap storage, fast global delivery
- *Alternative to bundling everything in the site — reduces build size*

**I2. IBM Event Notifications for Content Updates**
- When content syncs from upstream (via `scripts/sync-content.py`), trigger a Code Engine job
- Job re-generates embeddings and metadata for changed pages only (incremental)
- Keeps the AI enrichment fresh without manual re-runs
- *Automation layer on top of the build-time approach*

**I3. IBM Secrets Manager for API Keys**
- If we add runtime AI features, API keys for watsonx.ai need secure storage
- IBM Secrets Manager integrates with Code Engine
- *Better than environment variables for production*

---

## Cost Summary: Every Idea at a Glance

### $0/month — Build-time only (Claude Code Max or Granite free tier)

| Idea | Feature Area | What It Does |
|------|-------------|-------------|
| **1A** Semantic search via build-time embeddings | Search | Client-side vector search, no backend |
| **1B** AI-generated "Related Pages" | Search/Nav | Related topics cards at page bottom |
| **1C** Synonym/concept map | Search | Query expansion for keyword search |
| **1E** Search facets | Search | Filter results by type/difficulty |
| **2A** Content metadata (difficulty, prereqs, topics) | Learning | Foundation for all learning features |
| **2B** Difficulty badges | Learning | Visual indicators in sidebar/headers |
| **2C** Prerequisite breadcrumbs | Learning | Learning path context above each page |
| **2D** Client-side recommendation engine | Learning | "Suggested next" based on visit history |
| **2E** Knowledge assessment quizzes | Learning | AI-generated at build time, static JSON |
| **T2** Content gap analysis | Maintenance | Build-time health report |
| **T3** Auto-generated TL;DR summaries | Content | Collapsible summaries per page |
| **D1** Granite Code for Qiskit validation | Maintenance | CI check for deprecated API usage |
| **L1** AI-generated practice exercises | Learning | Static exercises at end of pages |
| **L3** "Concept of the Day" | Engagement | Pre-generated rotating banner |

### $0-5/month — Serverless on IBM Code Engine + Granite free/Lite tier

| Idea | Feature Area | What It Does |
|------|-------------|-------------|
| **1D** "Ask AI" button (hybrid search) | Search | On-demand answer synthesis |
| **R2** Code Engine + Granite RAG endpoint | Search | Serverless question answering |
| **R4** Hybrid static + on-demand | Search | Client-side search + optional AI |
| **2F** "Where should I start?" advisor | Learning | Personalized path recommendation |
| **D2** "Explain This Code/Error" | Debugging | Contextual code/error explanation |
| **RAG-2** Code-aware RAG | Debugging | Error explanation + relevant docs |
| **RAG-3** Workshop curriculum advisor | Workshops | Suggest tutorials for a time budget |
| **T1** Translation drafts with Granite | Content | Draft translations for review |

### ~$140+/month — Managed IBM services (likely over budget)

| Idea | Feature Area | What It Does |
|------|-------------|-------------|
| **R3** watsonx Assistant (Plus plan) | Search/Chat | Managed chatbot with conversational RAG |
| **R5** Self-hosted Granite on Code Engine | Search | Run model directly, no token limits |
| **RAG-1** Multi-turn conversational RAG | Search/Chat | Chat sidebar with session context |

### Cost ramp & scaling (salvaged from BOB_AI_INNOVATION_RECOMMENDATIONS, 2026-05-08, then deleted as redundant)

Phased monthly cost if features ship incrementally (most are client-side/build-time = $0):

| Stage | Features added | Monthly |
|---|---|---|
| Phase 1 | Code assistant, recommendations, error explanations | $0–5 |
| Phase 2 | + semantic search, learning paths | $0–10 |
| Phase 3 | + circuit debugger, translation accel | $0–15 |
| All | + quality checks, adaptive difficulty | $10–30 |

Scaling: ~1K MAU → $10–20/mo; ~10K MAU → $80–100/mo (serverless $30–50 + possible Granite tier upgrade). Client-side features stay $0 at any scale. (The rest of that doc duplicated ideas already covered above.)

---

## Open Questions

1. **Which $0/month ideas are most exciting?** The build-time metadata (2A) is foundational — it enables badges, breadcrumbs, recommendations, related pages, and search facets all at once.
2. **Is the $0-5/month tier acceptable** for features like "Ask AI" and error explanation? Or strictly $0?
3. **Content update cadence**: How often does content change? Determines if AI enrichment should be a CI step or manual one-off.
4. **NotebookLM synergy**: Could NLM-7 (Deep Research) help generate the content graph more accurately than Claude/Granite alone? (full NotebookLM idea set merged below)
5. **What should we explore next?** More ideas? Narrow down to favorites? Start thinking about implementation?

---

# Merged from AI_INTEGRATION_IDEAS.md (captured 2026-03-08, consolidated 2026-05-17)

> The earlier `AI_INTEGRATION_IDEAS.md` doc was folded in here so there is
> one canonical AI-ideation file. Its **UX audit already did its job** —
> ~40 fixes were cherry-picked from it into the shipped Phase 1 work
> (see `PROJECT_HANDOFF_ARCHIVE.md` "Branch integration Phase 1"). Only
> the still-relevant / non-duplicated parts are kept below. Its
> "Remaining PROJECT_REVIEW (6)" table was dropped — its 4 security
> items now live in `.claude/SECURITY_REVIEW_2026-05.md` (S1/S3/S4/S8)
> and its non-security SET-2 is UX-3 below + `plans/simplify-settings.md`.
> (`.claude/PROJECT_REVIEW.md` itself was deleted 2026-06-04 — the March
> code-review snapshot; recoverable from git history.)

## Additional AI ideas (not already covered by Smart Search / Adaptive Paths above)

- **Code Cell Error Explanation** — on cell failure, send error + code to Claude API, show contextual fix inline. Extends existing `showErrorHint` in `ExecutableCode/index.tsx`. (Pairs with UX-36 below.)
- **"Explain This Code" button** — per-cell button → plain-language explanation for learners. Plugs into ExecutableCode.
- **Exercise / quiz generation** — auto-generate practice problems from lesson content; build-time or on-demand. (Pairs with UX-33.)
- **Circuit from natural language** — "3-qubit GHZ circuit" → generated Qiskit → execute in existing kernel.

## NotebookLM integration ideas (unique — kept verbatim)

> Based on [NotebookLM's March 2026 features](https://blog.google/innovation-and-ai/products/notebooklm/generate-your-own-cinematic-video-overviews-in-notebooklm/): Cinematic Video Overviews, Interactive Audio, Custom Personas, Data Tables, Deep Research, Slide Generation.

### NLM-1. Audio Overviews for Quantum Tutorials (highest impact)
NotebookLM generates podcast-style audio from sources; Audio Overviews support [80+ languages](https://workspaceupdates.googleblog.com/2025/04/language-expansion-audio-overviews-notebooklm.html), aligning with 20 locales.
- **Difficulty tiers**: beginner/intermediate/advanced audio for the same tutorial (addresses UX-45)
- **Multi-language**: audio in DE/ES/JA/AR etc. — serves all 20 locale subdomains
- **Format variety**: [customizable tones](https://techcrunch.com/2025/09/03/googles-notebooklm-now-lets-you-customize-the-tone-of-its-ai-podcasts/) — "Deep Dive" courses, "Brief" guides, "Debate" concepts, "Critique" Qiskit pitfalls
- **Implementation**: pre-generate at build time via [NotebookLM Enterprise API](https://docs.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks), embed as `<audio>` alongside code blocks

### NLM-2. Cinematic Video Overviews for Complex Concepts
[Cinematic Video Overviews](https://blog.google/innovation-and-ai/products/notebooklm/generate-your-own-cinematic-video-overviews-in-notebooklm/) (Mar 2026, Gemini 3 + Veo 3) generate documentary-style explainer videos.
- Visualize gates, circuit diagrams, Bloch sphere rotations as animations
- Synthesize related tutorials into one video narrative (addresses UX-39)
- Supplement IBM Video embeds (`IBMVideo.tsx`) with curriculum-specific content
- Currently English-only, Google AI Ultra subscribers

### NLM-3. Interactive "Join" Mode as a Tutor
[Interactive Audio](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-custom-personas-engine-upgrade/) lets users interrupt AI hosts to ask questions.
- "Raise hand" during an audio overview (addresses UX-43)
- Hosts suggest what to study next (addresses UX-41)
- Lightweight alternative to a full chatbot (vs. AI Tutor sidebar)

### NLM-4. Custom Persona as Quantum Tutor
[Custom chat personas](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-custom-personas-engine-upgrade/) with 1M-token context via Gemini 3.
- "Qiskit Expert" persona loaded with all ~381 pages — grounded answers
- "Quantum Beginner" persona that simplifies / avoids jargon
- NL Q&A as search alternative (addresses UX-40)
- Notebook goals like "Help users understand quantum error correction"

### NLM-5. Data Tables for Backend & Feature Comparisons
[Data Tables](https://www.lbsocial.net/post/notebooklm-2026-update-knowledge-database) convert qualitative text into comparison grids.
- Simulators vs. real hardware (relevant to Settings' 30+ FakeBackend options)
- Sampler vs. Estimator across tutorials
- Transpiler optimization-level comparisons
- Pre-generate as MDX tables at build time, commit to docs

### NLM-6. Slide Generation for Course Content
NotebookLM generates editable presentation slides from sources.
- Auto-generate lecture slides from the 154 course pages
- Complements `CourseComponents` (IBMVideo, Figure, DefinitionTooltip)
- Lets educators build teaching materials from doQumentation content

### NLM-7. Deep Research for Content Graph & Prerequisites
[Deep Research](https://medium.com/@jimmisound/the-cognitive-engine-a-comprehensive-analysis-of-notebooklms-evolution-2023-2026-90b7a7c2df36) (Gemini 3) searches sources + web to synthesize findings.
- Auto-identify prerequisites between pages (addresses UX-41)
- Generate "Related Topics" sections (addresses UX-39)
- Build a content graph across tutorials/guides/courses/modules
- Output as frontmatter (`related`, `prerequisites`, `leads_to`) for build-time rendering

| Approach | Effort | Best for |
|---|---|---|
| Pre-generated audio via NotebookLM API at build time | Medium | NLM-1 |
| Link to shared NotebookLM notebooks | Low | NLM-4 |
| Pre-generated video embeds | Medium | NLM-2 |
| Build-time data tables committed as MDX | Low | NLM-5 |
| One-time Deep Research → frontmatter | Low | NLM-7 |
| [Open Notebook](https://github.com/lfnovo/open-notebook) self-hosted | High | Full API control |

## UX backlog (open items from the 2026-03-08 audit; shipped ones omitted)

> Spot-checked 2026-05-17: many of the original 46 shipped via Phase 1
> (e.g. UX-6 confirm dialogs). These are the ones still open / worth
> revisiting; several are AI/NotebookLM-addressable (cross-refs above).

- **UX-1** Onboarding too minimal — no guided tour / Get Started path
- **UX-2 / UX-25** Binder launch wait opaque; no upfront "first run = 10–25 min" interstitial + Colab offer
- **UX-3** Settings page overload (~1333-line `jupyter-settings.tsx`) — needs tabs/accordion (= PROJECT_REVIEW SET-2 + `plans/simplify-settings.md`)
- **UX-5** Credential expiry unnoticed — no content-page warning banner
- **UX-7** Kernel-death recovery unclear — no persistent Reconnect banner
- **UX-8** Error hints low-contrast in dark mode (fails WCAG AA)
- **UX-10** Simulator picker (50+ flat options) — searchable combobox
- **UX-11** No pip-install progress indicator
- **UX-13** No keyboard-shortcut documentation
- **UX-14** Learning progress lacks % completion
- **UX-15** No user data export/import (JSON)
- **UX-16 / UX-17 / UX-18 / UX-19** A11y: skip links, fieldset grouping, CodeMirror SR testing, onboarding `aria-live`
- **UX-20 / UX-39** No "Related Pages"/cross-references (NLM-7 / Deep Research candidate)
- **UX-21 / UX-40** Search keyword-only, no facets (= Smart Search above)
- **UX-22** No offline/PWA support
- **UX-23** No reading-time estimates
- **UX-24 / UX-29** Weak "Continue where you left off" CTA
- **UX-30 / UX-33** No goal-setting / comprehension feedback (quiz-gen candidate)
- **UX-31** Kernel state lost on navigation — no warning
- **UX-32** `save_account()` skip-hint wording scares users
- **UX-36** Error guidance limited to 3 patterns — add Qiskit-specific (TranspilerError, IBMNotAuthorizedError…) (AI error-explanation candidate)
- **UX-37** Cross-tab sync gaps (cookie writes; use `BroadcastChannel`)
- **UX-38** No personal "My Learning" analytics dashboard
- **UX-42** BetaNotice still `sessionStorage` (re-shows every session) — should be versioned localStorage
- **UX-43** No in-app "Was this helpful?" feedback widget
- **UX-44** Sidebar auto-suffix "(Guides)" — use intentional distinct names
- **UX-45** No difficulty/complexity badges
- **UX-46** Locale switch loses scroll/kernel — warn on active kernel

## Generic engineering backlog (non-AI; from same audit, still largely true)

No tests (Jest/Vitest/Playwright), no ESLint/Prettier, no `ARCHITECTURE.md`/`DEVELOPMENT.md`, no error monitoring (Sentry), no code-splitting/image-optimization/bundle-analysis. Remaining hardcoded English: `onboarding.ts` (~2 strings), `OpenInLabBanner` PHASE_LABELS/hints (~15 strings).

**Salvaged from BOB_FOUNDATION_REVIEW (2026-05-08, then deleted as redundant scorecard):**
- **Architecture**: `src/config/jupyter.ts` is a "god object" — flagged for splitting into focused modules (credentials / environment-detect / lab-url / session). Pairs with PROJECT_REVIEW SET-2 + UX-3 (the Settings/jupyter complexity cluster).
- **Documentation gaps** (not tracked elsewhere): no `CONTRIBUTING.md`, no Architecture Decision Records, no Storybook/component docs, no troubleshooting guide. (Foundation review scored Docs 8/10, Architecture 7/10, Perf 7.5/10, A11y 7.5/10, Testing 2/10 — Testing = the "no tests" item above; the rest of that scorecard duplicated items already in this backlog / the UX list / the security tracker.)
