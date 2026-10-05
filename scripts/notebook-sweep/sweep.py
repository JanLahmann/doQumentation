#!/usr/bin/env python3
"""
Host driver for the notebook sweep (runs OUTSIDE the container).

  python3 sweep.py            # Pass A + Pass S
  python3 sweep.py A          # Pass A only
  python3 sweep.py S          # Pass S only (site Simulator Mode)

Pass A: every EN notebook in the unmodified production image
        (the site's DEFAULT_QISKIT_TAG) -> what users actually hit.

The notebooks are read from NB_ROOT (default: the gitignored notebooks/
tree sync-content.py writes). That tree is only as fresh as the last local
sync; for what the live site serves, export the published branch first:
    git archive origin/notebooks tutorials guides learning | tar -x -C DIR
and run with DOQ_NB_ROOT=DIR. DOQ_IMG overrides the image.
Pass S: every EN notebook, stock image, with the site's own Simulator Mode
        kernel patch (src/kernel/, DOQ_SIM_MODE aer|fake, default aer)
        instead of sim_shim -> what a learner gets on the site.

Every install line in every cell is skipped (run_all.py), so the sweep
measures the image itself (#969). Results go to DOQ_OUT (default
REPO/.sweep-out); give concurrent sweeps different folders.

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
OUT = Path(os.environ.get("DOQ_OUT") or REPO / ".sweep-out").resolve()


def default_image() -> str:
    """The QuBins tag the site defaults to (src/config/jupyter.ts), so the
    sweep follows image bumps instead of hard-coding one (it sat on 2.3-xl
    after the site moved to 2.5-xl)."""
    ts = (REPO / "src" / "config" / "jupyter.ts").read_text(encoding="utf-8")
    m = re.search(r"DEFAULT_QISKIT_TAG\b[^=]*=\s*'([^']+)'", ts)
    return f"ghcr.io/qubins/images:{m.group(1) if m else '2.5-xl'}"


STOCK_IMG = os.environ.get("DOQ_IMG") or default_image()
NB_ROOT = Path(os.environ.get("DOQ_NB_ROOT") or REPO / "notebooks").resolve()
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



def chunk(lst: list[str], n: int) -> list[list[str]]:
    per = (len(lst) + n - 1) // n
    return [lst[i:i + per] for i in range(0, len(lst), per)] or [[]]


def run_pass(label: str, image: str, sub: str, nbs: list[str], site: bool = False) -> None:
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
            *(["-v", f"{REPO / 'src'}:/src:ro",
               "-v", f"{REPO / 'scripts'}:/scripts:ro",
               "-e", "DOQ_SHIM=site",
               "-e", f"DOQ_SIM_MODE={os.environ.get('DOQ_SIM_MODE', 'aer')}"] if site else []),
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
    mode = (sys.argv[1] if len(sys.argv) > 1 else "AS").upper()
    OUT.mkdir(exist_ok=True)

    if "A" in mode:
        nbs = discover_all()
        (OUT / "_all.txt").write_text("\n".join(nbs))
        run_pass("A", STOCK_IMG, "passA", nbs)

    if "S" in mode:
        nbs = discover_all()
        (OUT / "_all.txt").write_text("\n".join(nbs))
        run_pass("S", STOCK_IMG, f"passS-{os.environ.get('DOQ_SIM_MODE', 'aer')}", nbs, site=True)


    print("\nReports:")
    print(f"  {OUT/'passA'/'report.md'}   (sweep shim)")
    if "S" in mode:
        print(f"  {OUT/('passS-' + os.environ.get('DOQ_SIM_MODE', 'aer'))/'report.md'}   (site Simulator Mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
