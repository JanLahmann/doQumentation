# Build-Time AI: The Learning Compiler

> **Status**: Ideation round 2 (2026-07-18) — creative exploration, no implementation commitment.
> **Relationship to [`AI_FEATURES_BRAINSTORMING.md`](./AI_FEATURES_BRAINSTORMING.md)**: that doc is the *capability layer* (search, RAG, metadata, runtime-AI tiers, NotebookLM). This doc proposes *learner-facing products* composed on top of it — with a bias toward things only doQumentation can build. The shared foundation (idea 2A, content metadata) is assumed; several older ideas (2E quizzes, L1 exercises) are absorbed and upgraded here.
> **Budget frame**: unchanged — build-time AI via the existing Claude Code Max subscription (≈ $0 marginal), runtime stays static/client-side. The approved runtime-AI strategy (Granite in-browser, BYOK watsonx.ai, BYOK Anthropic) is untouched.
>
> *God does play dice. Come play, build, learn — and get certified.*

---

## 1. The thesis: we already run a build-time AI factory — point it at learners' goals

Step back and look at what this repo already does, because it's easy to stop seeing it:

| Existing system | What it really is |
|---|---|
| Translation pipeline (17 full locales + 9 dialects, 428 files each) | A **content compiler**: agent fan-out + deterministic gates (validate → lint → content-gate → build) + status bookkeeping + CI refresh cadence |
| Tiered linguistic review (Sonnet rounds, Opus deep-review with fixed rubric, 27+ rounds) | A **quality assurance factory** with adversarial verification |
| Weekly stale-translation refresh (git-diff hunk splice) | An **incremental recompiler** triggered by upstream drift |
| Notebook sweep + `ci/00_patch_runtime.py` (fake-backend patching) + QuBins pinned images | A **deterministic execution harness** for all 291 notebooks |
| Video transcripts (55 videos × 18 languages) | A **derived-artifact generator** |

This is one of the largest build-time-AI content operations in open source. The strategic insight of this doc:

**Translation is just one axis of transformation (language). The same factory generalizes to every other axis:**

- **Goal** — compile the content toward *certification* or *advocacy*
- **Form** — compile pages into *quizzes, flashcards, puzzles, docent scripts, challenges*
- **Level** — compile explanations across *abstraction lenses* (math-first, code-first, visual, ELI12)
- **Person** — compile the *entire decision space of a tutor* into static data, personalized client-side

And the architectural pattern that makes personalization compatible with our hard constraints (no accounts, no server state, no proxy):

> **Precompute the decision space at build time; personalize by selection at runtime.**
> localStorage tells a tiny client-side engine where the learner is. Static JSON tells it what to do about it.
> *The intelligence lives in the build. The personalization lives in the browser.*

Everything below is an application of that one pattern. Nothing requires a backend. Everything works offline on a RasQberry.

---

## 2. Flagship 1 — Qiskit Certification Studio

**Community context.** The Qiskit Advocate program relaunched as a tiered "Program 2.0" (2025): points for contributions, and the **Qiskit v2.x Developer Certification is mandatory to advance to Tier 1**. The current exam is **C1000-179** ("Fundamentals of Quantum Computing Using Qiskit v2.X Developer"): 68 questions, 90 minutes, ≥47 to pass, administered via Pearson VUE, with a public study guide, published section objectives (operations, visualization, circuit creation, running on Runtime primitives, …) and a short official sample test. So today, every aspiring advocate and every serious learner shares one concrete goal — and there is no high-quality, free, executable prep resource. That's our opening. *(Implementation step 0: pull the exact objective list + section weights from the IBM Training study guide as the build input — treat it like `_toc.json`, a machine-readable syllabus.)*

### 2.1 Objective → content coverage map

Build-time agents map **every official exam objective to the exact doQumentation pages/sections that teach it** — we host the very docs the exam is based on. Output: `certification-map.json` (objective → [pages], confidence, gaps).

