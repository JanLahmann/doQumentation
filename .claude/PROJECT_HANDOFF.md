# doQumentation — Project Handoff

## What is doQumentation

An **open-source website for IBM Quantum's tutorials and learning content**, built as part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) educational quantum computing platform.

All content comes from IBM's open-source [Qiskit documentation](https://github.com/Qiskit/documentation) repository (CC BY-SA 4.0). IBM's web application serving that content is closed-source. doQumentation provides the open-source frontend — adding the website, Binder-based code execution, multiple deployment options, and usability features like automatic credential injection and simulator mode.

**Three deployment tiers:**

| Tier | URL | Code execution |
|------|-----|----------------|
| **GitHub Pages** | [doqumentation.org](https://doqumentation.org) | Remote via [Binder](https://mybinder.org) |
| **Docker** | [ghcr.io/janlahmann/doqumentation](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | Local Jupyter + Qiskit |
| **RasQberry Pi** | `http://rasqberry.local` | Local Jupyter + Qiskit, offline capable |

**Content:** 42 Tutorials, 171 Guides, 154 Course pages, 14 Modules (~380 pages total).

**Live:** [doqumentation.org](https://doqumentation.org) | **Repo:** [JanLahmann/doQumentation](https://github.com/JanLahmann/doQumentation) | **License:** Apache 2.0 (code) + CC BY-SA 4.0 (content)

---

## Architecture Decisions

### Docusaurus 3.x (not Next.js, Hugo)
Purpose-built for documentation. Native MDX, auto-generated sidebar, static export (works offline). IBM's own frontend is Next.js but closed-source.

### thebelab 0.4.x for code execution (not JupyterLite, Voilà)
Connects static HTML to any Jupyter kernel. Minimal client-side code, graceful degradation. JupyterLite won't work (Qiskit has Rust extensions that don't compile to WASM). Must pin to `thebelab@0.4.0` — version 0.4.15 never existed on npm.

### Content transformation (not Docker mirroring)
IBM's Docker preview lacks navigation, search, and is designed for PR reviews. We transform their MDX to Docusaurus MDX (95% compatible) for full control.

### Single codebase, three deployments
Runtime detection handles environment differences. Only the Jupyter endpoint differs (Binder vs localhost vs custom).

---

## Features

### Content Sync
- `scripts/sync-content.py` — Sparse-clones [JanLahmann/Qiskit-documentation](https://github.com/JanLahmann/Qiskit-documentation), transforms MDX, converts notebooks, generates sidebars
- Custom notebook converter (no nbconvert dependency) — extracts cell outputs (images, LaTeX, text), handles `<Image>` JSX in `text/plain`, splits embedded code blocks from markdown cells
- Sidebar generation from upstream `_toc.json` files (guides, courses, modules) — handles external URLs as link items, skips "Lessons"/"Modules" wrapper levels
- Image path rewriting: upstream IBM URLs and `/docs/images/` paths → local `static/` paths
- Link path rewriting: both markdown `(/docs/...)` and JSX `href="/docs/..."` patterns → local or upstream IBM URLs
- Landing page generation: `create_learning_landing_pages()` generates `/learning/` and `/learning/modules/` index pages
- `docs/index.mdx` is preserved (not overwritten) — all other `docs/` content is regenerated
- **Notebook dependency scan** — `analyze_notebook_imports()` scans code cells for `import`/`from` statements at build time. Filters Python stdlib (`sys.stdlib_module_names`) + `BINDER_PROVIDED` set (verified against actual Binder `pip list`). Maps import→pip names via `IMPORT_TO_PIP` (e.g. `sklearn`→`scikit-learn`). Deduplicates against existing `!pip install` in notebooks. Injects `%pip install -q <pkgs>` cell before first code block in 46/260 notebooks. `--scan-deps` flag generates report without converting. On Docker tier, install cells are silent no-ops (all deps pre-installed). Runtime fallback (`ModuleNotFoundError` → Install button) catches any false negatives.

### Code Execution
- `ExecutableCode` component wraps Python code blocks with Run/Back toggle (Run activates cells, Back reverts to static view)
- thebelab 0.4.x bootstraps once per page, shared kernel across all cells
- Environment auto-detection: GitHub Pages → Binder (2i2c.mybinder.org), localhost/rasqberry/Docker → local Jupyter, custom → user-configured
- Cell execution feedback: persistent left border — amber (running), green (done), red (error) + toolbar legend
- Error detection: `detectCellError()` inspects output for `ModuleNotFoundError`, `NameError`, tracebacks → red border + contextual error hints
- Pip install injection: `ModuleNotFoundError` shows clickable "Install {pkg}" button → runs `!pip install -q` on kernel → auto-re-runs cell on success (falls back to static hint if kernel unavailable)
- Back button shows `window.confirm()` dialog if any cells have been executed (prevents accidental output loss)
- Static outputs (from MDX) remain visible alongside live outputs — intentional for comparison
- Dark mode: circuit/output images auto-inverted via CSS `filter: invert(1) hue-rotate(180deg)`
- Code blocks scroll horizontally on overflow (mobile-friendly)
- Warning suppression injected at kernel start (`warnings.filterwarnings('ignore')`)
- "Open in JupyterLab" button on notebook-derived pages (with descriptive tooltip)
- Dismissible Binder package hint after kernel ready (GitHub Pages only, localStorage-persisted dismiss)
- Kernel death detection: `kernelDead` flag set on thebelab `dead`/`failed` status → red border + "Kernel disconnected" hint, prevents misleading green borders
- Back resets all module-level state (`thebelabBootstrapped`, `kernelDead`, listeners) for clean re-bootstrap
- Event listener cleanup: `feedbackCleanupFns[]` prevents memory leaks across page navigations
- thebelab restart buttons hidden (don't integrate with feedback system)
- Toolbar: status only shows for `connecting`/`error` states; legend (running/done/error) indicates active kernel
- URL encoding in `getLabUrl()` prevents XSS via notebook paths
- Execution mode indicator: dynamic toolbar badge shows "AerSimulator"/"FakeSherbrooke" (blue) or "IBM Quantum" (teal) after injection confirmed
- Cell injection feedback: brief green toast ("Simulator active — using AerSimulator" / "IBM Quantum credentials applied") auto-fades after 4s
- Cell completion accuracy: subscribes to `kernel.statusChanged` signal from `@jupyterlab/services` (thebelab 0.4.0 only emits lifecycle events, not busy/idle). Resettable 800ms debounce cancels on each busy transition, preventing premature green borders during multi-phase executions (e.g. matplotlib). Safety-net fallback 60s.

### IBM Quantum Integration
- **Credential store** — API token + CRN saved in localStorage with 7-day auto-expiry. Auto-injected via `save_account()` at kernel start.
- **Simulator mode** — Monkey-patches `QiskitRuntimeService` with `_DQ_MockService` that returns AerSimulator or a FakeBackend. No IBM account needed.
- **Fake backend discovery** — Introspects `fake_provider` at kernel connect, caches available backends in localStorage. Device picker grouped by qubit count.
- **Conflict resolution** — When both credentials and simulator are configured, radio buttons let user choose. Banner shown at kernel connect if no explicit choice (defaults to simulator).

### Learning Progress
Automatic tracking of learning progress across all ~380 pages:
- **Page visit tracking** — `src/clientModules/pageTracker.ts` (Docusaurus client module) auto-records every page visit via `onRouteDidUpdate`. All localStorage access centralized in `src/config/preferences.ts`.
- **Sidebar indicators** — Swizzled `DocSidebarItem/Link`: clickable checkmark (✓ visited) or play icon (▶ executed). Swizzled `DocSidebarItem/Category`: aggregate badge ("3/10") showing visited/total leaf pages. Both use custom event `dq:page-visited` for real-time updates across client-side navigation.
- **Granular clearing** — Per page (click indicator), per section (click category badge uses `commonPrefix()` of leaf hrefs), per category (Settings page), all at once (Settings page).
- **Resume reading** — `ResumeCard` component on homepage shows "Continue where you left off" with last page title + time ago. Only appears for returning visitors.
- **Execution tracking** — `markPageExecuted()` called on Run button in ExecutableCode. Visual distinction in sidebar (▶ vs ✓).

### Bookmarks
- **Bookmark toggle** — Swizzled `DocItem/Footer` adds a star button (☆/★) below every doc page. Click toggles bookmark state, dispatches `dq:bookmarks-changed` custom event.
- **Homepage widget** — `BookmarksList` component renders bookmarked pages with remove buttons. Only shows if bookmarks exist. Listens for `dq:bookmarks-changed` for live updates.
- **Storage** — `dq-bookmarks` (JSON array of `{path, title, savedAt}`), max 50 bookmarks (FIFO if exceeded).
- **Settings** — "Bookmarks" subsection shows count + "Clear all bookmarks" button.

### Display Preferences
- **Code font size** — Adjustable 10–22px via `--dq-code-font-size` CSS custom property. Applied by `src/clientModules/displayPrefs.ts` on page load. Live-updates via `dq:display-prefs-changed` custom event. Affects both `.prism-code` (static) and `.thebelab-cell .CodeMirror` (live) blocks.
- **Hide static outputs** — When enabled and in Run mode, `ExecutableCode` adds `dq-hide-static-outputs` class to `<body>`. CSS sibling selectors hide `pre`, `img`, `.output_png` elements that follow `.executable-code` divs. Static outputs reappear on Back.
- **Storage** — `dq-code-font-size` (number), `dq-hide-static-outputs` (boolean).
- **Settings** — "Display Preferences" section with +/– font size controls (live preview code block) and hide-outputs toggle.

### Onboarding Tips
- **Client module** — `src/clientModules/onboarding.ts` injects a contextual tip bar at the top of `.theme-doc-markdown` for first-time visitors.
- **Contextual messages** — Notebook pages (with `.executable-code`): "Click Run to execute code blocks. First run starts a free Jupyter kernel (1–2 min)." Other content pages: "Track your progress — visited pages show ✓ in the sidebar."
- **Auto-completion** — Tips auto-dismiss after 3 page visits or manual dismiss (× button).
- **Storage** — `dq-onboarding-completed` (boolean), `dq-onboarding-visit-count` (number).
- **Settings** — "Reset onboarding tips" button in Other section.

### Recently Viewed Pages
- **Tracking** — `pageTracker.ts` calls `addRecentPage(path, title)` on every route change. Last 10 pages stored, deduplicated (move to front on revisit). Excludes homepage and settings.
- **Homepage widget** — `RecentPages` component shows last 5 pages (skipping current) with relative timestamps ("2 hours ago"). Only renders if recent pages exist.
- **Storage** — `dq-recent-pages` (JSON array of `{path, title, ts}`, capped at 10).
- **Settings** — "Clear recent history" button in Other section.

### Sidebar Collapse Memory
- **Approach** — Extended existing `DocSidebarItem/Category` swizzle with MutationObserver. Watches `.menu__list-item` class changes (Docusaurus toggles `--collapsed` class).
- **Restore on mount** — Reads saved state from localStorage. If it differs from current DOM state, programmatically clicks the collapsible header to toggle.
- **Storage** — `dq-sidebar-collapsed` (JSON object `{categoryLabel: boolean}`).
- **Graceful degradation** — If Docusaurus changes its DOM structure, the observer silently fails and sidebar reverts to default behavior.
- **Settings** — "Reset sidebar layout" button in Other section.

### User Preferences — localStorage Keys
All user preferences are centralized in `src/config/preferences.ts` with SSR guards. `clearAllPreferences()` clears all keys.

| Key | Type | Feature |
|-----|------|---------|
| `dq-visited-pages` | JSON set | Learning progress |
| `dq-executed-pages` | JSON set | Learning progress |
| `dq-last-page` | JSON `{path, title, ts}` | Resume reading |
| `dq-binder-hint-dismissed` | boolean | Binder hint |
| `dq-onboarding-completed` | boolean | Onboarding tips |
| `dq-onboarding-visit-count` | number (0–3) | Onboarding tips |
| `dq-bookmarks` | JSON array `{path, title, savedAt}` | Bookmarks (max 50) |
| `dq-code-font-size` | number (10–22) | Display preferences |
| `dq-hide-static-outputs` | boolean | Display preferences |
| `dq-sidebar-collapsed` | JSON object `{label: boolean}` | Sidebar collapse |
| `dq-recent-pages` | JSON array `{path, title, ts}` | Recent pages (max 10) |

Custom events for cross-component reactivity: `dq:page-visited`, `dq:bookmarks-changed`, `dq:display-prefs-changed`.

### Settings Page (`/jupyter-settings` — "doQumentation Settings")
Sections: IBM Quantum Account (5-step setup guide with direct links) → Simulator Mode (with hardware-difference note) → Display Preferences (code font size +/– controls with live preview, hide static outputs toggle) → Learning Progress (stats + clear buttons) → Bookmarks (count + clear button) → Binder Packages → Other (reset onboarding, clear recent history, reset sidebar layout) → Advanced (Custom Server + Setup Help)

### MDX Components
IBM's custom components mapped to Docusaurus equivalents:

| IBM Component | Solution |
|---------------|----------|
| `<Admonition>` | `@theme/Admonition` (NOT `:::` directives — breaks nesting in `<details>`) |
| `<Tabs>` / `<TabItem>` | Native Docusaurus |
| Math `$...$` `$$...$$` | KaTeX plugin + `text/latex` MIME handling |
| `<IBMVideo>` | YouTube-first (32 mapped IDs) + IBM Video Streaming fallback |
| `<DefinitionTooltip>`, `<Figure>`, `<LaunchExamButton>` | Course component stubs |
| `<Card>`, `<CardGroup>`, `<OperatingSystemTabs>`, `<CodeAssistantAdmonition>` | Guide component stubs |
| `<Image>` | Fallback `<img>` component |

### Docker
- `Dockerfile` — Static site only (nginx, ~60 MB)
- `Dockerfile.jupyter` — Full stack: site + Jupyter + Qiskit (~3 GB)
- Multi-arch: `linux/amd64` gets full Qiskit; `linux/arm64` excludes gem-suite, kahypar, ai-local-transpiler
- CI pushes to ghcr.io (`:latest` and `:jupyter` tags)

### Jupyter Authentication
Token-based authentication for Docker and RasQberry tiers. nginx injects the `Authorization` header server-side — the browser never sees or handles the token.

**Architecture:**
```
Browser --(no token)--> nginx:80 --(Authorization: token <TOKEN>)--> Jupyter:8888
```

**Per tier:**
- **GitHub Pages** — Uses Binder, no token involved
- **Docker** — `scripts/docker-entrypoint.sh` generates a random token at startup (or accepts `JUPYTER_TOKEN` env var). nginx injects it into `/api/` and `/terminals/` proxy requests via `# __JUPYTER_AUTH__` placeholder replacement. Website on port 8080 works transparently. Direct JupyterLab on port 8888 requires the token.
- **RasQberry Pi** — `scripts/setup-pi.sh` generates a random token at setup time, printed to the user

**Security model:**
- Jupyter runs as non-root `jupyter` user (not root)
- `disable_check_xsrf = True` stays because thebelab 0.4.0 can't send XSRF cookies — the token header is the security boundary (injected server-side, not in a browser cookie, so CSRF attacks can't include it)
- Token is printed to container stdout only, never stored in image layers or sent to browser

**Customization:** `JUPYTER_TOKEN=mytoken docker compose --profile jupyter up`

### CI/CD
- `deploy.yml` — Sync content → build (with `NODE_OPTIONS="--max-old-space-size=8192"`) → deploy to GitHub Pages
- `docker.yml` — Multi-arch Docker build → ghcr.io
- `sync-deps.yml` — Weekly auto-PR syncing Jupyter dependencies from upstream (with architecture exception rules)
- Binder repo has separate daily build workflow to keep 2i2c cache warm

### Homepage
Hero banner: "doQumentation" title + one-liner subtitle ("adds a feature-rich, user-friendly, open-source frontend to IBM Quantum's complete open-source tutorials, courses, and documentation library") + clickable content stats bar (42 / 171 / 154 / 14) inside hero. Below hero: "IBM Quantum's open-source content" (factual) → "What this project adds" (open-source frontend) → "Deployable anywhere" line + "See all features" link. Simulator callout card in "Getting started" section ("No IBM Quantum account? Enable Simulator Mode..."). Featured full-width "Basics of QI" course card + Hello World guide + 3 tutorial cards. Audience guidance intro sentence. "Code execution" section: step 1 (Run code) then simulator-first bullet alternatives (Simulator Mode / IBM Quantum Hardware). Three `<details>` blocks: "Available execution backends", "Deployment options", "Run locally with Podman / Docker" (Podman-first commands). Links to browse all Guides + CS/QM modules. Mobile responsive.

### Features Page
`src/pages/features.tsx` — standalone React page at `/features` showcasing all implemented features in 5 card-grid sections: Content Library (3 cards), Live Code Execution (6 cards), IBM Quantum Integration (4 cards), Learning & Progress (3 cards), Search/UI/Deployment (6 cards). Responsive grid: 3 columns on desktop, 2 tablet, 1 mobile. Linked from homepage ("See all features") and footer. Not in navbar.

### Search
`@easyops-cn/docusaurus-search-local` — client-side search across all ~380 pages. Hashed index, no blog indexing, routes from `/`.

### Landing Pages
`/learning/` and `/learning/modules/` auto-generated by `create_learning_landing_pages()` in `sync-content.py`. Lists all courses and modules with links. Regenerated on each content sync.

### Styling
Carbon Design-inspired: IBM Plex fonts, `#0f62fe` blue. Mobile hamburger menu with visible border/background. Top-level sidebar categories styled at 1.1rem/semibold. Navbar is always dark (`#161616`) regardless of theme — color mode toggle and GitHub icon forced to light colors via CSS. GitHub link uses octocat SVG icon (`header-github-link` class). Navbar links use `white-space: nowrap` to prevent wrapping at medium widths.

---

## Project Structure

```
doQumentation/
├── .github/workflows/
│   ├── deploy.yml                # Sync → build → deploy to GitHub Pages
│   ├── docker.yml                # Multi-arch Docker → ghcr.io
│   └── sync-deps.yml             # Weekly Jupyter dependency sync auto-PR
│
├── binder/
│   ├── jupyter-requirements.txt       # Full Qiskit deps (cross-platform)
│   └── jupyter-requirements-amd64.txt # amd64-only extras
│
├── docs/                          # Content (gitignored except index.mdx)
│   ├── index.mdx                  # Homepage (source of truth, preserved by sync)
│   ├── tutorials/                 # 42 tutorial pages (generated)
│   ├── guides/                    # 171 guide pages (generated)
│   └── learning/                  # 154 course + 14 module pages (generated)
│
├── notebooks/                     # Original .ipynb for JupyterLab (generated)
│
├── src/
│   ├── clientModules/
│   │   ├── pageTracker.ts         # Auto-tracks page visits + recent pages, dispatches dq:page-visited
│   │   ├── displayPrefs.ts        # Applies code font size CSS variable on load, listens for changes
│   │   └── onboarding.ts          # Injects contextual tip bar for first-time visitors
│   │
│   ├── components/
│   │   ├── ExecutableCode/        # Run/Back toggle, thebelab, kernel injection
│   │   │   └── index.tsx
│   │   ├── ResumeCard/            # "Continue where you left off" homepage card
│   │   │   └── index.tsx
│   │   ├── RecentPages/           # Recently viewed pages widget for homepage
│   │   │   └── index.tsx
│   │   ├── BookmarksList/         # Bookmarked pages list for homepage
│   │   │   └── index.tsx
│   │   ├── CourseComponents/      # DefinitionTooltip, Figure, IBMVideo, LaunchExamButton
│   │   ├── GuideComponents/       # Card, CardGroup, OperatingSystemTabs, CodeAssistantAdmonition
│   │   └── OpenInLabBanner/       # "Open in JupyterLab" banner
│   │       └── index.tsx
│   │
│   ├── config/
│   │   ├── jupyter.ts             # Environment detection, credential/simulator storage
│   │   └── preferences.ts         # Learning progress, visited/executed pages, user preferences
│   │
│   ├── css/
│   │   └── custom.css             # All styling (Carbon-inspired + homepage + settings)
│   │
│   ├── pages/
│   │   ├── features.tsx           # Features page (card-grid showcase of all features)
│   │   └── jupyter-settings.tsx   # Settings page (IBM credentials, simulator, custom server)
│   │
│   └── theme/
│       ├── CodeBlock/index.tsx    # Swizzle: wraps Python blocks with ExecutableCode
│       ├── DocItem/
│       │   └── Footer/index.tsx   # Swizzle: bookmark toggle button (☆/★)
│       ├── DocSidebarItem/
│       │   ├── Category/index.tsx # Swizzle: progress badge + sidebar collapse memory
│       │   └── Link/index.tsx     # Swizzle: visited ✓ / executed ▶ indicators
│       └── MDXComponents.tsx      # IBM component stubs + RecentPages, BookmarksList
│
├── scripts/
│   ├── sync-content.py            # Pull & transform content from upstream
│   ├── sync-deps.py               # Sync Jupyter deps with arch exception rules
│   ├── docker-entrypoint.sh       # Docker runtime: token generation, Jupyter config, nginx patching
│   └── setup-pi.sh               # Raspberry Pi setup (untested)
│
├── static/
│   ├── img/logo.svg               # Quantum circuit logo
│   ├── CNAME                      # GitHub Pages custom domain (excluded from containers)
│   ├── robots.txt                 # SEO: allow all + sitemap reference
│   ├── docs/                      # Synced images (gitignored)
│   └── learning/images/           # Synced course/module images (gitignored)
│
├── Dockerfile                     # Static site only (nginx)
├── Dockerfile.jupyter             # Full stack: site + Jupyter + Qiskit
├── docker-compose.yml             # web + jupyter services
├── nginx.conf                     # SPA routing + Jupyter proxy
├── docusaurus.config.ts           # Site config (URLs, thebe script, KaTeX, search, custom fields)
├── sidebars.ts                    # Navigation (imports generated sidebar JSONs)
├── package.json
├── tsconfig.json
└── README.md
```

**Generated at build time (gitignored):** `docs/tutorials/`, `docs/guides/`, `docs/learning/`, `notebooks/`, `static/docs/`, `static/learning/images/`, `sidebar-generated.json`, `sidebar-guides.json`, `sidebar-courses.json`, `sidebar-modules.json`

---

## Development

```bash
npm install                        # Install dependencies
npm start                          # Dev server (hot reload)
npm run build                      # Production build
python scripts/sync-content.py     # Sync all content from upstream
python scripts/sync-content.py --sample-only  # Sample content only (for testing)
npm run typecheck                  # Type check
```

**Build requires** `NODE_OPTIONS="--max-old-space-size=8192"` for ~380 pages.

### Deployment

**GitHub Pages** — Automatic on push to main. Custom domain via `static/CNAME` + IONOS DNS.

**Docker:** Services use profiles (mutually exclusive — they share port 8080):
```bash
podman compose --profile web up       # Static site only → http://localhost:8080
podman compose --profile jupyter up   # Full stack → http://localhost:8080 (site) + :8888 (JupyterLab)
JUPYTER_TOKEN=mytoken podman compose --profile jupyter up  # Fixed token
```
Both have `restart: unless-stopped` and HEALTHCHECK. The jupyter service generates a random authentication token at startup (printed in logs). Website access on port 8080 is transparent (nginx injects the token). Direct JupyterLab on port 8888 requires the token.

**Raspberry Pi** — `scripts/setup-pi.sh` (written but untested on actual hardware).

### Dependencies

- **Runtime:** Docusaurus 3.x, React 18, remark-math + rehype-katex, @easyops-cn/docusaurus-search-local, thebelab 0.4.x (CDN)
- **Build:** Node.js 18+, Python 3.9+ (sync scripts)
- **Binder repo:** [JanLahmann/Qiskit-documentation](https://github.com/JanLahmann/Qiskit-documentation) — deps in `binder/requirements.txt` (qiskit[visualization], qiskit-aer, qiskit-ibm-runtime, pylatexenc, qiskit-ibm-catalog, qiskit-addon-utils, pyscf), daily cache-warming workflow

---

## Gotchas

- **thebelab CDN pin** — Must use `thebelab@0.4.0`. Versions jump 0.4.0 → 0.5.0. Do not "upgrade" to 0.4.15 (doesn't exist).
- **sync-content.py overwrites docs/** — Only `docs/index.mdx` is preserved. Edit transforms in `sync-content.py`, not the generated MDX.
- **Admonition JSX vs directives** — Don't convert `<Admonition>` to `:::` directives. Breaks nesting inside `<details>`.
- **Build memory** — ~380 pages needs `NODE_OPTIONS="--max-old-space-size=8192"`.
- **Docusaurus `foo/foo.mdx` collision** — If filename matches parent dir, Docusaurus treats it as category index. Fix: add `slug: "./{name}"` in frontmatter.
- **MDX language prop** — MDX passes language via `className="language-python"` not `language` prop. CodeBlock swizzle must check both.
- **`static/CNAME`** — GitHub Pages only. Must be excluded from container builds.
- **thebelab config** — Pass options directly to `bootstrap(options)`. Do NOT inject `<script type="text/x-thebe-config">`.
- **Binder cache** — Keyed to commit hash. Any push to Binder repo invalidates 2i2c cache. Daily workflow keeps it warm.
- **Notebook `<Image>` in text/plain** — IBM's build replaces cell outputs with `<Image src="..." />` JSX. Our `_text_to_output()` detects and converts to markdown images.
- **Guide _toc.json external URLs** — Some entries point to GitHub, PyPI, etc. `toc_children_to_sidebar()` handles as `{type: 'link'}` items.
- **sidebar-*.json** — Build artifacts, gitignored. Generated by `sync-content.py`.
- **JSX `href` in upstream MDX** — Card/CardGroup components use `href="/docs/..."` not markdown links. `MDX_TRANSFORMS` has both markdown `(/docs/...)` and JSX `href="/docs/..."` rewrite rules.

---

## Open Items

### TODO
- ~~**Features page**~~ — DONE. `/features` page with 22 feature cards across 5 sections. Linked from homepage + footer.
- **Fork testing** — Verify the repo can be forked with Binder still working. May need a forked upstream repo as well to avoid hitting Binder user limits.
- ~~**Notebook dependency scan**~~ — DONE. `analyze_notebook_imports()` in `sync-content.py` scans 260 notebooks, filters stdlib + Binder baseline (verified from actual `pip list`), injects `%pip install -q` cells into 46 affected notebooks. 28 unique missing packages. Expanded upstream Binder baseline with qiskit-ibm-catalog, qiskit-addon-utils, pyscf (freed 16 notebooks). Report at `.claude/notebook-deps-report.md`.
- ~~**Jupyter token auth**~~ — DONE. `docker-entrypoint.sh` generates random token at startup, nginx injects `Authorization` header server-side. Jupyter runs as non-root `jupyter` user. Covers code review S1, S2, #1, #9.
- ~~**Code review**~~ — DONE. Full review at `.claude/code-review-2026-02-08.md` (20 issues + 2 security findings). Fixed: #4 heredoc injection, #5 docker-compose profiles, #7 localStorage `safeSave()`, #10 random token, #11/#12 nginx headers, #15 DEBUG-gated console.log, #18 HEALTHCHECK, #19 restart policies, #20 sidebar types. Previously fixed in website review: #2, #3, #6. Non-issues: #8, #13, #14. Skipped: #16, #17. Remaining S1/S2/#1/#9 deferred to Jupyter token auth plan.
- ~~**Website review**~~ — DONE. Full review at `.claude/website-review-2026-02-10.md` (41 issues across 6 sessions). All actionable items fixed in rounds 1-4. Round 4 (133911b): #15 thebelab button overflow CSS, #19 copy button visibility CSS, #24 mobile sidebar tap targets CSS, #28 contextual alt text (sync-content.py + ExecutableCode), #37 H4→H3 heading fix (sync-content.py), #41 Prism languages + untagged code block tagging (docusaurus.config.ts + sync-content.py).
- **Homepage refinement** — Hero done (775dd83). Getting started cards could better represent each content category.

### Needs Testing
- **Raspberry Pi deployment** — `scripts/setup-pi.sh` written but untested on actual hardware

### Future Ideas
- **Auto-discover YouTube mappings** — `YOUTUBE_MAP` in `IBMVideo.tsx` is static (32 entries). New videos work without this (IBM embed fallback).
- **LED Integration** — Could tutorials trigger LED visualizations on RasQberry?
- **Offline AI Tutor** — Granite 4.0 Nano for offline Q&A about tutorials?

---

## Related Resources

- **RasQberry:** https://github.com/JanLahmann/RasQberry-Two
- **Content source (fork):** https://github.com/JanLahmann/Qiskit-documentation
- **IBM Quantum:** https://quantum.cloud.ibm.com
- **Docusaurus:** https://docusaurus.io
- **Thebe:** https://thebe.readthedocs.io

---

*Last updated: February 11, 2026*
