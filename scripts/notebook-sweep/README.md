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
one sweep's snapshot, so refresh it after an image bump or a content sync.

The labels say where the code runs, and that depends on the platform: an
arm64 image (Apple silicon Macs, Raspberry Pi) lacks packages that have no
arm64 wheels (`gem_suite`, `tenpy`, ...), which the amd64 image (Binder, Code
Engine, Intel/AMD computers) has. So the sweep runs on **both**, each with
Binder's 1 CPU and 2 GB. The banner shows the label for the visitor's backend
(a local or RasQberry server counts as arm64, everything else as amd64) and
adds the other platform's where it differs. `make_page_status.py` checks each
report's arch. Run the **Notebook sweep** workflow
(`.github/workflows/notebook-sweep.yml`, 16 shards per platform), download its
`notebook-sweep` artifact, then:

```bash
git fetch origin notebooks
python3 scripts/notebook-sweep/make_page_status.py \
    --report <artifact>/amd64/passS-aer/report.json \
    --report-arm64 <artifact>/arm64/passS-aer/report.json
```

**Installs.** On the site, a page's install cell pip-installs what the image
lacks before the cells run. The sweep does the same for exactly those
notebooks: each one whose install cell lists a module the image lacks, or that
pip-installs itself, runs alone in a fresh container with installs on
(`DOQ_INSTALLS=1`). All others share containers with installs off, so no
install leaks into another notebook (#969).

Locally, `sweep.py` runs `--platform linux/amd64 --cpus 1 --memory 2g` by
default (`DOQ_PLATFORM=linux/arm64` for the native arm64 run, `DOQ_BINDER_LIMITS=0`
without limits); an arm64 Mac emulates amd64, slowly:

```bash
mkdir -p /tmp/nb && git archive origin/notebooks tutorials guides learning | tar -x -C /tmp/nb
DOQ_NB_ROOT=/tmp/nb DOQ_NB_REF=origin/notebooks python3 scripts/notebook-sweep/sweep.py S
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

## Catching regressions before an image bump

Before `DEFAULT_QISKIT_TAG` moves to a new QuBins tag (or to test a Qiskit
release candidate image), sweep the candidate and compare it with a sweep of
the current default:

1. Run the **Notebook sweep** workflow with `image_tag` = the candidate and
   `baseline_run` = the run ID of the last sweep of the current default (run it
   first if there is none). The run summary then lists, per platform, the
   pages whose label got worse, notebooks that still run but take at least
   twice as long (and 30 s more), and cells that slowed down the same way.
   The same tables are in `sweep/<arch>/diff.md` in the artifact.
2. Locally, the same comparison for two downloaded artifacts:

   ```bash
   python3 scripts/notebook-sweep/diff_reports.py \
       --base <baseline>/amd64/passS-aer/report.json \
       --new <candidate>/amd64/passS-aer/report.json
   ```

Every record in `report.json` has `cell_times` (seconds per code cell of at
least 1 s, by the cell's index in the notebook) and `slowest_cell` (the cell
the notebook stopped in, else the slowest), so a regression already names its
cell.

## Triage: from a slower page to an upstream fix

How the Qiskit 2.6 `decompose()` regression was found (qvc-qnn, Qiskit#16753);
each step makes the case smaller.

1. **Which cell.** `slowest_cell` / `cell_times` in both reports. To re-run
   one notebook in either image with Binder's limits:

   ```bash
   podman run --rm --user root --cpus 1 --memory 2g \
     -v "$PWD/notebooks:/repo:ro" -v "$PWD/scripts/notebook-sweep:/shim:ro" \
     -v "$PWD/src:/src:ro" -v "$PWD/scripts:/scripts:ro" -v /tmp/nbout:/out \
     -e DOQ_SHIM=site -e DOQ_SIM_MODE=aer --entrypoint python3 \
     ghcr.io/qubins/images:<tag> /shim/run_all.py /out/r /repo/<path>.ipynb
   ```

2. **Which call.** Copy the notebook's cells up to the slow one into a script
   and time the calls in that cell one by one, in both images. Then shrink
   the input: one gate type, one qubit, fewer parameters, until the slowdown
   needs only a few lines.
3. **Which package.** Run the short script against each image tag, and
   against single package versions (`pip install qiskit==X.Y.Z` in a
   container of the older image). Note how the time grows with the input
   size: doubling per step means an exponential path, not just a slow one.
4. **Which commit.** For Qiskit, build it from source in a Rust container
   (Qiskit's `rust-version` in `Cargo.toml`; fat LTO needs more than 8 GB of
   podman memory with debug info) and bisect between the two releases:

   ```bash
   podman run -d --name qkb --cpus 4 -v qkbuild:/work docker.io/library/rust:<rust-version>-bookworm sleep infinity
   # inside: clone Qiskit, python3 -m venv, pip install -e . once, then per commit:
   git checkout <sha> && python setup.py build_rust --inplace --release && python repro.py
   ```

5. **Upstream.** Search the project's issues first (the same mechanism may
   already be reported with a bigger reproducer). Jan files issues and PRs
   himself. For Qiskit, read its generative-AI policy
   (`docs/devguide/contributing.md`): the human submits and explains the
   change, and AI-written text or code is disclosed in the PR form.
6. **Here.** Until a fixed release is in the image, keep the default tag,
   or label the page from the candidate's sweep.

## Files

| File | Role |
|---|---|
| `sweep.py` | Host driver: discovers notebooks, shards across N podman containers, merges reports. Runs on the host. |
| `run_all.py` | In-container executor (one batch). Injects the shim, skips every install line, nbclient-executes each notebook. |
| `sim_shim.py` | Monkeypatches `qiskit_ibm_runtime` / `qiskit_ibm_catalog` so nothing touches hardware or cloud. Raises `CloudOnlyOffline` for genuinely cloud-only notebooks. |
| `merge_reports.py` | Combines per-batch JSON into a pass-level report. |
| `diff_reports.py` | Compares two pass reports of one platform: label regressions, slowdowns, slower cells. |
| `make_page_status.py` | Turns a Pass S report into the page labels (`src/config/pageRunStatus.json`). |

Each script has a module docstring with the details. The shim is
capture-only — it never edits notebooks.
