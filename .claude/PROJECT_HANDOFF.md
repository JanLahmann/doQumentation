# doQumentation — Project Handoff

## What is doQumentation

An **open-source website for IBM Quantum's tutorials and learning content**, built as part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) educational quantum computing platform.

All content comes from IBM's open-source [Qiskit documentation](https://github.com/Qiskit/documentation) repository (CC BY-SA 4.0). IBM's web application serving that content is closed-source. doQumentation provides the open-source frontend — adding the website, Binder-based code execution, multiple deployment options, and usability features like automatic credential injection and simulator mode.

**Three deployment tiers:**

| Tier | URL | Code execution |
|------|-----|----------------|
| **GitHub Pages** | [doqumentation.org](https://doqumentation.org) | Remote via [Binder](https://mybinder.org) or [IBM Code Engine](https://doqumentation.org/jupyter-settings#code-engine) |
| **Docker** | [ghcr.io/janlahmann/doqumentation](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | Local Jupyter + Qiskit |
| **RasQberry Pi** | `http://rasqberry.local` | Local Jupyter + Qiskit, offline capable |

**Content:** 42 Tutorials, 171 Guides, 154 Course pages, 14 Modules, 11 Qiskit Addon tutorials (~391 pages total). Qiskit Addons are built and URL-accessible (`/qiskit-addons/...`) but currently hidden from navbar and main sidebar.

**Live:** [doqumentation.org](https://doqumentation.org) | **Repo:** [JanLahmann/doQumentation](https://github.com/JanLahmann/doQumentation) | **License:** Apache 2.0 (code) + CC BY-SA 4.0 (content)

---

## Architecture Decisions

- **Docusaurus 3.x** (not Next.js, Hugo) — Purpose-built for documentation. Native MDX, auto-generated sidebar, static export. IBM's frontend is Next.js but closed-source.
- **thebelab 0.4.x** (not JupyterLite, Voilà) — Connects static HTML to any Jupyter kernel. JupyterLite won't work (Qiskit has Rust extensions). Must pin to `thebelab@0.4.0` — 0.4.15 doesn't exist on npm.
- **Content transformation** (not Docker mirroring) — IBM's Docker preview lacks navigation/search. We transform their MDX to Docusaurus MDX (95% compatible).
- **Single codebase, three deployments** — Runtime detection handles environment differences. Only the Jupyter endpoint differs.

---

## Features

### Content Sync (`scripts/sync-content.py`)
- Upstream content tracked as a git submodule (`upstream-docs/` → [JanLahmann/Qiskit-documentation](https://github.com/JanLahmann/Qiskit-documentation)). Falls back to sparse-clone for forks without the submodule. Transforms MDX, converts notebooks (custom converter, no nbconvert), generates sidebars from `_toc.json`
- Rewrites image paths (IBM URLs → local `static/`) and link paths (markdown `(/docs/...)` + JSX `href="/docs/..."` → local or upstream)
- `docs/index.mdx` is preserved — all other `docs/` content is regenerated on each sync
- **Dependency scan**: `analyze_notebook_imports()` injects `!pip install -q` cells into 46/260 notebooks missing packages (uses `!pip` not `%pip` to avoid misleading "restart kernel" note). `--scan-deps` flag for report only.
- **Colab/Binder notebook copies**: `copy_notebook_with_rewrite()` injects a prerequisites cell (pip install + commented-out `save_account()` template for IBM Quantum credentials) and Colab `cell_execution_strategy: "setup"` metadata. Also strips MDX frontmatter (`---...---`) from the first markdown cell and applies `clean_notebook_markdown()` to all markdown cells (removes JSX comments, heading anchors, converts `<Admonition>` to blockquotes) — necessary because Qiskit-documentation source notebooks embed Docusaurus directives that appear as raw text in JupyterLab. `publish_notebooks_to_static()` copies ~1,650 dependency-ready notebooks to `static/notebooks/` for gh-pages serving.
- **Translated notebooks**: `generate_translated_notebook()` merges an English `.ipynb` skeleton with translated `.mdx` text — code cells/outputs stay unchanged, markdown cells get translated text. Uses code blocks as alignment anchors. Handles consecutive markdown cells via heading-boundary splitting. Cleans Docusaurus syntax (heading anchors, MDX escapes, `<Admonition>` → blockquotes). `generate_locale_notebooks(locale)` orchestrates all notebooks for a locale, skipping untranslated fallbacks. CLI: `--generate-locale-notebooks --locale XX`.
- **Custom Hello World**: `hello-world.ipynb` from fork root imported as first tutorial with custom `OpenInLabBanner` description
- **Banner injection condition**: `OpenInLabBanner` is only injected when the notebook has ≥1 non-empty code cell (`has_code_cells` check). Code-cell-free pages (e.g., conceptual course lessons in Basics of Quantum Information, Foundations of QEC) get no banner — 86/261 notebook-derived pages are code-free.
- **Tutorial survey section**: IBM's upstream content includes a `## Tutorial survey` section at the end of tutorials with a link to IBM's feedback form. `sync-content.py` appends a clarifying note below the survey text: explains the survey belongs to IBM Quantum and points readers to [GitHub Issues](https://github.com/JanLahmann/doQumentation/issues) for feedback on doQumentation's website, translations, or code execution.

### Code Execution (`src/components/ExecutableCode/index.tsx`)
- `ExecutableCode` wraps Python code blocks with Run/Back toggle. thebelab bootstraps once per page, shared kernel.
- Environment auto-detection: GitHub Pages → Binder, localhost/Docker → local Jupyter, custom → user-configured
- Cell feedback: amber (running), green (done), red (error) left borders. Error detection for `ModuleNotFoundError` (with clickable Install button), `NameError`, tracebacks. All error types include a "Report this error" link that opens a pre-filled GitHub issue with error text, cell code, page path, environment, and simulator mode. **Output selectors**: thebelab 0.4.0 uses JupyterLab's `OutputArea` widget (`.jp-OutputArea` class), not `.thebelab-output` — all output queries use `OUTPUT_SELECTOR` constant. **Pip install**: uses `--user` flag (Binder's `/opt/conda/` is root-owned), then `site.addsitedir()` (conda disables user site-packages), `importlib.invalidate_caches()`, and `sys.modules` cleanup before auto-rerunning the cell.
- Cell completion uses `kernel.statusChanged` signal (not thebelab events) with 1500ms idle debounce (`IDLE_DEBOUNCE_MS`) to handle cells that cycle busy→idle→busy (matplotlib rendering, optimizers, async jobs). After debounce, `waitForOutputStable()` uses a MutationObserver on the output container to ensure DOM rendering is complete before marking green/red. Both single-cell and Run All paths use this two-stage wait.
- Execution mode indicator badge (links to Settings → Execution Mode) + injection toast.
- **OpenInLabBanner buttons**: "Open in: JupyterLab | Colab" — two buttons across all environments. JupyterLab (filled/primary, session-managed via `ensureBinderSession()` on GitHub Pages, direct link on CE/local), Colab (outlined, always available). Descriptive tooltips on hover. Uses `getColabUrl()`, `getLabUrl()`/`getBinderLabUrl()` from `jupyter.ts`. **Only shown on pages with executable code cells** — `sync-content.py` skips injection for code-cell-free notebooks; 1,634 i18n pages similarly cleaned up.
- **Binder tab reuse**: "Open in Lab" uses named window target `binder-lab` to reuse the same tab
- **Run All**: "Run All" button (visible when kernel is ready) executes all thebelab cells sequentially in DOM order. Auto-skips `save_account()` cells when credentials or simulator mode are active (cells with `.thebelab-cell__skip-hint`). Uses `waitForKernelIdle()` helper (subscribes to `kernel.statusChanged` signal) to wait for each cell to complete before starting the next. During execution: "Pause (N/M)" pauses after current cell finishes, "Stop" aborts. When paused: "Continue (N/M)" resumes, "Stop" aborts. Pause uses a promise-based gate (`waitForRunAllResume`) — the loop awaits until the user clicks Continue. Also aborts on Back, Restart, Clear Session, or page navigation.
- **Kernel restart**: "Restart Kernel" button (visible when kernel is ready) calls `kernel.restart()`, clears all cell outputs/feedback, re-injects credentials/simulator setup. Same Binder session, fresh kernel state.
- **Clear Session**: "Clear Session" button (GitHub Pages + Code Engine, visible when kernel is ready) clears `sessionStorage` session and resets to static view. Next Run starts a fresh server.
- **Binder startup cancel + slow detection**: Cancel button replaces "Connecting..." during Binder startup — cancels the EventSource immediately. Per-phase timeout thresholds (connecting 1m, waiting 3m, fetching/pushing/launching 5m, building 12m) trigger a red warning banner suggesting alternative backends. "Clear Binder Session" also available on Settings page.
- **Interception transparency**: All kernel modifications print `[doQumentation]` messages (simulator intercepts, credential injection, warning suppression, pip install cells). Exported notebooks include a setup notice cell explaining injections. "What's modified?" link on `OpenInLabBanner`. Dedicated `/about/code-modifications` page listing every automatic transform.
- **TutorialFeedback widget** (`src/components/TutorialFeedback/`): Thumbs up/down Umami-tracked widget appended to all tutorial + addon MDX pages via `sync-content.py`. Distinguishes doQumentation website feedback from IBM content survey. Label: "How was the doQumentation experience? (website, code execution, navigation — tutorial content is by IBM Quantum)".
- **TranslationFeedback banner** (`src/components/TranslationFeedback/`): Translation quality banner on non-EN pages (good/ok/poor rating → Umami). Session-dismissible.
- **"View in English" link**: Top entry in locale dropdown on non-EN pages — links to `https://doqumentation.org/{path}` for the original English version.
- **save_account() protection**: Dynamic blue "Skip this cell" banners (runtime-injected via `annotateSaveAccountCells()`, translated via `code.json`) when credentials/simulator active, prevents overwriting injected values. **Run All auto-skips** these cells — `handleRunAll` filters out any cell with `.thebelab-cell__skip-hint` before execution.
- **Full i18n**: All toolbar buttons, status messages, legend, settings link, and Binder hint wrapped with `translate()`/`<Translate>`

### IBM Quantum Integration (`src/config/jupyter.ts`)
- **Credentials** — API token + CRN with adjustable auto-expiry (1/3/7 days). Auto-injected at kernel start. Embedded execution only. Shared across locale subdomains via cookies.
- **Execution Mode** (`doqumentation_execution_mode` localStorage key, values `'aer' | 'fake' | 'credentials' | 'none'`) — single radio group on Settings replaces the old simulator-toggle + active-mode-conflict-resolution model. `getExecutionMode()` is the source of truth; `getSimulatorMode()` and `getSimulatorBackend()` derive from it for backward-compat. Lazy migration runs on first read: maps old keys (`doqumentation_simulator_mode` + `doqumentation_active_mode` + `doqumentation_simulator_backend`) → new key, then deletes the old keys. `injectKernelSetup()` is a clean switch on the mode: `aer`/`fake` → simulator patch, `credentials` → save_account + Open Plan patch, `none` → skip. **Exempt pages**: `SIMULATOR_EXEMPT_PAGES` in `ExecutableCode/index.tsx` — pages like `tutorials/hello-world` fall back from simulator → credentials (or `none` if no token) so they always demonstrate real hardware access. Credential skip-hints still appear on exempt pages when the user has credentials configured.
- **Simulator backend** — Monkey-patches `QiskitRuntimeService` with `_DQ_MockService` (AerSimulator or FakeBackend). Fake backend discovery cached, 55-backend fallback list.
- **Plan type** — Open (default) / Pay-as-you-go / Premium selector on Settings page (`doqumentation_ibm_plan` key). When set to Open, `injectKernelSetup()` monkey-patches `qiskit_ibm_runtime.Session` with `_DQ_JobModeSession` — a passthrough context manager that returns `backend` directly, converting `Sampler(mode=session)` to effective job mode. Per-cell amber banners on `Session(` cells via `annotateSessionCells()`. Toast includes "Session → job mode". Reactive error hint if the Session error fires without the patch (links to Settings).
- **Shared Binder session** — `ensureBinderSession()` in `jupyter.ts` manages a single Binder session shared by both "Open in Binder JupyterLab" and thebelab code execution. First interaction (either button): calls Binder build API (`EventSource` on `/build/gh/...`), captures server URL + token on `"ready"` event, stores in `sessionStorage` (`dq-binder-session`). Subsequent interactions (within 8 min): probes the server (`GET /api/status`) to verify the container is still alive before reusing — dead/culled containers are detected and trigger a fresh build automatically. Environment mismatch guard: if a cached session is from a different environment (e.g. mybinder.org session cached during github-pages, then user configures CE), the stale session is discarded immediately without probing. Both use the `doQumentation/notebooks` branch. Thebelab connects via `serverSettings` (baseUrl + wsUrl + token) instead of `binderOptions`. Both `OpenInLabBanner` and `ExecutableCode` toolbar show live Binder build phases (fetching, building, launching) with timing hints ("1–2 min on first run"). Session touched on kernel busy/idle to stay alive during active code execution. Session expires after 8 min idle or when browser closes. Cross-locale sessions are domain-scoped by design (security). `openBinderLab()` opens a blank tab synchronously on click (avoids popup blockers), then navigates to JupyterLab when the session is ready; on failure, the blank tab is auto-closed.
- **Colab URLs** — `getColabUrl(notebookPath, locale?)` generates locale-aware Colab links via the `/github/` scheme (Colab's `/url/` scheme blocks non-GitHub domains due to SSRF allowlist). All notebooks are processed copies with pip install cells + commented-out `save_account()` template injected by `sync-content.py`. EN: points to `doQumentation/blob/notebooks/` branch (pushed by `deploy.yml` CI step). Translated: points to satellite repos (`doqumentation-{locale}/blob/gh-pages/notebooks/`). Unified path mapping via `mapBinderNotebookPath()`: bare filenames (no `/`) get `tutorials/` prefix. Both `OpenInLabBanner` and `ExecutableCode` pass `currentLocale` from Docusaurus context.

### IBM Cloud Code Engine (`Dockerfile.jupyter` → `jupyter-codeengine` target)
- **What it is** — Serverless Jupyter container on user's IBM Cloud account. Drop-in Binder replacement with ~1s cold start (vs Binder's 10–25 min). Free tier covers ~14 hrs/month.
- **Architecture** — Single-port container (8080): nginx reverse proxy + Jupyter server (8888) + SSE build server (9091), managed by supervisord. SSE server (`sse-build-server.py`) mimics mybinder.org's `/build/` SSE protocol so `ensureBinderSession()` works unchanged — only 3 phases (connecting/launching/ready) instead of 7+. SSE server also handles `/health` endpoint (checks Jupyter readiness with token, no external auth needed). Uses port 9091 (not 9090 — Jupyter extensions bind that) and `allow_reuse_address`. Public URL in SSE ready event derived from `Host` header + `X-Forwarded-Proto`. Cold start ~12s (container start + Jupyter init); health returns 503 until Jupyter is ready, then 200.
- **Deployed app** — `jupyter.28mc794qh1og.eu-de.codeengine.appdomain.cloud` (eu-de region), project `doQumentation`, app `jupyter`. Min scale 0, max scale 1. Default size 1 vCPU / 2 GB. Token must be 32+ chars. Sizing validated via stress tests: 8 vCPU/16 GB handles 80 users with retry helpers (see `.claude/STRESS-TEST-FINDINGS.md`).
- **CE naming convention** — Projects = environments: `doQumentation` (production, CI deploys), `doQumentation-workshop-01`/`-02` (temporary, per workshop). Apps = instances: `jupyter` (single), `jupyter-01`/`-02` (multi-instance workshop). When `instance_count=1`, app name is used directly (no `-01` suffix); when >1, auto-numbered. All 6 CE workflows have configurable `project` and `app_name` inputs.
- **Scale-to-zero** — Works reliably in **fresh projects**. Old project `ce-doqumentation-01` (32 days, 47+ revisions) had stale Knative/Istio state preventing scale-to-zero. Verified by side-by-side test: fresh projects scale to zero within 10 min. Nginx improvements kept: `keepalive_timeout 0` (closes connections promptly), WebSocket timeouts reduced from 86400s to 7200s. **CE monitor workflow** (`ce-monitor.yml`): every 2h checks for running instances and oversized apps (>1 vCPU); daily 06:00 UTC summary. **CE list workflow** (`ce-list.yml`): on-demand inventory of all projects/apps/config.
- **Container image** — `ghcr.io/janlahmann/doqumentation-codeengine:latest`, built by `.github/workflows/codeengine-image.yml` using `Dockerfile.jupyter` with `--target jupyter-codeengine`. Base: `quay.io/jupyter/base-notebook:python-3.12` (shared `jupyter-base` stage). Security pins (`jupyter-requirements-security.txt`) installed with `--upgrade` in `jupyter-base` so both Docker targets inherit them. `linux/amd64` only. Trivy security scan (fails on HIGH/CRITICAL, `.trivyignore` for unfixable bundled deps). **Auto-deploy**: after image push + scan, workflow installs IBM Cloud CLI and runs `ibmcloud ce app update` to deploy the new image to CE (requires `IBM_CLOUD_API_KEY` repo secret).
- **Security** — Token auth (min 32 chars), CORS origin validation (`CORS_ORIGIN` env var, default `https://doqumentation.org`), XSRF disabled (thebelab 0.4.0 limitation), rate limiting on nginx endpoints (except `/lab` — JupyterLab loads dozens of JS/CSS chunks on first view, token auth is sufficient), security headers (HSTS, CSP, nosniff).
- **User flow** — Two paths on Settings page (`/jupyter-settings#code-engine`):
  - **Personal CE setup**: URL + token → Save (environment detected as `'code-engine'` in `detectJupyterConfig()`, priority: Custom > CE > Binder, credentials stored with TTL 1/3/7 days).
  - **Join Workshop**: unified into the Code Engine URL field on Settings (`handleCeSave()`). The same field auto-detects three formats: single URL → personal CE credentials, comma-separated URLs → workshop pool, base64-encoded pool config `{"pool":[...]}` → workshop pool. Token field is shared. Calls `saveWorkshopPool(urls, token)` for multi-URL paths, enabling workshop pool mode with sticky session assignment per tab. Base64 pool config (without token, for security) is generated by `workshop-start.yml` and posted to the job summary — safe for public repos.
  - Workshop pool auto-import via `#workshop=BASE64` URL fragment was removed for security (token was embedded in the URL, visible in browser history and GitHub Actions summaries on public repos).
  - All frontend components (ExecutableCode, OpenInLabBanner) CE-aware with fast phase labels.
- **Storage keys** — `doqumentation_ce_url`, `doqumentation_ce_token`, `doqumentation_ce_saved_at`
- **Files** — `Dockerfile.jupyter` (target `jupyter-codeengine`), `binder/sse-build-server.py`, `binder/nginx-codeengine.conf`, `binder/codeengine-entrypoint.sh`, `binder/jupyter-requirements-security.txt`, `.github/workflows/codeengine-image.yml`

### User Preferences
All storage access centralized in `src/config/preferences.ts` and `src/config/jupyter.ts`, backed by `src/config/storage.ts`. **Cross-subdomain sharing**: on `*.doqumentation.org`, all 28 keys are dual-written to cookies (`Domain=.doqumentation.org`) + localStorage. Values > 3.8KB auto-chunked across multiple cookies. On localhost/Docker, pure localStorage (no cookies). One-time migration copies existing localStorage to cookies on first page load (`pageTracker.ts`). Cross-component reactivity via custom events: `dq:page-visited`, `dq:bookmarks-changed`, `dq:display-prefs-changed`.

- **Learning progress** — Auto-tracks visits (`pageTracker.ts`). Sidebar indicators: ✓ visited, ▶ executed, `</>` notebook page (swizzled `DocSidebarItem`). Category badges ("3/10"). Resume card on homepage. Granular clearing per page/section/category.
- **Bookmarks** — ☆/★ toggle in swizzled `EditThisPage`. Homepage widget. Max 50.
- **Display prefs** — Code font size (10–22px), hide pre-computed outputs during live execution, Python warning suppression toggle
- **Onboarding** — Contextual tip bar for first 3 visits (`onboarding.ts` client module)
- **Recent pages** — Last 10 pages tracked, top 5 on homepage (`RecentPages` widget)
- **Sidebar collapse** — MutationObserver persists expand/collapse state

| Key | Type | Feature |
|-----|------|---------|
| `dq-visited-pages` | JSON set | Learning progress |
| `dq-executed-pages` | JSON set | Learning progress |
| `dq-last-page` | JSON `{path, title, ts}` | Resume reading |
| `dq-binder-hint-dismissed` | boolean | Binder hint |
| `dq-onboarding-completed` | boolean | Onboarding tips |
| `dq-onboarding-visit-count` | number (0–3) | Onboarding tips |
| `dq-bookmarks` | JSON array | Bookmarks (max 50) |
| `dq-code-font-size` | number (10–22) | Display preferences |
| `dq-hide-static-outputs` | boolean | Display preferences |
| `doqumentation_suppress_warnings` | boolean | Warning suppression (default: true) |
| `dq-sidebar-collapsed` | JSON object | Sidebar collapse |
| `dq-recent-pages` | JSON array | Recent pages (max 10) |
| `doqumentation_ibm_plan` | string (open/payg/premium) | IBM Quantum plan type |

### MDX Components

| IBM Component | Solution |
|---------------|----------|
| `<Admonition>` | `@theme/Admonition` (NOT `:::` — breaks in `<details>`) |
| `<Tabs>` / `<TabItem>` | Native Docusaurus |
| Math `$...$` `$$...$$` | KaTeX plugin |
| `<IBMVideo>` | YouTube-first (32 mapped IDs) + IBM fallback |
| `<Card>`, `<CardGroup>`, `<Image>`, etc. | Component stubs |

### Docker & Authentication
- `binder/Dockerfile` (main branch) — `FROM quay.io/jupyter/base-notebook:python-3.12`, installs from `jupyter-requirements.txt` (full Qiskit ecosystem: `qiskit[all]`, all addons, scipy, pyscf, plotly, ffsim, sympy, pandas, etc. — 21 packages). Single source of truth for Binder + Docker deps. `Dockerfile.web` — Static site only (nginx, ~60 MB). `Dockerfile.jupyter` — Multi-stage build with shared `jupyter-base` stage and two targets: `jupyter-local` (full stack + site build, ~3 GB) and `jupyter-codeengine` (CE kernel + SSE server, ~3 GB). Both targets share the same base image (`quay.io/jupyter/base-notebook:python-3.12`) and pip install layer.
- Multi-arch: `linux/amd64` gets full Qiskit; `linux/arm64` excludes some packages
- **Jupyter auth**: nginx injects `Authorization` header server-side. Browser never sees token. `docker-entrypoint.sh` generates random token (or accepts `JUPYTER_TOKEN` env var). Jupyter runs as non-root `jovyan` user.

### CI/CD
- `deploy.yml` — Sync → build → GitHub Pages (English only). Also pushes EN notebooks + Binder config to `notebooks` branch (preserves locale subdirs). Binder config: `binder/Dockerfile` + `binder/jupyter-requirements.txt` copied to `notebooks` branch. repo2docker uses repo root as Docker build context with `--file binder/Dockerfile`, so all `COPY` paths in the Dockerfile must be relative to repo root (e.g., `COPY binder/jupyter-requirements.txt`). No `postBuild` or `runtime.txt` needed.
- `deploy-locales.yml` — Matrix build per locale: sync content → populate fallbacks → generate translated notebooks → build → push to satellite repos. `fail-fast: false` + `if: always()` on consolidation job — one locale's build failure doesn't block other deploys or notebook merges.
- `docker.yml` — Multi-arch Docker → ghcr.io (EN only via `--locale en`). Builds `Dockerfile.jupyter` with `--target jupyter-local`. **Push trigger disabled** — only `workflow_dispatch` (re-enable `push: branches: [main]` when needed).
- `sync-deps.yml` — Weekly auto-PR for Jupyter dependencies. Runs `scripts/sync-deps.py` which fetches from [JanLahmann/Qiskit-documentation/scripts/nb-tester/requirements.txt](https://github.com/JanLahmann/Qiskit-documentation/blob/main/scripts/nb-tester/requirements.txt) and applies transformation rules: drops `sys.platform` markers (Linux-only containers), splits packages by architecture (amd64-only packages like `gem-suite`, `qiskit-ibm-transpiler[ai-local-mode]`, and `qiskit-addon-aqc-tensor[quimb-jax]` go to `jupyter-requirements-amd64.txt`), and adds `EXTRA_CROSS_PLATFORM` packages not in upstream (`pylatexenc` for LaTeX rendering, `pandas` for data analysis). Both `jupyter-requirements.txt` and `jupyter-requirements-amd64.txt` are auto-generated and marked with "DO NOT EDIT MANUALLY" warnings. `jupyter-requirements-security.txt` is manually maintained — it pins minimum versions for transitive dependencies with known CVEs (used only by `Dockerfile.codeengine`, where Trivy CI enforces no HIGH/CRITICAL vulns).
- `check-translations.yml` — Daily translation freshness check + STATUS.md update. Requires `permissions: contents: write, issues: write`.
- `binder.yml` — Daily cache warming for 3 Binder federation members (2i2c, BIDS, GESIS) + on every push to `notebooks` branch + manual `workflow_dispatch`.
- `workshop-start.yml` — Workshop lifecycle: setup only (~2 min). Resizes pod(s), sets fresh Jupyter token, warms pod, posts instructor/student setup guide to job summary. Size options: 1/2 to 12/48 vCPU/GB. No monitoring — completes immediately.
- `workshop-monitor.yml` — Standalone continuous monitor. Polls primary pod's `/stats` every 30s for the requested duration (30m–6h), then posts timeline report with sparklines, peak load, CE events, and cost estimate. Fully independent of workshop-start — can be started/stopped separately. Also usable via `workflow_call`.
- `workshop-close.yml` — Workshop cleanup. Captures final `/stats` snapshot, optionally cancels in-progress workshop-monitor runs, resizes pod down (1/2 to 2/8 vCPU/GB), rotates token, resets pod. Size options deliberately limited to small sizes (cost saving).
- `ce-monitor.yml` — Cost/config watchdog. Every 2h: alerts if any CE instance is running or app is >1 vCPU. Daily 06:00 UTC: full summary of all projects, apps, and config. Alerts via GH Actions annotations + job summary.

### Other
- **Homepage**: Beta notice banner (session-scoped, dismissible), hero with stats bar, Getting Started cards (category-tagged), simulator callout, code execution section. No sidebar or TOC (`hide_table_of_contents: true` in `docs/index.mdx` and all locale `index.mdx` copies).
- **Sidebar**: Home link at top, then Tutorials/Guides/Courses/Modules categories (autogenerated from `sidebar-*.json`). API Reference + Settings in navbar only. **Single unified indicator per item** — 5 states: pure MDX unvisited (nothing), pure MDX visited (`✓` gray), notebook unvisited (`</>` gray, non-clickable), notebook visited (`</>` blue, clickable), notebook executed (`</>` green, clickable). Clicking a clickable indicator clears visited/executed status. Notebook detection via `customProps.notebook` in sidebar JSON (uses `<OpenInLabBanner>` presence, not `notebook_path` frontmatter). **Category badges left of twistie**: badge DOM-injected via `document.createElement('span')` with `role="button"`. Two injection strategies depending on category type: href categories (Tutorials, Guides) have a separate `.menu__caret` button — badge inserted before it as a sibling in the collapsible flex flow. Non-href categories (Courses, Modules, subcategories) have the caret as `::after` pseudo-element on the link — badge appended inside the link, with CSS `display: flex` on `.menu__link--sublist-caret:has(.dq-category-badge)` to position badge between text and `::after` caret. Uses `useLayoutEffect` (no deps) to re-inject after every render — necessary because collapse-restore (`header.click()`) triggers React re-renders that can replace DOM nodes. Badge creation is a separate `useEffect([allHrefs])`. Link items have `padding-inline-end: 2.25rem` for indicator space. Long titles truncate with `text-overflow: ellipsis`.
- **Features page**: `/features` — 31 cards across 6 sections (Content Library, Live Code Execution, IBM Quantum Integration, Learning & Progress, Multi-Language, Search/UI/Deployment)
- **Search**: `@easyops-cn/docusaurus-search-local` — client-side, hashed index
- **Settings page** (`/jupyter-settings`): IBM credentials, simulator mode, display prefs, progress, bookmarks, custom server. Full-width card (`max-width: none` — outer `container` handles width).
- **Navbar**: Always dark (`#161616`). Right-side icons: locale (globe), settings (gear), dark mode, GitHub (octocat) — all icon-only on desktop (text hidden via `font-size: 0` + `::before` SVG). CSS `order` positions auto-placed dark mode toggle and search bar. Mobile sidebar header swizzled (`Navbar/MobileSidebar/Header`) with matching icon row. Locale dropdown filtered by `customFields.visibleLocales` in `docusaurus.config.ts` (currently `['en', 'de', 'es']`) — all 23 locales remain built/deployed, only the UI selector is filtered. Current locale always shown so users on hidden locales can navigate away. Both desktop (swizzled `LocaleDropdownNavbarItem`) and mobile (`MobileLocaleSelector`) respect this setting. Has "Deutsche Dialekte" separator before dialect locales (CSS `li:has()` on desktop, React separator `<li>` on mobile) — only renders when dialects are in the visible set.
- **Footer**: Three columns — doQumentation (Features, Settings, GitHub, Legal/Impressum), RasQberry (site + GitHub), IBM Quantum & Qiskit (docs, GitHub, Slack). IBM disclaimer in copyright.
- **Legal page** (`/legal`): Impressum (Jan-R. Lahmann, contact via GitHub Issues) + Privacy Policy (Umami analytics, GitHub Pages hosting, external services, localStorage, GDPR rights). German DDG §5 + GDPR compliant. Linked from footer.
- **Admin page** (`/admin`): Hidden reference page for admins/workshop hosts. Analytics dashboard link, CI/CD workflow links, translation commands, workshop checklist, satellite repo list. Not in navbar, excluded from search engines (`robots.txt` Disallow).
- **Qamposer page** (`/qamposer`): Unlisted experimental visual quantum circuit composer (`@qamposer/react`). Embeds `QamposerMicro` wired into the existing thebelab kernel so simulations honor Settings (ideal / noisy fake / real IBM Quantum). `thebelabAdapter` routes via the active kernel, branching Python between `Backend.run()` and `SamplerV2` based on execution mode. `thebelabRealtimeAdapter` provides always-ideal live preview (disabled in real-device mode). `withRealDeviceGuard` pops a `window.confirm()` before any hardware job. Red pulsing badge + warning banner whenever real mode is active. Intentionally unlisted: no navbar/footer/homepage link, discreet experimental banner, `<meta robots="noindex,nofollow">`. Exports new `executeOnKernelWithOutput`/`getActiveKernel`/`ensureKernel` from `ExecutableCode` for adapter reuse.
- **Breadcrumbs**: Enabled via `docs.breadcrumbs: true` in `docusaurus.config.ts` — auto-generated navigation trail at the top of every doc page.
- **Analytics**: Umami Cloud (cookie-free, GDPR-compliant, no consent banner). Script in `headTags`, centralized `src/config/analytics.ts` module. Custom events: Run Code, Run All, Binder Launch, Colab Open. Locale tracked via custom Pageview event with hostname-derived locale. Auto-disabled on localhost/Docker. Dashboard: https://cloud.umami.is
- **Styling**: Carbon Design-inspired (IBM Plex, `#0f62fe`).
- **SEO & social sharing**: Open Graph + Twitter Card meta tags, JSON-LD structured data (Organization, WebPage, SoftwareApplication), robots meta for AI indexing, preconnect hints for fonts/CDN. Social card image (`static/img/rasqberry-social-card.png`, 1200x630).
- **Keyboard accessibility**: `focus-visible` outlines on all interactive elements; light blue variant on dark navbar for contrast.

---

## Project Structure

```
doQumentation/
├── .github/workflows/          # deploy, deploy-locales, docker, sync-deps, check-translations, binder, workshop-{start,monitor,close}
├── upstream-docs/              # Git submodule → JanLahmann/Qiskit-documentation (CC BY-SA 4.0)
├── upstream-addons/            # Git submodules → 7 Qiskit addon repos (Apache 2.0)
├── binder/                     # Jupyter requirements (cross-platform + amd64-only)
├── docs/                       # Content (gitignored except index.mdx)
├── notebooks/                  # Original .ipynb for JupyterLab (generated)
├── src/
│   ├── clientModules/          # pageTracker, displayPrefs, onboarding
│   ├── components/             # ExecutableCode, QamposerEmbed, ResumeCard, RecentPages, BookmarksList, OpenInLabBanner, BetaNotice, TutorialFeedback, TranslationFeedback, CourseComponents, GuideComponents
│   ├── config/                 # storage.ts (cookie+localStorage), jupyter.ts (env detection, credentials), preferences.ts (user prefs)
│   ├── css/custom.css          # All styling
│   ├── pages/                  # features.tsx, jupyter-settings.tsx, qamposer.tsx (unlisted experimental)
│   └── theme/                  # Swizzled: Root (global BetaNotice), CodeBlock, DocItem/Footer, EditThisPage, DocSidebarItem/{Category,Link}, Navbar/MobileSidebar/Header, NavbarItem/LocaleDropdownNavbarItem, MDXComponents
├── i18n/                       # Translations: de/es/fr/it/uk/ja (387 each — 100%), ar (385), pt (386), tl (383), cs (400 — 100%), ro (400 — 100%), pl (378/400 — 94%), ko (308/400 — 77%), he (47), ksh (46), nds (43), gsw (42), sax (39), bln (36), aut (34), swg/bad/bar (31 each)
├── scripts/                    # sync-content.py, sync-deps.py, docker-entrypoint.sh, setup-pi.sh
├── translation/                # Translation infrastructure
│   ├── drafts/{locale}/{path}  # Staging area for new translations (git-tracked)
│   ├── status.json             # Per-file tracking (status, validation, source hash, dates)
│   ├── translation-prompt.md   # Claude Code automation prompt
│   ├── register-fix-prompt.md  # Claude Code register rewrite prompt
│   ├── review-prompt.md        # LLM review prompt (Haiku/Gemini Flash)
│   └── scripts/                # validate, lint, review, fix-anchors, promote, populate, get-register-fails, status dashboard
├── static/                     # logo.svg (favicon), CNAME, robots.txt, docs/ + learning/images/ (gitignored)
├── Dockerfile.web              # Static site only (nginx, ~60 MB)
├── Dockerfile.jupyter          # Multi-stage: jupyter-local (full stack) + jupyter-codeengine (CE)
├── docker-compose.yml          # web + jupyter profiles
├── nginx.conf                  # SPA routing + Jupyter proxy
├── docusaurus.config.ts
├── sidebars.ts                 # Imports generated sidebar JSONs
└── README.md
```

**Generated (gitignored):** `docs/tutorials/`, `docs/guides/`, `docs/learning/`, `docs/qiskit-addons/`, `notebooks/`, `static/docs/`, `static/learning/images/`, `sidebar-*.json`

---

## Development

```bash
npm install                        # Install dependencies
npm start                          # Dev server (hot reload)
npm run build                      # Production build (needs NODE_OPTIONS="--max-old-space-size=8192")
python scripts/sync-content.py     # Sync all content from upstream
python scripts/sync-content.py --sample-only  # Sample content only
python scripts/sync-content.py --generate-locale-notebooks --locale de  # Generate translated notebooks
```

**Docker:**
```bash
podman compose --profile web up       # Static site → http://localhost:8080
podman compose --profile jupyter up   # Full stack → :8080 (site) + :8888 (JupyterLab)
```

**Dependencies:** Docusaurus 3.x, React 18, remark-math + rehype-katex, thebelab 0.4.x (CDN), Node.js 18+, Python 3.9+

---

## Gotchas

- **thebelab CDN pin** — Must use `thebelab@0.4.0`. Versions jump 0.4.0 → 0.5.0.
- **sync-content.py overwrites docs/** — Only `docs/index.mdx` is preserved. Edit transforms in the script, not generated MDX.
- **Admonition JSX** — Don't convert `<Admonition>` to `:::` directives. Breaks nesting inside `<details>`.
- **Build memory** — ~380 pages needs `NODE_OPTIONS="--max-old-space-size=8192"`.
- **thebelab config** — Pass options to `bootstrap(options)`. Do NOT use `<script type="text/x-thebe-config">`.
- **Binder cache** — Keyed to commit hash. Any push to Binder repo invalidates cache. Site uses `mybinder.org` federation endpoint (not a specific member). Cache-warming workflow hits all 3 federation members (2i2c, BIDS, GESIS) in parallel.
- **JSX href** — Card components use `href="/docs/..."`. `MDX_TRANSFORMS` has rewrite rules for both markdown and JSX patterns.
- **Kernel busy/idle** — thebelab 0.4.0 only emits lifecycle events. Must subscribe to `kernel.statusChanged` signal from `@jupyterlab/services` for actual busy/idle.
- **`_tag_untagged_code_blocks` + LaTeX** — The regex can match across output boundaries (closing fence → bare `$$...$$` → opening fence). Guards in place: skip if `$$` in content, exclude `$$` from `$` shell heuristic.
- **Sidebar items persist** across client-side navigation — must use custom events, not just mount-time checks.

---

## Multi-Language Infrastructure

### Architecture

Each language gets its own subdomain via satellite GitHub repos. Wildcard DNS CNAME `*` → `janlahmann.github.io` at IONOS covers all subdomains automatically.

| Locale | URL | Pages | Status |
|--------|-----|-------|--------|
| DE | [de.doqumentation.org](https://de.doqumentation.org) | **385 + UI (100%)** | Live |
| ES | [es.doqumentation.org](https://es.doqumentation.org) | **385 + UI (100%)** | Live |
| FR | [fr.doqumentation.org](https://fr.doqumentation.org) | **385 + UI (100%)** | Live |
| UK | [uk.doqumentation.org](https://uk.doqumentation.org) | **387 + UI (100%)** | Live |
| JA | [ja.doqumentation.org](https://ja.doqumentation.org) | **387 + UI (100%)** | Live |
| IT | [it.doqumentation.org](https://it.doqumentation.org) | **387 + UI (100%)** | Live |
| PT | [pt.doqumentation.org](https://pt.doqumentation.org) | **387 + UI (100%)** | Live |
| TL | [tl.doqumentation.org](https://tl.doqumentation.org) | **387 + UI (100%)** | Live |
| AR | [ar.doqumentation.org](https://ar.doqumentation.org) | **387 + UI (100%)** | Live (RTL) |
| HE | [he.doqumentation.org](https://he.doqumentation.org) | **387 + UI (100%)** | Live (RTL) |
| MS | [ms.doqumentation.org](https://ms.doqumentation.org) | **387 + UI (100%)** | Live |
| ID | [id.doqumentation.org](https://id.doqumentation.org) | **387 + UI (100%)** | Live |
| TH | [th.doqumentation.org](https://th.doqumentation.org) | **387 + UI (100%)** | Live |
| KO | [ko.doqumentation.org](https://ko.doqumentation.org) | **45 (44 tutorials + index)** + fallbacks | Live |
| PL | [pl.doqumentation.org](https://pl.doqumentation.org) | **45 (44 tutorials + index)** + fallbacks | Live |
| RO | [ro.doqumentation.org](https://ro.doqumentation.org) | **45 (44 tutorials + index)** + fallbacks | Live |
| CS | [cs.doqumentation.org](https://cs.doqumentation.org) | **45 (44 tutorials + index)** + fallbacks | Live |
| KSH | [ksh.doqumentation.org](https://ksh.doqumentation.org) | 46 + UI | Live |
| NDS | [nds.doqumentation.org](https://nds.doqumentation.org) | 43 + UI | Live |
| GSW | [gsw.doqumentation.org](https://gsw.doqumentation.org) | 42 + UI | Live |
| SAX | [sax.doqumentation.org](https://sax.doqumentation.org) | 39 + UI | Live |
| BLN | [bln.doqumentation.org](https://bln.doqumentation.org) | 36 + UI | Live |
| AUT | [aut.doqumentation.org](https://aut.doqumentation.org) | 34 + UI | Live |
| SWG | [swg.doqumentation.org](https://swg.doqumentation.org) | 31 + UI | Live |
| BAD | [bad.doqumentation.org](https://bad.doqumentation.org) | 31 + UI | Live |
| BAR | [bar.doqumentation.org](https://bar.doqumentation.org) | 31 + UI | Live |

**Potential future locales:** Turkish (TR)

- **Config**: `docusaurus.config.ts` — `locales: ['en', 'de', 'es', 'uk', 'fr', 'it', 'pt', 'ja', 'tl', 'ar', 'he', 'swg', 'bad', 'bar', 'ksh', 'nds', 'gsw', 'sax', 'bln', 'aut', 'ms', 'id', 'th']`, per-locale `url` in `localeConfigs`, `DQ_LOCALE_URL` env var. Built-in `LocaleDropdown` handles cross-domain links natively. hreflang tags auto-generated.
- **RTL support**: AR and HE have `direction: 'rtl'` in `localeConfigs`. CSS uses logical properties (`border-inline-start`, `margin-inline-start`, `inset-inline-end`) throughout — direction-agnostic for both LTR and RTL. Noto Sans Arabic/Hebrew fonts loaded via Google Fonts. `[dir="rtl"]` overrides in `custom.css`. **KaTeX math forced LTR** (`direction: ltr` on `.katex`, `.katex-display`) to prevent browser bidi from flipping parentheses/operators on RTL pages.
- **CI**: `deploy.yml` builds EN only (`--locale en`). `deploy-locales.yml` matrix builds all 22 locales separately, pushes to satellite repos via SSH deploy keys (`DEPLOY_KEY_{DE,ES,UK,FR,IT,PT,JA,TL,AR,HE,SWG,BAD,BAR,KSH,NDS,GSW,SAX,BLN,AUT,MS,ID,TH}`).
- **Satellite repos**: `JanLahmann/doQumentation-{de,es,uk,fr,it,pt,ja,tl,ar,he}` + `doqumentation-{swg,bad,bar,ksh,nds,gsw,sax,bln,aut,ms,id,th}` — each has `main` branch (README + LICENSE + LICENSE-DOCS + NOTICE) and `gh-pages` branch (build output). GitHub Pages + custom domains configured. Setup script: `.claude/scripts/setup-satellite-repo.sh`.
- **German dialects**: 9 dialect locales (SWG, BAD, BAR, KSH, NDS, GSW, SAX, BLN, AUT) with "Deutsche Dialekte" separator in locale dropdown. Desktop: CSS `li:has(> a[href*="swg.doqumentation.org"])::before` targets first dialect. Mobile: `dialectLocales` Set in `Navbar/MobileSidebar/Header` renders separator `<li>`. To add a new dialect: add to `dialectLocales` Set + `locales`/`localeConfigs` in config + CI matrix + `BANNER_TEMPLATES` + `locale_label` in `translation/scripts/translate-content.py`.
- **Full UI i18n** (`code.json`): All user-visible strings across React pages and components use Docusaurus `<Translate>` and `translate()` APIs. This covers Settings page (~90 keys), Features page (~39 keys), ExecutableCode toolbar (Run/Back/Lab/Colab buttons, status messages, legend, conflict banner), EditThisPage bookmarks, BookmarksList, DocSidebarItem/Link, BetaNotice, and MobileSidebar header. Total: ~308 keys per locale (~92 theme + ~216 custom). When adding a new language, `npm run write-translations -- --locale {XX}` auto-generates entries with English defaults; translate all `message` values. Technical terms (Qiskit, Binder, AerSimulator, etc.) and code snippets stay in English. Placeholders like `{binder}`, `{saveAccount}`, `{url}`, `{pipCode}`, `{issueLink}`, `{mode}` must be preserved exactly.
- **Fallback system**: `populate-locale` fills untranslated pages with English + "not yet translated" banner. ~387 fallbacks per locale. 22 banner templates defined in `translation/scripts/translate-content.py`.
- **Translation freshness**: Genuine translations embed `{/* doqumentation-source-hash: XXXX */}` (SHA-256 first 8 chars of EN source). Daily CI workflow (`check-translations.yml`) compares embedded hashes against current EN files. CRITICAL = missing imports/components (features broken); STALE = content changed. After propagating EN changes, run `check-translation-freshness.py --stamp` to update hashes. **Key rule**: Any change to EN source files (imports, components, content) must be manually propagated to genuine translations — `populate-locale` only refreshes fallbacks, not genuine translations.
- **Draft pipeline**: Translations go through `translation/drafts/{locale}/{path}` → validate → fix → promote to `i18n/`. Scripts: `validate-translation.py` (12 structural checks, `--dir`/`--section`/`--report`/`--record` flags), `fix-heading-anchors.py` (`--dir` flag), `promote-drafts.py` (`--locale`/`--section`/`--file`/`--force`/`--keep` flags). Status tracked in `translation/status.json` (hybrid: grows as files are validated/promoted, with status, validation result, source hash, dates, failures). Direct-to-i18n still works (all scripts default to `i18n/` without `--dir`).
- **Status dashboard**: `translation-status.py` — combines on-the-fly file scanning with `status.json` data. Modes: overview (all locales), `--locale XX` (per-section detail), `--backlog` (prioritized untranslated files, `--limit N` to cap output), `--validate` (run + record structural checks), `--markdown`/`--json` (output formats), `--update-contributing` (auto-update table in CONTRIBUTING-TRANSLATIONS.md between marker comments), `--write-status` (generate `translation/STATUS.md` with full report), `--all` (include dialect locales). Backlog priority: tutorials → guides → courses → modules. Daily CI auto-updates `translation/STATUS.md`.
- **Translation**: See [`CONTRIBUTING-TRANSLATIONS.md`](../CONTRIBUTING-TRANSLATIONS.md) for contributor guide (any tool/LLM). Two Claude Code prompts: `translation/translation-prompt.md` (CLI, full locale) and `translation/translation-prompt-web.md` (web UI, 20-file sessions). Both use Sonnet agents, 3 parallel, minimal agent prompts to reduce token usage. One-liner: `Read translation/translation-prompt.md. Translate all untranslated pages to French (fr).`
- **Translation validation**: Three-step QA. Step 1: `validate-translation.py` — 15 binary PASS/FAIL structural checks (line count, code blocks byte-identical, LaTeX, indented headings, heading count, anchors, invalid anchor chars, duplicate anchors, image paths, frontmatter, JSX tags, URLs, paragraph inflation). Indented headings use position-based EN comparison (not text-based). Heading count excludes EN-indented headings consistently. Tuned thresholds: paragraph inflation (`LOCALE_WORD_RATIO`: de=3.0x, fr/es/it/pt=2.5x, default=2.2x; `MIN_TR_WORDS_FOR_INFLATION`=250; `MIN_WORDS_FOR_INFLATION`=20; >15% para count divergence skipped), line count (15% all locales, absolute ±8 for files <50 lines), LaTeX inline ±30, LaTeX display ±4. Supports `--dir translation/drafts` for staging, `--section` for filtering, `--report` for markdown feedback, `--record` for writing results to `status.json`. Step 2: `lint-translation.py` — MDX syntax lint for build-breaking errors (duplicate heading anchors, garbled XML tags, heading markers mid-line, invalid anchor chars, unmatched code fences, missing imports, unescaped quotes in JSX attributes). Fence count compares TR to EN (not odd/even). Both have `--record` for status.json. `promote-drafts.py` runs both validation AND lint before promoting. Step 3: linguistic review (register, word salad, verbosity, accuracy) — tracked via `review-translations.py` (`--record-review`). Review prompt: `translation/review-prompt.md`.
- **Structural sync**: `sync-translations.py` mechanically fixes code block drift between EN and translations (pip install blocks, differing code, survey URLs). Run after translations or EN content changes: `python translation/scripts/sync-translations.py --all-locales` (or `--locale XX --dry-run` to preview). Integrated into `translation-prompt.md` workflow.
- **Review orchestration**: `review-translations.py` manages systematic review across sessions. `--auto-check` runs structural validation + lint for all locales in bulk. `--progress` shows per-locale dashboard (struct/lint/review counts). `--next-chunk [--size N]` returns prioritized batch of files needing linguistic review. `--record-review` persists verdicts (PASS/MINOR_ISSUES/FAIL/SKIPPED) to status.json. Baseline: 885 files, 456 structural PASS, 440 ready for review. AR full review complete (387 files, all fixed).
- **Register**: Informal/familiar (du/tu/tú/ти — not Sie/vous/usted/Ви). The Qiskit community uses informal address. Register fix automation: `translation/register-fix-prompt.md` (targeted rewrite, Sonnet agents). Helper: `translation/scripts/get-register-fails.py` lists FAIL files from status.json by locale.
- **Heading anchors**: Translated headings get `{#english-anchor}` pins to preserve cross-reference links. `fix-heading-anchors.py` for batch fixing (supports `--dir` for drafts).
- **Build**: ~320 MB per single-locale build. Each fits GitHub Pages 1 GB limit independently.
- **Attribution**: `NOTICE` file in main repo and all satellite repos credits IBM/Qiskit as upstream content source and documents dual-license structure. `LICENSE` (Apache 2.0) + `LICENSE-DOCS` (CC BY-SA 4.0) are clean template files (no custom preamble) so GitHub's Licensee detection works correctly. Upstream content tracked as git submodule (`upstream-docs/`) for clear license boundary separation.

### How to Add a New Language

#### 1. UI strings (4 files)

Generate templates, then translate all `"message"` values:

```bash
npm run write-translations -- --locale {XX}
```

This creates `i18n/{XX}/code.json` and `i18n/{XX}/docusaurus-plugin-content-docs/current.json`. Then create:

- `i18n/{XX}/code.json` — theme UI (~92 strings) + custom UI strings (~216 strings: `features.*`, `settings.*`, `executable.*`, `bookmark.*`, `bookmarksList.*`, `betaNotice.*`, `sidebar.*`, `navbar.mobile.*`). Total ~308 strings.
- `i18n/{XX}/docusaurus-plugin-content-docs/current.json` — sidebar category labels (~60 strings)
- `i18n/{XX}/docusaurus-theme-classic/navbar.json` — navbar items (Tutorials, Guides, Courses, etc.)
- `i18n/{XX}/docusaurus-theme-classic/footer.json` — footer labels + copyright disclaimer

Use `i18n/de/` as reference for all files.

#### 2. Banner template

Add a `{XX}` entry to `BANNER_TEMPLATES` in `translation/scripts/translate-content.py` — an admonition with "This page has not been translated yet" in the target language.

#### 3. Config (`docusaurus.config.ts`)

- Add locale to `locales` array
- Add entry to `localeConfigs` with `label` and `url: 'https://{XX}.doqumentation.org'`
- Add to search plugin `language` array (if [`lunr-languages`](https://github.com/MihaiValentin/lunr-languages) supports it — currently no support for `uk` or `tl`; `th` has a module but requires `lunr.wordcut` which the search plugin doesn't load, so Thai also cannot be added)
- Optionally add to `customFields.visibleLocales` array to show in the language selector dropdown (otherwise the locale is built/deployed but hidden from the dropdown)

#### 4. CI matrix (`deploy-locales.yml`)

Add entry to the matrix:
```yaml
- locale: {XX}
  repo: JanLahmann/doqumentation-{XX}
```

#### 5. Satellite repo + deploy infrastructure

**Automated script:** `.claude/scripts/setup-satellite-repo.sh` handles steps a–c below.

```bash
# a) Create satellite repo on GitHub (if not already created)
gh repo create JanLahmann/doqumentation-{XX} --public --description "doQumentation – {Label} locale"

# b) Initialize main + gh-pages branches (use the script)
./.claude/scripts/setup-satellite-repo.sh {XX} "{Label}"
# Creates main branch (LICENSE, LICENSE-DOCS, NOTICE, README.md)
# Creates gh-pages branch (placeholder index.html + CNAME)

# c) Generate + configure SSH deploy key
ssh-keygen -t ed25519 -C "deploy-doqumentation-{XX}" -f /tmp/deploy_key_{XX} -N ""
# Add public key as deploy key (write access) on satellite repo:
gh repo deploy-key add /tmp/deploy_key_{XX}.pub --repo JanLahmann/doqumentation-{XX} --title "deploy-doqumentation-{XX}" --allow-write
# Add private key as secret on main repo (uppercase locale code):
gh secret set DEPLOY_KEY_{XX_UPPER} --repo JanLahmann/doQumentation --body "$(cat /tmp/deploy_key_{XX})"
# Clean up key files:
rm /tmp/deploy_key_{XX} /tmp/deploy_key_{XX}.pub

# d) Enable GitHub Pages + custom domain
gh api repos/JanLahmann/doqumentation-{XX}/pages --method POST --field source='{"branch":"gh-pages","path":"/"}'
gh api repos/JanLahmann/doqumentation-{XX}/pages --method PUT --field cname="{XX}.doqumentation.org" --field https_enforced=true
```

DNS: The wildcard CNAME `*` → `janlahmann.github.io` at IONOS covers all subdomains automatically. No per-locale DNS needed.

#### 6. Translate content

```bash
# Translate pages to drafts (via Claude Code — see translation/translation-prompt.md)
Read translation/translation-prompt.md. Translate all untranslated pages to {LANGUAGE} ({XX}).

# Validate drafts
python translation/scripts/validate-translation.py --locale {XX} --dir translation/drafts

# Fix heading anchors in drafts
python translation/scripts/fix-heading-anchors.py --locale {XX} --dir translation/drafts --apply

# Promote passing drafts to i18n/
python translation/scripts/promote-drafts.py --locale {XX}

# Populate English fallbacks for remaining untranslated pages
python translation/scripts/translate-content.py populate-locale --locale {XX}

# Verify build
DQ_LOCALE_URL=https://{XX}.doqumentation.org npx docusaurus build --locale {XX}

# Stage translations (gitignored, must force-add)
git add -f i18n/{XX}/docusaurus-plugin-content-docs/current/
```

#### 7. Git tracking

- `code.json`, `navbar.json`, `footer.json`, `current.json` — tracked normally
- MDX translations in `i18n/{XX}/docusaurus-plugin-content-docs/current/` — gitignored, must `git add -f`

---

## Open Items

### TODO
- **Translation expansion** — **15 locales at 100% (400/400)**: DE, ES, FR, IT, UK, JA, AR, PT, TL, HE, MS, ID, TH + **CS, RO** (completed Apr 14). **2 locales in progress**: PL 378/400 (94%, 22 remaining), KO 308/400 (77%, 92 remaining). All validated — CS and RO pass 400/400 structural validation. Build errors fixed for all 4 new locales. Run `python translation/scripts/translation-status.py --all` for current counts. German dialects: KSH 46, NDS 43, GSW 42, SAX 39, BLN 36, AUT 34.
- **Full linguistic review** — Sample-based review (6 files/locale) done for CS, PL, KO, RO (Mar 28). Found and fixed: PL meaning error (Pauli twirling→entanglement), PL false cognate (transpose→transpile, 4x), CS fabricated verb, CS/KO/RO register slips, RO terminology drift, typos/diacritics. **AR full review COMPLETE** (Mar 28, Opus): all 387 files reviewed → 252 PASS, 120 MINOR_ISSUES, 14 FAIL. All issues fixed (72 files, 383 edits). Key findings: Egyptian dialect contamination in 9 learning/module files (retranslated to MSA), 2 files with untranslated content (translated), terminology disasters fixed ("bachelors"→"spins", "distillation"→"diagonalization"). Cross-cutting terminology harmonized: observable, quasi-probability, resilience, Pauli twirling. Full issue log: `memory/project_ar_review_issues.md`. Post-fix validation: 386/387 PASS (1 false positive). **DE/ES/FR/IT full reviews COMPLETE** (Mar 28): merged from dedicated review branches. DE ~150 fixes (84 files): Sie→du conversion, untranslated sections, spelling/math errors. ES accent/diacritic fixes + tú/usted consistency (110 files, +1727/-1730). FR gate→porte terminology + capitalization + ~120 fixes (146 files). IT ~1160 fixes across 207 files (most comprehensive). Review reports: `translation/drafts/de/linguistic-review-2026-03-28.md`, `translation/drafts/fr/linguistic-review.md`, `translation/reviews/it-linguistic-review.md`. **TODO**: Full review of remaining locales (CS/PL/KO/RO have sample-based only; UK/JA/PT/TL/TH/MS/ID/HE not yet reviewed at file level). Use Haiku.
- **Binder cold build broken** (since Apr 17) — mybinder.org upgraded Docker 27→28 on Apr 13 ([jupyterhub/mybinder.org-deploy#3768](https://github.com/jupyterhub/mybinder.org-deploy/pull/3768)), wiping all Docker layer caches. Build completes (pip install CACHED, COPY 2s, export 1.2s) but **pod is killed by Kubernetes** during image push — matches [jupyterhub/binderhub#2094](https://github.com/jupyterhub/binderhub/issues/2094) exactly (no error message, just "failed"). Root cause: repo2docker clones all 44K files regardless of `.dockerignore`, builds context tarball in memory ([#3680](https://github.com/jupyterhub/mybinder.org-deploy/issues/3680)), and the image export exceeds build pod memory limits changed on Apr 13 (PRs [#2071](https://github.com/jupyterhub/binderhub/pull/2071), [#2093](https://github.com/jupyterhub/binderhub/pull/2093)). GESIS federation member decommissioned (301 redirect). **Interim fix**: `binderUrl` and `binder.yml` cache-warming pinned to commit `0fc67252` (last cached image, Apr 13). Thebelab unaffected — uses kernel only, translations come from MDX pages. **To fix properly**: (1) Wait for mybinder.org to fix the memory/push issue (monitor [mybinder.org-deploy](https://github.com/jupyterhub/mybinder.org-deploy/issues)). (2) Split Binder into two instances: lightweight thebelab-only repo (just `requirements.txt`, ~1 GB image, no notebooks) + full `notebooks` branch for JupyterLab (see TODO below). (3) Open issue on mybinder.org-deploy about build pod OOM after Docker 28 upgrade. Note: `.dockerignore` does NOT help — the git clone and in-memory tarball still process all 44K files. CE image (Dockerfile.jupyter) is unaffected.
- **Split Binder into two instances** — Thebelab (in-page code execution) and "Open in JupyterLab" currently share one Binder image (`doQumentation/notebooks`), but their needs differ. Thebelab only needs a **Python kernel** (Qiskit + deps, ~800 MB pip layer) — no notebooks, no translations, no static assets. "Open in JupyterLab" needs the full repo with all notebook files. Splitting into two repos/branches would allow: (1) A **lightweight thebelab-only repo** with just `requirements.txt` (no Dockerfile, no COPY — repo2docker auto-installs). Image ~1 GB, builds in <3 min, rarely invalidated (only on dependency changes). (2) The existing `notebooks` branch for JupyterLab with all translated notebooks. This decouples thebelab reliability from notebook content churn and solves the cold-build timeout for the common case (most users run code cells, not JupyterLab). Implementation: create `doQumentation-binder` repo (or `binder-kernel` branch) with just `requirements.txt` + `runtime.txt`. Point `jupyter.ts` thebelab config at the lightweight repo, keep `openBinderLab()` pointing at `notebooks` branch.
- **Upstream sync strategy** — Plan how to pull upstream changes from [Qiskit/documentation](https://github.com/Qiskit/documentation) weekly. Currently `sync-content.py` clones from the fork (`JanLahmann/Qiskit-documentation`), which must be manually synced with upstream. Need: automated fork sync (GitHub Actions or scheduled script), handling of merge conflicts in modified files (`hello-world.ipynb`, `_toc.json`), freshness checks for translated content after EN changes, and a rollback strategy if upstream breaks the build.
- **Translation structural sync script** — ✅ DONE. See `sync-translations.py` in Resolved section below.
- **Qiskit execution error hints** — When a Binder/thebelab cell raises a common error, surface a helpful inline hint. Typical errors to handle: `IBMRuntimeError`/`QiskitBackendNotFoundError` (no IBM account → hint to run the save-account cell), `ModuleNotFoundError` (package missing → hint to run the prerequisites cell), `QiskitError: 'AerSimulator'` (aer not installed → hint re: kernel restart after pip), kernel restart/dead messages, and `NameError` on common Qiskit objects (cell run out of order → hint to run from top). Hook into thebelab's output area (or a MutationObserver on cell output divs) and match stderr/stdout against known patterns to inject a styled hint below the output.

- **Qamposer Python backend reuse (Option 2)** — The `/qamposer` page currently runs an **inline port** of QAMP-62/qamposer-backend's Python modules (`simulator.py`, `converter.py`, `qsphere.py`) embedded as a template string in [src/components/QamposerEmbed/thebelabAdapter.ts](src/components/QamposerEmbed/thebelabAdapter.ts). This works but means any upstream bug fixes must be manually back-ported. The cleaner long-term solution is to wrap upstream's `src/backend/quantum/{simulator,converter,qsphere,backends}.py` as a tiny installable Python package (e.g. `qamposer-quantum`), publish to PyPI, add to `binder/jupyter-requirements.txt`, and replace the inline template with `from qamposer_quantum import simulate_qasm, compute_qsphere_points` plus a thin shim that injects our ideal/fake/real mode routing. This way we genuinely reuse upstream code instead of forking it in place. Preserve the ability to inject credentials and route by doQumentation Settings. Needs: decide packaging repo (fork `qamposer-backend`? new standalone repo?), minimal `pyproject.toml`, CI for version bumps from upstream, NOTICE update pointing at the package instead of the inline port.
- **Qiskit Addons Phase 2 expansion** — Phase 1 shipped 11 tutorial notebooks from 7 addons. Each addon repo has substantial additional documentation in `docs/how_tos/` (or `how-tos/`) and `docs/explanation(s)/` that is not yet integrated. Inventoried 2026-04-10:
  - **Phase 2a** (already-submoduled addons, notebooks only, no new dependencies): +19 `.ipynb` files — Circuit Cutting 4 how-tos, SQD 7 how-tos, OBP 3 how-tos, MPF 2 how-tos + 1 explanation, AQC-Tensor 1 how-to, PNA 1 how-to. Would triple addon content from 11 → 30 notebooks. Implementation: extend `ADDON_SOURCES` schema to `{"repo": ..., "sections": {"tutorials": "docs/tutorials", "how-tos": "docs/how-tos"}, ...}`, refactor `process_addons()` to iterate sections, update `generate_addons_sidebar()` to emit nested `Addon > Tutorials` / `Addon > How-tos` categories. The nested sidebar split also reinforces the addon labelling fix from 2e724820.
  - **Phase 2b** (new submodules, +7 notebooks): `qiskit-addon-opt-mapper` (5 how-tos: migrate from qiskit-optimization, problem definition, converters, validate with solvers, translate DOCPLEX) + `qiskit-addon-utils` (2 how-tos: color device edges, create circuit slices). Needs 2 new submodules + `NOTICE` attribution + optional `jupyter-requirements.txt` updates.
  - **Phase 2c** (mthree): `qiskit-addon-mthree` has a flat `docs/` layout (not tutorials/how-tos subdirs). One `.ipynb` (`sampling.ipynb`) + ~15 `.rst` conceptual pages. Ship only the notebook; defer `.rst`.
  - **Phase 3** (`.rst` conversion, much larger lift): Each Phase 1 addon also has `.rst` index pages, explanations, and how-to intros (~20 files across all 7 repos). Converting these requires adding a pandoc / `docutils`→MDX step to `sync-content.py`. Defer until the site has an overall RST story.
  - **Caveats before shipping**: (1) dependency bloat — each addon's pip package may pull additional data-processing libs; how-to notebooks can be heavier than tutorials. (2) Binder image size already ~3.5 GB; Phase 2 may push enough to hurt startup. Mitigation: keep addons as `%pip install` cells only (no pre-install). (3) Translation fallback disk/build cost — 19 × 22 locales = 418 new fallback MDX files. (4) Addons are currently hidden from navbar (`9cb954fe`); decide separately when to unhide. (5) All 10 addon repos are Apache 2.0 per MEMORY.md — no license re-work needed.
- **Addon sidebar labelling** — ✅ DONE (2e724820). Single-tutorial addons (OBP, MPF, AQC-Tensor, PNA, SLC) were rendered as bare entries showing only the notebook title. Fixed by removing the `len(items) == 1` special case in `generate_addons_sidebar()` — every addon is now always wrapped in its own category with display name.
- **Submodule pointer drift** — `upstream-docs/` submodule is locally at `6f006d7a` but committed pointer is `1472ac86`. Still uncommitted as of April 2026. Decide: commit the bump, or reset to committed state.
- **Hello World "What's Next" section** — The "What next?" in `tutorials/hello-world.mdx` (self-written) should recommend paths forward in both Qiskit-documentation and doQumentation, since the two projects offer different things.
- **Workshop mode — single-pod stress testing COMPLETE** (Apr 11-12 2026). Validated 1/4/8/12 vCPU pod sizes. Found and fixed: nginx rate limit (5→100 r/m), kernel cull tuning (600→300s), cgroup-aware `/stats` metrics, SSE shim async refactor (tornado), Jupyter race-condition retries (server-side `/api/status` retry + client-side WS handshake retry). **Final sizing with retries**: 8 vCPU/16 GB handles 80 users with ZERO failures at 5s burst (was 15 failures pre-retry). 12 vCPU/24 GB handles 80-100 users. Capacity scales ~6 sessions/vCPU with diminishing returns above 8 vCPU (SSE shim GIL contention, then Jupyter race conditions). Memory never the constraint for 5-qubit workloads (max 44% across all tests). Full writeup: `.claude/STRESS-TEST-FINDINGS.md`.
  - **Workshop lifecycle workflows**: `workshop-start.yml` (resize + token + warm, multi-pod via `instance_count`), `workshop-monitor.yml` (continuous `/stats` polling + timeline + sparklines), `workshop-close.yml` (cancel monitor + resize down + rotate token + reset pod). All verified working.
  - **Instructor flow**: run Workshop Start from GH Actions UI → read pod URL from summary, token from IBM Cloud Console or CLI → share URL publicly (slide/QR), token privately (verbal/handout). Students: open `/jupyter-settings` → paste URL(s) or base64 pool config into the Code Engine URL field + token → Save.
  - **Security**: token never appears in GH Actions summaries or logs (masked via `::add-mask::`). Base64 pool config in summary contains only URLs (no token). Token rotated on each Workshop Close (default `rotate_token=true`).
  - **Admin monitoring**: live `/admin` page with `PodMonitor` component (sparklines, health interpretation, per-pod cards, 15-min auto-stop timer).
  - **GH Actions self-service**: `stress-test.yml` (run harness from CI), `resize-pod.yml` (one-click pod resize), smarter deploy step in `codeengine-image.yml` (preserves pod size on push).
  - **Multi-pod still untested end-to-end**: `workshop-start.yml` supports `instance_count` > 1 and generates base64 pool config. Settings page CE URL field auto-detects base64 pool config. But the actual multi-pod pool with frontend random-assignment has never been tested with real CE deploys. Required for workshops >80 users.
  - **Harness**: `scripts/workshop-stress-test.py` — `KernelSession` (one WS per kernel), `--ramp-interval` (uniform stagger), real `/stats` polling. Client-side WS handshake retry (1 retry, 1s backoff).
  - **Known Jupyter Server 2.16.0 bugs**: (1) `TraitError: 'last_activity'` race — absorbed by server-side retry. (2) `AttributeError: NoneType.kernel_ws_protocol` — absorbed by client-side retry. (3) `connections_dict` underflow → prevents kernel culling → memory creep. Workaround: restart pods between workshops.
- **GH Actions automations using `IBM_CLOUD_API_KEY`** — three of four original automations implemented and verified working (commit `410c2ea5`), plus three workshop lifecycle workflows (commit `a0a1481b`, refactored Apr 12 2026 to separate monitoring):
  - **(a) ✅ Smarter `Deploy to Code Engine` step** in `codeengine-image.yml`. The deploy step now preserves the pod's existing CPU/memory size on push events instead of resetting to the workflow_dispatch input defaults. Verified by pushing the change itself: pod stayed at 1 vCPU / 2 GB across the CI rebuild instead of resetting to 1 vCPU / 4 GB. workflow_dispatch inputs default to empty (preserve current size) with explicit override available; new app creation still uses sensible defaults (4 vCPU / 8 GB instead of the old 1 vCPU / 4 GB).
  - **(b) ✅ `workflow_dispatch` "Stress Test" job** at `.github/workflows/stress-test.yml`. Runs `scripts/workshop-stress-test.py` from CI. Inputs: `app_name`, `users` (5/10/25/50/80/100/150), `ramp_interval` (0/5/10/30/75), `cells_per_user`, `simple_workload` boolean. Discovers Jupyter token at runtime from the CE app's env vars (no extra secrets needed). Posts a structured GitHub job summary with config + summary lines + full output (collapsed) + interpretation guide. Verified working with 10u/5s test (10/10 kernels, 0 fails, summary posted).
  - **(c) ✅ `workflow_dispatch` "Resize Pod" job** at `.github/workflows/resize-pod.yml`. Single `size` dropdown with all valid CE CPU/memory combinations the project uses (1/4, 2/8, 4/8, 4/16, 8/16, 8/32, 12/24, 12/48). Parses "8 vCPU / 16 GB" into separate cpu/memory values. Shows current pod state before and after the resize. Verified working: resized pod from 1 vCPU / 2 GB to 4 vCPU / 8 GB in 23 seconds.
  - **(d) NOT IMPLEMENTED** — Daily "Warm Pod" scheduled job. Skipped per user instruction. Pods will continue to cold-start (15-150s) on the first request of the day.
  - **(e) ✅ Workshop lifecycle workflows** — `workshop-start.yml` (pod setup: resize + token + warm, ~2 min), `workshop-monitor.yml` (continuous `/stats` polling + timeline report, 30m–6h), `workshop-close.yml` (cleanup: cancel monitor, resize down, rotate token). Monitor is fully independent — can be started/stopped without affecting start/close. Admin dashboard (`/admin`) PodMonitor component has 15-min auto-stop timer to prevent accidental pod keep-alive from browser polling.
  - **Result**: workshop instructors can now resize, monitor, and stress test pods entirely from the GitHub UI without local IBM Cloud CLI. The CI rebuild path no longer needs manual resize follow-ups. Burned ~10 min of manual resizes during the Apr 11 stress test session — fixed.
- **Workshop setup guide update** — `/workshop-setup` (`src/pages/workshop-setup.mdx`) references old project name `ce-doqumentation-01`, old sizing recommendations, and old CLI commands. Update to new naming convention (project `doQumentation`, app `jupyter`), new sizing data from stress tests, and current workflow names.
- **Admin page** (`/admin`) — password-protected via build-time SHA-256 hash. Set `ADMIN_PASSWORD` repo secret; hash injected into bundle via `docusaurus.config.ts` `customFields.adminPasswordHash`. Client hashes input with Web Crypto API, compares, stores in `sessionStorage` (survives navigation, clears on tab close). No password set = unprotected (local dev convenience). Both `deploy.yml` and `deploy-locales.yml` pass the secret as env var.
- **Fork testing** — Verify the repo can be forked with Binder still working
- **Raspberry Pi** — `scripts/setup-pi.sh` written but untested on actual hardware
- **IBM Quantum Ecosystem listing** — Submit doQumentation.org to https://www.ibm.com/quantum/ecosystem to increase visibility.
- **Video subtitles — 4 missing videos**: 55/55 videos fully translated (EN + 17 languages). 4 videos have no transcript at all (134371939, 134371940, 134371941, 134399598 — guide demos, may lack subtitles). See `.claude/transcript-status.md` for full breakdown.
- **Copy code button** — Add a one-click copy button to code blocks. Docusaurus supports this natively via `themeConfig.prism` — may be disabled or hidden by the swizzled `CodeBlock` component in `src/theme/CodeBlock/`.
- **Video subtitles — remaining work**:
  - **55/59 EN transcripts done** (32 YouTube via youtube-transcript-api + 23 IBM Video via Cowork). 4 IBM Video transcripts remaining — use `scripts/video-subtitle-cowork-prompt.md`.
  - **55/55 fully translated** (EN + 17 languages: ar, cs, de, es, fr, he, id, it, ja, ko, ms, pl, pt, ro, th, tl, uk). Batch 1 squash-merged 2026-04-04 (33 videos). Batch 2 merged 2026-04-09 from `claude/video-transcript-translations-P5nk1` (22 IBM Video transcripts, 374 VTT files).
  - **4 missing entirely** — 134371939, 134371940, 134371941, 134399598 (guide demos, may lack subtitles).
  - **Full status**: `.claude/transcript-status.md`
  - **Whisper alternative**: `pip install openai-whisper yt-dlp` for higher quality but slower (~5 min/video). Documented in `scripts/generate-transcripts.py` header.
  - **Post-processing**: Corrections dict in `generate-transcripts.py` fixes known errors (Kisket→Qiskit, Watchras→Watrous).
- **Review IBM tutorial survey links** — ~40 tutorials contain "Tutorial survey" sections linking to IBM's feedback system (`your.feedback.ibm.com`), inherited from upstream. Partially addressed: `sync-content.py` now appends a clarifying note ("This survey is by IBM Quantum…") + `<TutorialFeedback />` widget for doQumentation-specific feedback. May still want to further distinguish or strip entirely.

### Resolved (April 2026)
- **Branch integration (Apr 9)** — Merged 4 `claude/*` branches into main. **`claude/video-transcript-translations-P5nk1`**: 374 new VTT files completing all 17-locale translations for 22 IBM Video transcripts (55/55 videos now fully translated across all locales). **`claude/plan-ai-features-I1bzx`**: cherry-picked — adds `.claude/AI_FEATURES_BRAINSTORMING.md` (~30 AI feature ideas across search, learning, debugging, content, infra — tiered by cost $0 / $0–5 / $140+; Smart Search, Adaptive Learning Paths, Granite/Code Engine RAG). **`claude/document-todos-ideas-UQz3F`**: cherry-picked 8 of 9 commits — Qiskit Addons Phase 1 (7 submodules, sync-content.py extension, `sidebar-addons.json`, navbar entry later hidden via `Hide Qiskit Addons from navbar and main sidebar`), UX polish commit (`86a97b0f`): breadcrumbs enabled, Code Engine status messages (was still saying "Binder" for cache-miss/slow-startup), `TutorialFeedback` widget (Umami-tracked, appended to all tutorial MDX via sync-content.py), `TranslationFeedback` banner on non-EN pages, "View in English" link at top of locale dropdown, code-injection transparency (setup notice cell in exported notebooks, "What's modified?" link on `OpenInLabBanner`, new `/about/code-modifications` page listing every automatic transform). Skipped one commit (`499645f5` regenerated tutorial MDX — reproducible via sync-content.py) and deferred `7e50ebba` (upstream-docs submodule bump). Conflict resolution: 22 tutorial MDX files had bottom-chunk conflicts from the feedback widget injection — resolved with `--theirs` since content is regenerable. **`claude/add-qamposer-doqumentation-4IIR4`**: merged — unlisted `/qamposer` page (see Other features section). Auto-merged cleanly with the UX polish commit on `ExecutableCode/index.tsx` (different regions). Added `@qamposer/react ^0.1.3` npm dependency.

### Resolved (Feb–Mar 2026)
- **Backend selection UI** — Radio buttons on settings page when multiple backends available. `detectJupyterConfig()` refactored with `buildConfigFor()` helper and override support (`doqumentation_backend_override` key). Auto-clears stale overrides. Credential save/delete handlers refresh the backend list. Switching backends cancels in-flight builds and clears cached sessions.
- **Rethink user intro & settings page** — Settings page reorganized: essentials at top, advanced collapsed in `<details>`. Hash deep-links auto-open. Simulator defaults ON. Onboarding tip simplified ("Click Run — no setup needed", 2 visits).
- **Run All button** — Page-level "Run All" in toolbar. Sequential execution with `waitForKernelIdle()` (debounced idle, same `IDLE_DEBOUNCE_MS` as single-cell) + `waitForOutputStable()` (MutationObserver). Pause/Continue support: "Pause (3/8)" waits for current cell to finish then suspends loop via promise gate; "Continue (3/8)" resolves promise to resume; "Stop" aborts. Also aborts on Back/Restart/navigation.
- **Binder-enable this repo** — Full Binder setup on `notebooks` branch. Shared session reuse via `ensureBinderSession()`. Image ~3.5–4.5 GB (down from 7.6 GB conda-based).
- **Binder layer caching** — Option C deployed: `binder/Dockerfile` with `FROM quay.io/jupyter/base-notebook:python-3.12` + pip install. Bypasses repo2docker conda solver.
- **Binder startup UX** — Real-time progress in OpenInLabBanner, ExecutableCode toolbar, and JupyterLab loading tab. Per-phase duration hints, cache miss warnings.
- **Mobile side navigation** — Fixed locked sidebar (`transform: translateX(0) !important` removed), invisible arrows (invert filter), dark `Back to main menu` button.
- **Consolidate Docker images** — Single `Dockerfile.jupyter` with shared `jupyter-base` stage and two targets: `jupyter-local` + `jupyter-codeengine`.
- **Update features page** — 22→31 cards across 6 sections. Added CE, Colab, Bookmarks, Recent Pages, Display Preferences, Multi-Language section. Later added Run All & Restart, Onboarding Tips, backend selection mention, Binder cancel mention.
- **Translation review + register fix** — All 456 structurally-passing files reviewed across 19 locales. 194 formal-register files fixed via targeted LLM rewrite. Full linguistic review completed for all 9 major locales (3,477 files): DE 387, IT 387, AR 385, ES 387, FR 387, UK 387, JA 388, PT 387, TL 387 — zero FAILs remaining. Reviews checked register, word salad, verbosity, and accuracy. Fixed: ES 2 (wrong locale + word salad), FR 10 (Spanish files in FR dir), DE 8 (formal register). Results tracked in `translation/status.json`.
- **DE/ES/FR/IT full linguistic review (Mar 28)** — Merged 4 dedicated review branches into main. German: ~150 fixes across 84 files (Sie→du consistency, untranslated sections in DAG-representation.mdx and grovers.mdx, spelling/math errors). Spanish: accent/diacritic fixes + tú/usted mixing across 110 files. French: gate→porte terminology standardization, capitalization fixes ("Circuit"), ~120 issues across 146 files (including files that were accidentally in Spanish translated to French). Italian: ~1,160 fixes across 207 files — most comprehensive single-locale review. All branches forked from same point, no conflicts, clean merges.
- **IBM Cloud spending limits** — No hard limits available. Set $5/month spending notification. Existing controls: max-scale=1, min-scale=0, rate limiting.
- **Notebook MDX corruption in JupyterLab/Colab** — All 128 EN notebooks (86 guides + 42 tutorials) showed raw Docusaurus frontmatter (`---\ntitle: ...---`) and JSX comments (`{/* cspell:ignore... */}`, `{/* DO NOT EDIT THIS CELL */}`) as literal text when opened in JupyterLab or Colab. Fixed in `copy_notebook_with_rewrite()`: strip YAML frontmatter from first markdown cell + apply `clean_notebook_markdown()` to all markdown cells. Also added `re.DOTALL` to JSX comment regex in `clean_notebook_markdown()` for multi-line comments. Translated notebooks were unaffected (different pipeline already strips frontmatter). All 261 static notebooks scanned clean. Build: exit 0.
- **Hide "Open in:" banner on code-cell-free pages** — `sync-content.py` now checks `has_code_cells` before injecting `OpenInLabBanner`. 86 notebook-derived pages that contain only markdown/math (conceptual course lessons in Basics of QI, Foundations of QEC, Fundamentals of QA, General Formulation, etc.) and 7 guides no longer show the banner. 1,634 i18n files (86 pages × 19 locales) cleaned up in the same commit. Build: clean, exit 0.
- **Translation register fix (194 files)** — Linguistic review found 194 files across 10 locales using formal register instead of required informal. All fixed via targeted LLM register rewrite (`translation/register-fix-prompt.md`): DE (64), FR (36), ES (36), UK (18), IT (17), SWG (10), BAD (8), SAX (3), AUT (1). 2 non-register FAILs skipped (NDS soft hyphens, TL structural). Added `FIXED` verdict to `review-translations.py`. Helper: `translation/scripts/get-register-fails.py`.
- **Shared Binder session** — "Open in Binder JupyterLab" and thebelab code execution share a single Binder session. `ensureBinderSession()` handles build-or-reuse logic; `openBinderLab()` and `bootstrapOnce()` both call it. Thebelab switched from `Qiskit-documentation/main` (separate Binder) to `doQumentation/notebooks` (shared, via `serverSettings`). Session stored in `sessionStorage`, 8 min idle timeout, touched on kernel activity. Fixed initial tab reuse issue: `noopener`/`noreferrer` was discarding named window targets (per HTML spec).
- **Skip redundant pip install cells on Binder/CE** — Two-part fix: (1) Website thebelab: `ExecutableCode` detects injected pip install cells (via `Added by doQumentation` marker) and returns `null` on Binder/CE environments — cell completely hidden. (2) JupyterLab notebooks: `_make_prereq_cell()` helper uses `importlib.util.find_spec('qiskit')` to skip pip install when packages are pre-installed, prints "✓ Packages already installed" instead. Saves ~10-30s per notebook on Binder/CE. Colab unchanged (auto-runs pip install via `cell_execution_strategy: 'setup'`).
- **Comprehensive prerequisites cell** — Merged two pip install cells (base + extras) into single comprehensive cell per notebook. Deleted stale `BINDER_PROVIDED` set; now uses stdlib-only filtering so ALL third-party imports appear in the prerequisites cell. Fixes bug where 26 notebooks with `qiskit-ibm-catalog` (and others like `pyscf`, `ffsim`) were missing packages on Colab. Zero maintenance — no platform-specific package list to keep updated.
- **DE tutorial fixes (18/18 PASS)** — Fixed 8 failing DE tutorials: added 3 missing IBM survey links, restored EN code comments in 5 code blocks, fixed truncated code output, restored missing internal link, fixed 2 paragraph boundary misalignments. Added locale-specific paragraph inflation threshold (`de: 3.0x`). Added `--write-status` to daily CI workflow and German dialect locales to CONTRIBUTING-TRANSLATIONS.md table.
- **FR/ES/DE 100% translation completion** — Squash-merged 963-file `continue-translations` branch (FR/ES/DE guides, courses, modules). Fixed all 73 validation failures: 19 code block restorations, 12 heading count fixes, 7 missing link URLs, 3 truncated file reformats. Tuned validator to eliminate false positives (paragraph inflation MIN_TR_WORDS=250, LaTeX display ±4, LaTeX inline ±30, short-file absolute tolerance). Translated final 8 remaining course files (7 FR, 1 ES) via chunked parallel Sonnet agents. Promoted all drafts. Final: FR 385/385, ES 385/385, DE 385/385 — zero fallbacks.
- **Translation status dashboard** — New `translation-status.py` script: overview of all locales with section breakdown, `--locale` detail view, `--backlog` (prioritized untranslated files), `--validate` (run + record to status.json), `--markdown`/`--json` output, `--update-contributing` (auto-updates CONTRIBUTING-TRANSLATIONS.md table). `validate-translation.py` gained `--record` flag to persist results. `status.json` expanded with source hash, dates, failures. Hybrid approach: status.json grows over time as files are validated/promoted; existing i18n/ translations counted on-the-fly.
- **Colab "Open in Colab" 403 fix** — Colab's `/url/` scheme blocks non-GitHub domains (Google SSRF allowlist). Switched to `/github/` scheme pointing to processed notebooks (with pip install cells). EN: `doQumentation/blob/notebooks/` branch, auto-pushed by new CI step in `deploy.yml` (`contents: write` permission, force-pushes `build/notebooks/` after build). Translated: satellite repos `doqumentation-{locale}/blob/gh-pages/notebooks/` (already existed). Unified path mapping for both via `mapBinderNotebookPath()`: bare filenames get `tutorials/` prefix. KSH build fix: removed duplicate heading anchor with apostrophe in `transpilation-optimizations-with-sabre.mdx`.
- **Translation draft pipeline** — Added `translation/drafts/` staging area with validate → fix → promote workflow. New scripts: `promote-drafts.py` (with `--section`/`--file`/`--force`/`--keep` flags), `validate-translation.py` (added `--dir`/`--section`/`--report`), `fix-heading-anchors.py` (added `--dir`). Status tracking in `translation/status.json`. Backward compatible — all scripts default to `i18n/` without `--dir`.
- **Translation validation improvements** — Fixed 3 false-positive categories: code block trailing whitespace tolerance, frontmatter title allowlist (`FRONTMATTER_SAME_ALLOWED`), dialect locales in `ALL_LOCALES`. Overall pass rate improved from 53% to 63%. Fixed 130 missing heading anchors across 13 locales.
- **Translation build fixes** — Fixed 3+1 locale build failures: KSH garbled `<bcp47:` heading artifact, HE missing newlines before headings (×2), SAX image path `tutorial` → `tutorials`. All pre-existing from translation agents.
- **Locale dropdown separator** — "Deutsche Dialekte" CSS separator wasn't rendering. Root cause: Docusaurus applies navbar `className` to the `<a>` trigger, not the wrapper `<div>`. Fixed by changing descendant selector to sibling combinator (`~`).
- **BetaNotice global via Root wrapper** — Originally only on homepage `index.mdx` (missing from locale sites). Moved to swizzled `src/theme/Root.tsx` so it renders on every page (docs, homepage, settings, features) without per-file imports. Removed manual imports from EN + 19 locale `index.mdx` files. Session-based dismissal via sessionStorage.
- **MDX lint script** — New `lint-translation.py` catches build-breaking MDX syntax errors that `validate-translation.py` misses: duplicate heading anchors, garbled XML namespace tags, heading markers mid-line, invalid anchor characters, unmatched code fences, missing imports. Integrated into review workflow (`review-instructions.md`, `review-prompt.md`). Both `validate-translation.py` and `lint-translation.py` have `--record` flag for status.json persistence.
- **Translation review orchestration** — New `review-translations.py` manages systematic review of all 885 translations across sessions. `--auto-check` runs structural + lint in bulk (populated all 885 entries). `--progress` dashboard. `--next-chunk` returns prioritized batch for linguistic review. `--record-review` persists verdicts to status.json. Baseline: 456 PASS structural, 877 CLEAN lint, 440 ready for review, AR auto-skipped.
- **Translation freshness system** — Built `check-translation-freshness.py` with embedded source hashes (`{/* doqumentation-source-hash: XXXX */}`) in all 885 genuine translations. Daily CI workflow (`check-translations.yml`) detects CRITICAL (missing imports/components) and STALE (content changed) translations. Prevents future BetaNotice-type regressions.

- **Audit "Open in" button visibility** — Audited all environments: button visibility is correct by design (environment-dependent, not page-dependent). All notebook sources (Binder `notebooks` branch, CE container, Docker local, Colab) serve equivalent content from `copy_notebook_with_rewrite()`. Removed redundant raw Binder button — on GitHub Pages, JupyterLab already goes through Binder with better UX (SSE session management, progress indicators, session reuse). Now consistently 2 buttons (JupyterLab + Colab) across all environments. Removed `getRawBinderUrl()` from `jupyter.ts`.
- **Trivy CVE fixes (Mar 2026)** — Fixed 5+2 HIGH CVEs in CE image. Added `urllib3>=2.6.3` pin, `apt-get upgrade gpgv` in base stage, `pip install --upgrade` flag for security pins (conda base image wasn't honoring `>=` constraints). Added `.trivyignore` entries for 3 unfixable bundled deps (mathjax CVE-2023-39663, underscore CVE-2026-27601, gpgv CVE-2025-68973). Moved security pins from CE-only to shared `jupyter-base` stage so both Docker targets inherit them. Later added `PyJWT>=2.12.0` (CVE-2026-32597) and `pyasn1>=0.6.3` (CVE-2026-30922).
- **Sidebar indicator redesign (Mar 2026)** — Consolidated two separate indicator elements (`dq-sidebar-notebook-icon` + `dq-sidebar-indicator`) into a single unified indicator with 5 states: pure MDX visited (`✓` gray), notebook unvisited (`</>` gray, non-clickable), notebook visited (`</>` blue), notebook executed (`</>` green). Link indicators absolutely positioned with `padding-inline-end: 2.25rem`. Category badges DOM-injected as `<span role="button">`: before `.menu__caret` for href categories, inside the link for non-href categories (with CSS flex on `.menu__link--sublist-caret:has(.dq-category-badge)`). Badge creation in `useEffect([allHrefs])`, injection in `useLayoutEffect` (no deps) to survive React re-renders from collapse-restore clicks. Gray indicators use `emphasis-600` + higher opacity for readable contrast. Green executed indicator uses `font-weight: 700` + `opacity: 0.9` to distinguish from blue visited (`opacity: 0.7`, normal weight). CSS modifier classes: `--visited`, `--nb-unvisited`, `--nb-visited`, `--nb-executed`.
- **Translation prompt improvements (Mar 2026)** — Rewrote `translation/translation-prompt.md` to fix three recurring orchestrator issues: (1) Added explicit "Source File Paths" section with path table — courses are at `docs/learning/courses/` and modules at `docs/learning/modules/`, not top-level. (2) Made chunking instructions prescriptive — step-by-step algorithm the orchestrator MUST follow for files >400 lines, with "Common mistakes to AVOID" list. (3) Discovery now uses `translation-status.py --backlog` as primary method and globs all four source directories separately; drafts counted equally with promoted files.
- **Info icons on key UI elements** — Reusable `InfoIcon` component (`src/components/InfoIcon/`) with CSS-only tooltips via `data-tooltip` + `::after`. Placement: 5 Settings page fields (Simulator Mode, API Token, CRN, CE URL, CE Token), toolbar mode badge, plus 7 notebook-page locations: "Open in:" banner label, execution legend, Restart Kernel button, Clear Session button, Binder status phases, cache miss warning, and skip-cell banner (vanilla DOM with same CSS classes). All strings i18n-wrapped via `translate()`.
- **Thebelab bootstrap race fix** — First Run click didn't show per-cell run buttons. `bootstrapOnce()` ran synchronously before React rendered `<pre data-executable>` elements. Fixed by deferring to `requestAnimationFrame()`.
- **Test connection UX** — Removed "Jupyter version: unknown" from success message (just "Connected!"). Increased retry attempts from 4→6 (~90s) for CE cold starts.
- **Error submission for contextual help** — "Report this error" link on all cell errors (module, name, kernel, generic). Opens pre-filled GitHub issue with "Describe the issue" section at top for user input, then auto-populated sections: error text (1500 char cap), cell source code (1000 char cap), page path, environment, simulator mode, and user agent. Zero infrastructure — uses `github.com/.../issues/new` URL parameters. Also added generic error hint ("An error occurred.") for tracebacks that don't match specific patterns.
- **Homepage Code execution section** — Added IBM Code Engine to backends list (3→4), updated deployment options table, added backend selection link.
- **Three new locales: MS, ID, TH (Mar 2026)** — Added Bahasa Melayu (`ms`), Bahasa Indonesia (`id`), and Thai (`th`). Full infrastructure: `docusaurus.config.ts` (locales, localeConfigs), CI matrix entries in `deploy-locales.yml`, banner templates for ms/id in `translate-content.py`, ms/id added to `ALL_LOCALES` in `validate-translation.py`. Satellite repos created (`doqumentation-{ms,id,th}`) with main + gh-pages branches, SSH deploy keys, GitHub Pages + custom domains. UI string templates generated (4 JSON files each). 387 English fallback pages per locale. Not added to `visibleLocales` (hidden from dropdown, accessible via direct URL only). Also updated LICENSE, LICENSE-DOCS, and NOTICE across all 22 satellite repos to match main repo. **Build fix**: `th` removed from search `language` array — `lunr.th.js` requires `lunr.wordcut.init()` which `@easyops-cn/docusaurus-search-local` doesn't load, causing SSR crash (`Cannot read properties of undefined (reading 'init')`). **Post-fix**: All 12 UI string JSON files for ms/id/th had Berlin German (bln) dialect text instead of English defaults (caused by workaround during initial setup when `write-translations` agent failed). Deleted and regenerated fresh. One fallback page (`grovers.mdx`) had German content from a stale `docs/` build — re-ran `sync-content.py` + `populate-locale`.
- **Upstream license detection PR (Mar 2026)** — Discovered the same license preamble issue we fixed exists in the upstream `Qiskit/documentation` repo (GitHub shows "Other" instead of "Apache-2.0"). Filed PR [#4846](https://github.com/Qiskit/documentation/pull/4846) to remove the preamble from their `LICENSE` and `LICENSE-DOCS` files.
- **Branch integration Phase 1 (A–E)** — Cherry-picked ~40 non-CE improvements from `claude/ibm-cloud-serverless-concept-UP0PJ` (52 commits, manually applied due to interleaved CE code). Changes across 7 files: `storage.ts` (cross-tab cache sync, dev-gated logging), `preferences.ts` (Array.isArray guards, LRU cap 2000, schema guards, rename `clearRecentAndLastPage`), `jupyter.ts` (12 fixes: URL validation, ws URL regex, RFC 1918, TTL/backend/mode validation, 15s AbortController timeout, 20-min EventSource timeout+settled guard, encodeURIComponent on paths/tokens, escapeHtml+makeTabHtml for popup tabs, getColabUrl dedup), `jupyter-settings.tsx` (CRN validation, removed stale ibmExpiredNotice), `ExecutableCode/index.tsx` (resetModuleState consolidation, isValidPackageName helper, 15 i18n translate() keys, SPA cleanup via useLocation, MutationObserver for first-cell, timer leak fixes, bootstrap race fix, a11y roles, BOOTSTRAP_MAX_RETRIES), `custom.css` (6 CSS variables for badge/toast/conflict colors, cell execution icons ▶✓✗ via ::after, settings max-width 900px, mobile responsive, focus-visible toggle), `.dockerignore` (*.key, *.pem). Phase 2 (CE feature) deferred. Reference docs: `.claude/PROJECT_REVIEW.md`, `.claude/AI_INTEGRATION_IDEAS.md`.
- **License detection + content submodule** — Fixed GitHub "Unknown" license by removing custom preamble from `LICENSE` and `LICENSE-DOCS` (Licensee needs clean template text). Moved dual-license explanation to `NOTICE`. Added git submodule (`upstream-docs/` → `JanLahmann/Qiskit-documentation`) for clear Apache 2.0 / CC BY-SA 4.0 boundary separation. `sync-content.py` updated to prefer submodule with sparse-clone fallback for forks. All CI workflows updated with `submodules: true`.
- **Open Plan Session compatibility (Mar 2026)** — IBM Quantum Open Plan doesn't support `Session` execution mode. Added plan type selector (Open/PAYG/Premium) to Settings page (`doqumentation_ibm_plan` storage key, default: Open). When Open Plan + credentials active, `injectKernelSetup()` monkey-patches `qiskit_ibm_runtime.Session` with `_DQ_JobModeSession` — a passthrough context manager where `session` becomes `backend`, so `Sampler(mode=session)` works as job mode. Three notification layers: (1) per-cell amber banner on `Session(` cells via `annotateSessionCells()`, (2) injection toast "Session → job mode", (3) kernel `print()` output. Reactive fallback: `detectCellError()` catches "not authorized to run a session" and shows hint linking to Settings. Currently affects 1 notebook (QAOA tutorial, 2 cells).
- **Translation structural sync (Mar 2026)** — Built `sync-translations.py` to mechanically fix the most common translation validation failures without retranslation. Three fix functions: insert missing pip install blocks (EN adds them after translation via `sync-content.py`), restore differing code blocks from EN source, insert missing survey URL sections. Applied 727 fixes across 587 files in a single run across all 19 locales. Also tuned `validate-translation.py` tolerances (line count 5%→15% for all locales, short file threshold <50 lines ±8, extra URLs no longer fail). Updated `translation-prompt.md` with code block preservation rules to prevent recurrence. Results: DE/FR/IT 100%, ES 99%, JA 95%, UK 93%, HE 96% — up from 643 failures to 108 (83% reduction). Remaining failures are ES paragraph inflation (Gemini word salad, 4 files), AR structural issues (15 files, needs retranslation), and dialect frontmatter false positives.
- **Locale build MDX fixes (Mar 2026)** — Fixed 13+6 MDX compilation errors across DE/ES/FR/IT locale builds that were causing the Deploy Locale Sites CI workflow to fail. Five root cause categories: (1) leading space before headings with `{#anchor}` (MDX parses as JS expression instead of heading ID) in 3+4 `kipu-optimization.mdx` files (DE/FR/ES/IT) + IT `quantum-circuit-optimization.mdx`, (2) duplicate heading anchors containing dots (`{#name-1.0}` is invalid JS private field syntax) in 5 files (`qiskit-1.0-installation.mdx` ×3, `qiskit-1.0-features.mdx` ×2), (3) missing `<details><summary>` or `</details>` HTML tags in 4 files (`runtime-options-overview.mdx` ×2, `stern-gerlach-measurements-with-qiskit.mdx` ×2), (4) German typographic closing quote `"` (U+0022) inside JSX `definition="..."` attributes prematurely closing the attribute in 2 DE `DefinitionTooltip` files — fixed with `&quot;`, (5) `$$` math block indentation mismatch (opening at 3 spaces, content at 2) in FR `qiskit-implementation.mdx`. IT-specific: missing `##` before numbered heading in `vqe.mdx`, truncated `</Admonition>` in `qiskit-addons-sqd-get-started.mdx`. Also discovered FR `qiskit-1.0-installation.mdx` contained Spanish content (mislabeled file) — fully re-translated to French via chunked parallel Sonnet agents. Also fixed EN source files (`kipu-optimization.mdx`, `quantum-circuit-optimization.mdx`) to remove leading spaces that caused the translation pattern.

- **Full validation audit (Mar 2026)** — Ran structural validation + lint across all 19 locales. All promoted translations: 100% PASS (2,180 files). Fixed 4 remaining issues: DE/FR/ES `quantum-circuit-optimization.mdx` had leading space before `#` heading (not recognized as heading, `{#anchor}` parsed as JSX) — removed leading space + added translated heading text + anchor. IT `vqe.mdx` had spurious `## 6. Conclusione {#conclusion}` heading that doesn't exist in EN source — removed. ES heading was also untranslated (English text) — translated. Lint: 8 false positives from 2 EN source files with atypical code fence patterns (inline fences on one line, triple-backtick as parameter value inside code block) — no build impact.

### Testing (Feb 2026)
- 180+ comprehensive tests, ~200 Chrome browser tests — 99.5% pass, zero real bugs
- Binder execution: 19/19 passed, 30-40s kernel connect, 45-min stable session
- Test plans: `.claude/BINDER-EXECUTION-TEST-PLAN.md` + `.claude/test-checklist.md`

### Future Ideas
- Auto-discover YouTube mappings (currently 32 static entries)
- LED integration for RasQberry
- Offline AI tutor (Granite 4.0 Nano)
- "Add Cell" scratch pad (full JupyterLab available as alternative)
- **Qiskit Global Summer School content** — Labs from QGSS 2023/2024/2025 repos (`qiskit-community/qgss-2025` etc.) contain high-quality Jupyter lab notebooks. Curated labs could be added as a "Summer School" section. Content is version-pinned to specific Qiskit releases, so would need compatibility review. See [qgss-2025](https://github.com/qiskit-community/qgss-2025) (332 stars, 5 core labs + community labs + lecture notes in separate repo).

### Qiskit Addon Documentation (Phase 1 shipped, hidden)

**Status (April 2026):** Phase 1 implemented and on `main`. Seven addon repos are integrated as git submodules in `upstream-addons/`, `sync-content.py` converts their notebooks to MDX under `docs/qiskit-addons/`, and `sidebar-addons.json` is wired into `sidebars.ts`. The navbar entry is **intentionally hidden** (`claude/document-todos-ideas-UQz3F` chain ended with `Hide Qiskit Addons from navbar and main sidebar`) — addon pages are built and reachable via direct URL (`/qiskit-addons/...`) with their own `qiskitAddonsSidebar`, but nothing links to them from the main menus yet. Phase 2 (mthree, opt-mapper, utils — 12 more notebooks) and Phase 3 (qiskit-community application modules) remain future work.

**Goal:** Add tutorial notebooks from official Qiskit addon repos as a new content section in doQumentation, with live code execution and translations.

**License:** All addon repos are **Apache 2.0** — same as doQumentation's code license. Notebook content (tutorials/how-tos) would be served under the project's CC BY-SA 4.0 content license with proper attribution in NOTICE. Verified April 2026.

#### Repos & Content Inventory (verified April 2026)

| Repo | Notebooks | Path | Content |
|------|-----------|------|---------|
| qiskit-addon-cutting (101 stars) | 4 | `docs/tutorials/` | Gate cutting width/depth, wire cutting, automatic cut finding |
| qiskit-addon-sqd (83 stars) | 2 | `docs/tutorials/` | Chemistry Hamiltonian, fermionic lattice Hamiltonian |
| qiskit-addon-mthree (49 stars) | 5 | `tutorials/` | Measurement mitigation, quantum volume, dynamic BV, VQE |
| qiskit-addon-obp (45 stars) | 1 | `docs/tutorials/` | Getting started with OBP |
| qiskit-addon-mpf (35 stars) | 1 | `docs/tutorials/` | Getting started with MPF |
| qiskit-addon-aqc-tensor (26 stars) | 1 | `docs/tutorials/` | Initial state AQC |
| qiskit-addon-opt-mapper (14 stars) | 5 | `docs/how_tos/` | Migration, problem definition, converters, validation, DOCPLEX |
| qiskit-addon-pna (8 stars) | 1 | `docs/tutorials/` | Noise-mitigating observable generation |
| qiskit-addon-slc (5 stars) | 1 | `docs/tutorials/` | Getting started with SLC |
| qiskit-addon-utils (27 stars) | 2 | `docs/how_tos/` | Circuit slices, device edge coloring |
| **Total** | **23** | | |

**Repos with NO notebooks (skip):** qiskit-addon-sqd-hpc (C++ only), qiskit-addon-dice-solver (API docs only), qiskit-fermions (RST docs only, too new).

**Not in scope yet — future Phase 3 (qiskit-community application modules):** qiskit-machine-learning (13 notebooks), qiskit-nature (11), qiskit-optimization (12), qiskit-finance (12), qiskit-algorithms (11) — collectively ~59 notebooks. These live under `qiskit-community` org; some are no longer IBM-supported. Could be a major future expansion.

#### Approach: Git Submodules

Follow the existing pattern used for `upstream-docs/` (Qiskit-documentation fork):

1. **Add submodules** in `.gitmodules` for each addon repo:
   ```
   [submodule "upstream-addons/qiskit-addon-cutting"]
       path = upstream-addons/qiskit-addon-cutting
       url = https://github.com/Qiskit/qiskit-addon-cutting.git
   [submodule "upstream-addons/qiskit-addon-sqd"]
       path = upstream-addons/qiskit-addon-sqd
       url = https://github.com/Qiskit/qiskit-addon-sqd.git
   ...
   ```
   Direct submodules to Qiskit org repos (no fork needed — unlike the main docs, we don't need to customize content). Use sparse checkout or shallow clones to keep size down.

2. **Extend `sync-content.py`** to handle addon sources:
   - Add a new content type (e.g., `addons`) alongside existing `tutorials`, `guides`, `courses`, `modules`
   - For each addon submodule, locate its notebook path (`docs/tutorials/`, `tutorials/`, or `docs/how_tos/`)
   - Run the same notebook→MDX transform pipeline already used for main content
   - Output to `docs/qiskit-addons/<addon-name>/` (e.g., `docs/qiskit-addons/circuit-cutting/`)
   - Handle dependency injection: each addon needs its own package installed (already handled by the existing `%pip install` injection logic in sync-content.py)
   - Add an addon config map in sync-content.py:
     ```python
     ADDON_SOURCES = {
         "circuit-cutting":    {"submodule": "upstream-addons/qiskit-addon-cutting", "path": "docs/tutorials", "pip": "qiskit-addon-cutting"},
         "sqd":                {"submodule": "upstream-addons/qiskit-addon-sqd",     "path": "docs/tutorials", "pip": "qiskit-addon-sqd"},
         "mthree":             {"submodule": "upstream-addons/qiskit-addon-mthree",  "path": "tutorials",      "pip": "qiskit-addon-mthree"},
         "obp":                {"submodule": "upstream-addons/qiskit-addon-obp",     "path": "docs/tutorials", "pip": "qiskit-addon-obp"},
         "mpf":                {"submodule": "upstream-addons/qiskit-addon-mpf",     "path": "docs/tutorials", "pip": "qiskit-addon-mpf"},
         "aqc-tensor":         {"submodule": "upstream-addons/qiskit-addon-aqc-tensor", "path": "docs/tutorials", "pip": "qiskit-addon-aqc-tensor"},
         "opt-mapper":         {"submodule": "upstream-addons/qiskit-addon-opt-mapper",  "path": "docs/how_tos",   "pip": "qiskit-addon-opt-mapper"},
         "pna":                {"submodule": "upstream-addons/qiskit-addon-pna",     "path": "docs/tutorials", "pip": "qiskit-addon-pna"},
         "slc":                {"submodule": "upstream-addons/qiskit-addon-slc",     "path": "docs/tutorials", "pip": "qiskit-addon-slc"},
         "utils":              {"submodule": "upstream-addons/qiskit-addon-utils",   "path": "docs/how_tos",   "pip": "qiskit-addon-utils"},
     }
     ```

3. **Sidebar generation:**
   - Generate `sidebar-addons.json` (same pattern as `sidebar-guides.json`)
   - Add to `sidebars.ts` as a new top-level category: "Qiskit Addons"
   - Each addon becomes a subcategory with its tutorials listed inside

4. **Navbar integration** in `docusaurus.config.ts`:
   ```typescript
   {
     to: '/qiskit-addons',
     label: 'Qiskit Addons',
     position: 'left',
   },
   ```
   After "Modules" (last content item): Tutorials > Guides > Courses > Modules > Qiskit Addons.

5. **NOTICE file update** — add attribution:
   ```
   This project includes tutorial content from Qiskit Addon repositories:
     https://github.com/Qiskit/qiskit-addon-cutting (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-sqd (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-mthree (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-obp (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-mpf (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-aqc-tensor (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-opt-mapper (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-pna (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-slc (Apache 2.0)
     https://github.com/Qiskit/qiskit-addon-utils (Apache 2.0)
   ```

6. **Binder/Docker environment:**
   - Most addon packages are light; some like `pyscf` for sqd chemistry are heavy — handle via injected `%pip install` cells, not pre-install
   - Docker: Add commonly used addons to `Dockerfile.jupyter` requirements
   - The existing dependency injection logic in sync-content.py already handles `%pip install` cells

7. **CI/CD:**
   - Update `deploy.yml` and `deploy-locales.yml`: `submodules: recursive` (already uses `submodules: true`)
   - Add `--addons` flag to sync-content.py invocation in CI
   - Addon content enters translation pipeline automatically once sync is working (Phase 2)

8. **Qiskit Addons index page:**
   - Create `docs/qiskit-addons/index.mdx` with an overview of all addons, links to each section, and links to the upstream API docs (hosted on qiskit.github.io)
   - Could reuse the Card/CardGroup components already used on the homepage

#### Implementation Phases

- **Phase 1:** ✅ DONE — 7 core addons with `docs/tutorials/` (cutting, sqd, obp, mpf, aqc-tensor, pna, slc) = 11 notebooks. Submodules + sync-content.py extension + `sidebar-addons.json` all merged. UI entry hidden pending launch decision.
- **Phase 2:** Add mthree (5 tutorials), opt-mapper (5 how-tos), utils (2 how-tos) = 12 more notebooks. Total: 23 notebooks.
- **Phase 3 (future):** qiskit-community application modules (ML, nature, optimization, finance, algorithms) = ~59 notebooks. Separate submodules to `qiskit-community` org repos. Some may need Qiskit version compatibility fixes.

---

## User Test Session Feedback (April 14, 2026)

Live test session with multiple users. Overall reception very positive — "great experience, very fast, saved lots of hours, all functionality working as expected."

### Resolved

1. **~~Dark mode: black text in thebelab cells after "Run All"~~** — Fixed: added comprehensive dark mode CSS for CodeMirror 5 (background, text, cursor, selection, gutters, syntax highlighting tokens, output area) in `src/css/custom.css`.

2. **~~Add "Clear all data" option~~** — Fixed: "Reset Everything" button on Settings page with confirmation dialog. Clears all progress, bookmarks, preferences, onboarding, recent history, sidebar state, Binder session, and credentials.

3. **~~Settings page hard to find~~** — Fixed: responsive navbar — shows "Settings" text + gear icon on wide screens (≥1200px), icon-only on narrow screens.

4. **~~Japanese: nakaguro (・) rule~~** — Fixed: added to `translation/translation-prompt.md` JA locale instructions.

5. **~~Per-cell injection annotations~~** — Fixed: `annotateInjectedCells()` in `ExecutableCode/index.tsx` scans cell content and adds compact badges showing what doQumentation intercepts (e.g. "⚙ QiskitRuntimeService intercepted → AerSimulator", "⚙ least_busy() → AerSimulator", "⚙ Using saved IBM Quantum credentials"). Complements existing skip-hint/session-hint banners without duplicating them.

6. **~~IBM Quantum setup instructions unclear~~** — Fixed: compact 4-step list matching current IBM Quantum Platform UI. Register → Create instance (via Instances page) → Copy CRN (home page, copy icon) → Create API key (home page, "Create +"). Previous instructions incorrectly referenced a profile dropdown for API token.

### Open (needs investigation)

7. **API key error on real hardware (copy-paste)** — User saved valid IBM Quantum API token via copy-paste, got `InvalidAccountError: Unable to retrieve instances`. Token confirmed not expired. Possible whitespace/newline from copy-paste or save_account protection logic interfering.

8. **Kernel session interrupted on navigation** — Inherent to thebelab architecture (per-page kernel bootstrap). Cross-page persistence would require major architectural changes. Documented as known behavior.

## User Test Session Feedback (April 17–18, 2026)

Second round of feedback from multiple users. 12 items — all resolved.

### Resolved

1. **~~Default API key TTL → 1 day~~** — Changed `DEFAULT_TTL_DAYS` from 7 to 1 in `jupyter.ts`.

2. **~~Merge custom Jupyter server fields~~** — Removed separate "Custom Jupyter Server" `<details>` section from Advanced Settings. Added "Custom Server" as a radio button in the backend selector with inline URL/Token fields shown when selected.

3. **~~Add "Clear CE config" button~~** — CE Quick Config (with Clear button) now always visible, not just when CE is detected.

4. **~~Clarify "Clear All Preferences" vs "Reset Everything"~~** — Renamed to "Clear Learning Data" (progress, bookmarks, display settings only). "Reset Everything" unchanged (clears all data including credentials).

5. **~~Merge Compute Backend + CE sections~~** — Removed duplicate "Compute Backend" section. Current backend status always visible at top. CE config moved to Advanced Settings. Backend selector always shows all options.

6. **~~Compute Backend section hidden~~** — Fixed: backend status banner and selector always rendered at top of Settings page. CE and Custom Server always appear as options even when not configured.

7. **~~Reuse CE backend info from Settings~~** — Admin PodMonitor already reads from Settings localStorage. Added visible note: "CE credentials are read from the Settings page."

8. **~~Show Binder cache warming URLs on admin~~** — Added "Binder Federation Status" section with 3 clickable links (2i2c, BIDS, GESIS) in admin Infrastructure section.

9. **~~Improve CE setup instructions~~** — Expanded with direct IBM Cloud console link, sizing guidance (2 vCPU/4 GB → 8 vCPU/16 GB), CORS_ORIGIN example, link to admin sizing table.

10. **~~Run button not appearing after connection~~** — Added retry logic: `setupCellFeedback()` retries up to 3× at 2s intervals if cells exist but no run buttons found (thebelab render lag).

11. **~~Link to original IBM Quantum page~~** — `getOriginalPageUrl()` in `EditThisPage/index.tsx` computes IBM URL from page path. Renders "View original" link next to "Edit this page" and bookmark. Maps guides → docs.quantum.ibm.com, tutorials → learning.quantum.ibm.com, courses → learning.quantum.ibm.com/course, addons → qiskit.github.io.

12. **~~Hidden workshop notebooks directory~~** — `docs/workshop/` with `workshopSidebar` in `sidebars.ts`. Accessible at `/workshop/` via direct URL, not in navigation. `noindex` meta tag. Instructors add notebooks via PRs.

## Additional Changes (April 18, 2026)

Follow-up fixes from continued testing and feedback:

- **CE sizing corrected** — 1 vCPU / 2 GB for single user (was 2 vCPU / 4 GB)
- **"IBM Cloud Code Engine"** — Official product name used consistently across Settings + admin pages
- **Backend selector order fixed** — Always: Binder → IBM Cloud Code Engine → Custom Server (was dynamic, CE jumped around when configured)
- **Bookmark tooltip improved** — "Save to your bookmarks list on the homepage" (users didn't know what bookmark did)
- **"View original" link renamed** — "View original on IBM Quantum Platform"
- **Execution mode reordered** — No automatic injection first, then AerSimulator (default), FakeBackend, IBM Quantum
- **Admin page: no link from Settings** — Admin page kept undiscoverable for regular users
- **CE + Custom Server consolidated** — Single URL/Token section switches between CE and Custom based on radio selection (was two near-identical sections stacked)
- **Admin PodMonitor reads single CE URL** — Falls back to Settings CE URL when no workshop pool configured
- **Workshop notebooks** — `workshop-notebooks/` source dir + `sync-content.py` converts `.ipynb` → `docs/workshop/*.mdx`. 4 notebooks (01–04 prefix): Qiskit 101, Hands-on Intro, Hello World Patterns, DiVincenzo Criteria Lab. 2 solution notebooks (01, 04) with filled-in exercises. Category page at `/workshop/` uses `generated-index` (clickable heading = card listing, no duplicate sidebar entry). Solution/hidden notebooks get `unlisted: true` + `sidebar_class_name: hidden` — excluded from cards, search, and sidebar but accessible via direct URL. Community banner: "not part of the official IBM Quantum documentation". Auto-extracted descriptions for cards. Source filename shown in OpenInLabBanner. External `<img>` tags get JSX `onError` fallback. Generated files gitignored; source `.ipynb` tracked.
- **Cell execution labels visible** — "► Running…", "✓ Done", "✗ Error" now render as visible `::before` text above cells (was clipped `::after` icons). Run All clears all previous labels for clean slate.
- **"Manage Your Data" section restructured** — Replaced flat/confusing layout with grouped categories: Progress (per-category: Tutorials→Guides→Courses→Modules + Clear All), Bookmarks (always visible), Display & UI, Sessions & Credentials (Binder, IBM Quantum, IBM Cloud Code Engine). Privacy note added: "All data is stored locally in your browser. Nothing is sent to our servers." Removed confusing "Clear Learning Data" button.
- **Placeholder credential detection** — `annotatePlaceholderCells()` detects cells with `YOUR_API_KEY`, `deleteThisAndPaste`, etc. Shows red hint banner offering to inject saved credentials or link to Settings.
- **SPA navigation fix** — Bootstrap now polls up to 10 frames waiting for `<pre data-executable>` elements before calling thebelab (was single `requestAnimationFrame`, too early after client-side navigation).
- **Multi-line inline math fix** — `escape_mdx_outside_code()` regex now protects `$...$` spanning multiple lines (was single-line only, corrupting `\frac{}{}` and `\begin{pmatrix}` in workshop notebooks).
- **UI translations 100%** — 210 new keys translated across all 17 non-dialect locales (DE, ES, FR, IT, UK, JA, PT, TL, AR, HE, TH, MS, ID, KO, PL, RO, CS). Coverage: 308/484 → 518+/518. Covers Settings, ExecutableCode, Features, Qamposer, feedback widgets, "View original" link, workshop banner.

---

## Related Resources

- **RasQberry:** https://github.com/JanLahmann/RasQberry-Two
- **Content source (fork):** https://github.com/JanLahmann/Qiskit-documentation
- **IBM Quantum:** https://ibm.com/quantum
- **IBM Quantum Platform:** https://quantum.cloud.ibm.com
- **Docusaurus:** https://docusaurus.io

---

*Last updated: April 19, 2026 (workshop solutions, unlisted pages, SPA fix, math fix, full UI i18n)*
