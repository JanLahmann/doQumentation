# Notebook review rubric

You are reviewing the executed notebooks under `./artifact/` produced by the
Notebook CI workflow. These notebooks were run with `qiskit_ibm_runtime`
monkey-patched to use local fake backends (`FakeBrisbane`, `FakeFez`,
`FakeMarrakesh`). nbmake has already caught hard failures (exceptions, timeouts,
import errors). Your job is to surface issues that nbmake cannot see AND to
classify every finding by ownership so the report is directly actionable.

## Inputs

- `./artifact/` — the executed notebooks (preserves original repo paths).
- `./artifact/ci-report.xml` — JUnit summary if you want pass/fail context.
- `./batch.json` — `{source, offset, count, run_id, run_url}` for the upstream
  CI dispatch. Use these for the summary header.

## Procedure

1. List every `.ipynb` under `./artifact/` (use `Glob`).
2. For each notebook:
   - Read it. The interesting fields per cell are `source`, `outputs[].text`,
     `outputs[].data['text/plain']`, and `outputs` with `output_type == 'stream'
     && name == 'stderr'`.
   - For each failure or anomaly, decide its **ownership bucket** before
     deciding whether to include it. See "Ownership buckets" below.
   - The first cell of every notebook prints
     `[ci] qiskit_ibm_runtime patched: fake backends, shots<=...` — ignore
     that line; it is expected.
3. Write `findings.md` in the repo root (NOT inside `artifact/`) using the
   output format below. Always write the file, even when there are no findings.

You may use `Read`, `Glob`, `Write`, and `Bash` (`jq`, `grep`, `wc`, `find`).
Do not modify any file under `artifact/`.

## Ownership buckets

Every finding goes into exactly one of these. The bucket determines whether it
appears in `findings.md` at all and which section it lands in.

### 🟦 `infra` — fix in this repo (doQumentation)

Issues caused by **our** infrastructure, not by IBM's notebook content. Most
common signature: the published Jupyter image (`ghcr.io/janlahmann/doqumentation:jupyter`,
built from `Dockerfile.jupyter`) is missing tooling the notebook expects.

Examples:
- `MissingOptionalLibraryError: 'Graphviz' library` / `FileNotFoundError: 'dot'`
  → graphviz binaries not installed in the image. Fix: add `graphviz` to the
  `apt-get install` step in `Dockerfile.jupyter`.
- A pip dep that exists on PyPI but isn't in `binder/jupyter-requirements.txt`
  or `binder/jupyter-requirements-amd64.txt`. (Excluding deps that are
  intentionally vendor-only — see `ci/notebooks-skip.txt`.)
- Workshop notebooks **authored in this repo** (`workshop-notebooks/` on main,
  `workshop/` on the notebooks branch) with content bugs like undefined
  variables in solution notebooks.

### 🟥 `upstream` — report to the notebook / library maintainer

Real bugs in IBM-authored content (Qiskit-documentation guides, tutorials,
addons) or in Qiskit libraries themselves. The same failure would hit a user
on real IBM Quantum hardware with a fully-configured cloud account.

Subdivide via the `upstream-target` field:
- `qiskit` — bug in Qiskit core (transpiler, primitives, etc.). E.g.
  `TranspilerError: 'xx_minus_yy would be supported ... if the direction
  was swapped'` — `GateDirection` pass missing a flip rule.
- `qiskit-documentation` — bug in an IBM-authored guide or tutorial that
  affects real hardware too. E.g. `count_ops()['cz']` hardcoded against
  Heron, but ALSO fails on Eagle-family real hardware (`ibm_brisbane`)
  which uses `ecr`.
- `qiskit-ibm-runtime`, `qiskit-aer`, `qiskit-ibm-transpiler`, etc. — bug in
  the named library.

When unsure of target, use `qiskit-documentation` and explain.

### ⬛ `drop` — do not include in findings

These are artifacts of running on a simulator / local-mode runtime instead of
real IBM hardware. The notebook works as designed for users with real hardware
and cloud auth; we do not flag these.

Drop categories:
- **cloud-only API on local service.** Any call that requires the real IBM
  Cloud runtime to resolve. E.g. `service.job(job_id)` lookups,
  `job.update_tags(...)`, `job.metrics()`, anything in `qiskit_ibm_catalog`
  that contacts the catalog API. Local-mode primitives have no record of
  these.
