# Notebook Execution Sweep — Findings Report

**Date:** 2026-05-17
**Scope:** All 261 EN notebooks (43 tutorials + 86 guides + 132 learning),
executed cell-by-cell in the real production image
**`ghcr.io/qubins/images:2.3-xl`** (qiskit 2.3.1, qiskit-ibm-runtime 0.43.1
— byte-identical to what users hit on doqumentation.org and its locale
subdomains). Simulator/fake backends only — no IBM hardware, no jobs queued.
Origin: the `de.doqumentation.org/tutorials/dc-hex-ising` import crash.

Methodology, shim design, and reproduction: `scripts/notebook-sweep/README.md`.

---

## Headline

| Bucket | Count | Meaning |
|---|---:|---|
| **Runs clean** | ~166 (64%) | Executes end-to-end on simulator |
| **Cloud-only by design** | ~26 | Premium Qiskit Functions / job-id retrieval — *expected*, not bugs |
| **Real user-facing problems** | **~66** | Notebooks that **fail for real users on the live site** |
| Resource artifacts (sweep VM) | ~9 | Aer OOM / timeout on the 8 GB test VM — not notebook bugs |

**~66 of 261 notebooks (25%) are broken for end users** on
doqumentation.org today. None of these would have been caught by a static
import scan — they require actual execution to surface. They fall into a
small number of *systemic* causes, each with a single high-leverage fix.

---

## P0 — Systemic, one fix clears many notebooks

### F1 · Graphviz binaries missing from the production image — **~14 notebooks**

The QuBins image has **no `dot`/`neato`** and no `graphviz` pip package
(only `pydot`, which shells out to the absent `dot`). Every notebook
calling `plot_coupling_map` / `plot_circuit_layout` / `plot_gate_map` /
`dag_drawer` fails for users with `MissingOptionalLibraryError` or
`RuntimeError: Graphviz could not be found`.

**Proven by the sweep:** the same notebooks all run **clean** in a
graphviz-patched image (Pass B). This is purely the missing system binary.

Affected: dc-hex-ising, long-range-entanglement, qedma-2d-ising-with-qesem,
probabilistic-error-amplification, approximate-quantum-compilation-for-time-evolution,
multi-product-formula, operator-back-propagation, guides/custom-backend,
guides/represent-quantum-computers, guides/transpiler-stages,
guides/DAG-representation, guides/common-parameters,
utility-scale-quantum-computing/{teleportation,utility-i}.

**Fix (upstream, 1 line):** add `graphviz` to the QuBins image Dockerfile
(`apt-get install -y graphviz`). Owner: QuBins/qiskit-images.

### F2 · `qiskit-ibm-transpiler` (+ AI local-mode dep) missing — **~5 notebooks**

`No module named 'qiskit_ibm_transpiler'` in ai-transpiler-introduction,
ai-transpiler-passes, qiskit-transpiler-service,
compilation-methods-for-hamiltonian-simulation-circuits, measure-qubits.

**Deeper finding (revealed by Pass B):** installing `qiskit-ibm-transpiler`
alone is *not enough* — its local mode then raises
`ImportError: For using the local mode you need to install the package
'qiskit_ibm_ai_local_transpiler'`. Both packages are required.

**Fix (upstream):** add `qiskit-ibm-transpiler` **and**
`qiskit-ibm-ai-local-transpiler` to the QuBins image. Owner:
QuBins/qiskit-images.

### F4 · Notebooks need packages absent from the image AND not self-installed — **~13 notebooks**

These import packages the image lacks, and (unlike most notebooks) their
first cell does *not* `pip install` them, so they hard-fail for users:

| Missing module | Notebook |
|---|---|
| `qctrlvisualizer` | quantum-phase-estimation-qctrl, transverse-field-ising-model |
| `openfermion` | quantum-chem-with-vqe/hamiltonian-construction |
| `oqs` | quantum-safe-cryptography |
| `secretpy` | symmetric-key-cryptography |
| `qiskit_device_benchmarking` | ghz-spacetime-codes |
| `gem_suite` | nishimori-phase-transition |
| `category_encoders` | projected-quantum-kernels |
| `mthree` | readout-error-mitigation-sampler |
| `imblearn` | sml-classification |
| `qiskit_addon_opt_mapper` | solve-market-split-problem-with-iskay-quantum-optimizer |
| `qiskit_ibm_runtime.circuit` | measure-qubits, repetition-codes |

**Fix (decide per package):** either (a) patch the upstream notebooks to
add the missing package to their install cell, or (b) add the common ones
to the QuBins image. `qiskit_ibm_runtime.circuit` is suspicious — likely
an upstream-notebook-vs-0.43.1 API path that no longer exists; verify.

---

## P1 — Real notebook bugs (upstream `Qiskit/documentation`)

These are genuine defects in IBM's notebook source — not environment, not
the sweep harness. They fail on the live site regardless of image fixes.

