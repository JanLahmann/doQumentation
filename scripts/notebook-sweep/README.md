# notebook-sweep — reproduce

One-shot harness that executes every EN notebook in the real production
image (`ghcr.io/qubins/images:<DEFAULT_QISKIT_TAG>` from `src/config/jupyter.ts`)
on simulator/fake backends only —
no IBM hardware, no jobs queued. Surfaces import/runtime breakage that
users hit on doqumentation.org.

**Findings + methodology:** `../../notebook-sweep-report.md` (the punch-list
from the 2026-05-17 run, with the systemic F1/F2/F4 causes and action order).

## Run it

```bash
# from repo root. Needs podman (machine ≥8 GB RAM recommended).
python3 scripts/notebook-sweep/sweep.py        # Pass A + Pass S
python3 scripts/notebook-sweep/sweep.py A      # Pass A only
python3 scripts/notebook-sweep/sweep.py S      # Pass S only (DOQ_SIM_MODE=aer|fake)
```

Every install line in every cell (`!pip`, `%pip`, `uv`, `conda`, `subprocess … pip install`)
is skipped, so the sweep measures what the image provides; the report notes
how many each notebook had (`install_lines_skipped`). Before #969 a notebook's
own `pip install "qiskit_ibm_runtime<0.42"` downgraded the shared batch
container and failed every later notebook in it.

Output (gitignored) lands in `.sweep-out/`, or in `DOQ_OUT`:

- `passA/report.{json,md}` — every notebook, stock image = **user reality**
- `passS-<mode>/report.{json,md}` — every notebook with the **site's own**
  Simulator Mode kernel patch (`src/kernel/`) instead of `sim_shim.py` =
  what a learner gets in Simulator Mode
- `rerun/` — written only when you re-run a hand-picked subset via
  `run_all.py` directly

Knobs: `DOQ_PAR` (parallel containers, default 3), `DOQ_CELL_TIMEOUT`
(seconds/cell, default 300), `DOQ_OUT` (output folder), `DOQ_NB_ROOT`
(notebook tree), `DOQ_IMG` (image), `DOQ_SIM_MODE` (Pass S: aer|fake).

## Page labels ("Runs in Simulator Mode")

The "Open in" banner on each notebook page shows one line from the last
Pass S run: **runs**, **needs-ibm** (a cell needs IBM Quantum), **heavy**
(a cell timed out or ran out of memory) or **issue** (anything else, with the
error and a report link). The data is `src/config/pageRunStatus.json`; it is
one sweep's snapshot, so refresh it after an image bump or a content sync:

```bash
git fetch origin notebooks
mkdir -p /tmp/nb && git archive origin/notebooks tutorials guides learning | tar -x -C /tmp/nb
DOQ_NB_ROOT=/tmp/nb DOQ_NB_REF=origin/notebooks python3 scripts/notebook-sweep/sweep.py S
python3 scripts/notebook-sweep/make_page_status.py --report .sweep-out/passS-aer/report.json
```

`sweep.py` records the date, image and notebooks commit in the pass's
`meta.json`; `make_page_status.py` reads them and gives **no label** to a page
the sweep did not cover or whose code cells changed on the notebooks branch
since. `--drop-matching REGEX` leaves out failures known to be fixed in the
image since the run (the 2026-10-05 data drops the graphviz `neato`/`circo`
failures, fixed by QuBins/qiskit-images#165 after that run).

Pass B (a graphviz + qiskit-ibm-transpiler patched image) was removed in
#969's fix: graphviz ships in the QuBins image, and qiskit-ibm-transpiler
0.18 cannot import on Qiskit 2.5.

## Files

| File | Role |
|---|---|
| `sweep.py` | Host driver: discovers notebooks, shards across N podman containers, merges reports. Runs on the host. |
| `run_all.py` | In-container executor (one batch). Injects the shim, skips every install line, nbclient-executes each notebook. |
| `sim_shim.py` | Monkeypatches `qiskit_ibm_runtime` / `qiskit_ibm_catalog` so nothing touches hardware or cloud. Raises `CloudOnlyOffline` for genuinely cloud-only notebooks. |
| `merge_reports.py` | Combines per-batch JSON into a pass-level report. |

Each script has a module docstring with the details. The shim is
capture-only — it never edits notebooks.
