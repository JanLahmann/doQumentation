# doQumentation — Open-source website for IBM Quantum's tutorials and learning content

[![Build and Deploy](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml/badge.svg)](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

## IBM Quantum's open-source content

IBM provides a wealth of quantum computing learning material — all open source under CC BY-SA 4.0:

- **[Learning](https://quantum.cloud.ibm.com/learning)** — Structured courses from quantum basics to advanced topics
- **[Tutorials](https://quantum.cloud.ibm.com/docs/en/tutorials)** — 40+ tutorials on transpilation, error mitigation, and more
- **[Documentation](https://quantum.cloud.ibm.com/docs/en/guides)** — Guides and API reference for Qiskit
- **[Source repo](https://github.com/Qiskit/documentation)** — All content on GitHub

Their [Quantum Platform](https://quantum.cloud.ibm.com) is always up-to-date and well-designed — the best place for reading, learning, and reference.

## What this project adds

IBM's [Qiskit documentation](https://github.com/Qiskit/documentation) is open source (CC BY-SA 4.0), but their web application is not. doQumentation adds an open-source frontend with live code execution, automatic credential injection, and simulator mode — independently hostable, runnable offline, and deployable on [RasQberry](https://rasqberry.org/).

**See it live at [doQumentation.org](https://doqumentation.org)** — browse tutorials, guides, and courses, execute code via Binder, no install required.

**Content:** 42 Tutorials, 171 Guides, 154 Course pages, 14 Modules (~380 pages total).

## Deployment Tiers

| | [GitHub Pages](https://doqumentation.org) | [Docker (lite)](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | [Docker (jupyter)](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | [RasQberry](https://rasqberry.org/) |
|---|---|---|---|---|
| Browse tutorials, guides, & courses | Yes | Yes | Yes | Yes |
| Full-text search | Yes | Yes | Yes | Yes |
| Execute code | Via [Binder](https://mybinder.org) | Via [Binder](https://mybinder.org) | Local Jupyter | Local Jupyter |
| Open in JupyterLab | — | — | Planned | Yes |
| Offline access | — | Yes | Yes | Yes |

## Quick Start

### View Online

**[doqumentation.org](https://doqumentation.org)** — browse tutorials and courses, execute code via Binder, no install required.

### Run with Podman / Docker

```bash
# Full stack: site + Jupyter + Qiskit (~3 GB)
podman run -p 8080:80 -p 8888:8888 ghcr.io/janlahmann/doqumentation:jupyter

# Lite: static site only (~60 MB) — code execution still works via Binder
podman run -p 8080:80 ghcr.io/janlahmann/doqumentation:latest
```

Access at `http://localhost:8080`. Using Docker instead? Just replace `podman` with `docker` — the commands are identical. Or build locally with `podman compose --profile jupyter up` (full) or `podman compose --profile web up` (lite). Images are multi-arch (`linux/amd64` + `linux/arm64`).

**Jupyter token:** The full-stack container generates a random authentication token at startup (printed in the container logs). Code execution through the website on port 8080 is transparent — no token needed. Direct JupyterLab access on port 8888 requires the token. To set a fixed token: `JUPYTER_TOKEN=mytoken podman run ...`

### Deploy to RasQberry

> **Note:** RasQberry deployment is under development. Instructions will be provided soon.

<!--
```bash
wget https://github.com/JanLahmann/doQumentation/releases/latest/download/doQumentation-pi.tar.gz
tar -xzf doQumentation-pi.tar.gz
cd doQumentation-pi && ./install.sh
```

Access at `http://rasqberry.local` or your Pi's IP address.
-->

### Development

**Prerequisites:** Node.js 18+, Python 3.9+

```bash
git clone https://github.com/JanLahmann/doQumentation.git
cd doQumentation
npm install
python scripts/sync-content.py --sample-only  # or without flag for full sync
npm start
```

Other commands:

```bash
npm run build          # Production build
npm run build:search   # Build search index
npm run typecheck      # Type check
npm run sync-content   # Sync content from upstream
```

## How It Works

Tutorial content is sourced from [Qiskit/documentation](https://github.com/Qiskit/documentation) and transformed into a [Docusaurus](https://docusaurus.io) site with executable code blocks. Python code connects to a Jupyter kernel via [thebelab](https://github.com/executablebooks/thebelab):

- **GitHub Pages:** Uses [Binder](https://mybinder.org) for remote execution (first run may take 1-2 min)
- **Docker / RasQberry:** Connects to a local Jupyter server with Qiskit pre-installed
- **Custom:** Configure any Jupyter endpoint in [Settings](https://doqumentation.org/jupyter-settings)

On RasQberry, an **Open in Lab** button opens the full notebook in JupyterLab.

## Content Synchronization

```bash
python scripts/sync-content.py                # Full sync (requires git, Python, jupyter)
python scripts/sync-content.py --sample-only  # Sample only (for testing)
python scripts/sync-content.py --no-clone     # Use existing upstream clone
```

## Project Structure

```
doQumentation/
├── docs/                          # Tutorial content (MDX, mostly generated)
│   └── index.mdx                  # Homepage (source of truth, preserved by sync)
├── notebooks/                     # Original .ipynb for JupyterLab (generated)
├── src/
│   ├── components/
│   │   ├── ExecutableCode/        # Run/Stop toggle, thebelab, kernel injection
│   │   ├── CourseComponents/      # IBMVideo, DefinitionTooltip, Figure, etc.
│   │   ├── GuideComponents/       # Card, CardGroup, OperatingSystemTabs, etc.
│   │   └── OpenInLabBanner/       # "Open in JupyterLab" button
│   ├── config/
│   │   └── jupyter.ts             # Environment detection, credential/simulator storage
│   ├── css/
│   │   └── custom.css             # Carbon-inspired styling
│   ├── pages/
│   │   └── jupyter-settings.tsx   # Settings (IBM credentials, simulator, custom server)
│   └── theme/
│       ├── CodeBlock/             # Swizzle: wraps Python blocks with ExecutableCode
│       └── MDXComponents.tsx      # IBM component stubs (Admonition, Image, etc.)
├── scripts/
│   ├── sync-content.py            # Pull & transform content from upstream
│   ├── sync-deps.py               # Sync Jupyter deps with arch exception rules
│   └── setup-pi.sh                # Raspberry Pi setup
├── binder/
│   ├── jupyter-requirements.txt       # Full Qiskit deps (cross-platform)
│   └── jupyter-requirements-amd64.txt # amd64-only extras
├── .github/workflows/
│   ├── deploy.yml                 # Sync → build → deploy to GitHub Pages
│   ├── docker.yml                 # Multi-arch Docker → ghcr.io
│   └── sync-deps.yml              # Weekly Jupyter dependency sync auto-PR
├── Dockerfile                     # Static site only (nginx, ~60 MB)
├── Dockerfile.jupyter             # Full stack: site + Jupyter + Qiskit (~3 GB)
├── docker-compose.yml             # web + jupyter services
├── nginx.conf                     # SPA routing + Jupyter proxy
├── docusaurus.config.ts           # Site configuration
└── sidebars.ts                    # Navigation (imports generated sidebar JSONs)
```

## Deployment

Pushing to `main` automatically deploys to GitHub Pages and builds two multi-arch Docker images (`linux/amd64` + `linux/arm64`) to [GitHub Container Registry](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation).

## License

- **Tutorial content:** © IBM Corp, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- **Site code:** [Apache 2.0](LICENSE)

## Acknowledgments

- [IBM Quantum](https://quantum.cloud.ibm.com) for Qiskit and the open-source tutorials
- [Docusaurus](https://docusaurus.io) for the documentation framework
- [thebelab](https://github.com/executablebooks/thebelab) for Jupyter integration


---

[Qiskit documentation](https://github.com/Qiskit/documentation) content © IBM Corp. Code is licensed under Apache 2.0; content (tutorials, courses, media) under CC BY-SA 4.0.
IBM, IBM Quantum, and Qiskit are trademarks of IBM Corporation. doQumentation is part of the [RasQberry](https://rasqberry.org/) project and is not affiliated with, endorsed by, or sponsored by IBM Corporation.
