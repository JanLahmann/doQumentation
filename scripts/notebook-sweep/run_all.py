#!/usr/bin/env python3
"""
run_all.py — execute notebooks in the QuBins image, simulator/fake only.

Runs INSIDE the container (invoked via `podman run --entrypoint python3`).
The host driver (sweep.sh) mounts the repo read-only and this script
read-only, then calls:

    run_all.py <report_dir> <notebook> [<notebook> ...]

For each notebook: fresh kernel, sim_shim applied at kernel startup via a
0th injected code cell, `!pip install` cell neutralised, per-cell timeout.
Writes <report_dir>/report.json (machine) and report.md (human).

Capture-only: never edits notebooks, never fixes anything.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

CELL_TIMEOUT = int(__import__("os").environ.get("DOQ_CELL_TIMEOUT", "180"))
SHIM_PATH = "/shim/sim_shim.py"

# Prepended as the kernel's first executed cell so the shim patches
# qiskit_ibm_runtime before any notebook code imports from it.
SHIM_BOOTSTRAP = (
    "import sys as _s; _s.path.insert(0, '/shim')\n"
    "import sim_shim as _shim\n"
    "def _doq_reapply():\n"
    "    try: _shim.apply()\n"
    "    except Exception: pass\n"
    "_doq_reapply()\n"
)


def _is_pip_install_cell(src: str) -> bool:
    s = src.lstrip()
    return s.startswith("# Install required packages") or (
        "!pip install" in src and "find_spec" in src
    )


def run_one(nb_path: Path) -> dict:
    rec = {
        "notebook": str(nb_path),
        "status": "ok",
        "cells_executed": 0,
        "failure": None,
        "duration_s": 0.0,
    }
    t0 = time.time()
    try:
        nb = nbformat.read(nb_path, as_version=4)

        # Neutralise the gated pip-install cell (no network in sweep).
        for cell in nb.cells:
            if cell.get("cell_type") == "code" and _is_pip_install_cell(
                "".join(cell.get("source", ""))
            ):
                cell["source"] = "# [sweep] pip-install cell skipped (offline)\n"

        # Inject shim bootstrap as a new first code cell.
        boot = nbformat.v4.new_code_cell(source=SHIM_BOOTSTRAP)
        boot.metadata["doq_injected"] = True
        nb.cells.insert(0, boot)

        client = NotebookClient(
            nb,
            timeout=CELL_TIMEOUT,
            kernel_name="python3",
            allow_errors=False,
            record_timing=False,
        )
        client.execute()
        rec["cells_executed"] = sum(
            1 for c in nb.cells if c.get("cell_type") == "code"
        )
    except CellExecutionError as e:
        rec["status"] = "fail"
        # Locate the failing cell + first traceback line.
        ename = getattr(e, "ename", None) or e.__class__.__name__
        evalue = getattr(e, "evalue", None) or str(e).splitlines()[0][:300]
        tb = (str(e).splitlines() or [""])
        rec["failure"] = {
            "ename": ename,
            "evalue": evalue,
            "traceback_tail": tb[-1][:300] if tb else "",
        }
    except TimeoutError:
        rec["status"] = "timeout"
        rec["failure"] = {"ename": "TimeoutError",
                          "evalue": f">{CELL_TIMEOUT}s on a cell"}
    except Exception as e:  # noqa: BLE001 — runner must never crash the sweep
        rec["status"] = "error"
        rec["failure"] = {
            "ename": e.__class__.__name__,
            "evalue": str(e)[:300],
            "traceback_tail": traceback.format_exc().splitlines()[-1][:300],
        }
    rec["duration_s"] = round(time.time() - t0, 1)
    return rec


def main(argv: list[str]) -> int:
    report_dir = Path(argv[1])
    report_dir.mkdir(parents=True, exist_ok=True)
    notebooks = [Path(p) for p in argv[2:]]

    results = []
    for i, nb in enumerate(notebooks, 1):
        print(f"[{i}/{len(notebooks)}] {nb}", file=sys.stderr, flush=True)
        r = run_one(nb)
        results.append(r)
        print(
            f"    -> {r['status']} ({r['duration_s']}s)"
            + (f"  {r['failure']['ename']}: {r['failure']['evalue']}"
               if r["failure"] else ""),
            file=sys.stderr,
            flush=True,
        )
        # Stream partial results so a crash/OOM still leaves data.
        (report_dir / "report.json").write_text(json.dumps(results, indent=2))

    _write_markdown(report_dir / "report.md", results)
    n_fail = sum(1 for r in results if r["status"] != "ok")
    print(f"\nDONE: {len(results)} notebooks, {n_fail} not-ok",
          file=sys.stderr)
    return 0


def _write_markdown(path: Path, results: list[dict]) -> None:
    by_status: dict[str, list] = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)
    lines = ["# Notebook sweep report", ""]
    lines.append(f"- Total: **{len(results)}**")
    for st in ("ok", "fail", "timeout", "error"):
        if st in by_status:
            lines.append(f"- {st}: **{len(by_status[st])}**")
    # Group failures by exception name.
    lines += ["", "## Failures by error class", ""]
    cls: dict[str, list] = {}
    for r in results:
        if r["status"] == "ok":
            continue
        key = (r.get("failure") or {}).get("ename", r["status"])
        cls.setdefault(key, []).append(r)
    for key in sorted(cls, key=lambda k: -len(cls[k])):
        lines.append(f"### {key} ({len(cls[key])})")
        for r in sorted(cls[key], key=lambda x: x["notebook"]):
            f = r.get("failure") or {}
            lines.append(
                f"- `{r['notebook']}` — {f.get('evalue','')}"
            )
        lines.append("")
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
