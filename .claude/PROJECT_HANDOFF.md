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

**Content:** 42 Tutorials, 171 Guides, 154 Course pages, 14 Modules (~380 pages total).

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

### Code Execution (`src/components/ExecutableCode/index.tsx`)
- `ExecutableCode` wraps Python code blocks with Run/Back toggle. thebelab bootstraps once per page, shared kernel.
- Environment auto-detection: GitHub Pages → Binder, localhost/Docker → local Jupyter, custom → user-configured
- Cell feedback: amber (running), green (done), red (error) left borders. Error detection for `ModuleNotFoundError` (with clickable Install button), `NameError`, tracebacks. All error types include a "Report this error" link that opens a pre-filled GitHub issue with error text, cell code, page path, environment, and simulator mode. **Output selectors**: thebelab 0.4.0 uses JupyterLab's `OutputArea` widget (`.jp-OutputArea` class), not `.thebelab-output` — all output queries use `OUTPUT_SELECTOR` constant. **Pip install**: uses `--user` flag (Binder's `/opt/conda/` is root-owned), then `site.addsitedir()` (conda disables user site-packages), `importlib.invalidate_caches()`, and `sys.modules` cleanup before auto-rerunning the cell.
- Cell completion uses `kernel.statusChanged` signal (not thebelab events) with 1500ms idle debounce (`IDLE_DEBOUNCE_MS`) to handle cells that cycle busy→idle→busy (matplotlib rendering, optimizers, async jobs). After debounce, `waitForOutputStable()` uses a MutationObserver on the output container to ensure DOM rendering is complete before marking green/red. Both single-cell and Run All paths use this two-stage wait.
- Execution mode indicator badge (links to Settings → Simulator Mode) + injection toast.
- **OpenInLabBanner buttons**: "Open in: JupyterLab | Colab" — two buttons across all environments. JupyterLab (filled/primary, session-managed via `ensureBinderSession()` on GitHub Pages, direct link on CE/local), Colab (outlined, always available). Descriptive tooltips on hover. Uses `getColabUrl()`, `getLabUrl()`/`getBinderLabUrl()` from `jupyter.ts`. **Only shown on pages with executable code cells** — `sync-content.py` skips injection for code-cell-free notebooks; 1,634 i18n pages similarly cleaned up.
- **Binder tab reuse**: "Open in Lab" uses named window target `binder-lab` to reuse the same tab
- **Run All**: "Run All" button (visible when kernel is ready) executes all thebelab cells sequentially in DOM order. Auto-skips `save_account()` cells when credentials or simulator mode are active (cells with `.thebelab-cell__skip-hint`). Uses `waitForKernelIdle()` helper (subscribes to `kernel.statusChanged` signal) to wait for each cell to complete before starting the next. During execution: "Pause (N/M)" pauses after current cell finishes, "Stop" aborts. When paused: "Continue (N/M)" resumes, "Stop" aborts. Pause uses a promise-based gate (`waitForRunAllResume`) — the loop awaits until the user clicks Continue. Also aborts on Back, Restart, Clear Session, or page navigation.
- **Kernel restart**: "Restart Kernel" button (visible when kernel is ready) calls `kernel.restart()`, clears all cell outputs/feedback, re-injects credentials/simulator setup. Same Binder session, fresh kernel state.
- **Clear Session**: "Clear Session" button (GitHub Pages + Code Engine, visible when kernel is ready) clears `sessionStorage` session and resets to static view. Next Run starts a fresh server.
- **Binder startup cancel + slow detection**: Cancel button replaces "Connecting..." during Binder startup — cancels the EventSource immediately. Per-phase timeout thresholds (connecting 1m, waiting 3m, fetching/pushing/launching 5m, building 12m) trigger a red warning banner suggesting alternative backends. "Clear Binder Session" also available on Settings page.
- **Interception transparency**: All kernel modifications print `[doQumentation]` messages (simulator intercepts, credential injection, warning suppression, pip install cells)
- **save_account() protection**: Dynamic blue "Skip this cell" banners (runtime-injected via `annotateSaveAccountCells()`, translated via `code.json`) when credentials/simulator active, prevents overwriting injected values. **Run All auto-skips** these cells — `handleRunAll` filters out any cell with `.thebelab-cell__skip-hint` before execution.
- **Full i18n**: All toolbar buttons, status messages, legend, conflict banner, settings link, and Binder hint wrapped with `translate()`/`<Translate>`

