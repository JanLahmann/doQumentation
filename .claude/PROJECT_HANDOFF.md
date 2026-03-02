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
- **Colab/Binder notebook copies**: `copy_notebook_with_rewrite()` injects 1–2 pip install cells (base Qiskit + per-notebook extras) and Colab `cell_execution_strategy: "setup"` metadata. `publish_notebooks_to_static()` copies ~1,650 dependency-ready notebooks to `static/notebooks/` for gh-pages serving.
- **Translated notebooks**: `generate_translated_notebook()` merges an English `.ipynb` skeleton with translated `.mdx` text — code cells/outputs stay unchanged, markdown cells get translated text. Uses code blocks as alignment anchors. Handles consecutive markdown cells via heading-boundary splitting. Cleans Docusaurus syntax (heading anchors, MDX escapes, `<Admonition>` → blockquotes). `generate_locale_notebooks(locale)` orchestrates all notebooks for a locale, skipping untranslated fallbacks. CLI: `--generate-locale-notebooks --locale XX`.
- **Custom Hello World**: `hello-world.ipynb` from fork root imported as first tutorial with custom `OpenInLabBanner` description

### Code Execution (`src/components/ExecutableCode/index.tsx`)
- `ExecutableCode` wraps Python code blocks with Run/Back toggle. thebelab bootstraps once per page, shared kernel.
- Environment auto-detection: GitHub Pages → Binder, localhost/Docker → local Jupyter, custom → user-configured
- Cell feedback: amber (running), green (done), red (error) left borders. Error detection for `ModuleNotFoundError` (with clickable Install button), `NameError`, tracebacks.
- Cell completion uses `kernel.statusChanged` signal (not thebelab events) with 1500ms debounce to avoid premature green borders
- Execution mode indicator badge + injection toast. "Open in JupyterLab" button on all tiers. "Open in Colab" button always available.
- **Binder tab reuse**: "Open in Lab" uses named window target `binder-lab` to reuse the same tab
- **Interception transparency**: All kernel modifications print `[doQumentation]` messages (simulator intercepts, credential injection, warning suppression, pip install cells)
- **save_account() protection**: Dynamic blue "Skip this cell" banners (runtime-injected via `annotateSaveAccountCells()`, translated via `code.json`) when credentials/simulator active, prevents overwriting injected values
- **Full i18n**: All toolbar buttons, status messages, legend, conflict banner, settings link, and Binder hint wrapped with `translate()`/`<Translate>`

