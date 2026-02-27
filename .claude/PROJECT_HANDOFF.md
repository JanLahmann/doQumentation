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

- **Docusaurus 3.x** (not Next.js, Hugo) — Purpose-built for documentation. Native MDX, auto-generated sidebar, static export. IBM's frontend is Next.js but closed-source.
- **thebelab 0.4.x** (not JupyterLite, Voilà) — Connects static HTML to any Jupyter kernel. JupyterLite won't work (Qiskit has Rust extensions). Must pin to `thebelab@0.4.0` — 0.4.15 doesn't exist on npm.
- **Content transformation** (not Docker mirroring) — IBM's Docker preview lacks navigation/search. We transform their MDX to Docusaurus MDX (95% compatible).
- **Single codebase, three deployments** — Runtime detection handles environment differences. Only the Jupyter endpoint differs.

---

## Features

### Content Sync (`scripts/sync-content.py`)
- Sparse-clones [JanLahmann/Qiskit-documentation](https://github.com/JanLahmann/Qiskit-documentation), transforms MDX, converts notebooks (custom converter, no nbconvert), generates sidebars from `_toc.json`
- Rewrites image paths (IBM URLs → local `static/`) and link paths (markdown `(/docs/...)` + JSX `href="/docs/..."` → local or upstream)
- `docs/index.mdx` is preserved — all other `docs/` content is regenerated on each sync
- **Dependency scan**: `analyze_notebook_imports()` injects `%pip install -q` cells into 46/260 notebooks missing packages. `--scan-deps` flag for report only.
- **Custom Hello World**: `hello-world.ipynb` from fork root imported as first tutorial with custom `OpenInLabBanner` description

### Code Execution (`src/components/ExecutableCode/index.tsx`)
- `ExecutableCode` wraps Python code blocks with Run/Back toggle. thebelab bootstraps once per page, shared kernel.
- Environment auto-detection: GitHub Pages → Binder, localhost/Docker → local Jupyter, custom → user-configured
- Cell feedback: amber (running), green (done), red (error) left borders. Error detection for `ModuleNotFoundError` (with clickable Install button), `NameError`, tracebacks.
- Cell completion uses `kernel.statusChanged` signal (not thebelab events) with 1500ms debounce to avoid premature green borders
- Execution mode indicator badge + injection toast. "Open in JupyterLab" button on all tiers.
- **Interception transparency**: All kernel modifications print `[doQumentation]` messages (simulator intercepts, credential injection, warning suppression, pip install cells)
- **save_account() protection**: Blue "Skip this cell" banners when credentials/simulator active, prevents overwriting injected values

### IBM Quantum Integration (`src/config/jupyter.ts`)
- **Credentials** — API token + CRN in localStorage with adjustable auto-expiry (1/3/7 days). Auto-injected at kernel start. Embedded execution only.
- **Simulator mode** — Monkey-patches `QiskitRuntimeService` with `_DQ_MockService` (AerSimulator or FakeBackend). Fake backend discovery cached in localStorage, 55-backend fallback list.
- **Conflict resolution** — Radio buttons when both configured; defaults to simulator.

### User Preferences
All localStorage access centralized in `src/config/preferences.ts` (SSR guards, `clearAllPreferences()`). Cross-component reactivity via custom events: `dq:page-visited`, `dq:bookmarks-changed`, `dq:display-prefs-changed`.

- **Learning progress** — Auto-tracks visits (`pageTracker.ts`). Sidebar indicators: ✓ visited, ▶ executed (swizzled `DocSidebarItem`). Category badges ("3/10"). Resume card on homepage. Granular clearing per page/section/category.
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

### MDX Components

| IBM Component | Solution |
|---------------|----------|
| `<Admonition>` | `@theme/Admonition` (NOT `:::` — breaks in `<details>`) |
| `<Tabs>` / `<TabItem>` | Native Docusaurus |
| Math `$...$` `$$...$$` | KaTeX plugin |
| `<IBMVideo>` | YouTube-first (32 mapped IDs) + IBM fallback |
| `<Card>`, `<CardGroup>`, `<Image>`, etc. | Component stubs |

### Docker & Authentication
- `Dockerfile` — Static site only (nginx, ~60 MB). `Dockerfile.jupyter` — Full stack (~3 GB).
- Multi-arch: `linux/amd64` gets full Qiskit; `linux/arm64` excludes some packages
- **Jupyter auth**: nginx injects `Authorization` header server-side. Browser never sees token. `docker-entrypoint.sh` generates random token (or accepts `JUPYTER_TOKEN` env var). Jupyter runs as non-root `jupyter` user.

### CI/CD
- `deploy.yml` — Sync → build → GitHub Pages (English only)
- `deploy-locales.yml` — Matrix build per locale → push to satellite repos (DE/ES/UK subdomains)
- `docker.yml` — Multi-arch Docker → ghcr.io
- `sync-deps.yml` — Weekly auto-PR for Jupyter dependencies
- Binder repo: daily cache-warming workflow

### Other
- **Homepage**: Hero with stats bar, Getting Started cards (category-tagged), simulator callout, code execution section. No sidebar (homepage doc removed from sidebar config).
- **Features page**: `/features` — 22 cards across 5 sections
- **Search**: `@easyops-cn/docusaurus-search-local` — client-side, hashed index
- **Settings page** (`/jupyter-settings`): IBM credentials, simulator mode, display prefs, progress, bookmarks, custom server
- **Navbar**: Always dark (`#161616`). Right-side icons: locale (globe), settings (gear), dark mode, GitHub (octocat) — all icon-only on desktop (text hidden via `font-size: 0` + `::before` SVG). CSS `order` positions auto-placed dark mode toggle and search bar. Mobile sidebar header swizzled (`Navbar/MobileSidebar/Header`) with matching icon row.
- **Styling**: Carbon Design-inspired (IBM Plex, `#0f62fe`).

---

## Project Structure

```
doQumentation/
├── .github/workflows/          # deploy, deploy-locales, docker, sync-deps
├── binder/                     # Jupyter requirements (cross-platform + amd64-only)
├── docs/                       # Content (gitignored except index.mdx)
├── notebooks/                  # Original .ipynb for JupyterLab (generated)
├── src/
│   ├── clientModules/          # pageTracker, displayPrefs, onboarding
│   ├── components/             # ExecutableCode, ResumeCard, RecentPages, BookmarksList, OpenInLabBanner, CourseComponents, GuideComponents
│   ├── config/                 # jupyter.ts (env detection, credentials), preferences.ts (localStorage)
│   ├── css/custom.css          # All styling
│   ├── pages/                  # features.tsx, jupyter-settings.tsx
│   └── theme/                  # Swizzled: CodeBlock, DocItem/Footer, EditThisPage, DocSidebarItem/{Category,Link}, Navbar/MobileSidebar/Header, MDXComponents
├── i18n/                       # Translations: de (79), es (55), uk (55), fr/it/pt (44 each), ja (59), tl (8)
├── scripts/                    # sync-content.py, sync-deps.py, translate-content.py, docker-entrypoint.sh, setup-pi.sh
├── static/                     # logo.svg (favicon), CNAME, robots.txt, docs/ + learning/images/ (gitignored)
├── Dockerfile                  # Static site only
├── Dockerfile.jupyter          # Full stack
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
- **Binder cache** — Keyed to commit hash. Any push to Binder repo invalidates cache.
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
| DE | [de.doqumentation.org](https://de.doqumentation.org) | 79 + UI | Live |
| ES | [es.doqumentation.org](https://es.doqumentation.org) | 55 + UI | Live |
| UK | [uk.doqumentation.org](https://uk.doqumentation.org) | 55 + UI | Live |
| FR | [fr.doqumentation.org](https://fr.doqumentation.org) | 44 + UI | Configured |
| IT | [it.doqumentation.org](https://it.doqumentation.org) | 44 + UI | Configured |
| PT | [pt.doqumentation.org](https://pt.doqumentation.org) | 44 + UI | Configured |
| JA | [ja.doqumentation.org](https://ja.doqumentation.org) | 59 + UI | Configured |
| TL | [tl.doqumentation.org](https://tl.doqumentation.org) | 8 + UI | Configured |
| AR | [ar.doqumentation.org](https://ar.doqumentation.org) | 44 + UI | Configured (RTL) |
| HE | [he.doqumentation.org](https://he.doqumentation.org) | 9 + UI | Configured (RTL) |

- **Config**: `docusaurus.config.ts` — `locales: ['en', 'de', 'es', 'uk', 'fr', 'it', 'pt', 'ja', 'tl', 'ar', 'he']`, per-locale `url` in `localeConfigs`, `DQ_LOCALE_URL` env var. Built-in `LocaleDropdown` handles cross-domain links natively. hreflang tags auto-generated.
- **RTL support**: AR and HE have `direction: 'rtl'` in `localeConfigs`. CSS uses logical properties (`border-inline-start`, `margin-inline-start`, `inset-inline-end`) throughout — direction-agnostic for both LTR and RTL. Noto Sans Arabic/Hebrew fonts loaded via Google Fonts. `[dir="rtl"]` overrides in `custom.css`.
- **CI**: `deploy.yml` builds EN only (`--locale en`). `deploy-locales.yml` matrix builds all 10 locales separately, pushes to satellite repos via SSH deploy keys (`DEPLOY_KEY_{DE,ES,UK,FR,IT,PT,JA,TL,AR,HE}`).
- **Satellite repos**: `JanLahmann/doQumentation-{de,es,uk,fr,it,pt,ja,tl,ar,he}` — each has `main` branch (README + LICENSE + LICENSE-DOCS + NOTICE) and `gh-pages` branch (build output). GitHub Pages + custom domains configured.
- **Fallback system**: `populate-locale` fills untranslated pages with English + "not yet translated" banner. ~372 fallbacks per locale. 11 banner templates defined in `scripts/translate-content.py`.
- **Translation**: `.claude/translation-prompt.md` — Sonnet model, 1 file/agent, 20+ parallel agents. One-liner: `Read .claude/translation-prompt.md. Translate all untranslated pages to French (fr).`
- **Heading anchors**: Translated headings get `{#english-anchor}` pins to preserve cross-reference links. `scripts/fix-heading-anchors.py` for batch fixing.
- **Build**: ~320 MB per single-locale build. Each fits GitHub Pages 1 GB limit independently.
- **Attribution**: `NOTICE` file in main repo and all satellite repos credits IBM/Qiskit as upstream content source. `LICENSE` (Apache 2.0) + `LICENSE-DOCS` (CC BY-SA 4.0) included in all repos and CI deploy output.

### How to Add a New Language

#### 1. UI strings (4 files)

Generate templates, then translate all `"message"` values:

```bash
npm run write-translations -- --locale {XX}
```

This creates `i18n/{XX}/code.json` and `i18n/{XX}/docusaurus-plugin-content-docs/current.json`. Then create:

- `i18n/{XX}/code.json` — buttons, search placeholder, "Next"/"Previous", custom text (~200 strings)
- `i18n/{XX}/docusaurus-plugin-content-docs/current.json` — sidebar category labels (~60 strings)
- `i18n/{XX}/docusaurus-theme-classic/navbar.json` — navbar items (Tutorials, Guides, Courses, etc.)
- `i18n/{XX}/docusaurus-theme-classic/footer.json` — footer labels + copyright disclaimer

Use `i18n/de/` as reference for all files.

#### 2. Banner template

Add a `{XX}` entry to `BANNER_TEMPLATES` in `scripts/translate-content.py` — an admonition with "This page has not been translated yet" in the target language.

#### 3. Config (`docusaurus.config.ts`)

- Add locale to `locales` array
- Add entry to `localeConfigs` with `label` and `url: 'https://{XX}.doqumentation.org'`
- Add to search plugin `language` array (if [`lunr-languages`](https://github.com/MihaiValentin/lunr-languages) supports it — currently no support for `uk` or `tl`)

#### 4. CI matrix (`deploy-locales.yml`)

Add entry to the matrix:
```yaml
- locale: {XX}
  repo: JanLahmann/doqumentation-{XX}
```

#### 5. Satellite repo + deploy infrastructure

```bash
# Create satellite repo (public, empty)
gh repo create JanLahmann/doqumentation-{XX} --public

# Initialize main branch with README + licenses
# (see existing satellite repos for README template)
# Push LICENSE, LICENSE-DOCS, NOTICE, README.md

# Initialize gh-pages branch
git checkout --orphan gh-pages
echo "<h1>Deploying...</h1>" > index.html
echo "{XX}.doqumentation.org" > CNAME
git add -A && git commit -m "Init gh-pages" && git push origin gh-pages

# Generate SSH deploy key
ssh-keygen -t ed25519 -C "deploy-doqumentation-{XX}" -f deploy_key_{XX} -N ""
# Public key → deploy key (write access) on satellite repo
# Private key → secret DEPLOY_KEY_{XX} on main repo (uppercase locale)

# Enable GitHub Pages: source gh-pages, custom domain {XX}.doqumentation.org, HTTPS enforced
```

DNS: The wildcard CNAME `*` → `janlahmann.github.io` at IONOS covers all subdomains automatically. No per-locale DNS needed.

#### 6. Translate content

```bash
# Translate pages (via Claude Code — see .claude/translation-prompt.md)
Read .claude/translation-prompt.md. Translate all untranslated pages to {LANGUAGE} ({XX}).

# Populate English fallbacks for untranslated pages
python scripts/translate-content.py populate-locale --locale {XX}

# Fix heading anchors
python scripts/fix-heading-anchors.py --locale {XX} --apply

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
- **"Open in Google Colab" button** — Fallback for when Binder is unavailable. URL scheme: `colab.research.google.com/github/{owner}/{repo}/blob/{branch}/{path}`. Note: Colab lacks Qiskit pre-installed.
- **Translation expansion** — DE at 79/387, ES/UK at 55/387, others tutorials only. Use `.claude/translation-prompt.md` (Sonnet, 20+ parallel agents, 1 file each).
- **Fork testing** — Verify the repo can be forked with Binder still working
- **Raspberry Pi** — `scripts/setup-pi.sh` written but untested on actual hardware

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
- **IBM Quantum:** https://quantum.cloud.ibm.com
- **Docusaurus:** https://docusaurus.io

---

*Last updated: February 27, 2026*
