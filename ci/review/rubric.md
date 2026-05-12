# Notebook review rubric

You are reviewing the executed notebooks under `./artifact/` produced by the
Notebook CI workflow. These notebooks were run with `qiskit_ibm_runtime`
monkey-patched to use local fake backends (`FakeBrisbane`, `FakeFez`,
`FakeMarrakesh`). nbmake has already caught hard failures (exceptions, timeouts,
import errors). Your job is to surface **soft** issues that nbmake cannot see.

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
   - Look for the categories listed below. The first cell of every notebook
     prints `[ci] qiskit_ibm_runtime patched: fake backends, shots<=...` —
     ignore that line; it is expected.
3. Write `findings.md` in the repo root (NOT inside `artifact/`) using the
   output format below. Always write the file, even when there are no findings.

You may use `Read`, `Glob`, `Write`, and `Bash` (`jq`, `grep`, `wc`). Do not
modify any file under `artifact/`.

## Categories (severity in parentheses)

- **deprecation** (medium) — `DeprecationWarning` or `PendingDeprecationWarning`
  in stderr that references a Qiskit / qiskit-ibm-runtime / qiskit-aer API.
  Quote the message. Ignore deprecations from unrelated libraries (matplotlib,
  numpy) unless they will plausibly break the notebook on the next minor bump.
- **prose-mismatch** (medium) — the markdown cell immediately before a code
  cell makes a claim (e.g. "we expect the |11⟩ state to dominate", "the
  expectation value should be near 1.0") that the cell's actual output
  contradicts. Quote both the prose snippet and the contradicting output.
- **swallowed-error** (high) — a code cell printed a traceback or an error
  message to stdout/stderr but the notebook continued (a bare `try/except` is
  the usual cause). nbmake sees these as passing.
- **silent-fallback** (low) — output reveals an unintended path was taken
  (e.g. a `BackendV1` fallback when the prose teaches `BackendV2`).
  CI runs always use fake backends, so do NOT flag the fake-backend itself
  (`FakeBrisbane`, `FakeFez`, `FakeMarrakesh`, `AerSimulator`) as a fallback —
  that is the whole point of CI. Only flag fallbacks the notebook's own code
  would not have taken in production.
- **narrative-rot** (low) — the code uses a still-working but deprecated path
  that the surrounding prose actively teaches as the recommended way. (E.g.
  notebook teaches `Sampler` v1 patterns while running on v2.)

If you are unsure, prefer **not** to flag it. False positives are more costly
than false negatives at this stage.

## Output format (`findings.md`)

````markdown
# Notebook review

**Batch**: `source={source} offset={offset} count={count}`
**Upstream run**: [{run_id}]({run_url})
**Reviewed**: {N} notebooks

## Findings

### `relative/path/to/notebook.ipynb`
- 🔴 **swallowed-error** (cell 12): one-line summary. > quoted output
- 🟠 **deprecation** (cell 4): `DeprecationWarning: foo.bar is deprecated since X, use foo.baz instead`
- 🟡 **prose-mismatch** (cell 9): prose says ">99% on |00⟩" but counts show 47%.

### `another/notebook.ipynb`
- ✅ Clean

## Summary
- 🔴 high: 1
- 🟠 medium: 3
- 🟡 low: 5
- ✅ clean: 11
````

- Group findings by notebook. Sort notebooks: any with high-severity findings
  first, then medium, then low, then clean.
- If a notebook has more than 5 findings, keep the top 5 by severity and add a
  trailing line `- … (N more)`.
- Use these emoji exactly: 🔴 high, 🟠 medium, 🟡 low, ✅ clean.
- Keep each finding to one line. Quote the smallest evidence that makes the
  finding self-contained.
- If `artifact/` is empty or no `.ipynb` files are present, write a one-line
  `findings.md` saying so and return.
