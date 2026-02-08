# doQumentation

[![Build and Deploy](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml/badge.svg)](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

An open-source website that recreates [IBM Quantum's](https://quantum.ibm.com) tutorials and learning platform from their [open-source content](https://github.com/Qiskit/documentation). Part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) project.

**We recommend the official IBM Quantum platform for the best experience:**
[Learning](https://quantum.cloud.ibm.com/learning) · [Tutorials](https://quantum.cloud.ibm.com/docs/en/tutorials) · [Documentation](https://docs.quantum.ibm.com/) · [Source repo](https://github.com/Qiskit/documentation)

IBM's Qiskit tutorials and documentation are open-source, but the web application serving them is not. doQumentation provides an open-source frontend for this content — independently hostable, runnable offline, and deployable on devices like the Raspberry Pi.

**Live:** [doqumentation.org](https://doqumentation.org)

## Deployment Tiers

| | [GitHub Pages](https://doqumentation.org) | [Docker (lite)](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | [Docker (jupyter)](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) | [RasQberry Pi](https://github.com/JanLahmann/RasQberry-Two) |
|---|---|---|---|---|
| Browse tutorials | Yes | Yes | Yes | Yes |
| Full-text search | Yes | Yes | Yes | Yes |
| Execute code | Via [Binder](https://mybinder.org) | Via [Binder](https://mybinder.org) | Local Jupyter | Local Jupyter |
| Open in JupyterLab | — | — | — | Yes |
| Offline access | — | Yes | Yes | Yes |

## Quick Start

### View Online

Visit [doqumentation.org](https://doqumentation.org)

### Run with Docker

```bash
# Lite: static site only (~60 MB)
docker run -p 8080:80 ghcr.io/janlahmann/doqumentation:latest

# With Jupyter + Qiskit for local code execution (~3 GB)
docker run -p 8080:80 -p 8888:8888 ghcr.io/janlahmann/doqumentation:jupyter
```

Access at `http://localhost:8080`. Or build locally with `docker compose up web` (lite) or `docker compose up jupyter` (full).

### Deploy to Raspberry Pi

```bash
wget https://github.com/JanLahmann/doQumentation/releases/latest/download/doQumentation-pi.tar.gz
tar -xzf doQumentation-pi.tar.gz
cd doQumentation-pi && ./install.sh
```

Access at `http://rasqberry.local` or your Pi's IP address.

### Development

```bash
git clone https://github.com/JanLahmann/doQumentation.git
cd doQumentation
npm install
python scripts/sync-content.py --sample-only  # or without flag for full sync
npm start
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

## Development

### Prerequisites

- Node.js 18+
- Python 3.9+
- Jupyter (for notebook conversion)

### Commands

```bash
npm start              # Development server
npm run build          # Production build
npm run build:search   # Build search index
npm run typecheck      # Type check
npm run sync-content   # Sync content from upstream
```

### Adding Custom Tutorials

1. Create an MDX file in `docs/tutorials/`:

```mdx
---
title: My Tutorial
sidebar_label: My Tutorial
---

# My Tutorial

Some explanation...

```python
from qiskit import QuantumCircuit
qc = QuantumCircuit(2)
qc.h(0)
print(qc)
```

This code is automatically executable!
```

2. The sidebar is auto-generated from the file structure.

### Code Block Options

```mdx
```python
# Default: executable

```python noexec
# Not executable (display only)

```python notebook="tutorials/my-notebook.ipynb"
# Link to notebook for "Open in Lab"

```bash
# Non-Python: never executable
```

## Deployment

### GitHub Pages (Automatic)

Push to `main` branch triggers automatic deployment.

### Docker

Push to `main` builds and pushes two multi-arch images (`linux/amd64` + `linux/arm64`) to GitHub Container Registry:

```bash
docker run -p 8080:80 ghcr.io/janlahmann/doqumentation:latest          # Lite (~60 MB)
docker run -p 8080:80 -p 8888:8888 ghcr.io/janlahmann/doqumentation:jupyter  # Full (~3 GB)
```

### Manual Release

1. Go to Actions > "Build and Deploy"
2. Click "Run workflow"
3. Select target: `ghpages`, `pi-release`, or `both`

## License

- **Tutorial content:** © IBM Corp, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- **Site code:** [Apache 2.0](LICENSE)

## Acknowledgments

- [IBM Quantum](https://quantum.ibm.com) for Qiskit and the open-source tutorials
- [Docusaurus](https://docusaurus.io) for the documentation framework
- [thebelab](https://github.com/executablebooks/thebelab) for Jupyter integration
- [qotlabs](https://github.com/qotlabs/qiskit-documentation) for inspiration

---

Part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) project.
