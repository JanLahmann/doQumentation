# doQumentation — Open-source website for IBM Quantum's tutorials and learning content

[![Build and Deploy](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml/badge.svg)](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

## We recommend IBM's official platform

For reading and learning, IBM's official [Quantum Platform](https://quantum.cloud.ibm.com) and their [Qiskit documentation](https://quantum.cloud.ibm.com/docs/en/guides) is the best place to start:

- **[Learning](https://quantum.cloud.ibm.com/learning)** — Structured courses from quantum basics to advanced topics
- **[Tutorials](https://quantum.cloud.ibm.com/docs/en/tutorials)** — 40+ tutorials on transpilation, error mitigation, and more
- **[Documentation](https://quantum.cloud.ibm.com/docs/en/guides)** — Guides and API reference for Qiskit
- **[Source repo](https://github.com/Qiskit/documentation)** — All content is open source (CC BY-SA 4.0)

IBM's platform is always up-to-date, well-designed, and the best place to read the documentation.

## What this project adds

IBM's Qiskit tutorials and documentation are open-source, but the web application serving them is not. doQumentation provides an open-source frontend for this content — independently hostable, runnable offline, and deployable on [RasQberry](https://rasqberry.org/).

**See it live at [doQumentation.org](https://doqumentation.org)** — browse tutorials and courses, execute code via Binder, no install required.

## Deployment Tiers

| | [GitHub Pages](https://doqumentation.org) | [Docker (lite)](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | [Docker (jupyter)](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | [RasQberry](https://rasqberry.org/) |
|---|---|---|---|---|
| Browse tutorials | Yes | Yes | Yes | Yes |
| Full-text search | Yes | Yes | Yes | Yes |
| Execute code | Via [Binder](https://mybinder.org) | Via [Binder](https://mybinder.org) | Local Jupyter | Local Jupyter |
| Open in JupyterLab | — | — | Planned | Yes |
| Offline access | — | Yes | Yes | Yes |

## Quick Start

### View Online

**[doqumentation.org](https://doqumentation.org)** — browse tutorials and courses, execute code via Binder, no install required.

### Run with Docker / Podman

```bash
# Lite: static site only (~60 MB)
docker run -p 8080:80 ghcr.io/janlahmann/doqumentation:latest

# With Jupyter + Qiskit for local code execution (~3 GB)
docker run -p 8080:80 -p 8888:8888 ghcr.io/janlahmann/doqumentation:jupyter
```

Access at `http://localhost:8080`. Or build locally with `docker compose up web` (lite) or `docker compose up jupyter` (full). Works with Docker, Podman, or any OCI-compatible runtime.

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
├── docs/                    # Tutorial content (MDX)
├── notebooks/              # Original .ipynb files
├── src/
│   ├── components/
│   │   └── ExecutableCode/ # Interactive code execution
│   ├── config/
│   │   └── jupyter.ts      # Jupyter configuration
│   ├── css/
│   │   └── custom.css      # Carbon-inspired styling
│   ├── pages/
│   │   └── jupyter-settings.tsx
│   └── theme/
│       └── CodeBlock/      # Code block override
├── scripts/
│   └── sync-content.py     # Content sync from upstream
├── binder/                 # Dependency files for Jupyter
├── .github/workflows/
│   ├── deploy.yml          # GitHub Pages deployment
│   └── docker.yml          # Docker build → ghcr.io
├── Dockerfile              # Lite image (nginx)
├── Dockerfile.jupyter      # Full image (nginx + Jupyter + Qiskit)
└── docusaurus.config.ts    # Site configuration
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