- Where coverage is thin, generate a short **bridge page** per gap (marked "Created by doQumentation", reviewed before ship).
- The map is also the skeleton for everything else in the Studio.
- *This is idea 2A (metadata) with a purpose: instead of tagging pages abstractly, tag them against a syllabus people are actually trying to pass.*

### 2.2 Cert Mode

A toggle (localStorage, like display prefs) that re-frames the site around the exam:

- Sidebar filters to cert-relevant content in objective order; each page shows an **objective badge** ("Covers exam section 3: Create quantum circuits").
- Progress indicators switch from "pages visited" to "**objectives covered**" — visited/executed/quizzed per objective.
- Homepage resume card becomes "Your certification progress: 14/22 objectives touched, weakest: transpilation."

### 2.3 The machine-verified question bank ← the killer feature

Generate a large bank (500–1,000+) of **original** practice questions per objective: multiple choice, predict-the-output, spot-the-bug, "which circuit produces this distribution", "which primitive/execution mode fits this scenario".

What makes ours categorically better than every Udemy/exam-site bank:

1. **Every code-bearing question is executed at build time** against the pinned Qiskit stack — the same harness we already own (`ci/ipython_startup_dir/00_patch_runtime.py` routes to FakeBrisbane/FakeFez/FakeMarrakesh; QuBins `2.3-xl` image; seeded, shot-clamped). The correct answer is *proven* correct; distractors are *proven* wrong (executed and confirmed to produce different output or the claimed error).
2. **Adversarial verification fan-out** — the pattern we already trust from translation review: independent verifier agents try to refute each question (ambiguous stem? two defensible answers? version-sensitive?). Only survivors ship. Kill rate is a quality metric, not a bug.
3. **Questions can't rot.** Every weekly Qiskit bump re-runs the verification sweep; questions that break are auto-flagged for regeneration — same lifecycle as `STALE_REFRESH` in the translation pipeline. Every commercial question bank silently rots; ours is freshness-gated by CI.
4. **Distractors mined from real misconceptions** (see §6 flywheel): the wrong answers people actually believe, not random perturbations.

Ships as static JSON; client-side quiz player; per-objective mastery in localStorage (`dq-quiz-mastery`). Zero runtime cost.

**Guardrails (important):**
- Questions are generated from *public* exam objectives + our CC BY-SA content — **never** from actual exam content. No dumps, NDA-clean, and we say so prominently.
- Standard disclaimer: unofficial preparation material, not affiliated with or endorsed by IBM (we already carry this pattern site-wide).
- Marked as AI-generated + human-reviewed, per our existing convention.

### 2.4 Mock exam simulator

Client-side, fully static: 68 questions in 90 minutes, sampled from the bank **stratified by official section weights**, seeded shuffle, real pass line (47/68).

- Score report: per-section bars vs the pass threshold → each weak section links to the exact pages + practice sets to fix it (precomputed remediation text per section × score band — the compiled-tutor pattern, §5.1).
- "Readiness estimate" trend across attempts (localStorage history).
- Shareable (voluntary) result card: "I scored 52/68 on the doQumentation mock exam" — organic marketing loop into the advocate community.

### 2.5 Exam-drift watchdog

A weekly CI job (rides the existing sync cadence) that fetches the public certification/study-guide pages, hashes them, and on change lets an agent diff old→new objectives and open an issue listing affected map entries, questions, and bridge pages. Exactly our translation-freshness reflex, applied to the syllabus. When IBM ships a v3 exam, we're updated in days while every static Udemy course is stale for months.

### 2.6 Multilingual cert prep — for free

The question bank and bridge pages are *just content*, so the existing translation factory picks them up. Result: **the only Qiskit certification prep on Earth available in 17 languages** (exam itself is English — but studying in Bahasa Indonesia, Thai, or Ukrainian is how you lower the barrier for exactly the communities the advocate program wants to reach). This single sentence is a conference-talk headline.

