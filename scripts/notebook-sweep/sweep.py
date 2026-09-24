#!/usr/bin/env python3
"""
Host driver for the notebook sweep (runs OUTSIDE the container).

  python3 sweep.py            # Pass A (all, stock image) + Pass B
  python3 sweep.py A          # Pass A only
  python3 sweep.py B          # Pass B only (graphviz subset)

Pass A: every EN notebook in the unmodified production image
        (the site's DEFAULT_QISKIT_TAG) -> what users actually hit.

The notebooks are read from NB_ROOT (default: the gitignored notebooks/
tree sync-content.py writes). That tree is only as fresh as the last local
sync; for what the live site serves, export the published branch first:
    git archive origin/notebooks tutorials guides learning | tar -x -C DIR
and run with DOQ_NB_ROOT=DIR. DOQ_IMG overrides the image.
Pass B: only Graphviz-plotting notebooks, in a throwaway
        graphviz-patched image -> failures *behind* finding F1.

Python (not bash) on purpose: macOS ships bash 3.2 (no mapfile) and
process orchestration is cleaner here. Parallelism = PAR containers,
each handed a contiguous batch. 4 CPU / 8 GB VM -> PAR=3.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHIM_DIR = REPO / "scripts" / "notebook-sweep"
OUT = REPO / ".sweep-out"


def default_image() -> str:
    """The QuBins tag the site defaults to (src/config/jupyter.ts), so the
    sweep follows image bumps instead of hard-coding one (it sat on 2.3-xl
    after the site moved to 2.5-xl)."""
    ts = (REPO / "src" / "config" / "jupyter.ts").read_text(encoding="utf-8")
    m = re.search(r"DEFAULT_QISKIT_TAG\b[^=]*=\s*'([^']+)'", ts)
    return f"ghcr.io/qubins/images:{m.group(1) if m else '2.5-xl'}"


STOCK_IMG = os.environ.get("DOQ_IMG") or default_image()
NB_ROOT = Path(os.environ.get("DOQ_NB_ROOT") or REPO / "notebooks").resolve()
PATCH_IMG = "doq-sweep-depspatch:local"
PAR = int(os.environ.get("DOQ_PAR", "3"))
CELL_TIMEOUT = os.environ.get("DOQ_CELL_TIMEOUT", "300")


def discover_all() -> list[str]:
    out = []
    for root in ("tutorials", "guides", "learning"):
        for p in sorted((NB_ROOT / root).rglob("*.ipynb")):
            if ".ipynb_checkpoints" in p.parts:
                continue
            out.append(str(p.relative_to(NB_ROOT)))
    return out


def discover_passB() -> list[str]:
    # Union of notebooks blocked by the two proven missing deps:
    #   F1 graphviz-backed plotting, F2 qiskit-ibm-transpiler import.
    f1 = ("plot_coupling_map", "plot_circuit_layout", "plot_gate_map")
    f2 = ("qiskit_ibm_transpiler", "qiskit-ibm-transpiler")
    hits = set()
    for nb in discover_all():
        txt = (NB_ROOT / nb).read_text(errors="ignore")
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
            "-v", f"{NB_ROOT}:/repo:ro",
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
            ["podman", "build", "-t", PATCH_IMG, "--build-arg", f"BASE={STOCK_IMG}",
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
