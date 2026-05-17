# Notebook "Run-All" Sweep — Plan

**Status:** COMPLETE 2026-05-17. Findings →
`notebook-sweep-report.md` (repo root). Reproduce →
`scripts/notebook-sweep/README.md`. Headline: 261 nb swept, ~166 clean,
~26 cloud-only-by-design, **~66 broken for real users** (systemic: F1
graphviz, F2 transpiler, F4 missing pkgs + ~10 real notebook bugs).
Created 2026-05-17.
**Origin:** `de.doqumentation.org/tutorials/dc-hex-ising` first runnable cell
crashed with `ImportError: cannot import name 'QiskitBackendNotFoundError'
from 'qiskit_ibm_runtime.exceptions'` — an upstream notebook bug (symbol
lives in `qiskit.providers.exceptions`, never re-exported from runtime; absent
in pinned 0.43.1 *and* latest 0.46.1). Question that followed: how do we find
similar errors across all notebooks? Decision: **Option 2 — one-shot
execute-all, simulator/fake only, with credentials but NO real-hardware jobs.**

## Goal

Execute every code cell of every EN notebook in a controlled environment,
capture failures, classify them. No hardware, no jobs queued. Capture first,
fix second — do NOT fix during the sweep (mixing corrupts results).

## Measured scope (2026-05-17, on `main`-ish working tree)

- 261 EN notebooks: **43 tutorials + 86 guides + 132 learning** (courses + modules)
- All 19 locales are content twins — code cells identical → **run EN only**
  (optional 2-3 locale spot-checks at the end)
- 261 reference `QiskitRuntimeService` somewhere (mostly commented boilerplate)
- **115** actively call `QiskitRuntimeService()` / `.least_busy()` /
  `.save_account()` (uncommented)
- **113** actively submit jobs (`sampler.run`, `estimator.run`,
  `SamplerV2(mode=…)`, `EstimatorV2(mode=…)`, `job.result()`)
- Shared first cell everywhere: `!pip install` gated by
  `importlib.util.find_spec('qiskit')`

**Key insight:** credentials alone are NOT enough. With credentials,
`service.least_busy()` + `sampler.run()` would queue real jobs and burn quota.
We need a **monkey-patch shim** that intercepts `QiskitRuntimeService` and
rewrites primitive backends to fake/simulator. The shim is the heart of the
plan (~80 lines).

## Architecture

```
runner.py
  for each notebook:
    spawn isolated kernel, PYTHONSTARTUP=sim_shim.py
    nbclient.execute(nb, timeout=180, allow_errors=False)
    record ok | fail(cell_idx, ename, evalue, tb_head, src_head)
  write report.json + report.md (grouped by error class)

sim_shim.py  (auto-loaded via PYTHONSTARTUP)
  monkeypatch qiskit_ibm_runtime.QiskitRuntimeService:
    __init__()      -> no-op, no auth
    save_account()  -> no-op
    backends()      -> [FakeBackend, ...]
    backend(name)   -> FakeBrisbane()  (match by qubit count when possible)
    least_busy(...) -> FakeBrisbane()
  monkeypatch SamplerV2/EstimatorV2: any backend or mode=Session/Batch
    -> swap to qiskit_aer.primitives.SamplerV2 / EstimatorV2
  monkeypatch Session/Batch -> no-op context managers
  leave everything else untouched
```

## Phases

- **Phase 0 — Environment (~30 min):** venv/container from
  `binder/jupyter-requirements.txt` + `nbclient`/`jupyter-client`/`ipykernel`.
  Run on laptop, NOT CE (one-shot, not workshop traffic). Sanity import of all
  top-level modules first — this alone re-catches the dc-hex-ising class.
- **Phase 1 — Shim (~1–2 h):** write `scripts/notebook-sweep/sim_shim.py`,
  validate against `tutorials/dc-hex-ising.ipynb` +
  `guides/get-qpu-information.ipynb` (representative: service init + backends
  + least_busy + run/result) until both complete clean.
- **Phase 2 — Runner (~1 h):** `scripts/notebook-sweep/run_all.py`. Discover
  4 roots, fresh kernel per notebook, `NotebookClient(timeout=180,
  allow_errors=False)`, skip the `!pip install` cell, 4–6-way parallel.
  Est. wall time ≈ 20 min at 6-way (261 × ~30 s mean); long ones
  (`primitives-examples`, VQE) may hit 180 s cap → record as timeout, not fail.