**Effort sizing (rough):** coverage map + Cert Mode ≈ 1–2 orchestrated sessions + UI work; question bank v1 (300 verified Qs) ≈ 2–3 sessions (generation fan-out + verification harness reuse) + human spot-review; mock exam UI ≈ a focused frontend week. All build-time cost ≈ $0 on Max.

---

## 3. Flagship 2 — Advocate Launchpad

Certification is a milestone; advocacy is the journey. The program is now points-based (code, tutorials, blogs, events, Slack support, translations, …), applications reviewed monthly, with QAMP mentorship for Tier 1+. Most aspiring advocates fail at one thing: **finding a concrete first contribution.** We can compile that away.

### 3.1 The Advocate Path page

A generated, maintained `/advocate` guide: tiers, points, the cert milestone (→ Certification Studio), QAMP, honest timelines. Regenerated when the program pages change (same watchdog pattern as §2.5). Static, translated, always current — vs the blog posts from 2021 people currently find.

### 3.2 Contribution Compass

A 5-question interest mini-quiz (writer / coder / organizer / translator / artist / educator — localStorage, no accounts) → a **personalized list of concrete, currently-open first contributions**, regenerated *each build from live repo state* across the whole family:

- good-first-issues in doQumentation, Fun-with-Quantum, RasQberry, Qoffee-Maker
- untranslated dialect pages, missing video subtitles (4 known!), notebook modernization candidates
- "this tutorial has no quiz yet", "this guide's persona lens is missing" — our own AI outputs create well-scoped human tasks
- workshop/event support roles

The compass is a static JSON decision table + a rules engine — compiled-tutor pattern again. It turns "I want to contribute but don't know where" into a checklist with difficulty labels and expected time.

### 3.3 Adopt-a-Locale ← the beautiful loop

Our pipeline *already produces* a queue of human tasks: **~100 files/locale are pending linguistic review** after every sync refresh, tracked in `translation/status.json`. Today that's maintainer debt. Reframed, it's a **community program**:

- A per-locale "Adopt {language}" dashboard (generated from status.json — STATUS.md already renders this) listing exactly which files await native-speaker review.
- An auto-generated reviewer onboarding guide per locale (distilled from `translation/review-instructions.md` + the rubric).
- Reviewers get named credit in the locale's NOTICE/credits page — and real, documentable contributions for their advocate application.

This **flips the usual arrangement — the AI drafts, humans certify** — and it's honest about it. It also scales the one thing our translation factory can't automate: native-speaker judgment. Every locale community (Indonesian, Thai, Ukrainian quantum communities are highly active) gets a standing, meaningful, low-barrier contribution channel.

### 3.4 The Quantum CV (contribution log export)

The advocate application asks for evidence. We already track visited/executed/bookmarks; add quiz mastery, mock-exam history, passport stamps (§4.4), and self-logged contributions (links to merged PRs, reviewed files, events). One click → **exported markdown "learning & contribution record"** ready to paste into the application. Pure localStorage → file download; no backend, no privacy exposure; build-time AI writes the narrative templates. *(Import/export JSON also finally delivers UX-15.)*

### 3.5 QAMP project generator

Each QAMP season, an agent distills our own backlogs (`PROJECT_HANDOFF.md` TODOs, UX backlog, family repos) into **well-scoped 3-month mentee project briefs** (goal, deliverable, mentor touchpoints, first PR). We become a QAMP project supplier — advocacy leverage for the whole family.

---

## 4. Flagship 3 — The Family Quest Layer

The family already covers the full arc — **play** (Fun with Quantum games, Qoffee-Maker), **build** (RasQberry, Quantego, Qutie), **learn** (doQumentation), **advocate** (community) — but as islands. Build-time AI is the connective tissue: it can generate the bridges, the challenges, and the shared progression that no one has had time to write by hand.

### 4.1 Game bridges: "Beat the game, then learn the trick"

Ingest the Fun-with-Quantum notebooks through the existing sync pipeline into a **Play** section, then generate a *bridge path* per game:

