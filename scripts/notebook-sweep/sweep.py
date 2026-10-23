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
and run with DOQ_NB_ROOT=DIR DOQ_NB_REF=origin/notebooks (recorded in each
pass's meta.json so make_page_status.py can tell which pages changed since).
DOQ_IMG overrides the image.
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

import json
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
# Binder runs linux/amd64 on 1 CPU with 2 GB. The labels describe Binder, so
# the sweep runs that platform (emulated on an arm64 Mac: slow, but an arm64
# image lacks packages that have no arm64 wheels, e.g. gem_suite, tenpy).
# .github/workflows/notebook-sweep.yml runs it natively on amd64.
PLATFORM = os.environ.get("DOQ_PLATFORM", "linux/amd64")
LIMITS = ["--cpus", "1", "--memory", "2g"] if os.environ.get("DOQ_BINDER_LIMITS", "1") == "1" else []


def discover_all() -> list[str]:
    out = []
    for root in ("tutorials", "guides", "learning"):
        for p in sorted((NB_ROOT / root).rglob("*.ipynb")):
            if ".ipynb_checkpoints" in p.parts:
                continue
            out.append(str(p.relative_to(NB_ROOT)))
    return out



def chunk(lst: list[str], n: int) -> list[list[str]]:
    per = max(1, (len(lst) + n - 1) // n)
    return [lst[i:i + per] for i in range(0, len(lst), per)] or [[]]


def notebooks_ref() -> str | None:
    """The commit the swept notebooks came from: DOQ_NB_REF, else NB_ROOT's own
    git HEAD. make_page_status.py needs it to drop pages changed since."""
    if os.environ.get("DOQ_NB_REF"):
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", os.environ["DOQ_NB_REF"]],
                              capture_output=True, text=True).stdout.strip() or os.environ["DOQ_NB_REF"]
    head = subprocess.run(["git", "-C", str(NB_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    return head.stdout.strip() if head.returncode == 0 else None


def run_pass(label: str, image: str, sub: str, nbs: list[str], site: bool = False) -> None:
    pass_out = OUT / sub
    pass_out.mkdir(parents=True, exist_ok=True)
    print(f">>> Pass {label}: {len(nbs)} notebooks, image={image}, PAR={PAR}")
    (pass_out / "meta.json").write_text(json.dumps({
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "image": image,
        "pass": label,
        "sim_mode": os.environ.get("DOQ_SIM_MODE", "aer") if site else None,
        "notebooks_ref": notebooks_ref(),
        "cell_timeout_s": int(CELL_TIMEOUT),
    }, indent=2) + "\n")
    if not nbs:
        print("  (nothing to do)")
        return

    def podman(extra: list[str], args: list[str]) -> list[str]:
        return [
            "podman", "run", "--rm",
            "--platform", PLATFORM, *LIMITS,
            "-v", f"{NB_ROOT}:/repo:ro",
            "-v", f"{SHIM_DIR}:/shim:ro",
            "-v", f"{pass_out}:/out",
            "-e", f"DOQ_CELL_TIMEOUT={CELL_TIMEOUT}",
            *(["-v", f"{REPO / 'src'}:/src:ro",
               "-v", f"{REPO / 'scripts'}:/scripts:ro",
               "-e", "DOQ_SHIM=site",
               "-e", f"DOQ_SIM_MODE={os.environ.get('DOQ_SIM_MODE', 'aer')}"] if site else []),
            *extra,
            "--entrypoint", "python3", image,
            "/shim/run_all.py", *args,
        ]

    # A notebook that would install something runs alone in a fresh container
    # with installs on, as on the site (run_all.py needs_own_container); the
    # rest share containers with installs off, so no install leaks.
    own = subprocess.run(podman([], ["--needs-own-container", *[f"/repo/{nb}" for nb in nbs]]),
                         capture_output=True, text=True).stdout.split()
    own = [o.removeprefix("/repo/") for o in own]
    shared = [nb for nb in nbs if nb not in own]
    print(f"  {len(own)} notebooks install packages: each in its own container")

    procs = []
    for b, batch in enumerate(chunk(shared, PAR)):
        if not batch:
            continue
        logf = open(pass_out / f"batch-{b}.log", "w")
        cmd = podman([], [f"/out/batch-{b}", *[f"/repo/{nb}" for nb in batch]])
        procs.append((subprocess.Popen(cmd, stdout=logf, stderr=logf), logf, b))

    t0 = time.time()
    for p, logf, b in procs:
        p.wait()
        logf.close()
        print(f"  batch-{b} exit={p.returncode} ({int(time.time()-t0)}s elapsed)")

    for i, nb in enumerate(own, 1):
        with open(pass_out / f"batch-own-{i}.log", "w") as logf:
            rc = subprocess.run(podman(["-e", "DOQ_INSTALLS=1"], [f"/out/batch-own-{i}", f"/repo/{nb}"]),
                                stdout=logf, stderr=logf).returncode
        print(f"  {nb} (own container, installs on) exit={rc}")

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
