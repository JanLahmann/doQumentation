# RasQberry Tutorials

[![Build and Deploy](https://github.com/JanLahmann/rasqberry-tutorials/actions/workflows/deploy.yml/badge.svg)](https://github.com/JanLahmann/rasqberry-tutorials/actions/workflows/deploy.yml)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-sa/4.0/)

IBM Quantum tutorials optimized for local hosting on [RasQberry](https://github.com/JanLahmann/RasQberry-Two), with interactive code execution via Jupyter.

**🌐 Live Demo:** [https://janlahmann.github.io/rasqberry-tutorials](https://janlahmann.github.io/rasqberry-tutorials)

## Features

| Feature | GitHub Pages | RasQberry Pi |
|---------|--------------|--------------|
| 📖 Browse tutorials | ✅ | ✅ |
| 🔍 Full-text search | ✅ | ✅ |
| ▶️ Execute code | ⚠️ Via Binder | ✅ Local Jupyter |
| 🔬 Open in JupyterLab | ❌ | ✅ |
| 📴 Offline access | ❌ | ✅ |

## Quick Start

### Option 1: View Online

Visit [https://janlahmann.github.io/rasqberry-tutorials](https://janlahmann.github.io/rasqberry-tutorials)

### Option 2: Run Locally (Development)

```bash
# Clone the repository
git clone https://github.com/JanLahmann/rasqberry-tutorials.git
cd rasqberry-tutorials

# Install dependencies
npm install

# Sync content from Qiskit/documentation
python scripts/sync-content.py --sample-only  # or without flag for full sync

# Start development server
npm start
```

### Option 3: Deploy to Raspberry Pi

```bash
# Download latest release
wget https://github.com/JanLahmann/rasqberry-tutorials/releases/latest/download/rasqberry-tutorials-pi.tar.gz

# Extract
tar -xzf rasqberry-tutorials-pi.tar.gz
cd rasqberry-tutorials-pi

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
│   │ GitHub Pages │  │ RasQberry Pi │  │   Custom     │         │
│   ├──────────────┤  ├──────────────┤  ├──────────────┤         │
│   │ Static only  │  │ nginx        │  │ Any static   │         │
│   │ Binder exec  │  │ Jupyter :8888│  │ host         │         │
│   └──────────────┘  │ JupyterLab   │  └──────────────┘         │
│                     └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Code Execution Modes

The `ExecutableCode` component provides three interaction modes:

### 📖 Read Mode (Default)
Static syntax-highlighted code display.

### ▶️ Run Mode (Thebe)
Execute code in a Jupyter kernel:
- **RasQberry:** Connects to local Jupyter server (port 8888)
- **GitHub Pages:** Uses [Binder](https://mybinder.org) (slower startup)
- **Custom:** Configure your own server in Settings

### 🔬 Lab Mode
Open the full notebook in JupyterLab (RasQberry only).

## Project Structure

```
rasqberry-tutorials/
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
│   └── deploy.yml          # CI/CD pipeline
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

### Raspberry Pi

Download and run the release package:

```bash
wget https://github.com/JanLahmann/rasqberry-tutorials/releases/latest/download/rasqberry-tutorials-pi.tar.gz
tar -xzf rasqberry-tutorials-pi.tar.gz
cd rasqberry-tutorials-pi
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