| Game | Bridge path (generated, human-reviewed) |
|---|---|
| **Quantum Coin Game** | play → "why does the quantum player always win?" → superposition & interference pages → build the winning strategy in Qiskit (executable) → try to beat it classically (you can't — proof included) |
| **GHZ Game** | play → the 75% classical ceiling → entanglement & nonlocality → build the GHZ strategy → **run it on a real device** (GHZ-on-Real-Devices already exists!) → error mitigation as the plot twist |
| **Mermin–Peres Magic Square** | play → contextuality → the full magic-square strategy in Qiskit |

Each bridge ends with a quiz (§2.3 machinery) and a passport stamp (§4.4). Side benefit: the agents **modernize the aging game notebooks to Qiskit 2.x**, sweep-verified — a concrete contribution back to the family repo, done by the factory.

The funnel becomes explicit: someone plays the coin game at a booth → QR → "want to know the trick?" → doQumentation path → certification → advocate. **Play → learn → build → advocate.**

### 4.2 The Qoffee Barista Curriculum

The Qoffee-Maker maps 8 beverages to 3-qubit measurement outcomes. That's not just a demo — it's a *puzzle format*. Generate a **challenge ladder** of circuit puzzles, each auto-verified at build time (statevector/counts assertions, seeded):

1. ☕ *Espresso, deterministically* — produce |011⟩ using only X (warm-up)
2. ☕☕ *The indecisive customer* — equal superposition of latte and cappuccino, nothing else
3. ☕☕☕ *Entangled orders* — two cups that always match, using H + CNOT
4. ☕☕☕☕ *Interference brewing* — amplify espresso, cancel decaf, using phase + H
5. 🏆 *Decoherence-proof barista* — hit ≥95% fidelity on a noisy fake backend

Runs in the existing ExecutableCode runtime with a tiny checker (compare user counts vs target distribution — client-side). At events, the physical Qoffee-Maker gets a QR: *"Liked your quantum coffee? Here's your homework."* Booth demo → structured learning, finally connected.

### 4.3 RasQberry Docent Mode

RasQberry runs doQumentation *offline* at exhibits, schools, and museums — where the bottleneck is never the demo, it's the **explainer standing next to it**. Compile the explainer:

- Per demo on the RasQberry demo list: a generated **docent script** — 30-second hook, 3-minute explanation, kid-level FAQ ("is it a real quantum computer?" — honest answer included), "what's real vs. what's a model", common follow-up questions.
- In all 26 locales via the translation factory. A museum in Kyiv or a school in Manila gets a native-language docent for free.
- **Hardware anatomy cross-reference** for Quantego/Qutie/RasQberry models: each physical part (cryostat plate, wiring loom…) → what it does in the real System Two → the doQumentation guide page that explains it. Printable QR sheet per part; phone → offline page on the Pi.

This is the highest-resonance item for the exhibition/workshop community — it converts every RasQberry build into a self-explaining exhibit.

### 4.4 The Quantum Passport

A family-wide, no-backend progression layer: a **stamp book** in localStorage (+ export/import JSON, honoring UX-15; shared across `*.doqumentation.org` via the existing cookie layer).

- Stamps: *Beat the GHZ game · Brewed a quantum coffee · First circuit executed · First real-hardware job · First mock exam passed · Reviewed a translation · Built a Qutie · First PR merged…*
- Family sites grant stamps via low-stakes **claim codes / link fragments** (honor system — it's a passport, not a bank).
- Build-time AI designs the stamp set, criteria, and per-stamp "what you proved" micro-explanations, in every locale.
- **Printable passport PDF** for workshops: kids physically collect stamps at booth stations (RasQberry table → Qoffee table → games table). The digital and paper passports mirror each other.

Cheap to build, absurdly effective at events, and it gives the whole family a shared identity artifact.

### 4.5 The Daily Quantum Puzzle

One micro-puzzle per day, **365+ pre-generated and pre-verified at build time** (predict the histogram; reach this state in ≤4 gates; spot the bug; which gate is missing?). Date-keyed selection from static JSON, streak counter in localStorage, and a **shareable no-spoiler emoji grid** (🟦🟪⬛ …) like the Wordle culture that made daily puzzles a retention engine — fully static, works offline on the Pi.

This is the cheapest high-engagement feature in this document: a reason to open doQumentation every day, and a steady stream of organic social posts. (Name via community contest — resist the urge to call it Qordle.)

---

## 5. The Compiled Tutor — personalization without a backend

The engine behind §§2–4, stated once, reusable everywhere:

### 5.1 Precomputed policy tables

At build time, enumerate the meaningful learner states (progress class × quiz outcome × context) and generate the tutor's response for each: next-best page, remediation set, encouragement text. Runtime is a <5 KB rules engine selecting rows from static JSON. This upgrades old-doc idea 2D from "simple rules" to "a tutor whose entire brain was written by a frontier model at build time."

### 5.2 Persona lenses ("locales of abstraction")

For the ~60 core concept pages, generate alternative explanation blocks: **math-first / code-first / visual-intuition / ELI12**. A toggle (localStorage) swaps the lens site-wide. This is *exactly* the translation problem — same meaning, different rendering, needs gates and review — so the factory, validation mindset, and even the review rubric structure transfer directly. Scope control: lenses only for flagged concept blocks, not whole pages, to keep content volume sane. *(Easter egg with existing assets: an "Erklär's meiner Oma" lens already ships in 9 German dialects…)*

### 5.3 Spaced repetition, in-site and in-Anki

Compile each course/objective into flashcard decks (concept cloze, Q/A, predict-the-output). Two consumers:
- an in-site "Daily review" widget (SM-2 scheduling in localStorage; "7 cards due" nudge on the homepage), and
- **downloadable `.apkg`** built with genanki at build time — meet the certification crowd in the tool they already love.

### 5.4 Compiled Q&A (answer the head of the distribution for $0)

Mine likely questions (exam objectives, FAQ patterns, and §6 search-miss telemetry) → generate 1–2k **grounded Q&A pairs with page citations** at build time → ship as a searchable instant-answer layer. Most real queries are answered instantly with zero runtime AI; the long tail falls through to the already-approved runtime tiers (Granite in-browser / BYOK). This reorders the old doc's RAG plan: RAG becomes the *fallback*, not the front door.

---

## 6. The Flywheel: telemetry in → build-time analysis → better site out

We already close this loop for translation freshness. Generalize it:

| Signal (tiny additions to existing Umami) | Build-time consumer | Output |
|---|---|---|
| Cell-error events (**error class only** — e.g. `TranspilerError` — never user code; needs privacy sign-off) | **Misconception Miner**: weekly agent clusters real failures | New inline error hints (directly delivers the open "Qiskit execution error hints" TODO), plus quiz distractors mined from what people *actually* get wrong |
| Search queries with zero results | **Search-Miss Miner** | Synonym-map entries, §5.4 Q&A candidates, content-gap issues |
| Quiz/mock-exam aggregate outcomes (anonymous counts) | **Difficulty calibrator** | Re-rank question difficulty; flag pages whose readers fail downstream quizzes |
| All of the above | **Community Learning Report** (monthly, public, auto-drafted) | "What 10k learners struggled with this month" — transparency that builds community trust, doubles as our roadmap input, and is itself shareable content |

Each weekly build makes the site measurably better at anticipating the next learner's failure. No commercial docs site does this in the open.

---

## 7. Quick hits (build/ops layer)

- **Pedagogical consistency gate** — on upstream sync, agents check whether our *derived* content (bridges, lenses, quizzes, Q&A) still agrees with changed upstream claims; disagreements → `STALE_DERIVED` queue. Extends the `STALE_REFRESH` concept beyond translations to *all* generated artifacts. (This is the governance piece that makes everything above sustainable.)
- **Workshop Compiler** — organizer inputs (audience, duration, language, backend) → generated event page (`/events/<slug>`, the existing workstream), notebook selection with timing plan, printable handout PDF, CE pool config for `workshop-start.yml`. The existing workshop infra gets a curriculum brain.
- **Release explainers** — each weekly Qiskit bump: auto-draft "what changed for learners" (sweep already finds the breakage; add the narrative + affected-tutorial list).
- **Alt-text sweep** — generate alt text for ~1,650 notebook output images + a11y audit per template change. Quiet, but education orgs and grant applications care deeply.
- **YouTube mapping auto-discovery** — the existing future-idea, done as a build step with verification.

---

## 8. Why us — the moat table

| Idea | The asset nobody else has |
|---|---|
| Verified question bank (§2.3) | 291 *executable* notebooks + pinned QuBins images + fake-backend patch harness — we can *prove* answers, not assert them |
| Multilingual cert prep (§2.6), docent mode (§4.3) | A 26-locale translation factory with quality gates, already amortized |
| Compiled Tutor (§5), Passport (§4.4), Daily Puzzle (§4.5) | The no-backend discipline: everything works offline, on a Pi, at an exhibit, with zero monthly cost |
| Game bridges (§4.1), Barista curriculum (§4.2), anatomy cross-ref (§4.3) | We *own the family*: the games, the coffee machine, the LEGO model, the Pi platform, and the docs are one household |
| Flywheel (§6), drift watchdogs (§2.5, §7) | A proven orchestration culture: fan-out agents, deterministic gates, status.json bookkeeping, CI cadences |
| All of it | Claude Code Max ≈ frontier-model compute at $0 marginal — our build can afford to *think* |

---

## 9. Sequencing proposal

**Phase 1 — the goal people already have (highest demand signal):**
2A metadata foundation (from the old doc) → objective coverage map + Cert Mode (§2.1–2.2) → question bank v1, ~300 verified questions (§2.3) → flashcards + `.apkg` export (§5.3) → Advocate Path page (§3.1).
*Ship when the mock exam isn't ready yet — practice sets per objective are already a headline.*

**Phase 2 — the journey and the loop:**
Mock exam + readiness (§2.4) → Contribution Compass (§3.2) → **Adopt-a-Locale** (§3.3 — cheapest item here, the dashboard mostly exists) → Quantum CV export (§3.4) → Passport v1 (§4.4) → first game bridge (GHZ, §4.1).

**Phase 3 — the fun and the flywheel:**
Daily Puzzle (§4.5) → Barista Curriculum (§4.2) → Docent Mode (§4.3) → persona lenses, scoped (§5.2) → Misconception/Search-Miss miners + Community Report (§6).

**Continuous:** exam-drift + program-drift watchdogs, pedagogical consistency gate, release explainers — all riding existing weekly CI cadences.

**Cost:** build-time ≈ $0 (Max subscription), runtime $0 (all static/client-side), optional runtime AI unchanged from the approved multi-tier strategy. The only real spend is orchestration attention — which this repo has already proven it can systematize.

---

## 10. Open questions

1. **Priority**: Certification Studio first (recommended — clearest community demand, direct advocate-program tie-in) or Family Quest Layer first (higher emotional resonance, better event demos)?
2. **Question-bank human sign-off**: who reviews? *Proposal: recruit advocates as reviewers — bootstraps the §3 contribution loop on day one.*
3. **Umami error-class event**: privacy-acceptable? (Error class name only, never code/output; stays cookie-free.)
4. **Play section**: ingest Fun-with-Quantum notebooks into doQumentation (one home, our execution stack) or keep them in their repo and only host the bridges?
5. **Passport claim codes**: honor-system acceptable? (No backend alternative exists within our constraints — and it genuinely doesn't matter.)
6. **Trademark/positioning review** for cert-prep pages (unofficial-disclaimer wording, "not affiliated with IBM" placement) — same counsel as the existing site-wide disclaimer, one extra pass.
7. **Naming**: community contest for the Daily Puzzle and the Passport? (Free engagement before a single line ships.)