### IBM Quantum Integration (`src/config/jupyter.ts`)
- **Credentials** — API token + CRN with adjustable auto-expiry (1/3/7 days). Auto-injected at kernel start. Embedded execution only. Shared across locale subdomains via cookies.
- **Simulator mode** — Monkey-patches `QiskitRuntimeService` with `_DQ_MockService` (AerSimulator or FakeBackend). Fake backend discovery cached, 55-backend fallback list.
- **Conflict resolution** — Radio buttons when both configured; defaults to simulator.
- **Colab URLs** — `getColabUrl(notebookPath, locale?)` generates locale-aware Colab links via the `/github/` scheme (Colab's `/url/` scheme blocks non-GitHub domains due to SSRF allowlist). All notebooks are processed copies with pip install cells injected by `sync-content.py`. EN: points to `doQumentation/blob/notebooks/` branch (pushed by `deploy.yml` CI step). Translated: points to satellite repos (`doqumentation-{locale}/blob/gh-pages/notebooks/`). Unified path mapping: strips `docs/` prefix; bare filenames (no `/`) get `tutorials/` prefix. Both `OpenInLabBanner` and `ExecutableCode` pass `currentLocale` from Docusaurus context. `getBinderLabUrl()` is separate — points to dependency-ready copies in the Binder repo; always English.

### User Preferences
All storage access centralized in `src/config/preferences.ts` and `src/config/jupyter.ts`, backed by `src/config/storage.ts`. **Cross-subdomain sharing**: on `*.doqumentation.org`, all 28 keys are dual-written to cookies (`Domain=.doqumentation.org`) + localStorage. Values > 3.8KB auto-chunked across multiple cookies. On localhost/Docker, pure localStorage (no cookies). One-time migration copies existing localStorage to cookies on first page load (`pageTracker.ts`). Cross-component reactivity via custom events: `dq:page-visited`, `dq:bookmarks-changed`, `dq:display-prefs-changed`.

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
- `deploy.yml` — Sync → build → GitHub Pages (English only). Also pushes EN notebooks + Binder config to `notebooks` branch (preserves locale subdirs). Binder packages split across `binder/requirements.txt` (core: qiskit, aer, ibm-runtime — Docker-cached) + `binder/postBuild` (4 lighter packages + cleanup to reduce layer size).
- `deploy-locales.yml` — Matrix build per locale: sync content → populate fallbacks → generate translated notebooks → build → push to satellite repos. Consolidation job merges all locale notebooks into `notebooks` branch subdirectories.
- `docker.yml` — Multi-arch Docker → ghcr.io (EN only via `--locale en`)
- `sync-deps.yml` — Weekly auto-PR for Jupyter dependencies
- `check-translations.yml` — Daily translation freshness check + STATUS.md update
- `binder.yml` — Daily cache warming for 3 Binder federation members (2i2c, BIDS, GESIS). Push trigger temporarily disabled (manual `workflow_dispatch` only) until Binder builds verified.

### Other
- **Homepage**: Beta notice banner (session-scoped, dismissible), hero with stats bar, Getting Started cards (category-tagged), simulator callout, code execution section. No sidebar on homepage itself.
- **Sidebar**: Home link at top, then Tutorials/Guides/Courses/Modules categories (autogenerated from `sidebar-*.json`). API Reference + Settings in navbar only.
- **Features page**: `/features` — 22 cards across 5 sections
- **Search**: `@easyops-cn/docusaurus-search-local` — client-side, hashed index
- **Settings page** (`/jupyter-settings`): IBM credentials, simulator mode, display prefs, progress, bookmarks, custom server
- **Navbar**: Always dark (`#161616`). Right-side icons: locale (globe), settings (gear), dark mode, GitHub (octocat) — all icon-only on desktop (text hidden via `font-size: 0` + `::before` SVG). CSS `order` positions auto-placed dark mode toggle and search bar. Mobile sidebar header swizzled (`Navbar/MobileSidebar/Header`) with matching icon row. Locale dropdown has "Deutsche Dialekte" separator before dialect locales (CSS `li:has()` on desktop, React separator `<li>` on mobile).
- **Footer**: Three columns — doQumentation (Features, Settings, GitHub), RasQberry (site + GitHub), IBM Quantum & Qiskit (docs, GitHub, Slack). IBM disclaimer in copyright.
- **Styling**: Carbon Design-inspired (IBM Plex, `#0f62fe`).
- **SEO & social sharing**: Open Graph + Twitter Card meta tags, JSON-LD structured data (Organization, WebPage, SoftwareApplication), robots meta for AI indexing, preconnect hints for fonts/CDN. Social card image (`static/img/rasqberry-social-card.png`, 1200x630).
- **Keyboard accessibility**: `focus-visible` outlines on all interactive elements; light blue variant on dark navbar for contrast.

---

## Project Structure

```
doQumentation/
├── .github/workflows/          # deploy, deploy-locales, docker, sync-deps, check-translations, binder
├── binder/                     # Jupyter requirements (cross-platform + amd64-only)
├── docs/                       # Content (gitignored except index.mdx)
├── notebooks/                  # Original .ipynb for JupyterLab (generated)
├── src/
│   ├── clientModules/          # pageTracker, displayPrefs, onboarding
│   ├── components/             # ExecutableCode, ResumeCard, RecentPages, BookmarksList, OpenInLabBanner, BetaNotice, CourseComponents, GuideComponents
│   ├── config/                 # storage.ts (cookie+localStorage), jupyter.ts (env detection, credentials), preferences.ts (user prefs)
│   ├── css/custom.css          # All styling
│   ├── pages/                  # features.tsx, jupyter-settings.tsx
│   └── theme/                  # Swizzled: Root (global BetaNotice), CodeBlock, DocItem/Footer, EditThisPage, DocSidebarItem/{Category,Link}, Navbar/MobileSidebar/Header, MDXComponents
├── i18n/                       # Translations: de (81), es (76), uk (56), ja (56), fr/it/pt/tl (48 each), he (47), ar (44), swg/bad/bar (31 each), ksh (46), nds (43), gsw (42), sax (39), bln (36), aut (34)
├── scripts/                    # sync-content.py, sync-deps.py, docker-entrypoint.sh, setup-pi.sh
├── translation/                # Translation infrastructure
│   ├── drafts/{locale}/{path}  # Staging area for new translations (git-tracked)
│   ├── status.json             # Per-file tracking (status, validation, source hash, dates)
│   ├── translation-prompt.md   # Claude Code automation prompt
│   ├── register-fix-prompt.md  # Claude Code register rewrite prompt
│   ├── review-prompt.md        # LLM review prompt (Haiku/Gemini Flash)
│   └── scripts/                # validate, lint, review, fix-anchors, promote, populate, get-register-fails, status dashboard
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
| DE | [de.doqumentation.org](https://de.doqumentation.org) | 82 + UI | Live |
| ES | [es.doqumentation.org](https://es.doqumentation.org) | 55 + UI | Live |
| UK | [uk.doqumentation.org](https://uk.doqumentation.org) | 55 + UI | Live |
| FR | [fr.doqumentation.org](https://fr.doqumentation.org) | 48 + UI | Live |
| IT | [it.doqumentation.org](https://it.doqumentation.org) | 48 + UI | Live |
| PT | [pt.doqumentation.org](https://pt.doqumentation.org) | 48 + UI | Live |
| JA | [ja.doqumentation.org](https://ja.doqumentation.org) | 60 + UI | Live |
| TL | [tl.doqumentation.org](https://tl.doqumentation.org) | 48 + UI | Live |
| AR | [ar.doqumentation.org](https://ar.doqumentation.org) | 44 + UI | Live (RTL) |
| HE | [he.doqumentation.org](https://he.doqumentation.org) | 47 + UI | Live (RTL) |
| SWG | [swg.doqumentation.org](https://swg.doqumentation.org) | 31 + UI | Live |
| BAD | [bad.doqumentation.org](https://bad.doqumentation.org) | 31 + UI | Live |
| BAR | [bar.doqumentation.org](https://bar.doqumentation.org) | 31 + UI | Live |
| KSH | [ksh.doqumentation.org](https://ksh.doqumentation.org) | 46 + UI | Live |
| NDS | [nds.doqumentation.org](https://nds.doqumentation.org) | 43 + UI | Live |
| GSW | [gsw.doqumentation.org](https://gsw.doqumentation.org) | 42 + UI | Live |
| SAX | [sax.doqumentation.org](https://sax.doqumentation.org) | 39 + UI | Live |
| BLN | [bln.doqumentation.org](https://bln.doqumentation.org) | 36 + UI | Live |
| AUT | [aut.doqumentation.org](https://aut.doqumentation.org) | 34 + UI | Live |

- **Config**: `docusaurus.config.ts` — `locales: ['en', 'de', 'es', 'uk', 'fr', 'it', 'pt', 'ja', 'tl', 'ar', 'he', 'swg', 'bad', 'bar', 'ksh', 'nds', 'gsw', 'sax', 'bln', 'aut']`, per-locale `url` in `localeConfigs`, `DQ_LOCALE_URL` env var. Built-in `LocaleDropdown` handles cross-domain links natively. hreflang tags auto-generated.
- **RTL support**: AR and HE have `direction: 'rtl'` in `localeConfigs`. CSS uses logical properties (`border-inline-start`, `margin-inline-start`, `inset-inline-end`) throughout — direction-agnostic for both LTR and RTL. Noto Sans Arabic/Hebrew fonts loaded via Google Fonts. `[dir="rtl"]` overrides in `custom.css`.
- **CI**: `deploy.yml` builds EN only (`--locale en`). `deploy-locales.yml` matrix builds all 19 locales separately, pushes to satellite repos via SSH deploy keys (`DEPLOY_KEY_{DE,ES,UK,FR,IT,PT,JA,TL,AR,HE,SWG,BAD,BAR,KSH,NDS,GSW,SAX,BLN,AUT}`).
- **Satellite repos**: `JanLahmann/doQumentation-{de,es,uk,fr,it,pt,ja,tl,ar,he}` + `doqumentation-{swg,bad,bar,ksh,nds,gsw,sax,bln,aut}` — each has `main` branch (README + LICENSE + LICENSE-DOCS + NOTICE) and `gh-pages` branch (build output). GitHub Pages + custom domains configured. Setup script: `.claude/scripts/setup-satellite-repo.sh`.
- **German dialects**: 9 dialect locales (SWG, BAD, BAR, KSH, NDS, GSW, SAX, BLN, AUT) with "Deutsche Dialekte" separator in locale dropdown. Desktop: CSS `li:has(> a[href*="swg.doqumentation.org"])::before` targets first dialect. Mobile: `dialectLocales` Set in `Navbar/MobileSidebar/Header` renders separator `<li>`. To add a new dialect: add to `dialectLocales` Set + `locales`/`localeConfigs` in config + CI matrix + `BANNER_TEMPLATES` + `locale_label` in `translation/scripts/translate-content.py`.
- **Full UI i18n** (`code.json`): All user-visible strings across React pages and components use Docusaurus `<Translate>` and `translate()` APIs. This covers Settings page (~90 keys), Features page (~39 keys), ExecutableCode toolbar (Run/Back/Lab/Colab buttons, status messages, legend, conflict banner), EditThisPage bookmarks, BookmarksList, DocSidebarItem/Link, BetaNotice, and MobileSidebar header. Total: ~308 keys per locale (~92 theme + ~216 custom). When adding a new language, `npm run write-translations -- --locale {XX}` auto-generates entries with English defaults; translate all `message` values. Technical terms (Qiskit, Binder, AerSimulator, etc.) and code snippets stay in English. Placeholders like `{binder}`, `{saveAccount}`, `{url}`, `{pipCode}`, `{issueLink}`, `{mode}` must be preserved exactly.
- **Fallback system**: `populate-locale` fills untranslated pages with English + "not yet translated" banner. ~372 fallbacks per locale. 20 banner templates defined in `translation/scripts/translate-content.py`.
- **Translation freshness**: Genuine translations embed `{/* doqumentation-source-hash: XXXX */}` (SHA-256 first 8 chars of EN source). Daily CI workflow (`check-translations.yml`) compares embedded hashes against current EN files. CRITICAL = missing imports/components (features broken); STALE = content changed. After propagating EN changes, run `check-translation-freshness.py --stamp` to update hashes. **Key rule**: Any change to EN source files (imports, components, content) must be manually propagated to genuine translations — `populate-locale` only refreshes fallbacks, not genuine translations.
- **Draft pipeline**: Translations go through `translation/drafts/{locale}/{path}` → validate → fix → promote to `i18n/`. Scripts: `validate-translation.py` (12 structural checks, `--dir`/`--section`/`--report`/`--record` flags), `fix-heading-anchors.py` (`--dir` flag), `promote-drafts.py` (`--locale`/`--section`/`--file`/`--force`/`--keep` flags). Status tracked in `translation/status.json` (hybrid: grows as files are validated/promoted, with status, validation result, source hash, dates, failures). Direct-to-i18n still works (all scripts default to `i18n/` without `--dir`).
- **Status dashboard**: `translation-status.py` — combines on-the-fly file scanning with `status.json` data. Modes: overview (all locales), `--locale XX` (per-section detail), `--backlog` (prioritized untranslated files), `--validate` (run + record structural checks), `--markdown`/`--json` (output formats), `--update-contributing` (auto-update table in CONTRIBUTING-TRANSLATIONS.md between marker comments), `--write-status` (generate `translation/STATUS.md` with full report), `--all` (include dialect locales). Daily CI auto-updates `translation/STATUS.md`.
- **Translation**: See [`CONTRIBUTING-TRANSLATIONS.md`](../CONTRIBUTING-TRANSLATIONS.md) for contributor guide (any tool/LLM). For Claude Code automation: `translation/translation-prompt.md` (Sonnet, 3 parallel agents, 1 file or chunk each). One-liner: `Read translation/translation-prompt.md. Translate all untranslated pages to French (fr).`
- **Translation validation**: Three-step QA. Step 1: `validate-translation.py` — 12 binary PASS/FAIL structural checks (line count, code blocks byte-identical, LaTeX, headings, anchors, image paths, frontmatter, JSX tags, URLs, paragraph inflation). Locale-specific inflation thresholds (`LOCALE_WORD_RATIO`: de=3.0x, default=1.8x). Supports `--dir translation/drafts` for staging, `--section` for filtering, `--report` for markdown feedback, `--record` for writing results to `status.json`. Step 2: `lint-translation.py` — MDX syntax lint for build-breaking errors (duplicate heading anchors, garbled XML tags, heading markers mid-line, invalid anchor chars, unmatched code fences, missing imports). Both have `--record` for status.json. Step 3: linguistic review (register, word salad, verbosity, accuracy) — tracked via `review-translations.py` (`--record-review`). Review prompt: `translation/review-prompt.md`.
- **Review orchestration**: `review-translations.py` manages systematic review across sessions. `--auto-check` runs structural validation + lint for all locales in bulk. `--progress` shows per-locale dashboard (struct/lint/review counts). `--next-chunk [--size N]` returns prioritized batch of files needing linguistic review. `--record-review` persists verdicts (PASS/MINOR_ISSUES/FAIL/SKIPPED) to status.json. Baseline: 885 files, 456 structural PASS, 440 ready for review, AR auto-skipped (needs re-translation).
- **Register**: Informal/familiar (du/tu/tú/ти — not Sie/vous/usted/Ви). The Qiskit community uses informal address. Register fix automation: `translation/register-fix-prompt.md` (targeted rewrite, Sonnet agents). Helper: `translation/scripts/get-register-fails.py` lists FAIL files from status.json by locale.
- **Heading anchors**: Translated headings get `{#english-anchor}` pins to preserve cross-reference links. `fix-heading-anchors.py` for batch fixing (supports `--dir` for drafts).
- **Build**: ~320 MB per single-locale build. Each fits GitHub Pages 1 GB limit independently.
- **Attribution**: `NOTICE` file in main repo and all satellite repos credits IBM/Qiskit as upstream content source. `LICENSE` (Apache 2.0) + `LICENSE-DOCS` (CC BY-SA 4.0) included in all repos and CI deploy output.

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
- Add to search plugin `language` array (if [`lunr-languages`](https://github.com/MihaiValentin/lunr-languages) supports it — currently no support for `uk` or `tl`)

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
- **Translation review + register fix — COMPLETE** — All 456 structurally-passing files reviewed across 19 locales. 194 files failed due to formal register (Sie/vous/usted/Ві/voi). All 194 fixed via targeted LLM register rewrite (140 FIXED, 27 MINOR_ISSUES, 271 PASS, 2 non-register FAIL skipped, 44 AR SKIPPED). Run `review-translations.py --progress` for dashboard.
- **Translation expansion** — DE at 81/387 (69 PASS, 12 FAIL), ES at 76/387 (49 PASS, 27 FAIL), UK at 56/387, JA at 56/387, FR at 48 (36 PASS, 12 FAIL), IT/PT/TL at 48, HE at 47, AR at 44 (needs re-translation). German dialects: KSH (46), NDS (43), GSW (42), SAX (39), BLN (36), AUT (34). Run `python translation/scripts/translation-status.py` for current counts, or see `translation/STATUS.md`.
- **Binder-enable this repo (Phase 4 pending)** — CI infra done: `deploy.yml` should push EN notebooks + Binder config to `notebooks` branch (core packages in `requirements.txt` for Docker caching, lighter packages + aggressive cleanup in `postBuild` to reduce layer size), `deploy-locales.yml` consolidates locale notebooks into subdirs, `binder.yml` warms 3 federation members (push trigger temporarily disabled for manual verification). **BLOCKER**: `deploy.yml` notebook push step did not push to `notebooks` branch — needs investigation (possibly `git diff --cached --quiet` exiting early, or CI error). **Pending after fix**: verify Binder builds from `notebooks` branch, then switch URLs in `jupyter.ts` (Phase 4). Plan: `.claude/plans/binder-enable-notebooks.md`.
- **Fork testing** — Verify the repo can be forked with Binder still working
- **Upstream sync strategy** — Plan how to pull upstream changes from [Qiskit/documentation](https://github.com/Qiskit/documentation) weekly. Currently `sync-content.py` clones from the fork (`JanLahmann/Qiskit-documentation`), which must be manually synced with upstream. Need: automated fork sync (GitHub Actions or scheduled script), handling of merge conflicts in modified files (`hello-world.ipynb`, `_toc.json`), freshness checks for translated content after EN changes, and a rollback strategy if upstream breaks the build.
- **Hide Colab/Binder buttons on non-notebook pages** — Pages like "Discretization of errors" (course content without code cells, not generated from a notebook) still show "Open in Colab" and "Open in Binder JupyterLab" buttons. Consider hiding these buttons when the page has no executable code cells or no corresponding notebook file.
- **Hello World "What's Next" section** — The "What next?" in `tutorials/hello-world.mdx` (self-written) should recommend paths forward in both Qiskit-documentation and doQumentation, since the two projects offer different things. Currently points to Tutorials, Courses, and Local testing mode with Binder URLs.
- **Raspberry Pi** — `scripts/setup-pi.sh` written but untested on actual hardware

### Resolved (Mar 2026)
- **Translation register fix (194 files)** — Linguistic review found 194 files across 10 locales using formal register instead of required informal. All fixed via targeted LLM register rewrite (`translation/register-fix-prompt.md`): DE (64), FR (36), ES (36), UK (18), IT (17), SWG (10), BAD (8), SAX (3), AUT (1). 2 non-register FAILs skipped (NDS soft hyphens, TL structural). Added `FIXED` verdict to `review-translations.py`. Helper: `translation/scripts/get-register-fails.py`.
- **Comprehensive prerequisites cell** — Merged two pip install cells (base + extras) into single comprehensive cell per notebook. Deleted stale `BINDER_PROVIDED` set; now uses stdlib-only filtering so ALL third-party imports appear in the prerequisites cell. Fixes bug where 26 notebooks with `qiskit-ibm-catalog` (and others like `pyscf`, `ffsim`) were missing packages on Colab. Zero maintenance — no platform-specific package list to keep updated.
- **DE tutorial fixes (18/18 PASS)** — Fixed 8 failing DE tutorials: added 3 missing IBM survey links, restored EN code comments in 5 code blocks, fixed truncated code output, restored missing internal link, fixed 2 paragraph boundary misalignments. Added locale-specific paragraph inflation threshold (`de: 3.0x`). Added `--write-status` to daily CI workflow and German dialect locales to CONTRIBUTING-TRANSLATIONS.md table.
- **Translation status dashboard** — New `translation-status.py` script: overview of all locales with section breakdown, `--locale` detail view, `--backlog` (prioritized untranslated files), `--validate` (run + record to status.json), `--markdown`/`--json` output, `--update-contributing` (auto-updates CONTRIBUTING-TRANSLATIONS.md table). `validate-translation.py` gained `--record` flag to persist results. `status.json` expanded with source hash, dates, failures. Hybrid approach: status.json grows over time as files are validated/promoted; existing i18n/ translations counted on-the-fly.
- **Colab "Open in Colab" 403 fix** — Colab's `/url/` scheme blocks non-GitHub domains (Google SSRF allowlist). Switched to `/github/` scheme pointing to processed notebooks (with pip install cells). EN: `doQumentation/blob/notebooks/` branch, auto-pushed by new CI step in `deploy.yml` (`contents: write` permission, force-pushes `build/notebooks/` after build). Translated: satellite repos `doqumentation-{locale}/blob/gh-pages/notebooks/` (already existed). Unified path mapping for both: strips `docs/` prefix; bare filenames get `tutorials/` prefix. KSH build fix: removed duplicate heading anchor with apostrophe in `transpilation-optimizations-with-sabre.mdx`.
- **Translation draft pipeline** — Added `translation/drafts/` staging area with validate → fix → promote workflow. New scripts: `promote-drafts.py` (with `--section`/`--file`/`--force`/`--keep` flags), `validate-translation.py` (added `--dir`/`--section`/`--report`), `fix-heading-anchors.py` (added `--dir`). Status tracking in `translation/status.json`. Backward compatible — all scripts default to `i18n/` without `--dir`.
- **Translation validation improvements** — Fixed 3 false-positive categories: code block trailing whitespace tolerance, frontmatter title allowlist (`FRONTMATTER_SAME_ALLOWED`), dialect locales in `ALL_LOCALES`. Overall pass rate improved from 53% to 63%. Fixed 130 missing heading anchors across 13 locales.
- **Translation build fixes** — Fixed 3+1 locale build failures: KSH garbled `<bcp47:` heading artifact, HE missing newlines before headings (×2), SAX image path `tutorial` → `tutorials`. All pre-existing from translation agents.
- **Locale dropdown separator** — "Deutsche Dialekte" CSS separator wasn't rendering. Root cause: Docusaurus applies navbar `className` to the `<a>` trigger, not the wrapper `<div>`. Fixed by changing descendant selector to sibling combinator (`~`).
- **BetaNotice global via Root wrapper** — Originally only on homepage `index.mdx` (missing from locale sites). Moved to swizzled `src/theme/Root.tsx` so it renders on every page (docs, homepage, settings, features) without per-file imports. Removed manual imports from EN + 19 locale `index.mdx` files. Session-based dismissal via sessionStorage.
- **MDX lint script** — New `lint-translation.py` catches build-breaking MDX syntax errors that `validate-translation.py` misses: duplicate heading anchors, garbled XML namespace tags, heading markers mid-line, invalid anchor characters, unmatched code fences, missing imports. Integrated into review workflow (`review-instructions.md`, `review-prompt.md`). Both `validate-translation.py` and `lint-translation.py` have `--record` flag for status.json persistence.
- **Translation review orchestration** — New `review-translations.py` manages systematic review of all 885 translations across sessions. `--auto-check` runs structural + lint in bulk (populated all 885 entries). `--progress` dashboard. `--next-chunk` returns prioritized batch for linguistic review. `--record-review` persists verdicts to status.json. Baseline: 456 PASS structural, 877 CLEAN lint, 440 ready for review, AR auto-skipped.
- **Translation freshness system** — Built `check-translation-freshness.py` with embedded source hashes (`{/* doqumentation-source-hash: XXXX */}`) in all 885 genuine translations. Daily CI workflow (`check-translations.yml`) detects CRITICAL (missing imports/components) and STALE (content changed) translations. Prevents future BetaNotice-type regressions.

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

*Last updated: March 2, 2026*
