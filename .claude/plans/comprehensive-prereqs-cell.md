# Plan: Comprehensive Prerequisites Cell for Colab/Binder Notebooks

## Context

Each notebook gets two pip install cells injected by `copy_notebook_with_rewrite()` in `scripts/sync-content.py`:
- **Cell 0** (base): `!pip install -q qiskit qiskit-aer qiskit-ibm-runtime pylatexenc` — auto-runs on Colab
- **Cell 1** (extras, optional): per-notebook dependencies detected by `analyze_notebook_imports()`

Cell 1 filters imports against `BINDER_PROVIDED` (line 310) — a set of ~60 packages verified against the **old** Binder image (JanLahmann/Qiskit-documentation, Feb 2026). This creates a gap:

**Bug**: Packages in `BINDER_PROVIDED` that are NOT in Colab's default environment and NOT in Cell 0 will be **missing on Colab**. Examples: `qiskit-ibm-catalog`, `pyscf`, `qiskit-addon-utils` are in `BINDER_PROVIDED` (filtered out of Cell 1) but NOT installed by Cell 0 and NOT pre-installed on Colab.

Additionally, `BINDER_PROVIDED` is now stale — it was verified against the sister repo's Binder image, but this repo's `notebooks` branch has a different `binder/requirements.txt` (only 7 packages vs the full list).

## Proposed Fix

**Stdlib-only filtering**: Remove `BINDER_PROVIDED` entirely. Filter imports only against Python's stdlib (built into Python, never stale). ALL third-party imports go into a single comprehensive pip install cell. Zero maintenance.

On Binder: fast no-op (~1-2s, all packages pre-installed). On Colab: installs what's missing (pre-installed packages are fast no-ops too).

### Result for user

**Before** (2 cells, incomplete on Colab):
```python
# Cell 0 (auto-runs):
!pip install -q qiskit qiskit-aer qiskit-ibm-runtime pylatexenc

# Cell 1 (extras only — misses Binder-only packages like qiskit-ibm-catalog):
!pip install -q python-sat
```

**After** (1 cell, complete, auto-runs on Colab):
```python
# Install required packages (runs automatically in Colab, fast no-op in Binder)
!pip install -q qiskit qiskit-aer qiskit-ibm-runtime pylatexenc numpy scipy matplotlib qiskit-ibm-catalog python-sat
```

## Changes

### `scripts/sync-content.py`

**Delete `BINDER_PROVIDED` (lines 307–328)** — no longer needed.

**Simplify `analyze_notebook_imports()` (lines 331–399)**: remove `BINDER_PROVIDED` check at line 388. Only filter against `sys.stdlib_module_names` + packages the notebook itself already installs.

**Merge Cell 0 + Cell 1 in `copy_notebook_with_rewrite()` (lines 920–950)**:
```python
# Compute ALL non-stdlib third-party deps for this notebook
extra_pkgs = analyze_notebook_imports(cells)
all_pkgs = list(COLAB_BASE_PKGS)
for p in extra_pkgs:
    if p not in all_pkgs:
        all_pkgs.append(p)

prereq_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": [
        "# Install required packages (runs automatically in Colab, fast no-op in Binder)\n",
        f"!pip install -q {' '.join(all_pkgs)}"
    ]
}
nb['cells'] = [prereq_cell] + cells
```

**Update `generate_translated_notebook()`** (~lines 1108–1291): same single-cell logic (currently mirrors the two-cell pattern).

**Update MDX pip block injection** (lines 476–490): update comment text to match.

## Files Modified

1. `scripts/sync-content.py` — Delete `BINDER_PROVIDED`, simplify `analyze_notebook_imports()`, merge two cells into one in `copy_notebook_with_rewrite()` + `generate_translated_notebook()`

## Verification

1. `python scripts/sync-content.py` — inspect `build/notebooks/tutorials/hello-world.ipynb`: single prereq cell with base + detected packages
2. Check a notebook that imports `qiskit_ibm_catalog` (e.g., one of the catalog tutorials) — should appear in the single cell
3. Open generated notebook in Colab — all imports resolve after auto-run cell
4. Open in Binder — pip install is a fast no-op (~1-2s)
5. `npm run build` — no regressions in MDX pip blocks on site
6. Spot-check translated notebook (e.g., `static/notebooks/de/tutorials/hello-world.ipynb`) — same single-cell pattern