- **real-backend properties absent on fakes.** E.g. `backend.properties().general`
  with `lf_*` (layer-fidelity) entries, `backend.coupling_map` differences
  driven by current calibration state, `backend.target.dt` etc. that only
  populate on real hardware.
- **Deprecation/missing-id warnings emitted by the test harness itself**
  (nbformat `MissingIDFieldWarning`, traitlets cell-id validation warnings).
  These don't affect notebook correctness.
- Any failure that would clearly disappear if the notebook ran against
  `QiskitRuntimeService(channel="ibm_cloud", ...)` with a real account on a
  real backend.

If in doubt about whether a failure is `drop` vs `upstream`: ask "would a real
hardware user with a real cloud account hit this?". If yes → `upstream`. If
no → `drop`.

## Soft-issue categories (apply within `infra` and `upstream` only)

Every reported finding also gets a category and severity:

- **swallowed-error** (high) — code cell printed a traceback or error message
  to stdout/stderr but the notebook continued (bare `try/except` is the usual
  cause). nbmake sees these as passing.
- **deprecation** (medium) — `DeprecationWarning` or
  `PendingDeprecationWarning` in stderr referencing a Qiskit /
  qiskit-ibm-runtime / qiskit-aer API. Quote the message. Ignore deprecations
  from unrelated libraries (matplotlib, numpy) unless they will plausibly
  break the notebook on the next minor bump.
- **prose-mismatch** (medium) — the markdown cell immediately before a code
  cell makes a claim (e.g. "we expect the |11⟩ state to dominate") that the
  cell's actual output contradicts. Quote both prose and contradicting output.
- **hard-failure** (high, only when nbmake already failed the cell) — used
  when a cell raised an exception. Capture the exception type and one-line
  message; do not paste the full traceback.
- **narrative-rot** (low) — code uses a still-working but deprecated path that
  the surrounding prose actively teaches as the recommended way.

If you are unsure, prefer **not** to flag it. False positives are more costly
than false negatives at this stage.

## Output format (`findings.md`)

````markdown
# Notebook review

**Batch**: `source={source} offset={offset} count={count}`
**Upstream run**: [{run_id}]({run_url})
**Reviewed**: {N} notebooks · {dropped} dropped as simulator artifacts

## 🟦 To fix in doQumentation

### `relative/path/to/notebook.ipynb`
- 🔴 **hard-failure** (cell 3): `MissingOptionalLibraryError: 'Graphviz' library is required`. _Fix: add `graphviz` to Dockerfile.jupyter apt-get._
- 🟠 **deprecation** (cell 4): `DeprecationWarning: foo.bar is deprecated...`

## 🟥 To report upstream

### `relative/path/to/notebook.ipynb` &mdash; target: `qiskit-documentation`
- 🔴 **hard-failure** (cell 17): `KeyError: 'cz'` — `count_ops()['cz']` hardcoded; fails on Eagle-family backends (ecr).
- 🟡 **prose-mismatch** (cell 9): prose says ">99% on |00⟩" but counts show 47%.

### `relative/path/to/other.ipynb` &mdash; target: `qiskit`
- 🔴 **hard-failure** (cell 32): `TranspilerError: xx_minus_yy direction not auto-flippable` — `GateDirection` missing flip rule.

## ✅ Clean

- `path/to/clean1.ipynb`
- `path/to/clean2.ipynb`

## ⬛ Dropped (simulator artifacts, not reported)

- `path/to/cloud-only.ipynb` — `service.job(...)` requires real IBM Cloud.
- `path/to/layer-fidelity.ipynb` — `backend.properties().general` `lf_*` entries.

## Summary
- 🟦 infra (us): {n}
- 🟥 upstream: {n} ({per-target breakdown})
- ✅ clean: {n}
- ⬛ dropped: {n}
````

- Sort the `infra` and `upstream` sections by severity (high → medium → low).
- Within `upstream`, group by `target` (e.g. all `qiskit-documentation`
  notebooks together).
- If a notebook has more than 5 findings, keep the top 5 by severity and add a
  trailing line `- … (N more)`.
- Use these emoji exactly: 🔴 high, 🟠 medium, 🟡 low, ✅ clean, 🟦 infra,
  🟥 upstream, ⬛ dropped.
- Keep each finding to one line. Quote the smallest evidence that makes it
  self-contained.
- If `artifact/` is empty or no `.ipynb` files are present, write a one-line
  `findings.md` saying so and return.
