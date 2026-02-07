# doQumentation

[![Build and Deploy](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml/badge.svg)](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

Interactive IBM Quantum tutorials and courses, with live code execution via Jupyter. Part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) project.

**🌐 Live:** [https://doqumentation.org](https://doqumentation.org)

## Features

| Feature | GitHub Pages | Docker | RasQberry Pi |
|---------|--------------|--------|--------------|
| 📖 Browse tutorials | ✅ | ✅ | ✅ |
| 🔍 Full-text search | ✅ | ✅ | ✅ |
| ▶️ Execute code | ⚠️ Via Binder | ⚠️ Via Binder | ✅ Local Jupyter |
| 🔬 Open in JupyterLab | ❌ | ❌ | ✅ |
| 📴 Offline access | ❌ | ✅ | ✅ |

## Quick Start

### Option 1: View Online

Visit [https://doqumentation.org](https://doqumentation.org)

### Option 2: Run Locally (Development)

```bash
# Clone the repository
git clone https://github.com/JanLahmann/doQumentation.git
cd doQumentation

# Install dependencies
npm install

# Sync content from Qiskit/documentation
python scripts/sync-content.py --sample-only  # or without flag for full sync

# Start development server
npm start
```

### Option 3: Run with Docker

```bash
docker pull ghcr.io/janlahmann/doqumentation:latest
docker run -p 8080:80 ghcr.io/janlahmann/doqumentation:latest
```

Access at `http://localhost:8080`.

Or build locally:

```bash
docker compose up
```

### Option 4: Deploy to Raspberry Pi

```bash
# Download latest release
wget https://github.com/JanLahmann/doQumentation/releases/latest/download/doQumentation-pi.tar.gz

# Extract
tar -xzf doQumentation-pi.tar.gz
cd doQumentation-pi

# Install (requires RQB2 venv with Qiskit)
./install.sh
```

Access at `http://rasqberry.local` or your Pi's IP address.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Single Codebase                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Docusaurus Static Site                      │   │
│   │  • MDX tutorials (transformed from Qiskit/documentation) │   │
│   │  • Carbon-inspired styling                               │   │
│   │  • Pagefind search                                       │   │
│   │  • KaTeX math rendering                                  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│   │ GitHub Pages │  │   Docker     │  │ RasQberry Pi │         │
│   ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│   │ Static only  │  │ nginx in     │  │ nginx        │         │
│   │ Binder exec  │  │ container    │  │ Jupyter :8888│         │
│   └──────────────┘  │ amd64+arm64  │  │ JupyterLab   │         │
│                     └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Code Execution

Python code blocks include a **Run** button that connects to a Jupyter kernel via thebelab:
- **RasQberry:** Connects to local Jupyter server (port 8888)
- **GitHub Pages / Docker:** Uses [Binder](https://mybinder.org) (first launch may take 1–2 minutes)
- **Custom:** Configure your own server in Settings

On RasQberry, an **Open in Lab** button opens the full notebook in JupyterLab.

## Project Structure

```
doQumentation/
├── docs/                    # Tutorial content (MDX)
│   ├── index.mdx           # Home page
│   └── tutorials/          # Tutorial pages
├── notebooks/              # Original .ipynb files
├── src/
│   ├── components/
│   │   └── ExecutableCode/ # Interactive code component
│   ├── config/
│   │   └── jupyter.ts      # Jupyter configuration
│   ├── css/
│   │   └── custom.css      # Carbon-inspired styling
│   ├── pages/
│   │   └── jupyter-settings.tsx
│   └── theme/
│       └── CodeBlock/      # Code block override
├── scripts/
│   ├── sync-content.py     # Content sync from upstream
│   └── setup-pi.sh         # Raspberry Pi setup
├── .github/workflows/
│   ├── deploy.yml          # GitHub Pages deployment
│   └── docker.yml          # Docker build and push to ghcr.io
├── docusaurus.config.ts    # Site configuration
└── sidebars.ts             # Navigation structure
```

## Content Synchronization

Tutorials are sourced from [Qiskit/documentation](https://github.com/Qiskit/documentation) and transformed for Docusaurus compatibility:

```bash
# Full sync (requires git, Python, jupyter)
python scripts/sync-content.py

# Sample content only (for testing)
python scripts/sync-content.py --sample-only

# Skip git clone (use existing upstream)
python scripts/sync-content.py --no-clone
```

### MDX Transformations

| Qiskit Syntax | Docusaurus Equivalent |
|---------------|----------------------|
| `<Admonition type="note">` | `:::note` |
| `<Admonition type="attention">` | `:::warning` |
| `<Tabs>` / `<TabItem>` | Same (native) |
| Math: `$...$`, `$$...$$` | Same (KaTeX) |

## Development

### Prerequisites

- Node.js 18+
- Python 3.9+
- Jupyter (for notebook conversion)

### Commands

```bash
# Start development server
npm start

# Build for production
npm run build

# Build search index
npm run build:search

# Type check
npm run typecheck

# Sync content
npm run sync-content
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

2. Add to `sidebars.ts` for navigation.

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

### Manual Release

1. Go to Actions → "Build and Deploy"
2. Click "Run workflow"
3. Select target: `ghpages`, `pi-release`, or `both`

### Docker

Push to `main` also builds and pushes a multi-arch image (`linux/amd64` + `linux/arm64`) to GitHub Container Registry:

```bash
docker pull ghcr.io/janlahmann/doqumentation:latest
docker run -p 8080:80 ghcr.io/janlahmann/doqumentation:latest
```

### Raspberry Pi

Download and run the release package:

```bash
wget https://github.com/JanLahmann/doQumentation/releases/latest/download/doQumentation-pi.tar.gz
tar -xzf doQumentation-pi.tar.gz
cd doQumentation-pi
./install.sh
```

## Configuration

### Jupyter Server (Pi)

Edit `~/.jupyter/jupyter_server_config.py`:

```python
c.ServerApp.token = 'your-token'
c.ServerApp.port = 8888
c.ServerApp.allow_origin = '*'
```

### Custom Jupyter (Browser)

Visit `/jupyter-settings` to configure a custom Jupyter server URL.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run `npm run build` to verify
5. Submit a pull request

## License

- **Tutorial content:** © IBM Corp, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- **Site code:** [Apache 2.0](LICENSE)

## Acknowledgments

- [IBM Quantum](https://quantum.ibm.com) for Qiskit and tutorials
- [Docusaurus](https://docusaurus.io) for the documentation framework
- [Thebe](https://thebe.readthedocs.io) for Jupyter integration
- [qotlabs](https://github.com/qotlabs/qiskit-documentation) for inspiration

---

Part of the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) project.
