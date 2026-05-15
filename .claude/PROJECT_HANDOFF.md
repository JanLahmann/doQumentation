# doQumentation — Project Handoff

> Pre-April-2026 resolved items and Phase 1 addon-implementation detail live in [`PROJECT_HANDOFF_ARCHIVE.md`](./PROJECT_HANDOFF_ARCHIVE.md). Add new TODO/Resolved entries here; archive when older than ~6 weeks.

---

## What is doQumentation

An **open-source website for IBM Quantum's tutorials and learning content**, built as part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) educational quantum computing platform.

All content comes from IBM's open-source [Qiskit documentation](https://github.com/Qiskit/documentation) repository (CC BY-SA 4.0). IBM's web app serving that content is closed-source. doQumentation provides the open-source frontend — adding the website, Binder-based code execution, multiple deployment options, and usability features like automatic credential injection and simulator mode.

**Three deployment tiers:**

| Tier | URL | Code execution |
|------|-----|----------------|
| **GitHub Pages** | [doqumentation.org](https://doqumentation.org) | Remote via [Binder](https://mybinder.org) or [IBM Code Engine](https://doqumentation.org/jupyter-settings#code-engine) |
| **Docker** | [ghcr.io/janlahmann/doqumentation](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | Local Jupyter + Qiskit |
| **RasQberry Pi** | `http://rasqberry.local` | Local Jupyter + Qiskit, offline capable |

**Content:** 42 Tutorials, 171 Guides, 160 Course pages (14 courses), 14 Modules, 11 Qiskit Addon tutorials (~397 pages). Qiskit Addons are built and URL-accessible (`/qiskit-addons/...`) but currently hidden from navbar and main sidebar.

**Live:** [doqumentation.org](https://doqumentation.org) | **Repo:** [JanLahmann/doQumentation](https://github.com/JanLahmann/doQumentation) | **License:** Apache 2.0 (code) + CC BY-SA 4.0 (content)

---

## Architecture Decisions

- **Docusaurus 3.x** (not Next.js, Hugo) — purpose-built for docs, native MDX, auto sidebar, static export. IBM's frontend is Next.js but closed.
- **thebelab 0.4.x** (not JupyterLite, Voilà) — connects static HTML to any Jupyter kernel. JupyterLite can't run Qiskit (Rust extensions). Pin `thebelab@0.4.0` — 0.4.15 doesn't exist on npm.
- **Content transformation** (not Docker mirroring) — IBM's Docker preview lacks navigation/search. We transform their MDX to Docusaurus MDX (95% compatible).
- **Single codebase, three deployments** — runtime detection handles environment differences. Only the Jupyter endpoint differs.

---

## Features

### Content Sync (`scripts/sync-content.py`)
- Upstream tracked as git submodule (`upstream-docs/` → [Qiskit/documentation](https://github.com/Qiskit/documentation)). Sparse-clone fallback for environments without the submodule. Transforms MDX, converts notebooks (custom converter, no nbconvert), generates sidebars from `_toc.json`.
- **Freshness report**: `python scripts/sync-content.py --freshness-report PATH` writes a markdown report of EN-vs-upstream drift + per-locale staleness counts. Reads only `src/config/upstreamFileMeta.json` and `translation/status.json` — no submodule access required, fast and side-effect-free. Useful in PR bodies, ad-hoc inspection, or piped into `$GITHUB_STEP_SUMMARY` from a workflow.
- **Rolling back a bad sync**: revert the merge commit on `main` (GitHub "Revert" button or `git revert -m 1 <merge-sha> && git push`). `deploy.yml` republishes the prior site within ~5 min; translated locales follow on the next `deploy-locales.yml`. The submodule pointer travels with the revert, so subsequent `sync-content.py` runs replay against the rolled-back upstream until the underlying issue is fixed.
- Rewrites image paths (IBM URLs → local `static/`) and link paths (markdown + JSX `href`).
- `docs/index.mdx` preserved; everything else under `docs/` is regenerated each sync.
- **Dependency scan**: `analyze_notebook_imports()` injects `!pip install -q` cells into 46/260 notebooks missing packages (uses `!pip` not `%pip` to avoid "restart kernel" note). `--scan-deps` for report only.
- **Colab/Binder notebook copies**: `copy_notebook_with_rewrite()` injects prerequisites cell + commented `save_account()` template + Colab `cell_execution_strategy: "setup"`. Strips MDX frontmatter and applies `clean_notebook_markdown()` (removes JSX comments, heading anchors, `<Admonition>` → blockquote). `publish_notebooks_to_static()` copies ~1,650 notebooks to `static/notebooks/`.
- **Translated notebooks**: `generate_translated_notebook()` merges EN `.ipynb` skeleton with translated `.mdx` text (code cells unchanged). Uses code blocks as alignment anchors. `--generate-locale-notebooks --locale XX`.
- **Custom Hello World**: `hello-world.ipynb` from fork root imported as first tutorial with custom `OpenInLabBanner`.
- **Banner injection guard**: `OpenInLabBanner` only injected when notebook has ≥1 non-empty code cell. 86/261 notebook-derived pages are code-free (Basics QI, Foundations of QEC) → no banner.
- **Tutorial survey section**: appends clarifying note below IBM's survey link pointing readers to our [GitHub Issues](https://github.com/JanLahmann/doQumentation/issues) for site/translation/execution feedback.

### Image asset placement (notebook output PNGs)
- Single canonical location: `static/img/<section>/<stem-slug>/output_N.png`. Served at absolute `/img/<section>/<stem-slug>/output_N.png`.
  - `<section>` = relative path from `docs/` to MDX parent (`workshop`, `qiskit-addons/cutting`, …).
  - `<stem-slug>` = lowercased notebook stem with non-alphanum → `-`.
- All MDX (EN + 17 i18n locales) reference the same files via absolute paths — no per-locale duplication. New locale = zero PNG copies.
- Migration: 2026-05-06 (PR #34, branch `feat/dedupe-output-images`). One-shot script: `scripts/migrate_output_imgs.py`. Saved ~12 MB / 1,800 relative refs.
- `convert_notebook()` enforces this for new notebooks; future syncs can't reintroduce the legacy layout.
- **Other image trees (untouched)**: `docs/qiskit-addons/images/`, `docs/qiskit-addons/_static/`, `static/img/logo.svg`, `static/img/rasqberry-social-card.png`.
- **CI guard**: `.github/workflows/lint-image-paths.yml` fails any PR introducing `](./_<stem>_imgs/...)` refs or `_*_imgs/` dirs under `docs/`/`i18n/`.
- For new hand-added images: `static/img/<section>/<descriptive-name>/...` with absolute paths.

### Code Execution (`src/components/ExecutableCode/index.tsx`)
- `ExecutableCode` wraps Python code blocks with Run/Back toggle. thebelab bootstraps once per page, shared kernel.
- Environment auto-detection: GitHub Pages → Binder, localhost/Docker → local, custom → user-configured.
- Cell feedback: amber (running) / green (done) / red (error) borders. Detects `ModuleNotFoundError` (clickable Install button), `NameError`, generic tracebacks. All errors include "Report this error" link with pre-filled GitHub issue. Cell completion uses `kernel.statusChanged` (debounced) + `waitForOutputStable()` MutationObserver — handles cells that cycle busy→idle→busy (matplotlib, optimizers). Output queries use `OUTPUT_SELECTOR` constant (`.jp-OutputArea`, not `.thebelab-output` — thebelab 0.4.0 uses JupyterLab's widget). Pip install uses `--user` flag and `site.addsitedir()` workaround for Binder/conda before auto-rerun.
- Execution mode indicator badge (links to Settings → Execution Mode) + injection toast.
- **OpenInLabBanner**: "JupyterLab | Colab" — two buttons, all environments. Lab is session-managed via `ensureBinderSession()` on GitHub Pages, direct on CE/local. Only shown on pages with executable code cells. Lab uses named target `binder-lab` for tab reuse.
- **Run All**: sequential, auto-skips `save_account()` when credentials/simulator active. Pause / Continue / Stop. Aborts on Back/Restart/Clear/navigation.
- **Restart Kernel** / **Clear Session** buttons (visible when kernel ready). Restart re-injects credentials/simulator setup; Clear resets to static view.
- **Binder startup cancel + slow detection**: per-phase timeouts (connecting 1m → building 12m) trigger red warning suggesting alternative backends.
- **Interception transparency**: all kernel modifications print `[doQumentation]` messages. Exported notebooks include setup notice cell. "What's modified?" link on banner. `/about/code-modifications` page lists every transform.
- **FeedbackWidget** (`src/components/FeedbackWidget/`): thumbs up/down, Umami-tracked. Mounted by unified DocItem footer on `tutorials/` + `learning/`. Legacy `<TutorialFeedback />` wrapper returns null; ~240 MDX files still import it as a no-op.
- **TranslationFeedback banner** (`src/components/TranslationFeedback/`): non-EN pages, good/ok/poor → Umami. Session-dismissible.
- **"View in English" link**: top of locale dropdown on non-EN pages.
- **save_account() protection**: dynamic blue "Skip this cell" banners (`annotateSaveAccountCells()`) when credentials/simulator active. Run All filters cells with `.thebelab-cell__skip-hint`.
- **Full i18n**: all toolbar buttons / status / legend wrapped with `translate()`/`<Translate>`.

### IBM Quantum Integration (`src/config/jupyter.ts`)
- **Credentials** — API token + CRN, auto-expiry 1/3/7 days (default 1). Auto-injected at kernel start. Embedded execution only. Shared across locale subdomains via cookies.
- **Execution Mode** (`doqumentation_execution_mode`, `'aer' | 'fake' | 'credentials' | 'none'`) — single radio replaces old simulator-toggle + conflict-resolution model. `getExecutionMode()` is source of truth; `getSimulatorMode()` / `getSimulatorBackend()` derive. Lazy migration maps old keys → new on first read. `injectKernelSetup()` switches on the mode. **Exempt pages** (`SIMULATOR_EXEMPT_PAGES`): `tutorials/hello-world` etc. fall back simulator → credentials → none.
- **Simulator backend** — monkey-patches `QiskitRuntimeService` with a mock service (AerSimulator or FakeBackend). Discovery cached, 55-backend fallback list.
- **Plan type** — Open / Pay-as-you-go / Premium selector (`doqumentation_ibm_plan`). Open Plan patches `qiskit_ibm_runtime.Session` with a passthrough that returns `backend` directly. Per-cell amber banners on `Session(` cells via `annotateSessionCells()`. Reactive error hint links to Settings on "not authorized" failures.
- **Shared Binder session** — `ensureBinderSession()` manages a single Binder session for both Lab button and thebelab. Stored in `sessionStorage` (`dq-binder-session`), 8-min idle, kept alive on kernel busy/idle. Probes `/api/status` before reuse — dead/culled containers and environment-mismatched cached sessions trigger fresh build. Both use `doQumentation/notebooks` branch. Live build phases shown in both UIs. Cross-locale sessions domain-scoped (security). `openBinderLab()` opens blank tab synchronously (popup blocker workaround) then navigates when ready.
- **Colab URLs** — `getColabUrl(notebookPath, locale?)` via `/github/` scheme (Colab's `/url/` blocks non-GitHub via SSRF allowlist). EN → `doQumentation/blob/notebooks/`; translated → `doqumentation-{locale}/blob/gh-pages/notebooks/`. Path mapping in `mapBinderNotebookPath()`.

### IBM Cloud Code Engine (`Dockerfile.jupyter` → `jupyter-codeengine` target)
- **What** — serverless Jupyter container on user's IBM Cloud account. Drop-in Binder replacement, ~1s cold start (vs 10–25 min). Free tier ~14 hrs/month.
- **Architecture** — single-port (8080): nginx reverse proxy + Jupyter (8888) + SSE build server (9091), supervisord-managed. SSE server (`sse-build-server.py`) mimics mybinder.org `/build/` SSE so `ensureBinderSession()` works unchanged (3 phases instead of 7+). Public URL derived from `Host` + `X-Forwarded-Proto`. Cold start ~12s; `/health` returns 503 until Jupyter ready.
- **Deployed** — `jupyter.28mc794qh1og.eu-de.codeengine.appdomain.cloud` (eu-de), project `doQumentation`, app `jupyter`. Min 0 / max 1. Default 1 vCPU / 2 GB. Token 32+ chars. Sizing per `.claude/STRESS-TEST-FINDINGS.md`: 8 vCPU/16 GB handles 80 users.
- **Naming convention** — Projects = environments: `doQumentation` (prod), `doQumentation-workshop-XX` (temp). Apps = instances: `jupyter` (single) or `jupyter-XX` (multi). `instance_count=1` → no suffix; >1 → auto-numbered. All 6 CE workflows have configurable `project` + `app_name`.
- **Scale-to-zero** — works in fresh projects; old `ce-doqumentation-01` had stale Knative/Istio state. Nginx kept: `keepalive_timeout 0`, WS timeouts 7200s. **CE monitor workflow** (`ce-monitor.yml`): every 2h checks running/oversized; daily 06:00 UTC summary. **CE list** (`ce-list.yml`): on-demand inventory.
- **Image** — `ghcr.io/janlahmann/doqumentation-codeengine:latest`, built by `codeengine-image.yml` using `Dockerfile.jupyter --target jupyter-codeengine`. Base `quay.io/jupyter/base-notebook:python-3.12`. Security pins (`jupyter-requirements-security.txt`) installed `--upgrade` in `jupyter-base` so both targets inherit. `linux/amd64` only. Trivy scan (HIGH/CRITICAL fail; `.trivyignore` for unfixable). Auto-deploy to CE after push (needs `IBM_CLOUD_API_KEY` secret).
- **Security** — token (32+ chars), CORS validation (`CORS_ORIGIN`, default `https://doqumentation.org`), XSRF disabled (thebelab 0.4.0 limit), nginx rate limiting (except `/lab` — token suffices), HSTS/CSP/nosniff.
- **User flow** — `/jupyter-settings#code-engine`. Single Code Engine URL field auto-detects: single URL → personal, comma-separated → workshop pool, base64 `{"pool":[...]}` → workshop pool. Token shared. Workshop pool gives sticky session per tab. Base64 config (no token) safe in public repos.
  - `#workshop=BASE64` URL fragment removed for security (token in browser history).
- **Storage** — `doqumentation_ce_url`, `doqumentation_ce_token`, `doqumentation_ce_saved_at`.
- **Files** — `Dockerfile.jupyter`, `binder/sse-build-server.py`, `binder/nginx-codeengine.conf`, `binder/codeengine-entrypoint.sh`, `binder/jupyter-requirements-security.txt`, `.github/workflows/codeengine-image.yml`.

### User Preferences
All storage in `src/config/preferences.ts` and `src/config/jupyter.ts`, backed by `src/config/storage.ts`. **Cross-subdomain**: on `*.doqumentation.org` all 28 keys dual-written to cookies (`Domain=.doqumentation.org`) + localStorage. Values >3.8KB auto-chunked. Localhost/Docker = pure localStorage. One-time migration on first load (`pageTracker.ts`). Cross-component reactivity via `dq:page-visited`, `dq:bookmarks-changed`, `dq:display-prefs-changed`.

- **Learning progress** — auto-tracks visits. Sidebar indicators: ✓ visited / ▶ executed / `</>` notebook (swizzled `DocSidebarItem`). Category badges. Resume card on homepage. Granular clearing.
- **Bookmarks** — ☆/★ in swizzled `EditThisPage`. Homepage widget. Max 50.
- **Display prefs** — code font size (10–22), hide pre-computed outputs during live exec, warning suppression toggle.
- **Onboarding** — contextual tip bar for first 3 visits.
- **Recent pages** — last 10, top 5 on homepage.
- **Sidebar collapse** — MutationObserver persists state.

| Key | Feature |
|-----|---------|
| `dq-visited-pages` | Learning progress (JSON set) |
| `dq-executed-pages` | Learning progress (JSON set) |
| `dq-last-page` | Resume reading (JSON `{path,title,ts}`) |
| `dq-binder-hint-dismissed` | Binder hint |
| `dq-onboarding-completed` | Onboarding |
| `dq-onboarding-visit-count` | Onboarding (0–3) |
| `dq-bookmarks` | Bookmarks (JSON, ≤50) |
| `dq-code-font-size` | Display (10–22) |
| `dq-hide-static-outputs` | Display |
| `doqumentation_suppress_warnings` | Warning suppression (default true) |
| `dq-sidebar-collapsed` | Sidebar collapse (JSON) |
| `dq-recent-pages` | Recent (JSON, ≤10) |
| `doqumentation_ibm_plan` | IBM Quantum plan (open/payg/premium) |

### MDX Components

| IBM Component | Solution |
|---|---|
| `<Admonition>` | `@theme/Admonition` (NOT `:::` — breaks in `<details>`) |
| `<Tabs>` / `<TabItem>` | Native Docusaurus |
| Math `$...$` `$$...$$` | KaTeX plugin |
| `<IBMVideo>` | YouTube-first (32 mapped IDs) + IBM fallback |
| `<Card>`, `<CardGroup>`, `<Image>`, `<Accordion>`, `<AccordionItem>` | Component stubs |

### Unified DocItem footer (dates + feedback)

Built by swizzled `src/theme/DocItem/Footer/index.tsx`. Two zones:

**Zone 1 — page-dates** (top, faint border above):
- `Source: IBM Quantum docs — updated <date>` (link when path maps; absent on doQ-original).
- EN: `This page on doQumentation — updated <date>`.
- Translated: `English version on doQumentation — updated <date>` + `This translation based on the English version of <date>` (italic; "approx." when `en_base_source: "promoted-fallback"` or `"clamped"`).

**Zone 2 — feedback panel** (two-column grid):

| Left | Right |
|------|-------|
| `Was doQumentation helpful here?` 👍 👎 | `[Site or translation issue?]` (primary) |
| `[☆ Bookmark]` | *Content issue? Edit on IBM Quantum docs* (secondary) |

👍/👎 gated to `tutorials/` + `learning/`. Bookmark always shows. doQ-original pages (`hello-world.mdx`, `workshop/*`, `about/*`) point content-edit to our repo. Stacks vertically <640px.

**Date semantics — important.** All dates are *upstream content dates*, not local mtimes, so freshness `upstream ≥ EN ≥ translation` always holds:
- `upstream_date` = latest commit date in `Qiskit/documentation`. Refreshed daily.
- `en_date` = upstream commit date for the version of the upstream file *currently in our submodule*. NOT `git log` of local MDX. Computed by hashing on-disk upstream file and walking `ibm/main` history (`_content_authored_date`, binary-safe via `text=False`).
- `en_base_commit_date` = EN-side commit date the translation was based on. Clamped at render to ≤ `en_date` so a translation can't appear newer than its source (`page-dates` plugin tags clamped values).

Data flow:
- `sync-content.py --meta-only` writes `src/config/upstreamFileMeta.json` (upstream_date, upstream_sha, en_date). Requires `ibm/main` fetched in `upstream-docs/` — JanLahmann fork flattens per-file dates, so we need real IBM history. `_ensure_ibm_history()` adds+fetches the `ibm` remote.
- `translation/scripts/promote-drafts.py` records `en_base_commit_date` per locale × path in `translation/status.json`.
- `translation/scripts/backfill-en-base-date.py` (one-shot) backfilled 4,964/7,342 entries with hash-verified dates; 2,170 fell back to promoted date with `en_base_source: "promoted-fallback"`.
- `plugins/page-dates/index.js` exposes per-locale page-date map via `globalData["page-dates"]`. Clamps `translationBaseDate` ≤ `enDate`.
- `Footer/index.tsx` reads `useDoc().metadata.source` (strip `@site/docs/` AND `@site/i18n/<locale>/.../current/` prefixes), looks up globalData, formats via `Intl.DateTimeFormat(locale)`. No `<OriginalFooter>` — built from swizzled `<EditThisPage>` + `<FeedbackWidget>` + `<BookmarkButton>`.
- `EditThisPage/index.tsx` produces only Zone 2 right-column links. `editUrlToRelPath()` extracts doc key; page-dates manifest decides IBM-upstream → `Qiskit/documentation/edit/main/<upstream_path>` vs doQ-original → our repo. "Site or translation issue?" always points to `JanLahmann/doQumentation/issues/new` with prefilled body.
- IBM-source URL mapping: `src/lib/originalUrl.ts`.

**Refresh**: `.github/workflows/refresh-page-dates.yml` daily at 07:00 UTC, calls `sync-content.py --meta-only`, commits if changed, push triggers `deploy.yml`.

### Docker & Authentication
- `binder/Dockerfile` (main branch) — `FROM quay.io/jupyter/base-notebook:python-3.12`, installs from `jupyter-requirements.txt` (Qiskit ecosystem: `qiskit[all]`, all addons, scipy, pyscf, plotly, ffsim, sympy, pandas — 21 packages). Single source of truth for Binder + Docker.
- `Dockerfile.web` — static site (nginx, ~60 MB). `Dockerfile.jupyter` — multi-stage with shared `jupyter-base` + targets `jupyter-local` (~3 GB) and `jupyter-codeengine` (~3 GB).
- Multi-arch: `linux/amd64` full Qiskit; `linux/arm64` excludes some packages.
- **Jupyter auth**: nginx injects `Authorization` server-side. Browser never sees token. `docker-entrypoint.sh` generates random token (or accepts `JUPYTER_TOKEN` env). Runs as non-root `jovyan`.

### CI/CD
- **`deploy.yml`** — sync → build → GH Pages (EN). Force-pushes EN notebooks + Binder config to `notebooks` branch. repo2docker uses repo root with `--file binder/Dockerfile`, so all `COPY` paths relative to repo root.
- **`deploy-locales.yml`** — matrix per locale. `fail-fast: false`, `if: always()` on consolidation — one locale failure doesn't block others.
- **`docker.yml`** — multi-arch → ghcr.io (EN only, `--locale en`). `Dockerfile.jupyter --target jupyter-local`. Push trigger disabled — `workflow_dispatch` only.
- **`sync-deps.yml`** — weekly auto-PR. `scripts/sync-deps.py` fetches from upstream `nb-tester/requirements.txt`, drops `sys.platform` markers, splits architecture-specific packages (`gem-suite`, `qiskit-ibm-transpiler[ai-local-mode]`, `qiskit-addon-aqc-tensor[quimb-jax]` → `jupyter-requirements-amd64.txt`), adds `EXTRA_CROSS_PLATFORM` (`pylatexenc`, `pandas`). Both files marked "DO NOT EDIT MANUALLY". `jupyter-requirements-security.txt` is manual (CVE pins, Trivy-enforced for CE).
- **`check-translations.yml`** — daily freshness + STATUS.md update.
- **`refresh-page-dates.yml`** — daily 07:00 UTC, `sync-content.py --meta-only`.
- **`binder.yml`** — daily cache-warming for 3 federation members (2i2c, BIDS, GESIS) + on push to `notebooks` + `workflow_dispatch`.
- **Workshop lifecycle** — `workshop-start.yml` (resize + token + warm, ~2 min, `instance_count` for multi-pod), `workshop-monitor.yml` (continuous `/stats` polling + sparklines + cost estimate, 30m–6h, `workflow_call`-able), `workshop-close.yml` (capture stats, optional cancel monitor, resize down, rotate token).
- **`ce-monitor.yml`** — every 2h alerts on running/oversized; daily 06:00 UTC full summary.
- **GH Actions self-service** — `stress-test.yml`, `resize-pod.yml`, smarter deploy in `codeengine-image.yml` (preserves pod size on push).

### Other
- **Homepage** — Beta notice (session-dismissible), hero + stats, Getting Started cards, simulator callout, code execution. No sidebar/TOC.
- **Sidebar** — Home → Tutorials/Guides/Courses/Modules. API Reference + Settings in navbar. Single unified indicator per item, 5 states. Notebook detection via `customProps.notebook` in sidebar JSON. Category badges DOM-injected (different strategies for href vs. non-href categories). `useLayoutEffect` re-injects after re-renders. Long titles truncate with ellipsis.
- **Features page** — `/features`, 31 cards / 6 sections.
- **Search** — `@easyops-cn/docusaurus-search-local` (client-side, hashed index).
- **Settings** (`/jupyter-settings`) — credentials, simulator, display prefs, progress, bookmarks, custom server. Full-width card.
- **Navbar** — always dark `#161616`. Right-side icons: locale (globe), settings (gear), dark mode, GitHub. Locale dropdown filtered by `customFields.visibleLocales` (`['en','de','es']`); all 23 locales remain built. "Deutsche Dialekte" separator before dialect locales.
- **Footer** — three columns: doQumentation / RasQberry / IBM Quantum & Qiskit. IBM disclaimer.
- **Legal** (`/legal`) — Impressum + Privacy Policy. DDG §5 + GDPR.
- **Admin** (`/admin`) — hidden, password-gated (SHA-256 of `ADMIN_PASSWORD`). Sensitive URLs AES-256-GCM encrypted at build time (`scripts/encrypt-for-admin.mjs`); plaintext never in source. Secrets `ADMIN_PASSWORD`, `UMAMI_SHARE_URL`. Excluded from `robots.txt`.
- **Breadcrumbs** — enabled via `docs.breadcrumbs: true`.
- **Analytics** — Umami Cloud (cookie-free, GDPR, no consent banner). `src/config/analytics.ts`. Custom events: Run Code, Run All, Binder Launch, Colab Open, Notebook Download, Tutorial Feedback, Translation Feedback, Outbound, Outbound IBM. Auto-disabled on localhost/Docker.
  - **Outbound link tracking** (`src/clientModules/outboundTracker.ts`): single capture-phase listener (mousedown + auxclick — middle/cmd-click). Skips same-host + `*.doqumentation.org`. IBM hosts also fire `Outbound IBM`. Categories: `quantum-platform`, `quantum-docs`, `quantum-learning`, `ibm-cloud`, `ibm-marketing`, `ibm-video`, `ibm-other`, `github`, `external-other`. Path-aware (`quantum.cloud.ibm.com/docs/*` → `quantum-docs`, etc.). Properties: `category`, `host`, `path`, `url`, `from`, `locale`.
- **Styling** — Carbon Design (IBM Plex, `#0f62fe`).
- **SEO & social** — OG + Twitter Card, JSON-LD (Organization/WebPage/SoftwareApplication), AI-indexing robots meta, preconnect hints, social card 1200×630.
- **Keyboard accessibility** — `focus-visible` outlines; light blue variant on dark navbar.

---

## Project Structure

```
doQumentation/
├── .github/workflows/          # deploy, deploy-locales, docker, sync-deps, check-translations, binder, workshop-{start,monitor,close}, ce-{monitor,list}, codeengine-image, refresh-page-dates, stress-test, resize-pod
├── upstream-docs/              # Submodule → Qiskit/documentation (CC BY-SA 4.0)
├── upstream-addons/            # Submodules → 7 Qiskit addon repos (Apache 2.0)
├── binder/                     # Jupyter requirements (cross-platform + amd64-only) + nginx/SSE/entrypoint for CE
├── docs/                       # Content (regenerated by sync-content.py, but committed for per-file history + PR review)
├── notebooks/                  # Original .ipynb for JupyterLab (generated, gitignored)
├── src/
│   ├── clientModules/          # pageTracker, displayPrefs, onboarding, outboundTracker
│   ├── components/             # ExecutableCode, ResumeCard, RecentPages, BookmarksList, OpenInLabBanner, BetaNotice, FeedbackWidget, BookmarkButton, TranslationFeedback, TutorialFeedback (no-op), CourseComponents, GuideComponents, InfoIcon
│   ├── config/                 # storage.ts, jupyter.ts, preferences.ts, contentMeta.ts (generated)
│   ├── css/custom.css          # All styling
│   ├── pages/                  # features.tsx, jupyter-settings.tsx, admin/, workshop-setup.mdx
│   └── theme/                  # Swizzled: Root, CodeBlock, DocItem/Footer, EditThisPage, DocSidebarItem/{Category,Link}, Navbar/MobileSidebar/Header, NavbarItem/LocaleDropdownNavbarItem, MDXComponents
├── i18n/                       # Translations (see Multi-Language section)
├── local-content/              # In-repo course overlay (e.g. use-a-qc-today). Merged into upstream-docs/learning/courses/ at sync time.
├── scripts/                    # sync-content.py, sync-deps.py, docker-entrypoint.sh, setup-pi.sh, encrypt-for-admin.mjs, migrate_output_imgs.py, workshop-stress-test.py
├── translation/                # drafts/{locale}/{path}, status.json, *-prompt.md, scripts/{validate,lint,review,fix-anchors,promote,populate,get-register-fails,translation-status,sync-translations,update-translations}
├── static/                     # logo.svg (favicon), CNAME, robots.txt, img/<section>/<stem-slug>/output_N.png
├── Dockerfile.web              # Static site only (nginx, ~60 MB)
├── Dockerfile.jupyter          # Multi-stage: jupyter-local + jupyter-codeengine
├── docker-compose.yml          # web + jupyter profiles
├── nginx.conf                  # SPA + Jupyter proxy
├── docusaurus.config.ts
├── sidebars.ts                 # Imports generated sidebar JSONs
└── README.md
```

**Generated but tracked:** `docs/tutorials/`, `docs/guides/`, `docs/learning/`, `docs/qiskit-addons/`, `sidebar-*.json` — committed so each upstream sync is a reviewable diff and `git log` returns real per-file history.

**Generated and gitignored:** `notebooks/`, `static/docs/`, `static/learning/images/`.

---

## Development

```bash
npm install                                       # Install deps
npm start                                         # Dev server (hot reload)
npm run build                                     # Production (NODE_OPTIONS="--max-old-space-size=8192")
python scripts/sync-content.py                    # Sync all content from upstream
python scripts/sync-content.py --sample-only      # Sample only
python scripts/sync-content.py --generate-locale-notebooks --locale de
```

**Docker:**
```bash
podman compose --profile web up       # Static → http://localhost:8080
podman compose --profile jupyter up   # Full stack → :8080 + :8888
```

**Deps:** Docusaurus 3.x, React 18, remark-math + rehype-katex, thebelab 0.4.x (CDN), Node.js 18+, Python 3.9+.

---

## Gotchas

- **thebelab CDN pin** — `thebelab@0.4.0`. Versions jump 0.4.0 → 0.5.0.
- **sync-content.py overwrites docs/** — only `docs/index.mdx` preserved. Edit transforms in the script.
- **Admonition JSX** — don't convert `<Admonition>` to `:::` — breaks inside `<details>`.
- **Build memory** — ~380 pages → `NODE_OPTIONS="--max-old-space-size=8192"`.
- **thebelab config** — pass options to `bootstrap(options)`. Do NOT use `<script type="text/x-thebe-config">`.
- **Binder cache** — keyed to commit hash. Site uses `mybinder.org` federation endpoint, not specific member.
- **JSX href** — Card components use `href="/docs/..."`. `MDX_TRANSFORMS` rewrites both markdown and JSX.
- **Kernel busy/idle** — thebelab 0.4.0 only emits lifecycle events; subscribe to `kernel.statusChanged` from `@jupyterlab/services`.
- **`_tag_untagged_code_blocks` + LaTeX** — regex can match across output boundaries. Guards: skip if `$$` in content, exclude `$$` from `$` shell heuristic.
- **Sidebar items persist** across SPA navigation — use custom events, not just mount-time checks.

---

## Multi-Language Infrastructure

Each language gets its own subdomain via satellite GitHub repos. Wildcard DNS CNAME `*` → `janlahmann.github.io` at IONOS covers all subdomains.

| Locale | URL | Pages | Status |
|---|---|---|---|
| DE / ES / FR / UK / JA / IT / PT / TL / AR / MS / ID / KO / PL / RO / CS | `XX.doqumentation.org` | **412/412 (100%)** | Live |
| HE / TH | `XX.doqumentation.org` | 391/412 (95%) | Live (HE = RTL) |
| KSH / NDS / GSW / SAX / BLN / AUT / SWG / BAD / BAR | `XX.doqumentation.org` | 31–46 | Live (German dialects) |

**Potential future:** Turkish (TR).

- **Config**: `docusaurus.config.ts` — `locales: ['en','de','es','uk','fr','it','pt','ja','tl','ar','he','swg','bad','bar','ksh','nds','gsw','sax','bln','aut','ms','id','th']`, per-locale `url` in `localeConfigs`, `DQ_LOCALE_URL` env var. hreflang tags auto-generated.
- **RTL**: AR, HE have `direction: 'rtl'`. CSS uses logical properties (`border-inline-start`, `margin-inline-start`, `inset-inline-end`). Noto Sans Arabic/Hebrew via Google Fonts. KaTeX forced LTR (`direction: ltr` on `.katex`, `.katex-display`).
- **CI**: `deploy.yml` builds EN. `deploy-locales.yml` matrix builds 22 locales separately, pushes to satellite repos via SSH deploy keys (`DEPLOY_KEY_{XX_UPPER}`).
- **Satellite repos**: `JanLahmann/doQumentation-{de,es,uk,…}` — each has `main` (README/LICENSE/LICENSE-DOCS/NOTICE) and `gh-pages` (build output). Setup: `.claude/scripts/setup-satellite-repo.sh`.
- **German dialects**: 9 locales with "Deutsche Dialekte" separator. To add: `dialectLocales` Set + `locales`/`localeConfigs` + CI matrix + `BANNER_TEMPLATES` + `locale_label` in `translate-content.py`.
- **UI i18n** (`code.json`): all React strings via `<Translate>`/`translate()`. ~308 keys per locale (~92 theme + ~216 custom). New language: `npm run write-translations -- --locale {XX}` auto-generates with EN defaults; technical terms (Qiskit, Binder, AerSimulator) and code stay in English. Preserve placeholders `{binder}`, `{saveAccount}`, `{url}`, `{pipCode}`, `{issueLink}`, `{mode}`.
- **Fallback**: `populate-locale` fills untranslated with EN + "not yet translated" banner. ~387 fallbacks/locale.
- **Translation freshness**: genuine translations embed `{/* doqumentation-source-hash: XXXX */}` (SHA-256 first 8). Daily CI compares vs current EN. CRITICAL = missing imports/components; STALE = content changed. After EN changes propagate, run `check-translation-freshness.py --stamp`. **Rule**: any EN-source change (imports, components, content) must be manually propagated to genuine translations — `populate-locale` only refreshes fallbacks.
- **Draft → review pipeline** — `translation/drafts/{locale}/{path}` → validate → fix anchors → promote to `i18n/`. Status in `translation/status.json` (status, validation, source hash, dates, failures). Scripts default to `i18n/` without `--dir`.
  - **Status & dashboard**: `translation-status.py` (`--locale` / `--backlog` / `--validate` / `--markdown`/`--json` / `--update-contributing` / `--write-status` / `--all`). Daily CI auto-updates `translation/STATUS.md`.
  - **3-step QA**: (1) `validate-translation.py` — 15 binary checks (line count, code blocks byte-identical, LaTeX, headings, anchors, image paths, frontmatter, JSX, URLs, paragraph inflation; locale thresholds `de=3.0x`, `fr/es/it/pt=2.5x`, default 2.2x; `MIN_TR_WORDS_FOR_INFLATION=250`). (2) `lint-translation.py` — MDX syntax (duplicate anchors, garbled XML, mid-line headings, unmatched fences, missing imports, unescaped JSX quotes). (3) `review-translations.py` — linguistic review (register, word salad, verbosity, accuracy) with `--record-review`. Review prompt: `translation/review-prompt.md`. **Lesson:** Haiku unreliable for review (~33% miss rate, fabricates "word salad"). Always Sonnet, 5 files/chunk.
  - **Sync & update**: `sync-translations.py` mechanically fixes code-block drift (run after EN changes: `--all-locales` or `--locale XX --dry-run`). `update-translations.py` (838 lines) — diff-based DETECT (severity NOOP/MINOR/MODERATE/MAJOR) → AUTO-FIX → WORKFILE for translation agents. Needs runtime testing.
  - **Orchestration**: `review-translations.py` — `--auto-check` (struct + lint, all locales), `--progress`, `--next-chunk [--size N]`, `--record-review` (PASS/MINOR_ISSUES/FAIL/SKIPPED).
- **Register**: informal/familiar (du / tu / tú / ти — not Sie/vous/usted/Ви). Targeted rewrite: `translation/register-fix-prompt.md`. Helper: `get-register-fails.py`.
- **Heading anchors**: translated headings get `{#english-anchor}` to preserve cross-references. `fix-heading-anchors.py` (with `--dir`).
- **Contributor guide**: [`CONTRIBUTING-TRANSLATIONS.md`](../CONTRIBUTING-TRANSLATIONS.md). Two Claude Code prompts: `translation/translation-prompt.md` (CLI) and `translation/translation-prompt-web.md` (web, 20-file sessions). Both Sonnet, 3 parallel.
- **Build**: ~320 MB per single-locale build. Each fits GitHub Pages 1 GB independently.
- **Attribution**: `NOTICE` in main + all satellite repos credits IBM/Qiskit and documents dual-license. `LICENSE` (Apache 2.0) + `LICENSE-DOCS` (CC BY-SA 4.0) clean templates so Licensee detection works.

### How to add a new language

1. **UI strings (4 files)** — `npm run write-translations -- --locale {XX}` then translate `"message"` values:
   - `i18n/{XX}/code.json` (~308: theme + custom `features.*`/`settings.*`/`executable.*`/`bookmark.*`/`bookmarksList.*`/`betaNotice.*`/`sidebar.*`/`navbar.mobile.*`)
   - `i18n/{XX}/docusaurus-plugin-content-docs/current.json` (~60 sidebar labels)
   - `i18n/{XX}/docusaurus-theme-classic/navbar.json`
   - `i18n/{XX}/docusaurus-theme-classic/footer.json`

   Reference: `i18n/de/`.

2. **Banner template** — add `{XX}` to `BANNER_TEMPLATES` in `translation/scripts/translate-content.py`.

3. **Config** (`docusaurus.config.ts`) — add to `locales`, `localeConfigs` (`label`, `url: 'https://{XX}.doqumentation.org'`), search plugin `language` (skip if [`lunr-languages`](https://github.com/MihaiValentin/lunr-languages) doesn't support it — `uk`, `tl`, `th` are unsupported). Optional: add to `customFields.visibleLocales` to show in dropdown.

4. **CI matrix** (`deploy-locales.yml`):
   ```yaml
   - locale: {XX}
     repo: JanLahmann/doqumentation-{XX}
   ```

5. **Satellite repo + deploy infra** — automated via `.claude/scripts/setup-satellite-repo.sh`:
   ```bash
   gh repo create JanLahmann/doqumentation-{XX} --public --description "doQumentation – {Label} locale"
   ./.claude/scripts/setup-satellite-repo.sh {XX} "{Label}"           # main + gh-pages branches
   ssh-keygen -t ed25519 -C "deploy-doqumentation-{XX}" -f /tmp/deploy_key_{XX} -N ""
   gh repo deploy-key add /tmp/deploy_key_{XX}.pub --repo JanLahmann/doqumentation-{XX} --title "deploy-doqumentation-{XX}" --allow-write
   gh secret set DEPLOY_KEY_{XX_UPPER} --repo JanLahmann/doQumentation --body "$(cat /tmp/deploy_key_{XX})"
   rm /tmp/deploy_key_{XX} /tmp/deploy_key_{XX}.pub
   gh api repos/JanLahmann/doqumentation-{XX}/pages --method POST --field source='{"branch":"gh-pages","path":"/"}'
   gh api repos/JanLahmann/doqumentation-{XX}/pages --method PUT --field cname="{XX}.doqumentation.org" --field https_enforced=true
   ```
   Wildcard `*` CNAME at IONOS covers DNS automatically.

6. **Translate content**:
   ```bash
   # via Claude Code — see translation/translation-prompt.md
   Read translation/translation-prompt.md. Translate all untranslated pages to {LANGUAGE} ({XX}).
   python translation/scripts/validate-translation.py --locale {XX} --dir translation/drafts
   python translation/scripts/fix-heading-anchors.py --locale {XX} --dir translation/drafts --apply
   python translation/scripts/promote-drafts.py --locale {XX}
   python translation/scripts/translate-content.py populate-locale --locale {XX}
   DQ_LOCALE_URL=https://{XX}.doqumentation.org npx docusaurus build --locale {XX}
   git add -f i18n/{XX}/docusaurus-plugin-content-docs/current/   # gitignored, force-add
   ```

7. **Git tracking** — `code.json`, `navbar.json`, `footer.json`, `current.json` tracked normally. MDX translations gitignored, must `git add -f`.

---

## Open Items

### Active TODO

- **Translation expansion** — 17 standard locales at 100% (412/412). HE/TH 95% (21 fallback files in about + qiskit-addons). German dialects: KSH 46, NDS 43, GSW 42, SAX 39, BLN 36, AUT 34, SWG/BAD/BAR 31. TH/MS/ID/CS still have 13–213 ✗ files needing fixes despite full structural coverage. Run `python translation/scripts/translation-status.py --all` for current counts.
- **Linguistic review remaining** — Phase 3 stratified samples done for KO (414/414, full), TH (44, mostly clean), PL (45), CS (45). RO + MS + ID samples still pending (~10/412 each). Optional: deeper TH/PL/CS coverage. Translator passes still owed: TL `workshop/03*` (~75% English), AR `quantum-diagonalization-algorithms/` (`تقطير`→`قطرنة` systematic), KO `tutorials/transpilation-optimizations-with-sabre.mdx` (8 untranslated EN passages, lines 579–823). Full per-locale status + Phase 4 cheap-fixes in `.claude/PHASE_4_LINGUISTIC_TRIAGE_2026-05-07.md`.
- **Bump QuBins pin in lockstep with Qiskit** — `src/config/jupyter.ts` pins Binder to `mybinder.org/v2/gh/JanLahmann/qubins/2.3-xl`. When `binder/jupyter-requirements.txt` moves to Qiskit 2.4 (or later), bump this string to the matching QuBins tag. Same applies to `admin.tsx` Federation links.
- **Upstream sync strategy follow-ups** — submodule now tracks `Qiskit/documentation` directly (as of 2026-05-15) and `sync-upstream.yml` provides a workflow_dispatch entry point. Still TODO: schedule the workflow weekly once a few manual dispatches have proven the auto-PR path is reliable; teach `sync-content.py` to flag conflicts on our locally-customized files (`hello-world.ipynb`, `_toc.json`); document the rollback recipe in CONTRIBUTING (currently only in README + this file).
- **Qiskit execution error hints** — surface inline hints for `IBMRuntimeError`/`QiskitBackendNotFoundError` (no IBM account → save-account), `ModuleNotFoundError` (run prerequisites), `QiskitError: 'AerSimulator'` (kernel restart after pip), kernel-dead messages, and `NameError` (run from top). Hook MutationObserver on cell output divs, match stderr/stdout against patterns, inject styled hint.
- **Plan-type disclaimer for paid users** — when Plan ≠ Open and `executionMode === 'credentials'`, show a yellow `<div className="alert alert--warning">` warning that credentials live in localStorage (plain text) and this site isn't recommended for paid-tier accounts. Below Plan dropdown in `src/pages/jupyter-settings.tsx`. Translate via existing `<Translate id="settings.ibm.paidPlanWarning">`.
- **Make kernel-side code injections transparent** — `injectKernelSetup()` silently runs Python before user cells (save_account guard, `_DQ_MockService`, `_DQ_JobModeSession`, warning suppression, save_account placeholder guard). Add expandable "Show injected setup code" panel — either next to "What's modified?" on `OpenInLabBanner` or on `/about/code-modifications`. Build `getInjectedSetupCode()` helper that concatenates `getSaveAccountCode()` + `getSimulatorPatchCode()` + `getOpenPlanPatchCode()` for the current execution mode + page (respecting `SIMULATOR_EXEMPT_PAGES`, plan type) and renders a collapsible code block.
- **Qiskit Addons Phase 2 expansion** — Phase 1 shipped 11 tutorials; Phase 2 adds ~26 more across already-submoduled repos (+19 how-tos / explanations) plus 2 new submodules (opt-mapper, utils, +7) and mthree (1 notebook + deferred `.rst`). Phase 3 = `.rst` conversion (~20 files). Implementation pattern, repo inventory, and caveats (Binder image size, 418 new fallback MDX files, navbar-hidden status, all-Apache-2.0) in `PROJECT_HANDOFF_ARCHIVE.md`. Schema work: extend `ADDON_SOURCES` to `{"sections": {"tutorials": ..., "how-tos": ...}}`, refactor `process_addons()`, update `generate_addons_sidebar()` for nested categories.
- **Submodule pointer drift** — `upstream-docs/` locally at `6f006d7a` but committed pointer `1472ac86`. Decide: commit the bump or reset.
- **Hello World "What's Next"** — `tutorials/hello-world.mdx` (self-written) should recommend paths in both Qiskit-documentation and doQumentation.
- **Multi-pod workshop end-to-end test** — `workshop-start.yml` supports `instance_count > 1` and generates base64 pool config. Settings page auto-detects. Frontend random-assignment never tested with real CE deploys. Required for >80-user workshops.
- **API key error after copy-paste** (Apr 14 user test) — valid token saved via copy-paste → `InvalidAccountError: Unable to retrieve instances`. Possible whitespace/newline or save_account protection interference.
- **Workshop setup guide update** — `/workshop-setup` references old project name `ce-doqumentation-01`, old sizing, old CLI. Update to current naming (project `doQumentation`, app `jupyter`), stress-test sizing data, current workflow names.
- **Fork testing** — verify the repo can be forked with Binder still working.
- **Raspberry Pi** — `scripts/setup-pi.sh` written, untested on real hardware.
- **IBM Quantum Ecosystem listing** — submit doqumentation.org to https://www.ibm.com/quantum/ecosystem.
- **Video subtitles — 4 missing** — 55/55 fully translated (EN + 17 langs). 4 IBM Video transcripts have no source subtitles (134371939, 134371940, 134371941, 134399598 — guide demos). Use `scripts/video-subtitle-cowork-prompt.md`. Whisper alternative: `pip install openai-whisper yt-dlp` (~5 min/video). Corrections dict in `generate-transcripts.py` (Kisket→Qiskit, Watchras→Watrous). Full status: `.claude/transcript-status.md`.
- **Copy code button** — Docusaurus supports natively via `themeConfig.prism`. May be disabled or hidden by swizzled `CodeBlock` in `src/theme/CodeBlock/`.
- **Review IBM tutorial survey links** — ~40 tutorials still link to IBM's `your.feedback.ibm.com`. `sync-content.py` already appends clarifying note + `<TutorialFeedback />`. Decide whether to further distinguish or strip.
- **i18n PNG deduplication** — translations under `i18n/<loc>/.../qiskit-addons/` still duplicate ~660 PNGs (~3–5 MB) per locale. Git dedupes blobs internally, but working tree grows linearly with locales. If size matters, build plugin or static-routes config to resolve `./output_N.png` from `docs/` when missing from locale.
- **Locale build: 62 MDX compilation failures from missing `static/docs/images/`** — Observed running `npm run build -- --locale de` (May 9 2026): 62 errors of the form `Markdown image with URL '/docs/images/guides/<page>/extracted-outputs/<uuid>.svg' couldn't be resolved`. Pattern is identical across `guides/qiskit-addons-aqc.mdx`, `guides/DAG-representation.mdx`, `guides/build-noise-models.mdx`, `guides/algorithmiq-tem.mdx`, etc. **Pre-existing and unrelated to any recent migration**. **Root cause**: `static/docs/` is gitignored (`.gitignore:42`); `sync_upstream_images()` in `scripts/sync-content.py` populates it from `upstream-docs/public/docs/images/{tutorials,guides}/`. In environments where the `upstream-docs/` submodule has never been initialized AND `sync-content.py` has not been run, those images are absent and the locale build aborts. CI deploy workflows (`deploy.yml`, `deploy-locales.yml`) run sync first so this does not affect production. **Action items**: (a) make `npm run build` fail-fast with a clearer message ("run `python scripts/sync-content.py` first") when `static/docs/images/` is missing, e.g. via a Docusaurus plugin's `loadContent` precondition or a `prebuild` npm script that probes for the dir; (b) consider letting `onBrokenMarkdownImages: 'warn'` apply to locale builds the same way `onBrokenLinks: 'warn'` already does, so a partial local build still completes for review; (c) document the dependency in the README's Development section ("First-time: `git submodule update --init && python scripts/sync-content.py`"). Won't be visible until the next time someone builds locales without a prior sync, but makes onboarding less confusing.

### Recently Resolved

#### May 2026
- **Upstream submodule: fork → Qiskit/documentation direct** (May 15) — `.gitmodules` now tracks `Qiskit/documentation` directly. The fork's submodule pointer (`6f006d7a`, March 10) happens to exist on upstream too (it was a JanLahmann PR landed via upstream's PR flow), so the URL flip leaves the pointer resolvable without any content sync. Sparse-clone fallback in `sync-content.py` flipped too. `_ensure_ibm_history` becomes a no-op when origin is already upstream; the legacy `ibm` remote shim is preserved for any developer checkout still on the fork. Adds `.github/workflows/sync-upstream.yml` (workflow_dispatch only; weekly cron commented out for now) that fetches upstream, advances the submodule, runs `sync-content.py`, gates on `npm run build`, and opens an auto-PR with a freshness report. First dispatch becomes the real "advance the pointer + sync content" PR.
- **Binder cold-build broken + image split** (May 14) — both resolved by switching Binder to QuBins ([JanLahmann/QuBins](https://github.com/JanLahmann/QuBins)), the sibling repo that publishes versioned Qiskit images (`ghcr.io/janlahmann/qiskit:{version}-{small,xl}`) with daily-rebuilt stub branches on mybinder. doQumentation now points `binderUrl` at `mybinder.org/v2/gh/JanLahmann/qubins/2.3-xl`; thebelab and "Open in JupyterLab" both consume it. **nbgitpuller pulls notebooks** at session-launch time from this repo's `notebooks` branch (EN) or the locale's satellite repo's `notebooks` branch (translated). `deploy-locales.yml` gains a step to maintain those satellite branches. Eliminates doQumentation's image-publishing pipeline entirely — no `Dockerfile.jupyter` `jupyter-binder` target, no `binder-kernel` stub branch, no `binder.yml` cache warmer (QuBins owns its own warm-up). Retires the `0fc67252` Apr-13 pin. **Bump in lockstep when doQumentation's Qiskit pin moves** (see TODO above).
- **"Use a quantum computer today" course** (May 7) — new IBM course added via `local-content/` overlay (cherry-pick without modifying the JanLahmann fork). Sidebar 13→14 courses; 102 i18n files (the 2 lessons overlapping with workshop notebooks were seeded from existing workshop translations). Detail: commit log + PR.
- **Index "When you're ready for more" — all 26 locales** (May 5, PRs #12 + #14) — homepage section translated to 17 standard + 9 dialect locales. Dialect translations need native-speaker review.
- **Archive-branch merge `claude/translation-status-review-nal3k`** (May 5, PRs #5–#10) — 6-step staged merge of 662-commit archive, 699 files / +83k −16k lines. KO + PL now 100%. Tags `archive/claude-translation-status-review-nal3k` and `archive/claude-verify-translation-status-ujt0Y` preserve full history.
- **Translation Phase 4 cheap fixes** (May 8) — 619 replacements / 289 files. Honorifics/formal-register cleanup across JA, UK, TL, DE, FR, PT, AR. 12 files re-recorded as FIXED in `status.json`. Detail: `.claude/PHASE_4_LINGUISTIC_TRIAGE_2026-05-07.md`.
- **HE Phase 2 review** (May 8) — 100% reviewed via Sonnet 5-file chunks. 1,448 register/terminology slips fixed via find-replace + 26 surgical accuracy fixes (incl. critical reversals like inverted little-endian description, "encrypt" used for "observe"). HE structural now 412/0. **Lesson:** HE translator had biblical/literary register defaults; find-replace pass made real accuracy issues visible. Detail: `.claude/PHASE_4_LINGUISTIC_TRIAGE_2026-05-07.md`.
- **KO Phase 3 — 100% reviewed** (May 8, commits `cbf1b2016` + `15adcc8a6`) — 414/414. Site-wide deferential-honorific cleanup across 26 files. 383 PASS / 22 MINOR / 5 FAIL (intentional `doqumentation-untranslated-fallback`).
- **TH/PL/CS Phase 3 stratified samples** (May 8) — ~45 files each, 4-wave parallel Sonnet, balanced across sections. TH `ce6071604`: 41/2/1 → 3 fixes incl. swapped CHSH Bell-bound labels. PL `90a81d95c`: 33/11/1 → 6 fixes. CS in flight: 30/13/2 → 2 FAIL fixes. All three locales: zero polite/formal-register slips.

#### Items also resolved (one-liners)
- ✅ **Download notebook option** — "Download ↓" button on `OpenInLabBanner` between Colab and "What's modified?". Links to `/notebooks/{path}.ipynb`. Analytics event `Notebook Download`.
- ✅ **Remove Qamposer** (Apr 24) — deleted `/qamposer` page, `QamposerEmbed/` dir, `@qamposer/react` dep, 11 `qamposer.*` i18n keys × 18 locales, debug scripts.
- ✅ **Workshop mode — single-pod stress testing** (Apr 11–12) — 1/4/8/12 vCPU validated. Final sizing with retries: 8 vCPU/16 GB → 80 users, 0 failures at 5s burst. 12/24 → 80–100. ~6 sessions/vCPU, diminishing >8. Memory never the constraint. `scripts/workshop-stress-test.py`. Fixes: nginx rate limit 5→100/m, kernel cull 600→300s, cgroup-aware `/stats`, SSE shim async refactor (tornado), Jupyter race retries (server `/api/status` + client WS handshake). **Known Jupyter Server 2.16.0 bugs**: `TraitError: 'last_activity'` (server retry absorbs), `AttributeError: NoneType.kernel_ws_protocol` (client retry absorbs), `connections_dict` underflow → kernel cull broken → memory creep (workaround: restart pods between workshops). Full writeup: `.claude/STRESS-TEST-FINDINGS.md`.
- ✅ **GH Actions automations using `IBM_CLOUD_API_KEY`** — smarter `Deploy to Code Engine` (preserves pod size on push), Stress Test workflow (5/10/25/50/80/100/150 users), Resize Pod workflow (1/4 → 12/48 dropdown), Workshop lifecycle (start/monitor/close, monitor independent). Daily Warm Pod skipped per user instruction.
- ✅ **Admin page** — password-protected via build-time SHA-256. `ADMIN_PASSWORD` secret hashed into `customFields.adminPasswordHash`. Web Crypto API client-hashes input, stores in `sessionStorage`. No password = unprotected (local dev). Both `deploy.yml` and `deploy-locales.yml` pass the secret.

---

## Future Ideas

- Auto-discover YouTube mappings (currently 32 static entries).
- LED integration for RasQberry.
- Offline AI tutor (Granite 4.0 Nano).
- "Add Cell" scratch pad (full JupyterLab available as alternative).
- **Qiskit Global Summer School content** — labs from QGSS 2023/2024/2025 (`qiskit-community/qgss-2025` etc.). Curated labs as a "Summer School" section. Version-pinned to specific Qiskit releases — needs compatibility review. See [qgss-2025](https://github.com/qiskit-community/qgss-2025).

---

## Related Resources

- **RasQberry:** https://github.com/JanLahmann/RasQberry-Two
- **Content source (upstream):** https://github.com/Qiskit/documentation
- **Content source (legacy fork):** https://github.com/JanLahmann/Qiskit-documentation
- **IBM Quantum:** https://ibm.com/quantum
- **IBM Quantum Platform:** https://quantum.cloud.ibm.com
- **Docusaurus:** https://docusaurus.io
- **Archived history:** [`PROJECT_HANDOFF_ARCHIVE.md`](./PROJECT_HANDOFF_ARCHIVE.md)

---

## Operational Maturity Workstreams (May 2026 handoff)

Handover from another developer. The platform's core differentiators (open, no-account, multilingual, mobile, CC BY-SA, no server-side proxy) are working well. Next round of work focuses on the **operational layer**: making the platform feel reliable and well-organized for instructors, course authors, and event organizers who want to point their audiences at it.

**Reference target for first deliverables:** QGSS content on GitHub under `qiskit-community` (Apache-2.0) — `qgss-2025`, `qgss-2024`, `qgss-2023`, plus `qgss-2025-lecture-notes`. Structure: `lab-0/` … `lab-4/`, `solutions/`, `community-labs/`, `functions-labs/`, `lecture_supplementary/`. Drop-in compatible with doQumentation's existing notebook execution model.

### Architectural constraints (do not violate)

- No user accounts, no server-side state
- No server-side proxy for IBM Quantum API calls — users authenticate with their own IBM Cloud tokens
- Two backends remain: MyBinder (PoC/demo) and IBM Code Engine (production)

### Workstreams

#### 1. "Launch on doQumentation" badge + URL flow

A GitHub README badge that opens any public notebook repo in doQumentation's execution environment.

```
[![Launch on doQumentation](badge.svg)](https://doqumentation.org/launch?repo=qiskit-community/qgss-2025&path=lab-0/lab0.ipynb&env=qgss-2025)
```

Scope:
- URL pattern: `repo`, `path` (optional, defaults to repo root listing), `env` (optional, references a named environment — see workstream 2), `branch` (optional, defaults to `main`)
- Pull notebook from `raw.githubusercontent.com`
- Spawn CE (or Binder) session with the requested environment
- Open in existing execution UI

Highest distribution leverage of any item here — it lets other people's repos point at us.

#### 2. Named, pinned environments with a public registry

Today the CE image is general-purpose. Move to *named environments* that pin known-good dependency sets so courses don't break when Qiskit ships changes.

Scope:
- Each environment = a public GitHub repo with a Dockerfile and a manifest (name, description, package list, Qiskit version)
- A registry (could be a single repo with one folder per environment, or a JSON index)
- Launch URL references environments by name: `env=qgss-2025`, `env=qiskit-1.x-stable`, `env=qgss-2024`
- Community contributions via PR — no auth needed
- Start with: `qgss-2023`, `qgss-2024`, `qgss-2025`, `qiskit-default`

First concrete addition: QGSS 2025 needs `qiskit`, `qiskit-ibm-runtime`, `qiskit-aer`, `qiskit-addon-sqd`, `pylatexenc`, `matplotlib`. The `qiskit-addon-sqd` is the main delta from current image.

> **Update (May 15, 2026):** [JanLahmann/QuBins](https://github.com/JanLahmann/QuBins) now covers the spirit of this workstream — it publishes versioned Qiskit images (`ghcr.io/janlahmann/qiskit:{1.4..2.4,latest}-{small,xl}`) with mybinder stub branches, daily-rebuilt and Trivy-gated. doQumentation already consumes `qubins/2.3-xl` (PR #52). Workstream 2 reshapes to: use QuBins tags as `env=` values, plus a small JSON registry mapping friendly names (`qgss-2025`) to QuBins tags, and contribute any QGSS-specific dep deltas (e.g. `matplotlib`) back to QuBins.

#### 3. Per-event onboarding pages

Dedicated landing pages for specific cohorts or events, so each audience has a polished entry point rather than landing on generic docs.

Scope:
- Template at `doqumentation.org/events/<event-slug>`
- Per-event: intro, prerequisites, "Launch on doQumentation" buttons for each lab, language toggle, link to original repo, link to lecture notes
- Initial pages: `events/qgss-2025`, `events/qgss-2024`, `events/qgss-2023`, plus a template for upcoming Southeast Asia workshops
- Should be just-MDX, no backend

#### 4. Job status widget for real-hardware runs

When users run cells against real IBM Quantum hardware via their own token, surface job status inline.

Scope:
- Lightweight widget that queries IBM Quantum Runtime API *with the user's own token* (no proxy)
- Shows: job ID, status, queue position, estimated wait, link to IBM Quantum Platform for details
- Renders in notebook or as a sidebar
- Crucially: token stays in the browser, all calls go directly to IBM endpoints — preserves the no-proxy architecture

#### 5. Course-as-structured-path metaphor

Move from flat tutorial lists to explicit learning paths: a course = ordered notebooks with prerequisites and a defined progression.

Scope:
- Course manifest format (YAML or JSON): ordered notebooks, prerequisites, suggested time, optional/required tags
- Course landing page: visual progression, "next/previous" navigation between notebooks
- Progress hints via `localStorage` (no accounts, no server state) — checkmarks, "resume where you left off"
- Convert existing courses to the new format as a migration step

### Suggested sequencing

1. **Workstream 2** (named environments) first — workstream 1 depends on it for the `env=` parameter to mean anything. Now mostly a thin layer over QuBins.
2. **Workstream 1** (launch badge + URL flow) second — unlocks distribution.
3. **Workstream 3** (per-event pages) third — gives 1 and 2 a showcase. Build `events/qgss-2025` as the reference page.
4. **Workstream 5** (course paths) fourth — bigger refactor, less time-sensitive.
5. **Workstream 4** (job status widget) fifth — nice-to-have polish, not blocking other deliverables.

The first three together form a coherent demo: past years of QGSS, runnable in any browser, on any device, in multiple languages, with no signup.

### Out of scope (explicitly do not build)

- User accounts, login, identity
- Persistent per-user notebook state across sessions
- Autograder / submission tracking
- QPU credit management
- Any server-side proxy for IBM Quantum API calls
- Cross-SDK conversion (Cirq, Braket, etc.) — Qiskit-only by design
- AI features beyond the existing multi-tier AI strategy (Granite in-browser default, BYOK watsonx.ai, BYOK Anthropic)

### Open questions

- Environment registry: pure mapping to QuBins tags, or also accept arbitrary Dockerfile-repo entries for projects that need something QuBins doesn't ship?
- Launch URL: should it accept arbitrary GitHub repos, or whitelist `qiskit-community` + a few trusted orgs initially? (Security/abuse consideration.)
- Job status widget: pure-frontend (fetch from IBM Runtime API directly) or Jupyter notebook extension? (Pure-frontend preserves the architecture better.)
- Course manifest: define our own or adopt an existing standard (e.g., Jupyter Book's `_toc.yml`)?

---

*Last updated: May 15, 2026 (added Operational Maturity Workstreams handoff — launch badge, named environments, event pages, job-status widget, course paths)*