- **Phase 3 — Triage (~half day):** expected classes:
  1. Hard import errors (dc-hex-ising class) → real bugs, fix in source
  2. Shim gaps (un-patched provider method) → patch shim, re-run subset
  3. Genuine sim-incompatible (fractional gates, dynamic circuits, hw-only
     metrics) → tag cell `"tags": ["skip-execution"]` or accept as hw-only
  4. Timeouts → bump / mark hw-only / downscale
  5. Cosmetic (matplotlib backend, missing pylatexenc) → trivial
  Re-run only failing subset until each remaining failure is explained.
- **Phase 4 — Output (~1 h):** `notebook-sweep-report.md` punch list grouped
  by class with file:cell links + one-line patch suggestion per real bug;
  decide local-fix vs report-upstream to `Qiskit/documentation`.

## Explicitly out of scope

- No real-hardware execution (shim guarantees, even if a notebook builds a
  real service)
- No locale notebooks (content twins; optional 2–3 spot-checks)
- Not wired into CI (one-shot diagnostic; the import-only static subset could
  later be a ~50-line / ~30-s CI guard)
- No fixing during the sweep

## Risks / unknowns

- **Determinism:** some VQE/ML notebooks use unseeded stochastic optimization
  — may pass/fail across runs. Acceptable for one-shot; document.
- Notebooks already using `Aer_Sampler` — verify not double-patched.
- **Pin question:** `qiskit-ibm-runtime` pinned at 0.43.1, latest 0.46.1.
  **Decision: sweep at current pin** (reflects what Binder users actually
  hit). Bumped-pin sweep = separate later run.

## Deliverables

- `scripts/notebook-sweep/sim_shim.py`
- `scripts/notebook-sweep/run_all.py`
- `scripts/notebook-sweep/README.md`
- `notebook-sweep-report.md`

## Effort

~1 working day (Phase 0–2 ≈ half day build, Phase 3 ≈ half day triage,
Phase 4 ≈ 1 h). Up to 2 days if triage finds many shim gaps.

## Environment — RESOLVED 2026-05-17

Sweep runs **locally in the QuBins image via podman** (user-directed).

- **Image: `ghcr.io/qubins/images:2.3-xl`** (arm64/linux, 2.98 GB).
  NOTE the package name is **`images`**, NOT `qiskit` / `qiskit-images`.
  Repo [QuBins/qiskit-images] but GHCR package `ghcr.io/qubins/images`
  (build-matrix.yml: `IMAGE: images`, tags `:{version}-{arch}`,
  `:2.3-xl` = multi-arch manifest). **Codebase docs are stale** —
  `src/config/jupyter.ts:240` + `.claude/PROJECT_HANDOFF.md:398` say
  `ghcr.io/qubins/qiskit:...`; both should be corrected (separate fix).
- **Env check (in-image):** qiskit 2.3.1, **qiskit-ibm-runtime 0.43.1**
  (== `binder/jupyter-requirements.txt` pin — fidelity confirmed, this
  IS what live-site users hit), qiskit-aer 0.17.2, rustworkx 0.17.1,
  pylatexenc 2.10, numpy 2.3.0, scipy 1.17.1, matplotlib 3.10.9,
  python 3.13.13. **`qiskit-ibm-transpiler` MISSING** → ai-transpiler
  notebooks (`tutorials/ai-transpiler-introduction`,
  `guides/ai-transpiler-passes`) will ModuleNotFoundError — a real
  finding to capture, not a sweep bug.
- dc-hex-ising reproduces here: runtime 0.43.1 lacks BOTH
  `QiskitBackendNotFoundError` re-export AND `draw_circuit_schedule_timing`
  (latter arrived 0.46.x) — two stacked import failures in cell 7.
- **Runner gotcha:** image has a Jupyter start wrapper (`start.sh` +
  conda hooks) that prints to stdout before the command. Phase 2 runner
  must invoke python so wrapper noise doesn't pollute nbclient.
- **Resource constraint:** podman VM = 2 CPU / 3.79 GB RAM / 38 GB disk.
  Decision on resize/parallelism still pending (decide-after-env-check).

## VM resourcing — RESOLVED 2026-05-17

Podman VM resized to **8 GB RAM / 4 CPU** (`podman machine set
--memory 8192 --cpus 4`, stop/set/start). Image persists across
restart. Plan ~3–4-way parallel for the full sweep.

## Phase 1 — DONE 2026-05-17

