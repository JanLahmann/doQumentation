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
- `docs/index.mdx` is preserved (not overwritten) — all other `docs/` content is regenerated

### Code Execution
- `ExecutableCode` component wraps Python code blocks with Run/Stop toggle
- thebelab 0.4.x bootstraps once per page, shared kernel across all cells
- Environment auto-detection: GitHub Pages → Binder (2i2c.mybinder.org), localhost/rasqberry/Docker → local Jupyter, custom → user-configured
- Cell execution feedback: persistent left border (amber while running, green when done)
- "Open in JupyterLab" button on notebook-derived pages (local environments only)
- Binder package hint shown after kernel ready (GitHub Pages only)

### IBM Quantum Integration
- **Credential store** — API token + CRN saved in localStorage with 7-day auto-expiry. Auto-injected via `save_account()` at kernel start.
- **Simulator mode** — Monkey-patches `QiskitRuntimeService` with `_DQ_MockService` that returns AerSimulator or a FakeBackend. No IBM account needed.
- **Fake backend discovery** — Introspects `fake_provider` at kernel connect, caches available backends in localStorage. Device picker grouped by qubit count.
- **Conflict resolution** — When both credentials and simulator are configured, radio buttons let user choose. Banner shown at kernel connect if no explicit choice (defaults to simulator).

### Settings Page (`/jupyter-settings`)
Sections: IBM Quantum Account (5-step setup guide with direct links) → Simulator Mode → Binder Packages → Advanced (Custom Server + Setup Help)

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

### CI/CD
- `deploy.yml` — Sync content → build (with `NODE_OPTIONS="--max-old-space-size=8192"`) → deploy to GitHub Pages
- `docker.yml` — Multi-arch Docker build → ghcr.io
- `sync-deps.yml` — Weekly auto-PR syncing Jupyter dependencies from upstream (with architecture exception rules)
- Binder repo has separate daily build workflow to keep 2i2c cache warm

### Homepage
Hero banner with CTA buttons, content stats bar (clickable numbers), featured full-width "Basics of QI" course card + Hello World guide + 3 tutorial cards. Audience guidance intro sentence. Quick Start: step 1 (Run code) then bullet alternatives (IBM Quantum / Simulator Mode). "How code execution works" and "Deployment options" collapsed into `<details>`. RasQberry mentioned after "What this project adds". Links to browse all Guides + CS/QM modules. Mobile responsive.

### Styling
Carbon Design-inspired: IBM Plex fonts, `#0f62fe` blue. Mobile hamburger menu with visible border/background. Top-level sidebar categories styled at 1.1rem/semibold.

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
│   ├── components/
│   │   ├── ExecutableCode/        # Run/Stop toggle, thebelab, kernel injection
│   │   │   └── index.tsx
│   │   ├── CourseComponents/      # DefinitionTooltip, Figure, IBMVideo, LaunchExamButton
│   │   ├── GuideComponents/       # Card, CardGroup, OperatingSystemTabs, CodeAssistantAdmonition
│   │   └── OpenInLabBanner/       # "Open in JupyterLab" banner
│   │       └── index.tsx
│   │
│   ├── config/
│   │   └── jupyter.ts             # Environment detection, credential/simulator storage
│   │
│   ├── css/
│   │   └── custom.css             # All styling (Carbon-inspired + homepage + settings)
│   │
│   ├── pages/
│   │   └── jupyter-settings.tsx   # Settings page (IBM credentials, simulator, custom server)
│   │
│   └── theme/
│       ├── CodeBlock/index.tsx    # Swizzle: wraps Python blocks with ExecutableCode
│       └── MDXComponents.tsx      # IBM component stubs (Admonition, Image, etc.)
│
├── scripts/
│   ├── sync-content.py            # Pull & transform content from upstream
│   ├── sync-deps.py               # Sync Jupyter deps with arch exception rules
│   └── setup-pi.sh               # Raspberry Pi setup (untested)
│
├── static/
│   ├── img/logo.svg               # Quantum circuit logo
│   ├── CNAME                      # GitHub Pages custom domain (excluded from containers)
│   ├── docs/                      # Synced images (gitignored)
│   └── learning/images/           # Synced course/module images (gitignored)
│
├── Dockerfile                     # Static site only (nginx)
├── Dockerfile.jupyter             # Full stack: site + Jupyter + Qiskit
├── docker-compose.yml             # web + jupyter services
├── nginx.conf                     # SPA routing + Jupyter proxy
├── docusaurus.config.ts           # Site config (URLs, thebe script, KaTeX, custom fields)
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

**Docker:**
```bash
docker compose up web              # Static site only → http://localhost:8080
docker compose up jupyter          # Full stack → http://localhost:8080 (site) + :8888 (JupyterLab)
```

**Raspberry Pi** — `scripts/setup-pi.sh` (written but untested on actual hardware).

### Dependencies

- **Runtime:** Docusaurus 3.x, React 18, remark-math + rehype-katex, thebelab 0.4.x (CDN)
- **Build:** Node.js 18+, Python 3.9+ (sync scripts)
- **Binder repo:** [JanLahmann/Qiskit-documentation](https://github.com/JanLahmann/Qiskit-documentation) — slim deps in `binder/requirements.txt`, daily cache-warming workflow

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

---

## Open Items

### TODO
- **Jupyter token auth** — Enable authentication for Docker/RasQberry containers. Plan at `.claude/plans/jupyter-token-auth.md`.
- **Code review fixes** — Full review at `.claude/code-review-2026-02-08.md`. Quick wins: URL encoding in `getLabUrl()`, listener cleanup in `setupCellFeedback()`, docker-compose port conflict, a11y/aria-live, error handling in jupyter-settings, deprecated `onBrokenLinks`.

### Needs Testing
- **Offline search** — Test search functionality works end-to-end (Pagefind or Docusaurus built-in)
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

*Last updated: February 9, 2026*
