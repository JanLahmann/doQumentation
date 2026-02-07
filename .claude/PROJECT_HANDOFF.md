# RasQberry Tutorials - Project Handoff Document

## Executive Summary

This project creates a **local hosting solution for IBM Quantum tutorials** on Raspberry Pi, with interactive Jupyter code execution. It's part of the larger [RasQberry](https://github.com/JanLahmann/RasQberry-Two) educational quantum computing platform.

**Key deliverable:** A Docusaurus-based static site that:
- Hosts IBM Quantum tutorials offline on Raspberry Pi
- Enables live Python/Qiskit code execution via Jupyter
- Also deploys to GitHub Pages for online access
- Uses a single codebase for both deployment targets

---

## Project Context

### The Problem

IBM Quantum tutorials live at https://quantum.cloud.ibm.com/docs/tutorials but:
- Require internet connection
- Cannot execute code locally
- The web application is **closed source** (only content is open)
- No official way to host them locally

### The Solution

Build a custom static site generator that:
1. Pulls tutorial and course content from [JanLahmann/Qiskit-documentation](https://github.com/JanLahmann/Qiskit-documentation) (fork of Qiskit/documentation)
2. Transforms IBM's MDX format to Docusaurus-compatible MDX
3. Adds interactive code execution via Thebe + Jupyter
4. Deploys to both GitHub Pages AND Raspberry Pi

### Why This Matters for RasQberry

RasQberry is used at **trade shows and educational environments** where:
- Internet may be unreliable or unavailable
- Users need hands-on quantum computing experience
- The 3D-printed IBM Quantum System Two replica with LED visualization needs tutorial content
- "Simplicity above all else" is the guiding philosophy

---

## Architecture Decisions Made

### 1. Framework: Docusaurus (not Next.js, Hugo, etc.)

**Decision:** Use Docusaurus 3.x

**Rationale:**
- Purpose-built for documentation sites
- Native MDX support with extensibility
- Auto-generates sidebar from file structure
- Static export is first-class (works offline)
- Large community, Meta-backed, active maintenance
- IBM's own site uses Next.js but that's closed source

### 2. Code Execution: Thebe + Jupyter

**Decision:** Use Thebe library to connect static HTML to Jupyter kernels

**Rationale:**
- Minimal client-side code
- Works with any Jupyter server (local or remote)
- Graceful degradation when Jupyter unavailable
- On GitHub Pages: can fall back to Binder (slow but works)
- On RasQberry: connects to local Jupyter server (fast)

**Rejected alternatives:**
- JupyterLite (WASM) - Qiskit has Rust extensions that won't compile to WASM
- Direct JupyterLab only - Less controlled, overwhelming UI
- Voilà - Hides code, less educational

### 3. Single Codebase, Dual Deployment

**Decision:** One codebase deploys to both GitHub Pages and Raspberry Pi

**Rationale:**
- Reduces maintenance burden
- Runtime detection handles environment differences
- Same static build works everywhere
- Only Jupyter endpoint differs (localhost vs Binder vs custom)

### 4. Content Transformation (not Docker mirroring)

**Decision:** Transform Qiskit MDX to Docusaurus MDX, don't mirror IBM's Docker preview

**Rationale:**
- IBM's Docker preview lacks navigation sidebar, search, top nav
- It's designed for PR previews, not production
- Building our own gives full control
- Transformation is straightforward (95% compatible already)

### 5. Search: Pagefind (static)

**Decision:** Use Pagefind for fully static search

**Rationale:**
- No server-side component needed
- Works offline on Pi
- Fast, small index
- Runs at build time

---

## Technical Implementation

### MDX Component Mapping

IBM's custom MDX components and their Docusaurus equivalents:

| IBM Component | Docusaurus Solution | Status |
|---------------|---------------------|--------|
| `<Admonition type="note">` | `:::note` directive | ✅ Native |
| `<Admonition type="attention">` | `:::warning` | ✅ Transform |
| `<Tabs>` / `<TabItem>` | Same (native) | ✅ Native |
| Math `$...$` `$$...$$` | Same (KaTeX plugin) | ✅ Plugin |
| Code blocks | ExecutableCode wrapper | ✅ Custom |
| `<DefinitionTooltip>` | Custom component or `<abbr title>` transform | ❌ Courses only (183 uses) |
| `<IBMVideo>` | Iframe/placeholder component | ❌ Courses only (38 uses) |
| `<Figure>` | Styled wrapper component | ❌ Courses only (36 uses) |
| `<LaunchExamButton>` | Link/button component | ❌ Courses only (10 uses) |

**Key insight:** IBM's MDX is 95% standard Docusaurus-compatible. Main transform is Admonition syntax. Courses introduce 4 additional custom components not found in tutorials.

### ExecutableCode Component

The core interactive component provides three modes:

```
┌─────────────────────────────────────────────────┐
│ [📖 Read] [▶️ Run] [🔬 Open in Lab]  ● Ready    │
├─────────────────────────────────────────────────┤
│ from qiskit import QuantumCircuit               │
│ qc = QuantumCircuit(2)                          │
│ qc.h(0)                                         │
│ qc.cx(0, 1)                                     │
│ print(qc)                                       │
├─────────────────────────────────────────────────┤
│ OUTPUT                                          │
│      ┌───┐                                      │
│ q_0: ┤ H ├──■──                                 │
│      └───┘┌─┴─┐                                 │
│ q_1: ────┤ X ├                                  │
│          └───┘                                  │
└─────────────────────────────────────────────────┘
```

**Modes:**
1. **Read** - Static syntax highlighting (default)
2. **Run** - Execute via Thebe → Jupyter kernel
3. **Lab** - Open full notebook in JupyterLab (Pi only)

### Environment Detection

The `src/config/jupyter.ts` module auto-detects:

| Environment | Detection | Behavior |
|-------------|-----------|----------|
| GitHub Pages | `hostname.includes('github.io')` | Thebe → Binder |
| RasQberry | `localhost`, `rasqberry`, `192.168.*` | Thebe → localhost:8888, Lab enabled |
| Custom | `localStorage.jupyterUrl` set | User-configured |

### Content Sync Pipeline

```
JanLahmann/Qiskit-documentation (GitHub fork)
        │
        ▼ git sparse-checkout (tutorials + courses + images)
        │   paths: docs/tutorials, learning/courses, learning/images
        │
        ▼ sync-content.py transforms:
        │   • MDX: Admonition syntax, add imports
        │   • .ipynb → .mdx via nbconvert
        │   • Copy original .ipynb for "Open in Lab"
        │   • Parse _toc.json for course sidebar ordering
        │   • Transform course-specific components (see below)
        │
        ▼
   docs/tutorials/*.mdx
   docs/courses/**/*.mdx  (nested: course/chapter/lesson)
   notebooks/tutorials/*.ipynb
   notebooks/courses/**/*.ipynb
        │
        ▼ Docusaurus build
        │
        ▼ Pagefind search index
        │
        ▼
   ┌────┴────┐
   ▼         ▼
GitHub    Raspberry
Pages     Pi (nginx)
```

---

## Project Structure

```
doQumentation/
├── .github/workflows/
│   └── deploy.yml              # CI/CD: sync, build, deploy
│
├── docs/                        # Tutorial content (MDX)
│   ├── index.mdx               # Home page
│   └── tutorials/              # Transformed tutorials
│       └── hello-world.mdx     # Sample tutorial
│
├── notebooks/                   # Original .ipynb for JupyterLab
│
├── src/
│   ├── components/
│   │   └── ExecutableCode/     # [Read] [Run] [Lab] component
│   │       └── index.tsx
│   │
│   ├── config/
│   │   └── jupyter.ts          # Environment detection
│   │
│   ├── css/
│   │   └── custom.css          # Carbon Design-inspired styling
│   │
│   ├── pages/
│   │   └── jupyter-settings.tsx # Custom Jupyter server config UI
│   │
│   └── theme/
│       └── CodeBlock/          # Override to wrap Python blocks
│           └── index.tsx
│
├── scripts/
│   ├── sync-content.py         # Pull & transform from Qiskit
│   └── setup-pi.sh             # Raspberry Pi setup script
│
├── static/
│   └── img/
│       └── logo.svg            # Quantum circuit logo
│
├── docusaurus.config.ts        # Site configuration
├── sidebars.ts                 # Navigation structure
├── package.json                # Dependencies
├── tsconfig.json               # TypeScript config
└── README.md                   # Documentation
```

---

## Current State

### What's Complete

1. ✅ **Project scaffold** - Full Docusaurus setup with TypeScript
2. ✅ **ExecutableCode component** - Three modes (Read/Run/Lab)
3. ✅ **Jupyter configuration** - Auto-detection for GH Pages/Pi/Custom
4. ✅ **Content sync script** - Transforms Qiskit MDX → Docusaurus
5. ✅ **GitHub Actions workflow** - Dual deployment pipeline
6. ✅ **Pi setup script** - Jupyter + nginx configuration
7. ✅ **Carbon-inspired CSS** - IBM Plex fonts, blue color scheme
8. ✅ **Sample tutorial** - Hello World with executable code
9. ✅ **Jupyter settings page** - UI to configure custom server
10. ✅ **README** - Comprehensive documentation

### What's NOT Done Yet

1. ❌ **Push to GitHub** - Tarball created but not yet pushed
2. ❌ **Test full content sync** - Only sample content generated
3. ❌ **Test Thebe integration** - Needs running Jupyter to verify
4. ❌ **Test on actual Pi** - Scripts written but untested
5. ❌ **Pagefind integration** - Config added but not tested
6. ❌ **More tutorials** - Only hello-world.mdx exists as sample
7. ❌ **Course support** - Requires work listed below

### What's Needed for Course Support

Files to create:
- `src/components/DefinitionTooltip/index.tsx` — Hover tooltip for terms (183 uses in courses)
- `src/components/IBMVideo/index.tsx` — Embedded video player or offline placeholder (38 uses)
- `src/components/Figure/index.tsx` — Titled content wrapper for diagrams/math (36 uses)
- `src/components/LaunchExamButton/index.tsx` — Link button to IBM Training exams (10 uses)

Files to modify:
- `scripts/sync-content.py` — Add `process_courses()` mirroring `process_tutorials()`, parse `_toc.json` for sidebar ordering, handle 3-level nesting (course/chapter/lesson), add `learning/images` to sparse checkout paths
- `sidebars.ts` — Add `coursesSidebar` generated from `_toc.json` files
- `docusaurus.config.ts` — Add "Courses" navbar item alongside "Tutorials"
- `src/css/custom.css` — Styles for the 4 new components

Structural differences from tutorials:
- Courses use `_toc.json` per course for ordering (not flat directory listing)
- Images live at `/learning/images/courses/` (separate from content)
- 3-level nesting: `course/chapter/lesson.ipynb` vs flat `tutorials/*.ipynb`
- Mixed content: some courses are all `.ipynb`, others mix `.mdx` + `.ipynb` subdirs

---

## Key Files to Understand

### 1. `docusaurus.config.ts`
Site configuration including:
- URLs for GitHub Pages deployment
- Thebe script loading
- KaTeX for math
- Custom fields for Jupyter config

### 2. `src/components/ExecutableCode/index.tsx`
The main interactive component. Key features:
- Three-button toolbar (Read/Run/Lab)
- Thebe initialization for Jupyter connection
- Status indicators (connecting/ready/error)
- Output capture and display

### 3. `src/config/jupyter.ts`
Environment detection logic:
- `detectJupyterConfig()` - Returns appropriate config for current environment
- `saveJupyterConfig()` / `clearJupyterConfig()` - localStorage persistence
- `testJupyterConnection()` - Verify server connectivity
- `getLabUrl()` - Generate JupyterLab URLs

### 4. `scripts/sync-content.py`
Content synchronization:
- Sparse git clone of JanLahmann/Qiskit-documentation
- MDX transformation (Admonition syntax, imports)
- Notebook conversion via nbconvert
- Sidebar generation

### 5. `scripts/setup-pi.sh`
Raspberry Pi deployment:
- Installs Jupyter in RQB2 venv
- Configures CORS for Thebe
- Creates systemd service
- Sets up nginx reverse proxy

### 6. `.github/workflows/deploy.yml`
CI/CD pipeline:
- `sync-content` job - Pull from Qiskit
- `build` job - Docusaurus + Pagefind
- `deploy-ghpages` job - GitHub Pages deployment
- `create-pi-release` job - Tarball for Pi

---

## Configuration to Update

Before first deployment, update these in `docusaurus.config.ts`:

```typescript
url: 'https://JanLahmann.github.io',      // Your GitHub username
baseUrl: '/doQumentation/',          // Repo name
organizationName: 'JanLahmann',            // GitHub username
projectName: 'doQumentation',        // Repo name
```

---

## Development Commands

```bash
# Install dependencies
npm install

# Start dev server (hot reload)
npm start

# Build for production
npm run build

# Build search index
npm run build:search

# Sync content from Qiskit/documentation
npm run sync-content
# or: python scripts/sync-content.py

# Create sample content only (for testing)
python scripts/sync-content.py --sample-only

# Type check
npm run typecheck
```

---

## Deployment

### GitHub Pages
Automatic on push to main. Or manually:
1. Actions → "Build and Deploy" → Run workflow
2. Select target: `ghpages`

### Raspberry Pi
```bash
# Download release
wget https://github.com/USER/doQumentation/releases/latest/download/doQumentation-pi.tar.gz

# Extract and install
tar -xzf doQumentation-pi.tar.gz
cd doQumentation-pi
./install.sh
```

---

## Dependencies

### Runtime
- Docusaurus 3.7
- React 18
- remark-math + rehype-katex (LaTeX)
- Thebe 0.9.2 (loaded via CDN)

### Development
- Node.js 18+
- Python 3.9+ (for sync script)
- Jupyter (for notebook conversion)
- Pagefind (search indexing)

### On Raspberry Pi
- RQB2 Python venv with Qiskit
- nginx
- systemd

---

## Related Resources

- **RasQberry Main Project:** https://github.com/JanLahmann/RasQberry-Two
- **Qiskit Documentation Source (fork):** https://github.com/JanLahmann/Qiskit-documentation
- **IBM Quantum Tutorials:** https://quantum.cloud.ibm.com/docs/tutorials
- **Docusaurus Docs:** https://docusaurus.io
- **Thebe Docs:** https://thebe.readthedocs.io
- **qotlabs mirror (inspiration):** https://github.com/qotlabs/qiskit-documentation

---

## Open Questions / Future Considerations

1. **LED Integration** - Could tutorials trigger LED visualizations on RasQberry?
2. **Offline AI Tutor** - Granite 4.0 Nano for offline Q&A about tutorials?
3. **PWA Dashboard** - Integrate with RasQberry's existing FastAPI backend?
4. **Physical Circuit Composer** - Magnetic tiles → image recognition → quantum circuits?
5. **Container Deployment** - Third deployment target (alongside GitHub Pages and Raspberry Pi) as a container image, supporting both `arm64` and `x64` architectures.
6. **Qiskit Courses** - Pull and host Qiskit learning courses from https://github.com/JanLahmann/Qiskit-documentation/tree/main/learning/courses in addition to tutorials.
7. **Custom Domain** - Make site available at `doQumentation.org`. Domain owned at IONOS. Requires: CNAME file in static/, DNS config at IONOS (CNAME → `janlahmann.github.io`), update `url` in `docusaurus.config.ts` to `https://doQumentation.org`, set `baseUrl` to `/`.

---

## Session Continuity

**Tarball location:** A complete project tarball was created and provided to the user. It needs to be:
1. Uploaded to a new GitHub repository
2. GitHub Pages enabled (Settings → Pages → Source: GitHub Actions)
3. First workflow run triggered

**User context:** Jan is accessing from iPad, planning to use GitHub Codespaces to push the code. The upload flow in Codespaces from iPad may require dragging the file to the Explorer panel.

---

*Document created: February 2025*
*For: RasQberry Tutorials Project Handoff*
