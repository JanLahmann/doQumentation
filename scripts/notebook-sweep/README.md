# notebook-sweep — reproduce

One-shot harness that executes every EN notebook in the real production
image (`ghcr.io/qubins/images:2.3-xl`) on simulator/fake backends only —
no IBM hardware, no jobs queued. Surfaces import/runtime breakage that
users hit on doqumentation.org.

**Findings:** `../../notebook-sweep-report.md`
**Methodology / triage history:** `../../.claude/NOTEBOOK_SWEEP_PLAN.md`

## Run it

```bash
# from repo root. Needs podman (machine ≥8 GB RAM recommended).
python3 scripts/notebook-sweep/sweep.py        # Pass A (all 261) + Pass B
python3 scripts/notebook-sweep/sweep.py A      # Pass A only
python3 scripts/notebook-sweep/sweep.py B      # Pass B only
```

Output (gitignored) lands in `.sweep-out/`:

- `passA/report.{json,md}` — every notebook, stock image = **user reality**
- `passB/report.{json,md}` — F1/F2-affected subset in the deps-patched
  image (graphviz + qiskit-ibm-transpiler) = failures *behind* the
  missing-dep wall
- `rerun/` — written only when you re-run a hand-picked subset via
  `run_all.py` directly

Knobs: `DOQ_PAR` (parallel containers, default 3), `DOQ_CELL_TIMEOUT`
(seconds/cell, default 300).

## Files

| File | Role |
|---|---|
| `sweep.py` | Host driver: discovers notebooks, shards across N podman containers, merges reports. Runs on the host. |
| `run_all.py` | In-container executor (one batch). Injects the shim, neutralises the pip-install cell, nbclient-executes each notebook. |
| `sim_shim.py` | Monkeypatches `qiskit_ibm_runtime` / `qiskit_ibm_catalog` so nothing touches hardware or cloud. Raises `CloudOnlyOffline` for genuinely cloud-only notebooks. |
| `merge_reports.py` | Combines per-batch JSON into a pass-level report. |
| `Dockerfile.depspatch` | Throwaway image for Pass B = stock image + graphviz + qiskit-ibm-transpiler. **Not** what users run. |

Each script has a module docstring with the details. The shim is
capture-only — it never edits notebooks.
