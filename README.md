# doQumentation — Open-source website for IBM Quantum's tutorials and learning content

[![Qiskit Ecosystem](https://qisk.it/e-dd84980a)](https://qisk.it/e)
[![Build and Deploy](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml/badge.svg)](https://github.com/JanLahmann/doQumentation/actions/workflows/deploy.yml)
[![License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](LICENSE)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/Content-CC%20BY--SA%204.0-lightgrey.svg)](LICENSE-DOCS)

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

| | [GitHub Pages](https://doqumentation.org) | [Docker / Podman](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation) (`:jupyter`) | [RasQberry](https://rasqberry.org/) |
|---|---|---|---|
| Browse tutorials, guides, & courses | Yes, 17 languages | Yes, English | Yes, English |
| Full-text search | Yes | Yes | Yes |
| Execute code | Via [Binder](https://mybinder.org) | Local Jupyter | Local Jupyter |
| JupyterLab | Via Binder | On port 8888 (token) | On port 8888 (token) |
| Offline access | — | Yes | Yes |

## Quick Start

### View Online

**[doqumentation.org](https://doqumentation.org)** — browse tutorials and courses, execute code via Binder, no install required.

### Run with Podman / Docker

```bash
# Site + Jupyter + Qiskit: about 1.2 GB to download, ~3 GB on disk.
# Pull it before you travel if the venue has no internet.
podman run -d --name doq --restart unless-stopped \
  -e JUPYTER_TOKEN=choose-a-token \
  -p 8080:80 -p 127.0.0.1:8888:8888 \
  ghcr.io/janlahmann/doqumentation:jupyter
```

Access at `http://localhost:8080`. Using Docker instead? Replace `podman` with `docker`; the commands are identical. Or build locally with `podman compose --profile jupyter up`. Images are multi-arch (`linux/amd64` + `linux/arm64`).

**Jupyter token:** Code execution through the website on port 8080 needs no token. JupyterLab on port 8888 asks for the token: the one you pass with `-e JUPYTER_TOKEN=…`, or, without it, a random token printed in the container logs (`podman logs doq`), which changes on every restart. `-p 127.0.0.1:8888:8888` keeps JupyterLab reachable from the host machine only; drop `127.0.0.1:` to reach it from other machines.

**Classroom use:** one container can serve a whole room. Participants on the same network open `http://<host-ip>:8080` (or `http://<hostname>.local:8080`) and can run code. Code execution is accepted only from the site itself when it is reached by a local-network address (loopback, private IP, `.local` or single-label name), so other websites a participant has open cannot use the server. To let a site at another address use it too (for example a copy of the site you host yourself), list that address: `-e CORS_ORIGIN=https://docs.example.org`. `CORS_ORIGIN` takes a comma-separated list; plain `http://` is accepted only for local-network hosts.

Switches for workshops (pass with `-e`):

| Variable | Default | Effect |
|---|---|---|
| `LAB_ENABLED` | `false` | `true` shows an "Open in JupyterLab" button on notebook pages. It needs JupyterLab reachable at `/lab` on the site's address, which this image's web server does not provide; the teacher uses port 8888 instead. |
| `ALLOW_TERMINALS` | `false` | `true` lets anyone who can open the site start a shell in the container. Leave it off for a room of participants. |
| `CULL_IDLE_TIMEOUT` | `600` | Seconds before an idle kernel is shut down (`0` = never). |

All participants share one Jupyter server and one user account in the container: any of them can run arbitrary Python there. Use it with a group you trust, keep secrets out of the container, and restart it between groups (`podman restart doq`).

### Deploy to RasQberry

[RasQberry Two](https://rasqberry.org/) ships this image as its Workshop & Qiskit Server; see rasqberry.org for how to start it on the Pi.

### Development

**Prerequisites:** Node.js 20+, Python 3.9+ (only for content sync and the translation tools)

```bash
git clone https://github.com/JanLahmann/doQumentation.git
cd doQumentation
npm install
npm start              # English dev server at http://localhost:3000
```

`docs/` (the generated English pages) is committed, so `npm start` needs no sync. Do not edit `docs/` by hand: it is regenerated from upstream by `scripts/sync-content.py`. Content fixes belong upstream in [Qiskit/documentation](https://github.com/Qiskit/documentation); translations live in `i18n/<locale>/po/` and are written only by the tools in `translation/v2/`.

Other commands:

```bash
npm run typecheck                                    # Type check
NODE_OPTIONS=--max-old-space-size=8192 \
  npx docusaurus build --locale en                   # Production build of ONE locale
npx docusaurus start --locale de                     # Dev server for a translated locale (render it first, see translation/v2/README.md)
python3 scripts/sync-content.py                      # Full content sync from upstream (needs the upstream-docs submodule)
```

Build one locale at a time. `npm run build` builds all 18 locales and needs far more memory than a laptop has; CI builds each locale in its own job.

## How It Works

Tutorial content is sourced from [Qiskit/documentation](https://github.com/Qiskit/documentation) and transformed into a [Docusaurus](https://docusaurus.io) site with executable code blocks. Python code connects to a Jupyter kernel via [thebelab](https://github.com/executablebooks/thebelab):

- **GitHub Pages:** Uses [Binder](https://mybinder.org) for remote execution (first run may take 1-2 min)
- **Docker / RasQberry:** Connects to a local Jupyter server with Qiskit pre-installed
- **Custom:** Configure any Jupyter endpoint in [Settings](https://doqumentation.org/jupyter-settings)

On doqumentation.org, an **Open in JupyterLab** button opens the full notebook on Binder.

## Content Synchronization

```bash
python scripts/sync-content.py                              # Full sync (requires git, Python, jupyter)
python scripts/sync-content.py --sample-only                # Sample only (for testing)
python scripts/sync-content.py --no-clone                   # Use existing upstream clone
python scripts/sync-content.py --freshness-report report.md # Markdown report of EN-vs-upstream
                                                            # drift + per-locale staleness
```

**Rolling back a bad sync.** If a content sync introduces a regression, revert the merge commit on `main` and force-push (or use the GitHub "Revert" button). The `deploy.yml` workflow republishes the prior site within ~5 min. Translated locales follow on the next `deploy-locales.yml` run. The `upstream-docs/` submodule pointer is part of the revert, so subsequent `sync-content.py` runs replay against the rolled-back upstream until the underlying issue is fixed.

## Project Structure

```
doQumentation/
├── upstream-docs/                 # Git submodule → Qiskit/documentation (CC BY-SA 4.0)
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
│   └── setup-pi.sh                # native Pi install (unsupported, see #385; use the container)
├── binder/
│   └── jupyter-requirements-security.txt # CVE floors on top of the QuBins base image
├── .github/workflows/
│   ├── deploy.yml                 # Sync → build → deploy to GitHub Pages
│   └── docker.yml                 # Multi-arch Docker → ghcr.io
├── Dockerfile.jupyter             # Full stack: site + Jupyter + Qiskit on ghcr.io/qubins/images (~3 GB)
├── docker-compose.yml             # jupyter service (jupyter-local target)
├── nginx.conf                     # SPA routing + Jupyter proxy
├── docusaurus.config.ts           # Site configuration
└── sidebars.ts                    # Navigation (imports generated sidebar JSONs)
```

## Deployment

Pushing to `main` automatically deploys to GitHub Pages and builds two multi-arch Docker images (`linux/amd64` + `linux/arm64`) to [GitHub Container Registry](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation).

## Contributing

Ways to help, from no tools to the full pipeline:

- **Ask a question or suggest an idea** in
  [Discussions](https://github.com/JanLahmann/doQumentation/discussions),
  one question per discussion. Issues are for bugs and wrong translations.
- **Read pages in your language and report what is wrong.** Use the
  [Wrong or awkward translation](https://github.com/JanLahmann/doQumentation/issues/new?template=translation-report.yml)
  form; no tools or accounts beyond GitHub needed. A fluent reader is the
  most valuable reviewer this project has.
- **Report a site bug or code that does not run** with the
  [Site bug](https://github.com/JanLahmann/doQumentation/issues/new?template=site-bug.yml) or
  [Code does not run](https://github.com/JanLahmann/doQumentation/issues/new?template=execution-error.yml) forms.
- **Run a review round with Claude Code** (below).
- **Code:** see Development above. `docs/` and `i18n/*/po/` are generated; change the scripts, not the files.

The translations into 17 languages are machine-produced and then reviewed
against the English source, page by page. That review is where help is most
useful, and it is designed to be run **by Claude Code** rather than by hand.

- **[CONTRIBUTING-NOW.md](CONTRIBUTING-NOW.md)** — what we need right now:
  which locales still have unreviewed pages, how much is left in each, and
  what recent rounds have been finding. Regenerated daily; start here.
- **[CONTRIBUTING-REVIEWS.md](CONTRIBUTING-REVIEWS.md)** — the complete
  recipe for running one review round.
- **[CONTRIBUTING-TRANSLATIONS.md](CONTRIBUTING-TRANSLATIONS.md)** — for
  translating newly-synced English content.

The shortest path: fork the repo, clone your fork, open Claude Code in it
and say **"I want to help with reviews. What should I do?"** The repo's
`CLAUDE.md` routes that to the recipe, checks your setup and asks for what
is missing. You need a Claude Max subscription, `git`, `python3`, the `gh`
CLI, and po4a + gettext + `polib` to render a locale locally.

Claim a locale first so two people don't review the same one: open an
issue with the **Claim a locale** template (label `translation-claim`);
the open claims are listed in `CONTRIBUTING-NOW.md`.

**Sync your fork with upstream `main` before every session** — not just on
the first clone. Which pages still need work is read from a status file that
every merged round rewrites, so a fork that is a few days old will send you
to re-do pages someone has already finished:

```bash
gh repo sync <YOUR-USER>/doQumentation --source JanLahmann/doQumentation --branch main
```

## License

This repository is dual-licensed:

- **Code** (scripts, source files, configuration) — [Apache License 2.0](LICENSE)
- **Content** (tutorials, guides, courses, media, translations) — [CC BY-SA 4.0](LICENSE-DOCS)

Upstream content from [Qiskit/documentation](https://github.com/Qiskit/documentation) © IBM Corp is tracked as a git submodule in `upstream-docs/`. Translations in `i18n/` are adapted material under CC BY-SA 4.0. See [NOTICE](NOTICE) for full attribution.

## Acknowledgments

- [IBM Quantum](https://quantum.cloud.ibm.com) for Qiskit and the open-source tutorials
- [Docusaurus](https://docusaurus.io) for the documentation framework
- [thebelab](https://github.com/executablebooks/thebelab) for Jupyter integration


---

[Qiskit documentation](https://github.com/Qiskit/documentation) content © IBM Corp. Code is licensed under [Apache 2.0](LICENSE); content (tutorials, courses, media, translations) under [CC BY-SA 4.0](LICENSE-DOCS). See [NOTICE](NOTICE) for full attribution.
IBM, IBM Quantum, and Qiskit are trademarks of IBM Corporation. doQumentation is part of the [RasQberry](https://rasqberry.org/) project and is not affiliated with, endorsed by, or sponsored by IBM Corporation.

<!-- FWQ-FAMILY:START format=list — generated from family.json in JanLahmann/Fun-with-Quantum, do not edit by hand -->
## Part of the Fun with Quantum family

This project is part of [**Fun with Quantum**](https://fun-with-quantum.org), a family of open-source quantum outreach projects: [Fun with Quantum](https://fun-with-quantum.org) · [RasQberry Two](https://rasqberry.org) · [RasQberry One](https://rasqberry.one) · [Quantego](https://quantego.org) · [Qutie](https://qutie.org) · [Qoffee-Maker](https://qoffee-maker.org) · [Entangible](https://entangible.org) · [CertiQ](https://certiq.dev) · [QuBins](https://qubins.org) · [QAMPoser](https://qamposer.org).

*God does play dice. Come play, build, learn.*
<!-- FWQ-FAMILY:END -->
