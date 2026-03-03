# Plan: Fix Binder Layer Caching

## Problem

Every Binder build (re-)builds all Docker layers from scratch — including the 7.6 GB
conda base and ~2 GB pip install — because mybinder.org build workers don't share a
Docker layer cache between machines. Even though mybinder.org uses `--cache-from`
pointing to the previously built image, this only works if the previous image is still
in their registry AND the same worker machine handles the build.

Result: every push to `main` (→ `notebooks` branch) triggers a full 10-min rebuild
on all 3 federation members (2i2c, BIDS, GESIS).

Current mitigation: `binder.yml` runs warming after each `deploy.yml` (via
`workflow_run`) + daily cron. Keeps the image alive in Binder's registry (~7-day
eviction window), so users see a fast cache hit. But warming itself is slow (~10 min
× 3 federation members).

## Option C — pip-only, drop conda (try first)

Replace `binder/requirements.txt` (which triggers repo2docker's conda solver) with
a pure `binder/requirements.txt` that repo2docker installs via pip into a pre-existing
Python environment.

**How**: Rename to use repo2docker's pip-only path by using `binder/requirements.txt`
WITHOUT any conda-format specs (no `conda install` lines). repo2docker will use
`python:3.12` slim base + pip install — eliminating the 7.6 GB miniconda layer.

**Steps**:
1. Check if all packages in `binder/requirements.txt` + `binder/postBuild` are
   pip-installable (no conda-only deps). Key packages: qiskit, qiskit-aer,
   qiskit-ibm-runtime, pylatexenc — all pip-installable.
2. Remove `binder/runtime.txt` (no longer needed — Python version set differently).
3. Rewrite `binder/requirements.txt` as plain pip requirements (one package per line,
   optionally pinned).
4. Move postBuild lighter packages into requirements.txt.
5. Test: push to `notebooks` branch, verify Binder build works.
6. Measure: compare build time before/after.

**Risk**: Some packages (e.g. `pyscf`, `ffsim`, `qiskit-nature`) may have C extensions
that need conda for binary wheels. Check if pip wheels are available on PyPI.

**Expected result**: Base layer ~500 MB (python:3.12-slim) instead of 7.6 GB. Build
time reduced from ~10 min to ~2–3 min.

## Option B — Pre-built base image on GHCR (fallback if C fails)

Build a Docker image with all heavy packages once, push to
`ghcr.io/janlahmann/doqumentation-binder-base:latest`. Binder uses it as FROM.

**New files**:
- `binder/Dockerfile` — replaces `binder/requirements.txt` + `binder/postBuild`:
  ```dockerfile
  FROM ghcr.io/janlahmann/doqumentation-binder-base:latest
  COPY --chown=jovyan:jovyan . /home/jovyan/
  ```
- `.github/workflows/binder-base.yml` — builds + pushes base image only when
  `binder/requirements.txt` or `binder/postBuild` changes:
  ```yaml
  on:
    push:
      paths: [binder/requirements.txt, binder/postBuild]
      branches: [notebooks]
    workflow_dispatch:
  jobs:
    build:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: docker/login-action@v3
          with: { registry: ghcr.io, username: ${{ github.actor }},
                  password: ${{ secrets.GITHUB_TOKEN }} }
        - uses: docker/build-push-action@v5
          with:
            context: binder
            file: binder/Dockerfile.base
            push: true
            tags: ghcr.io/janlahmann/doqumentation-binder-base:latest
  ```
- `binder/Dockerfile.base` — the actual heavy build (conda + pip installs).

**Considerations**:
- GHCR image must be public (Binder can pull it without auth).
- The `jovyan` user + PATH + conda setup must match what repo2docker expects.
  Easiest: start FROM `quay.io/jupyter/base-notebook:python-3.12` which already
  has the right user/environment.
- repo2docker compatibility: when a `binder/Dockerfile` is present, repo2docker
  uses it as-is (no further wrapping). Ensure JupyterLab is in the base image.

**Expected result**: Binder build = docker pull base (~fast, layers cached on GHCR) +
COPY notebooks (~30s). Total: ~1–2 min regardless of cache state.

## Decision

Try C first. If any package fails to install via pip, fall back to B.