| Notebook | Error | Likely cause |
|---|---|---|
| `tutorials/dc-hex-ising` | `ImportError QiskitBackendNotFoundError` (cell 7) | **The original report.** Imported from `qiskit_ibm_runtime.exceptions`; real home is `qiskit.providers.exceptions`. Also imports `draw_circuit_schedule_timing` (needs runtime ≥0.46). |
| `utility-scale-quantum-computing/bits-gates-and-circuits` | `PrimitiveJob.status() takes 1 positional argument but 2 were given` | Notebook-vs-qiskit-2.3 API drift |
| `utility-scale-quantum-computing/quantum-circuit-optimization` | `excitation_preserving() unexpected kwarg 'flatten'` | API drift |
| `modules/computer-science/quantum-teleportation` | `Instruction if_else is already in the target` | Real logic bug (re-adds instruction) |
| `tutorials/real-time-benchmarking-for-qubit-selection` | `'list' object is not callable` | Real bug |
| `modules/computer-science/grovers` | `FileNotFoundError: 'C:\\Users\\...file location here...\\my_circuit.qpy'` | Unedited Windows placeholder path in source |
| `guides/kipu-optimization` | `NameError: 'backend_name' is not defined` | Real bug (undefined var) |
| `utility-scale-quantum-computing/hardware` | `NameError: 'fig' is not defined` | Real bug |
| `tutorials/advanced-techniques-for-qaoa` | `KeyError: 'cz'` | Real bug |
| `guides/monitor-job`, `guides/visualize-circuit-timing` | `KeyError: 'execution'` / `'compilation'` | Likely real (API key renamed) — verify |

## P2 — Simulator-incompatible (won't run without hardware/large RAM)

Not bugs in the usual sense, but users on doqumentation.org (simulator
path) hit these. Worth a "needs hardware" note in the UI for these pages.

- **Aer statevector OOM** (`QiskitError: Insufficient memory` /
  `requires more memory than max_memory_mb`) ×~9 — large-qubit circuits:
  primitives-examples, get-started-with-primitives, run-jobs-batch,
  run-jobs-session, quantum-chem-with-vqe/ground-state, qvc-qnn,
  utility-ii, combine-error-mitigation-techniques,
  quantum-approximate-optimization-algorithm. (Some overlap with the
  sweep-VM artifact bucket; on a bigger box a subset of these pass.)
- `ValueError: could not broadcast … shape (0,N)` ×~5 — wire-cutting /
  circuit-cutting / fractional-gates notebooks: a primitive returns an
  empty result under simulation. Likely sim-incompatible by design.
- `noise-learning`: ``NoiseLearner`` not supported in local mode.
- `krylov-quantum-diagonalization`: DAG component too large for the
  coupling map under the fake backend.

## Expected — cloud-only by design (NOT bugs, ~26)

Correctly classified by the sweep's `CloudOnlyOffline` marker. These call
**premium IBM-hosted Qiskit Functions** (`catalog.load(...).run()`),
deploy serverless programs (`catalog.upload()`), or retrieve a
**pre-existing cloud job by pasted ID** (`service.job("<id>")`). None have
an offline equivalent — failing offline is correct behaviour.

Examples: algorithmiq-tem, colibritd-pde, qedma-2d-ising-with-qesem,
function-template-{chemistry-workflow,hamiltonian-simulation},
serverless-{first-program,run-first-workload,manage-resources},
spin-chain-vqe, quantum-kernel-training, error-mitigation (job-id),
quantum-phase-estimation (job-id), utility-scale teleportation/utility-iii.

**Recommendation:** these pages should show a clear "requires IBM Quantum
Premium / cloud — cannot run on the public simulator" banner so users
aren't confused by the failure.

---

## Recommended action order

1. **Upstream to QuBins/qiskit-images** (clears ~32 notebooks, 2 Dockerfile
   lines): add `graphviz` (F1) + `qiskit-ibm-transpiler` &
   `qiskit-ibm-ai-local-transpiler` (F2). Highest leverage by far.
2. **F4 triage** — decide image-add vs notebook-install-cell per package
   (~13 notebooks).
3. **Upstream notebook bugs (P1)** — report to `Qiskit/documentation`;
   dc-hex-ising is the known one, ~9 others newly found.
4. **UI "needs hardware/cloud" banners** for the ~26 cloud-only + the
   sim-incompatible set, so users get a clear message instead of a crash.
5. **dc-hex-ising local fix** — if a faster path than upstream is wanted,
   patch the import in our synced copy + add a `sync-content.py` transform
   so it survives re-sync.

## Caveats

- Sweep VM = 8 GB / 4 CPU, 3-way parallel. ~9 OOM/timeout results are
  partly VM artifacts; a subset would pass on a larger box. Flagged, not
  treated as notebook bugs.
- Unseeded stochastic notebooks (some VQE/ML) may vary run-to-run;
  one-shot snapshot.
- Locale notebooks not swept — code cells are byte-identical twins of EN.
- Raw data: `.sweep-out/passA/report.json` (user reality),
  `.sweep-out/rerun/report.json` (post-shim-fix overlay),
  `.sweep-out/passB/report.json` (deps-patched deep coverage).
