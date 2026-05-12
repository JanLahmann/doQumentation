# Notebook CI

Manual-trigger CI that executes English notebooks against local fake backends
so we catch regressions (especially from weekly Qiskit bumps) without touching
real IBM hardware or paid services.

## How it works

`.github/workflows/notebook-ci.yml` does, in one job:

1. Checkout the chosen source:
   - `source=main`: this branch (PoC notebooks under `local-content/`).
   - `source=notebooks`: the built `notebooks` branch (all 291 English notebooks).
2. Install `binder/jupyter-requirements.txt` + `nbmake` + `pytest-xdist`.
3. Set `IPYTHONDIR` to `ci/ipython_startup_dir/`, which auto-loads
   `00_patch_runtime.py` at kernel startup. The patch replaces
   `qiskit_ibm_runtime.QiskitRuntimeService` (and `SamplerV2` / `EstimatorV2` /
   `Session` / `Batch`) with thin wrappers that route every backend reference to
   `FakeBrisbane`, `FakeFez`, or `FakeMarrakesh` from
   `qiskit_ibm_runtime.fake_provider`.
4. Compute a slice of the testable notebook list using `count` / `offset` inputs.
5. Run `pytest --nbmake --nbmake-timeout=300 -n 2 ...`.
6. Upload executed notebooks + JUnit XML as a workflow artifact.

Notebooks are not modified: the patch is loaded before any user cell, so
`from qiskit_ibm_runtime import QiskitRuntimeService` resolves to the fake.

## Ramp-up plan

Trigger via the Actions UI → "Notebook CI" → "Run workflow".

| Step | `source` | `count` | `offset` | What it proves |
| --- | --- | --- | --- | --- |
| 1 | `main` | `2` | `0` | Sampler + Estimator paths on two `use-a-qc-today` notebooks. |
| 2 | `notebooks` | `10` | `0` | Stratified slice (covers all 5 categories). |
| 3 | `notebooks` | `20` | `0` | First real batch. |
| 4 | `notebooks` | `20` | `20`, `40`, `60`, ... | Walk the list. |
| 5 | `notebooks` | `50` | `N` | Larger batches once batches at 20 are clean. |
| 6 | `notebooks` | `all` | `0` | Full sweep (consider sharding once batches at 50 are clean). |

Inputs:
- `source` — `main` or `notebooks`.
- `count` — integer or `all`. Default `2`.
- `offset` — integer index into the sorted list. Default `0`.
- `max_shots` — clamps `default_shots` on Sampler/Estimator primitives. Default `1024`.

## Local run

From a checkout of the `notebooks` branch:

```bash
pip install -r binder/jupyter-requirements.txt nbmake pytest-xdist
IPYTHONDIR=$PWD/ci/ipython_startup_dir \
CI_MAX_SHOTS=1024 \
  pytest --nbmake --nbmake-timeout=300 -n 2 \
         $(./ci/list-notebooks.sh | head -10)
```

On `main` (PoC scope, two notebooks):

```bash
IPYTHONDIR=$PWD/ci/ipython_startup_dir \
  pytest --nbmake --nbmake-timeout=300 -n 2 \
         "local-content/learning/courses/use-a-qc-today/build-and-run-your-first-quantum-program.ipynb" \
         "local-content/learning/courses/use-a-qc-today/your-first-quantum-experiment.ipynb"
```

## Skipping cells / notebooks

- Skip a whole notebook: add its repo-relative path to `ci/notebooks-skip.txt`.
- Skip a single cell: in the notebook JSON, add the tag `nbmake-skip-cell` to
  the cell's `metadata.tags`. Use this for cells that legitimately need real
  hardware (e.g. `service.job("some-id")` lookups) or that intentionally raise.

## Files

- `ci/ipython_startup_dir/profile_default/startup/00_patch_runtime.py` — the
  monkey-patch (qiskit-ibm-runtime → fake_provider).
- `ci/notebooks-skip.txt` — vendor / lab-template exclusions.
- `ci/list-notebooks.sh` — stratified, deterministic notebook list.
- `.github/workflows/notebook-ci.yml` — the workflow.