`scripts/notebook-sweep/sim_shim.py` + `run_all.py` written and
validated in-container. Runner uses `--entrypoint python3` to bypass
the `start.sh` wrapper (clean stdout). Shim injected as notebook cell 0
+ re-apply hook; pip-install cell neutralised; per-cell timeout.

Validation results (the 2 representative notebooks):

- `guides/get-qpu-information.ipynb` → **ok** (3.7 s). Shim handles
  service/backends/least_busy.
- `tutorials/dc-hex-ising.ipynb`: shim correctly carried it PAST the
  original cell-7 import bug. Then surfaced two further issues:
  1. **Shim gap (FIXED):** `least_busy(use_fractional_gates=True)` was
     routed to 5q `fake_fractional` → bogus
     `TranspilerError: More virtual qubits (106) than physical (5)`.
     Fix: fractional requests now get the largest (127q) fake; Aer
     simulates it fine. Re-ran → got further.
  2. **Real image finding (OPEN):** then failed
     `MissingOptionalLibraryError: 'Graphviz' library required for
     'plot_circuit_layout'`.

### Phase 1 FINDINGS (carry into the report)

- **F1 — Graphviz missing from QuBins image (HIGH, upstream).**
  `ghcr.io/qubins/images:2.3-xl` has NO `dot`/`neato` binary and no
  `graphviz` pip pkg (only `pydot` 4.0.1, which shells out to the
  absent `dot`). **17 notebooks** call `plot_coupling_map` /
  `plot_circuit_layout` / `plot_gate_map` and will fail for live-site
  users at those cells. Fix belongs upstream in QuBins Dockerfile
  (`apt-get install graphviz`). Affected (partial): dc-hex-ising,
  long-range-entanglement, qedma-2d-ising-with-qesem,
  ghz-spacetime-codes, guides/represent-quantum-computers,
  guides/transpiler-stages, guides/custom-backend,
  utility-scale-quantum-computing/{teleportation,utility-iii,hardware},
  modules/computer-science/quantum-teleportation.
- **F2 — `qiskit-ibm-transpiler` missing from image (MED, upstream).**
  ai-transpiler notebooks will ModuleNotFoundError.
- **F3 — dc-hex-ising wrong-module import (the original bug, real).**
  `QiskitBackendNotFoundError` imported from
  `qiskit_ibm_runtime.exceptions` (lives in
  `qiskit.providers.exceptions`); also `draw_circuit_schedule_timing`
  needs runtime ≥0.46. Source notebook fix still required; shim only
  masks it so the sweep can see deeper failures.
- **DOC — codebase refs `ghcr.io/qubins/qiskit:...` stale** —
  FIXED 2026-05-17 (jupyter.ts:237 comment + 3× PROJECT_HANDOFF.md;
  runtime config was already correct, only human-readable names wrong).

## Phase 3a — Pass A COMPLETE + shim fixed (2026-05-17)

**Pass A final: 261 nb → 156 ok / 99 fail / 3 timeout / 3 error.**
26 min, 3-way parallel. Full class breakdown in
`.sweep-out/passA/report.md`. Top classes: ModuleNotFoundError 17,
AccountNotFoundError 17, AttributeError 16, MissingOptionalLibraryError
10, QiskitError 7, QiskitServerlessException 7.

**4 shim-gap fixes applied to sim_shim.py (unit-verified in-image):**
1. **Qiskit Functions/Serverless** (`AccountNotFoundError`×17 root
   cause = unpatched `qiskit_ibm_catalog`): patched
   `QiskitFunctionsCatalog`/`QiskitServerless` to construct offline;
   `.load()` returns a handle, `.run()`/`.job()` raise new
   `CloudOnlyOffline` — these notebooks call PREMIUM IBM-hosted
   functions with NO offline equivalent, so this is correct
   classification, not masking.
2. **Permissive `_Opts` stub** (`AttributeError 'Options' has no
   attribute …`×14): notebooks plumb deeply-nested mutable options
   (`sampler.options.dynamical_decoupling.enable=True`,
   `EstimatorOptions().resilience.zne.noise_factors=...`). Installed a
   class-level `__getattr__` fallback on Aer's real options type
   (Python only calls `__getattr__` on lookup MISS, so real Aer attrs
   untouched) + replaced standalone `*Options` classes with the stub.
   Init-order bug found by unit test (Aer reads `self.options.
   backend_options` during `super().__init__`) → fixed by not
   overriding the `options` property, only adding the miss-fallback.
3. **`service.job(id)`** (`LookupError`×4): was raising a confusing
   "no jobs submitted"; now raises `CloudOnlyOffline` — these retrieve
   a pre-existing real cloud job by pasted ID, inherently not offline.