### IBM Quantum Integration (`src/config/jupyter.ts`)
- **Credentials** — API token + CRN with adjustable auto-expiry (1/3/7 days). Auto-injected at kernel start. Embedded execution only. Shared across locale subdomains via cookies.
- **Simulator mode** — Monkey-patches `QiskitRuntimeService` with `_DQ_MockService` (AerSimulator or FakeBackend). Fake backend discovery cached, 55-backend fallback list.
- **Conflict resolution** — Radio buttons when both configured; defaults to simulator.
- **Plan type** — Open (default) / Pay-as-you-go / Premium selector on Settings page (`doqumentation_ibm_plan` key). When set to Open, `injectKernelSetup()` monkey-patches `qiskit_ibm_runtime.Session` with `_DQ_JobModeSession` — a passthrough context manager that returns `backend` directly, converting `Sampler(mode=session)` to effective job mode. Per-cell amber banners on `Session(` cells via `annotateSessionCells()`. Toast includes "Session → job mode". Reactive error hint if the Session error fires without the patch (links to Settings).
- **Shared Binder session** — `ensureBinderSession()` in `jupyter.ts` manages a single Binder session shared by both "Open in Binder JupyterLab" and thebelab code execution. First interaction (either button): calls Binder build API (`EventSource` on `/build/gh/...`), captures server URL + token on `"ready"` event, stores in `sessionStorage` (`dq-binder-session`). Subsequent interactions (within 8 min): reuses stored session instantly. Both use the `doQumentation/notebooks` branch. Thebelab connects via `serverSettings` (baseUrl + wsUrl + token) instead of `binderOptions`. Both `OpenInLabBanner` and `ExecutableCode` toolbar show live Binder build phases (fetching, building, launching) with timing hints ("1–2 min on first run"). Session touched on kernel busy/idle to stay alive during active code execution. Session expires after 8 min idle or when browser closes. Cross-locale sessions are domain-scoped by design (security). `openBinderLab()` opens a blank tab synchronously on click (avoids popup blockers), then navigates to JupyterLab when the session is ready; on failure, the blank tab is auto-closed.
- **Colab URLs** — `getColabUrl(notebookPath, locale?)` generates locale-aware Colab links via the `/github/` scheme (Colab's `/url/` scheme blocks non-GitHub domains due to SSRF allowlist). All notebooks are processed copies with pip install cells + commented-out `save_account()` template injected by `sync-content.py`. EN: points to `doQumentation/blob/notebooks/` branch (pushed by `deploy.yml` CI step). Translated: points to satellite repos (`doqumentation-{locale}/blob/gh-pages/notebooks/`). Unified path mapping via `mapBinderNotebookPath()`: bare filenames (no `/`) get `tutorials/` prefix. Both `OpenInLabBanner` and `ExecutableCode` pass `currentLocale` from Docusaurus context.

### IBM Cloud Code Engine (`Dockerfile.jupyter` → `jupyter-codeengine` target)
- **What it is** — Serverless Jupyter container on user's IBM Cloud account. Drop-in Binder replacement with ~1s cold start (vs Binder's 10–25 min). Free tier covers ~14 hrs/month.
- **Architecture** — Single-port container (8080): nginx reverse proxy + Jupyter server (8888) + SSE build server (9091), managed by supervisord. SSE server (`sse-build-server.py`) mimics mybinder.org's `/build/` SSE protocol so `ensureBinderSession()` works unchanged — only 3 phases (connecting/launching/ready) instead of 7+. SSE server also handles `/health` endpoint (checks Jupyter readiness with token, no external auth needed). Uses port 9091 (not 9090 — Jupyter extensions bind that) and `allow_reuse_address`. Public URL in SSE ready event derived from `Host` header + `X-Forwarded-Proto`. Cold start ~12s (container start + Jupyter init); health returns 503 until Jupyter is ready, then 200.
- **Deployed app** — `ce-doqumentation-01.27boe8ie8nv4.eu-de.codeengine.appdomain.cloud` (eu-de region), project `ce-doqumentation-01`. Min scale 0 (scales to zero when idle), max scale 1, 4G memory, 1 CPU. Token must be 32+ chars.
- **Container image** — `ghcr.io/janlahmann/doqumentation-codeengine:latest`, built by `.github/workflows/codeengine-image.yml` using `Dockerfile.jupyter` with `--target jupyter-codeengine`. Base: `quay.io/jupyter/base-notebook:python-3.12` (shared `jupyter-base` stage). Security pins (`jupyter-requirements-security.txt`) installed with `--upgrade` in `jupyter-base` so both Docker targets inherit them. `linux/amd64` only. Trivy security scan (fails on HIGH/CRITICAL, `.trivyignore` for unfixable bundled deps). **Auto-deploy**: after image push + scan, workflow installs IBM Cloud CLI and runs `ibmcloud ce app update` to deploy the new image to CE (requires `IBM_CLOUD_API_KEY` repo secret).
- **Security** — Token auth (min 32 chars), CORS origin validation (`CORS_ORIGIN` env var, default `https://doqumentation.org`), XSRF disabled (thebelab 0.4.0 limitation), rate limiting on nginx endpoints (except `/lab` — JupyterLab loads dozens of JS/CSS chunks on first view, token auth is sufficient), security headers (HSTS, CSP, nosniff).
- **User flow** — Settings page (`/jupyter-settings#code-engine`) → enter CE URL + token → Save. Environment detected as `'code-engine'` in `detectJupyterConfig()` (priority: Custom > CE > Binder). Credentials stored with same TTL as IBM Quantum (1/3/7 days). All frontend components (ExecutableCode, OpenInLabBanner) CE-aware with fast phase labels.
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
- `deploy-locales.yml` — Matrix build per locale: sync content → populate fallbacks → generate translated notebooks → build → push to satellite repos. Consolidation job merges all locale notebooks into `notebooks` branch subdirectories.
- `docker.yml` — Multi-arch Docker → ghcr.io (EN only via `--locale en`). Builds `Dockerfile.jupyter` with `--target jupyter-local`. **Push trigger disabled** — only `workflow_dispatch` (re-enable `push: branches: [main]` when needed).
- `sync-deps.yml` — Weekly auto-PR for Jupyter dependencies. Runs `scripts/sync-deps.py` which fetches from [JanLahmann/Qiskit-documentation/scripts/nb-tester/requirements.txt](https://github.com/JanLahmann/Qiskit-documentation/blob/main/scripts/nb-tester/requirements.txt) and applies transformation rules: drops `sys.platform` markers (Linux-only containers), splits packages by architecture (amd64-only packages like `gem-suite`, `qiskit-ibm-transpiler[ai-local-mode]`, and `qiskit-addon-aqc-tensor[quimb-jax]` go to `jupyter-requirements-amd64.txt`), and adds `EXTRA_CROSS_PLATFORM` packages not in upstream (`pylatexenc` for LaTeX rendering, `pandas` for data analysis). Both `jupyter-requirements.txt` and `jupyter-requirements-amd64.txt` are auto-generated and marked with "DO NOT EDIT MANUALLY" warnings. `jupyter-requirements-security.txt` is manually maintained — it pins minimum versions for transitive dependencies with known CVEs (used only by `Dockerfile.codeengine`, where Trivy CI enforces no HIGH/CRITICAL vulns).
- `check-translations.yml` — Daily translation freshness check + STATUS.md update. Requires `permissions: contents: write, issues: write`.
- `binder.yml` — Daily cache warming for 3 Binder federation members (2i2c, BIDS, GESIS) + on every push to `notebooks` branch + manual `workflow_dispatch`.

### Other
- **Homepage**: Beta notice banner (session-scoped, dismissible), hero with stats bar, Getting Started cards (category-tagged), simulator callout, code execution section. No sidebar or TOC (`hide_table_of_contents: true` in `docs/index.mdx`).
- **Sidebar**: Home link at top, then Tutorials/Guides/Courses/Modules categories (autogenerated from `sidebar-*.json`). API Reference + Settings in navbar only. **Single unified indicator per item** — 5 states: pure MDX unvisited (nothing), pure MDX visited (`✓` gray), notebook unvisited (`</>` gray, non-clickable), notebook visited (`</>` blue, clickable), notebook executed (`</>` green, clickable). Clicking a clickable indicator clears visited/executed status. Notebook detection via `customProps.notebook` in sidebar JSON (uses `<OpenInLabBanner>` presence, not `notebook_path` frontmatter). **Category badges left of twistie**: badge DOM-injected via `document.createElement('span')` with `role="button"`. Two injection strategies depending on category type: href categories (Tutorials, Guides) have a separate `.menu__caret` button — badge inserted before it as a sibling in the collapsible flex flow. Non-href categories (Courses, Modules, subcategories) have the caret as `::after` pseudo-element on the link — badge appended inside the link, with CSS `display: flex` on `.menu__link--sublist-caret:has(.dq-category-badge)` to position badge between text and `::after` caret. Uses `useLayoutEffect` (no deps) to re-inject after every render — necessary because collapse-restore (`header.click()`) triggers React re-renders that can replace DOM nodes. Badge creation is a separate `useEffect([allHrefs])`. Link items have `padding-inline-end: 2.25rem` for indicator space. Long titles truncate with `text-overflow: ellipsis`.
- **Features page**: `/features` — 31 cards across 6 sections (Content Library, Live Code Execution, IBM Quantum Integration, Learning & Progress, Multi-Language, Search/UI/Deployment)
- **Search**: `@easyops-cn/docusaurus-search-local` — client-side, hashed index
- **Settings page** (`/jupyter-settings`): IBM credentials, simulator mode, display prefs, progress, bookmarks, custom server. Full-width card (`max-width: none` — outer `container` handles width).
- **Navbar**: Always dark (`#161616`). Right-side icons: locale (globe), settings (gear), dark mode, GitHub (octocat) — all icon-only on desktop (text hidden via `font-size: 0` + `::before` SVG). CSS `order` positions auto-placed dark mode toggle and search bar. Mobile sidebar header swizzled (`Navbar/MobileSidebar/Header`) with matching icon row. Locale dropdown filtered by `customFields.visibleLocales` in `docusaurus.config.ts` (currently `['en', 'de', 'es']`) — all 23 locales remain built/deployed, only the UI selector is filtered. Current locale always shown so users on hidden locales can navigate away. Both desktop (swizzled `LocaleDropdownNavbarItem`) and mobile (`MobileLocaleSelector`) respect this setting. Has "Deutsche Dialekte" separator before dialect locales (CSS `li:has()` on desktop, React separator `<li>` on mobile) — only renders when dialects are in the visible set.
- **Footer**: Three columns — doQumentation (Features, Settings, GitHub), RasQberry (site + GitHub), IBM Quantum & Qiskit (docs, GitHub, Slack). IBM disclaimer in copyright.
- **Styling**: Carbon Design-inspired (IBM Plex, `#0f62fe`).
- **SEO & social sharing**: Open Graph + Twitter Card meta tags, JSON-LD structured data (Organization, WebPage, SoftwareApplication), robots meta for AI indexing, preconnect hints for fonts/CDN. Social card image (`static/img/rasqberry-social-card.png`, 1200x630).
- **Keyboard accessibility**: `focus-visible` outlines on all interactive elements; light blue variant on dark navbar for contrast.

---

## Project Structure

```
doQumentation/
├── .github/workflows/          # deploy, deploy-locales, docker, sync-deps, check-translations, binder
├── upstream-docs/              # Git submodule → JanLahmann/Qiskit-documentation (CC BY-SA 4.0)
├── binder/                     # Jupyter requirements (cross-platform + amd64-only)
├── docs/                       # Content (gitignored except index.mdx)
├── notebooks/                  # Original .ipynb for JupyterLab (generated)
├── src/
│   ├── clientModules/          # pageTracker, displayPrefs, onboarding
│   ├── components/             # ExecutableCode, ResumeCard, RecentPages, BookmarksList, OpenInLabBanner, BetaNotice, CourseComponents, GuideComponents
│   ├── config/                 # storage.ts (cookie+localStorage), jupyter.ts (env detection, credentials), preferences.ts (user prefs)
│   ├── css/custom.css          # All styling
│   ├── pages/                  # features.tsx, jupyter-settings.tsx
│   └── theme/                  # Swizzled: Root (global BetaNotice), CodeBlock, DocItem/Footer, EditThisPage, DocSidebarItem/{Category,Link}, Navbar/MobileSidebar/Header, NavbarItem/LocaleDropdownNavbarItem, MDXComponents
├── i18n/                       # Translations: de/es/fr (385 each — 100% complete), uk (56), ja (56), it/pt/tl (48 each), he (47), ar (44), ksh (46), nds (43), gsw (42), sax (39), bln (36), aut (34), swg/bad/bar (31 each)
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

**Generated (gitignored):** `docs/tutorials/`, `docs/guides/`, `docs/learning/`, `notebooks/`, `static/docs/`, `static/learning/images/`, `sidebar-*.json`

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
| UK | [uk.doqumentation.org](https://uk.doqumentation.org) | 56 + UI | Live |
| JA | [ja.doqumentation.org](https://ja.doqumentation.org) | 60 + UI | Live |
| IT | [it.doqumentation.org](https://it.doqumentation.org) | 48 + UI | Live |
| PT | [pt.doqumentation.org](https://pt.doqumentation.org) | 48 + UI | Live |
| TL | [tl.doqumentation.org](https://tl.doqumentation.org) | 48 + UI | Live |
| AR | [ar.doqumentation.org](https://ar.doqumentation.org) | 44 + UI | Live (RTL) |
| HE | [he.doqumentation.org](https://he.doqumentation.org) | 47 + UI | Live (RTL) |
| KSH | [ksh.doqumentation.org](https://ksh.doqumentation.org) | 46 + UI | Live |
| NDS | [nds.doqumentation.org](https://nds.doqumentation.org) | 43 + UI | Live |
| GSW | [gsw.doqumentation.org](https://gsw.doqumentation.org) | 42 + UI | Live |
| SAX | [sax.doqumentation.org](https://sax.doqumentation.org) | 39 + UI | Live |
| BLN | [bln.doqumentation.org](https://bln.doqumentation.org) | 36 + UI | Live |
| AUT | [aut.doqumentation.org](https://aut.doqumentation.org) | 34 + UI | Live |
| SWG | [swg.doqumentation.org](https://swg.doqumentation.org) | 31 + UI | Live |
| BAD | [bad.doqumentation.org](https://bad.doqumentation.org) | 31 + UI | Live |
| BAR | [bar.doqumentation.org](https://bar.doqumentation.org) | 31 + UI | Live |

- **Config**: `docusaurus.config.ts` — `locales: ['en', 'de', 'es', 'uk', 'fr', 'it', 'pt', 'ja', 'tl', 'ar', 'he', 'swg', 'bad', 'bar', 'ksh', 'nds', 'gsw', 'sax', 'bln', 'aut', 'ms', 'id', 'th']`, per-locale `url` in `localeConfigs`, `DQ_LOCALE_URL` env var. Built-in `LocaleDropdown` handles cross-domain links natively. hreflang tags auto-generated.
- **RTL support**: AR and HE have `direction: 'rtl'` in `localeConfigs`. CSS uses logical properties (`border-inline-start`, `margin-inline-start`, `inset-inline-end`) throughout — direction-agnostic for both LTR and RTL. Noto Sans Arabic/Hebrew fonts loaded via Google Fonts. `[dir="rtl"]` overrides in `custom.css`.
- **CI**: `deploy.yml` builds EN only (`--locale en`). `deploy-locales.yml` matrix builds all 22 locales separately, pushes to satellite repos via SSH deploy keys (`DEPLOY_KEY_{DE,ES,UK,FR,IT,PT,JA,TL,AR,HE,SWG,BAD,BAR,KSH,NDS,GSW,SAX,BLN,AUT,MS,ID,TH}`).
- **Satellite repos**: `JanLahmann/doQumentation-{de,es,uk,fr,it,pt,ja,tl,ar,he}` + `doqumentation-{swg,bad,bar,ksh,nds,gsw,sax,bln,aut,ms,id,th}` — each has `main` branch (README + LICENSE + LICENSE-DOCS + NOTICE) and `gh-pages` branch (build output). GitHub Pages + custom domains configured. Setup script: `.claude/scripts/setup-satellite-repo.sh`.
- **German dialects**: 9 dialect locales (SWG, BAD, BAR, KSH, NDS, GSW, SAX, BLN, AUT) with "Deutsche Dialekte" separator in locale dropdown. Desktop: CSS `li:has(> a[href*="swg.doqumentation.org"])::before` targets first dialect. Mobile: `dialectLocales` Set in `Navbar/MobileSidebar/Header` renders separator `<li>`. To add a new dialect: add to `dialectLocales` Set + `locales`/`localeConfigs` in config + CI matrix + `BANNER_TEMPLATES` + `locale_label` in `translation/scripts/translate-content.py`.
- **Full UI i18n** (`code.json`): All user-visible strings across React pages and components use Docusaurus `<Translate>` and `translate()` APIs. This covers Settings page (~90 keys), Features page (~39 keys), ExecutableCode toolbar (Run/Back/Lab/Colab buttons, status messages, legend, conflict banner), EditThisPage bookmarks, BookmarksList, DocSidebarItem/Link, BetaNotice, and MobileSidebar header. Total: ~308 keys per locale (~92 theme + ~216 custom). When adding a new language, `npm run write-translations -- --locale {XX}` auto-generates entries with English defaults; translate all `message` values. Technical terms (Qiskit, Binder, AerSimulator, etc.) and code snippets stay in English. Placeholders like `{binder}`, `{saveAccount}`, `{url}`, `{pipCode}`, `{issueLink}`, `{mode}` must be preserved exactly.
- **Fallback system**: `populate-locale` fills untranslated pages with English + "not yet translated" banner. ~387 fallbacks per locale. 22 banner templates defined in `translation/scripts/translate-content.py`.
- **Translation freshness**: Genuine translations embed `{/* doqumentation-source-hash: XXXX */}` (SHA-256 first 8 chars of EN source). Daily CI workflow (`check-translations.yml`) compares embedded hashes against current EN files. CRITICAL = missing imports/components (features broken); STALE = content changed. After propagating EN changes, run `check-translation-freshness.py --stamp` to update hashes. **Key rule**: Any change to EN source files (imports, components, content) must be manually propagated to genuine translations — `populate-locale` only refreshes fallbacks, not genuine translations.
- **Draft pipeline**: Translations go through `translation/drafts/{locale}/{path}` → validate → fix → promote to `i18n/`. Scripts: `validate-translation.py` (12 structural checks, `--dir`/`--section`/`--report`/`--record` flags), `fix-heading-anchors.py` (`--dir` flag), `promote-drafts.py` (`--locale`/`--section`/`--file`/`--force`/`--keep` flags). Status tracked in `translation/status.json` (hybrid: grows as files are validated/promoted, with status, validation result, source hash, dates, failures). Direct-to-i18n still works (all scripts default to `i18n/` without `--dir`).
- **Status dashboard**: `translation-status.py` — combines on-the-fly file scanning with `status.json` data. Modes: overview (all locales), `--locale XX` (per-section detail), `--backlog` (prioritized untranslated files), `--validate` (run + record structural checks), `--markdown`/`--json` (output formats), `--update-contributing` (auto-update table in CONTRIBUTING-TRANSLATIONS.md between marker comments), `--write-status` (generate `translation/STATUS.md` with full report), `--all` (include dialect locales). Daily CI auto-updates `translation/STATUS.md`.
- **Translation**: See [`CONTRIBUTING-TRANSLATIONS.md`](../CONTRIBUTING-TRANSLATIONS.md) for contributor guide (any tool/LLM). For Claude Code automation: `translation/translation-prompt.md` (Sonnet, 3 parallel agents, 1 file or chunk each). One-liner: `Read translation/translation-prompt.md. Translate all untranslated pages to French (fr).`
- **Translation validation**: Three-step QA. Step 1: `validate-translation.py` — 12 binary PASS/FAIL structural checks (line count, code blocks byte-identical, LaTeX, headings, anchors, image paths, frontmatter, JSX tags, URLs, paragraph inflation). Tuned thresholds: paragraph inflation (`LOCALE_WORD_RATIO`: de=3.0x, fr/es/it/pt=2.5x, default=2.2x; `MIN_TR_WORDS_FOR_INFLATION`=250; `MIN_WORDS_FOR_INFLATION`=20; >15% para count divergence skipped), line count (20% for FR/ES/IT/PT/DE, absolute ±6 for files <30 lines), LaTeX inline ±30, LaTeX display ±4. Supports `--dir translation/drafts` for staging, `--section` for filtering, `--report` for markdown feedback, `--record` for writing results to `status.json`. Step 2: `lint-translation.py` — MDX syntax lint for build-breaking errors (duplicate heading anchors, garbled XML tags, heading markers mid-line, invalid anchor chars, unmatched code fences, missing imports). Both have `--record` for status.json. Step 3: linguistic review (register, word salad, verbosity, accuracy) — tracked via `review-translations.py` (`--record-review`). Review prompt: `translation/review-prompt.md`.
- **Review orchestration**: `review-translations.py` manages systematic review across sessions. `--auto-check` runs structural validation + lint for all locales in bulk. `--progress` shows per-locale dashboard (struct/lint/review counts). `--next-chunk [--size N]` returns prioritized batch of files needing linguistic review. `--record-review` persists verdicts (PASS/MINOR_ISSUES/FAIL/SKIPPED) to status.json. Baseline: 885 files, 456 structural PASS, 440 ready for review, AR auto-skipped (needs re-translation).
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
- **Translation expansion** — **DE/ES/FR are 100% complete (385/385 each, zero fallbacks)**. Remaining: UK at 56/387, JA at 56/387, IT/PT/TL at 48, HE at 47, AR at 44 (needs re-translation). German dialects: KSH (46), NDS (43), GSW (42), SAX (39), BLN (36), AUT (34). New locales: MS, ID, TH (all at 0/387 — English fallbacks only). **6 translation branches still to merge**: AR (342 files), UK (339), JA (331), IT (301), TL (169), PT (167) — each single-locale, no overlaps, ready for squash merge after validation. Run `python translation/scripts/translation-status.py` for current counts, or see `translation/STATUS.md`.
- **Upstream sync strategy** — Plan how to pull upstream changes from [Qiskit/documentation](https://github.com/Qiskit/documentation) weekly. Currently `sync-content.py` clones from the fork (`JanLahmann/Qiskit-documentation`), which must be manually synced with upstream. Need: automated fork sync (GitHub Actions or scheduled script), handling of merge conflicts in modified files (`hello-world.ipynb`, `_toc.json`), freshness checks for translated content after EN changes, and a rollback strategy if upstream breaks the build.
- **Translation structural sync script** — When English source changes (code blocks, imports, frontmatter), translated files go stale. Code blocks should be byte-identical between EN and translations, so they can be mechanically synced without re-translating prose. Need a script that takes a translated MDX file + latest EN MDX, replaces code blocks/imports/frontmatter from EN while preserving translated text. Would complement `check-translation-freshness.py` (which detects staleness but doesn't fix it).
- **Qiskit execution error hints** — When a Binder/thebelab cell raises a common error, surface a helpful inline hint. Typical errors to handle: `IBMRuntimeError`/`QiskitBackendNotFoundError` (no IBM account → hint to run the save-account cell), `ModuleNotFoundError` (package missing → hint to run the prerequisites cell), `QiskitError: 'AerSimulator'` (aer not installed → hint re: kernel restart after pip), kernel restart/dead messages, and `NameError` on common Qiskit objects (cell run out of order → hint to run from top). Hook into thebelab's output area (or a MutationObserver on cell output divs) and match stderr/stdout against known patterns to inject a styled hint below the output.

- **Hello World "What's Next" section** — The "What next?" in `tutorials/hello-world.mdx` (self-written) should recommend paths forward in both Qiskit-documentation and doQumentation, since the two projects offer different things.
- **Fork testing** — Verify the repo can be forked with Binder still working
- **Raspberry Pi** — `scripts/setup-pi.sh` written but untested on actual hardware
- **IBM Quantum Ecosystem listing** — Submit doQumentation.org to https://www.ibm.com/quantum/ecosystem to increase visibility.

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
- **Translation review + register fix** — All 456 structurally-passing files reviewed across 19 locales. 194 formal-register files fixed via targeted LLM rewrite.
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
- **Locale build MDX fixes (Mar 2026)** — Fixed 13 MDX compilation errors across DE/ES/FR locale builds that were causing the Deploy Locale Sites CI workflow to fail. Five root cause categories: (1) leading space before headings with `{#anchor}` (MDX parses as JS expression instead of heading ID) in 3 `kipu-optimization.mdx` files, (2) duplicate heading anchors containing dots (`{#name-1.0}` is invalid JS private field syntax) in 5 files (`qiskit-1.0-installation.mdx` ×3, `qiskit-1.0-features.mdx` ×2), (3) missing `<details><summary>` or `</details>` HTML tags in 4 files (`runtime-options-overview.mdx` ×2, `stern-gerlach-measurements-with-qiskit.mdx` ×2), (4) German typographic closing quote `"` (U+0022) inside JSX `definition="..."` attributes prematurely closing the attribute in 2 DE `DefinitionTooltip` files — fixed with `&quot;`, (5) `$$` math block indentation mismatch (opening at 3 spaces, content at 2) in FR `qiskit-implementation.mdx`. Also discovered FR `qiskit-1.0-installation.mdx` contained Spanish content (mislabeled file) — fully re-translated to French via chunked parallel Sonnet agents.

### Testing (Feb 2026)
- 180+ comprehensive tests, ~200 Chrome browser tests — 99.5% pass, zero real bugs
- Binder execution: 19/19 passed, 30-40s kernel connect, 45-min stable session
- Test plans: `.claude/BINDER-EXECUTION-TEST-PLAN.md` + `.claude/test-checklist.md`

### Future Ideas
- Auto-discover YouTube mappings (currently 32 static entries)
- LED integration for RasQberry
- Offline AI tutor (Granite 4.0 Nano)
- "Add Cell" scratch pad (full JupyterLab available as alternative)

---

## Related Resources

- **RasQberry:** https://github.com/JanLahmann/RasQberry-Two
- **Content source (fork):** https://github.com/JanLahmann/Qiskit-documentation
- **IBM Quantum:** https://ibm.com/quantum
- **IBM Quantum Platform:** https://quantum.cloud.ibm.com
- **Docusaurus:** https://docusaurus.io

---

*Last updated: March 18, 2026 (fix lunr.th search crash; archive continue-translations branch)*
