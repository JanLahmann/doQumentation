#!/usr/bin/env python3
"""
Host driver for the notebook sweep (runs OUTSIDE the container).

  python3 sweep.py            # Pass A (all, stock image) + Pass B
  python3 sweep.py A          # Pass A only
  python3 sweep.py B          # Pass B only (graphviz subset)

Pass A: every EN notebook in the unmodified production image
        ghcr.io/qubins/images:2.3-xl  -> what users actually hit.
Pass B: only Graphviz-plotting notebooks, in a throwaway
        graphviz-patched image -> failures *behind* finding F1.

Python (not bash) on purpose: macOS ships bash 3.2 (no mapfile) and
process orchestration is cleaner here. Parallelism = PAR containers,
each handed a contiguous batch. 4 CPU / 8 GB VM -> PAR=3.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHIM_DIR = REPO / "scripts" / "notebook-sweep"
OUT = REPO / ".sweep-out"
STOCK_IMG = "ghcr.io/qubins/images:2.3-xl"
PATCH_IMG = "doq-sweep-depspatch:local"
PAR = int(os.environ.get("DOQ_PAR", "3"))
CELL_TIMEOUT = os.environ.get("DOQ_CELL_TIMEOUT", "300")


def discover_all() -> list[str]:
    out = []
    for root in ("tutorials", "guides", "learning"):
        for p in sorted((REPO / root).rglob("*.ipynb")):
            if ".ipynb_checkpoints" in p.parts:
                continue
            out.append(str(p.relative_to(REPO)))
    return out


def discover_passB() -> list[str]:
    # Union of notebooks blocked by the two proven missing deps:
    #   F1 graphviz-backed plotting, F2 qiskit-ibm-transpiler import.
    f1 = ("plot_coupling_map", "plot_circuit_layout", "plot_gate_map")
    f2 = ("qiskit_ibm_transpiler", "qiskit-ibm-transpiler")
    hits = set()
    for nb in discover_all():
        txt = (REPO / nb).read_text(errors="ignore")
        if any(p in txt for p in f1) or any(p in txt for p in f2):
            hits.add(nb)
    return sorted(hits)


def chunk(lst: list[str], n: int) -> list[list[str]]:
    per = (len(lst) + n - 1) // n
    return [lst[i:i + per] for i in range(0, len(lst), per)] or [[]]


def run_pass(label: str, image: str, sub: str, nbs: list[str]) -> None:
    pass_out = OUT / sub
    pass_out.mkdir(parents=True, exist_ok=True)
    print(f">>> Pass {label}: {len(nbs)} notebooks, image={image}, PAR={PAR}")
    if not nbs:
        print("  (nothing to do)")
        return

    procs = []
    for b, batch in enumerate(chunk(nbs, PAR)):
        if not batch:
            continue
        cbatch = [f"/repo/{nb}" for nb in batch]
        logf = open(pass_out / f"batch-{b}.log", "w")
        cmd = [
            "podman", "run", "--rm",
            "-v", f"{REPO}:/repo:ro",
            "-v", f"{SHIM_DIR}:/shim:ro",
            "-v", f"{pass_out}:/out",
            "-e", f"DOQ_CELL_TIMEOUT={CELL_TIMEOUT}",
            "--entrypoint", "python3", image,
            "/shim/run_all.py", f"/out/batch-{b}", *cbatch,
        ]
        procs.append((subprocess.Popen(cmd, stdout=logf, stderr=logf), logf, b))

    t0 = time.time()
    for p, logf, b in procs:
        p.wait()
        logf.close()
        print(f"  batch-{b} exit={p.returncode} ({int(time.time()-t0)}s elapsed)")

    subprocess.run(
        [sys.executable, str(SHIM_DIR / "merge_reports.py"), str(pass_out)],
        check=False,
    )
    print(f">>> Pass {label} done -> {pass_out/'report.md'}")


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "AB").upper()
    OUT.mkdir(exist_ok=True)

    if "A" in mode:
        nbs = discover_all()
        (OUT / "_all.txt").write_text("\n".join(nbs))
        run_pass("A", STOCK_IMG, "passA", nbs)

    if "B" in mode:
        print(">>> Building graphviz-patched image for Pass B")
        rc = subprocess.run(
            ["podman", "build", "-t", PATCH_IMG,
             "-f", str(SHIM_DIR / "Dockerfile.depspatch"), str(SHIM_DIR)],
        ).returncode
        if rc != 0:
            print("  deps-patch image build FAILED — skipping Pass B")
        else:
            sub = discover_passB()
            (OUT / "_passB.txt").write_text("\n".join(sub))
            run_pass("B", PATCH_IMG, "passB", sub)

    print("\nReports:")
    print(f"  {OUT/'passA'/'report.md'}   (user reality)")
    if "B" in mode:
        print(f"  {OUT/'passB'/'report.md'}   (graphviz subset, deep)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