4. **FakeBackend edges**: added `target_history` property
   (`AttributeError`×1); `not callable`×1 noted.

`CloudOnlyOffline` is a NEW distinct exception so the report cleanly
buckets "expected cloud-only" vs shim-gap vs real bug.

## Phase 3b — IN PROGRESS: re-run (2026-05-17)

Background driver: (1) 48-nb shim-gap subset (ename ∈
{AccountNotFound, AttributeError, LookupError, TypeError,
QiskitServerlessException}) in stock image w/ fixed shim →
`.sweep-out/rerun/`; then (2) FULL Pass B re-run (depspatch image:
graphviz + qiskit-ibm-transpiler) → `.sweep-out/passB/`. NOTE Pass B
never completed earlier — the "wait with fixing" pkill killed its
driver mid-run (containers finished in-flight nb, no merge); partial
5/batch data discarded, clean re-run now.

### Confirmed REAL findings (carry to report regardless of re-run)
- **F4 (NEW, HIGH)** — ~13 nb need packages ABSENT from image AND not
  pip-installed by their first cell: `qctrlvisualizer`, `openfermion`,
  `oqs`, `secretpy`, `qiskit_device_benchmarking`, `gem_suite`,
  `category_encoders`, `mthree`, `imblearn`, `qiskit_addon_opt_mapper`,
  `qiskit_ibm_runtime.circuit`. Unrunnable for live users.
- F1 Graphviz (Pass B covers), F2 qiskit-ibm-transpiler (Pass B
  covers), F3 dc-hex-ising wrong-module import (source fix).
- Cloud-only-by-design (NOT bugs): ~24 nb = Qiskit Functions
  (algorithmiq-tem, colibritd-pde, function-template-*) + job-id
  retrieval (error-mitigation, quantum-phase-estimation). Now cleanly
  bucketed via `CloudOnlyOffline`.
- Resource artifacts (note, don't fix): DeadKernelError×3 (OOM 8GB/3-
  way), TimeoutError×3 (heavy Aer).

## Phase 2b — Pass A IN PROGRESS (mid-run triage signal, 2026-05-17)

At ~169/261 the failures are a healthy DIFFERENTIATED mix (NOT one
systematic shim artifact). Batch-0 high not-ok rate = it concentrates
F1/F2/serverless notebooks, not noise. Early class breakdown:

**Confirmed real production-image findings (Pass B will deep-cover):**
- F2 `ModuleNotFoundError qiskit_ibm_transpiler` ×12+ (wider than the
  4 import-grep hits — transitive). F1 Graphviz ×several.

**Shim gaps to fix in Phase 3 (masking deeper signal):**
- `AccountNotFoundError: channel 'ibm_quantum_platform'` — shim
  `_FakeService` doesn't cover the newer `ibm_quantum_platform`
  channel path.
- `QiskitServerlessException: Credentials couldn't be verified` ×6 —
  Qiskit Serverless / functions notebooks not intercepted at all.
  Decide: stub serverless, or accept as cloud-only finding.
- `TypeError: 'FakeBrisbane' object is not callable` — shim returns a
  backend instance where a notebook calls it like a factory. Real
  shim defect.
- `AttributeError: 'Options' object has no attribute
  'dynamical_decoupling'` — triage: real 0.43.1 API-drift bug vs shim
  Options stub.

**Genuine notebook / sim findings (keep):**
- `KeyError 'cz'`, `TranspilerError connected component too large`,
  `ValueError broadcast (0,14)` — likely real notebook/sim bugs.
- `TimeoutError >300s` — expected heavy-Aer tail.
- `DeadKernelError: Kernel died` — likely OOM (8 GB VM, 3-way, heavy
  notebook). Resource artifact, not a notebook bug — note, don't fix.

**F2 Pass-B scope (verified):** 4 notebooks import qiskit_ibm_transpiler
directly (guides/ai-transpiler-passes, guides/qiskit-transpiler-service,
tutorials/ai-transpiler-introduction,
tutorials/compilation-methods-for-hamiltonian-simulation-circuits) —
but Pass A shows ModuleNotFoundError in 12+, so Pass B subset =
union(F1 plot-fns, F2 import) via `discover_passB()`. depspatch image
adds graphviz + unpinned qiskit-ibm-transpiler (PyPI declares
qiskit<3.0,>=1.4.2 → latest 0.18.0 ok with image's qiskit 2.3.1).
