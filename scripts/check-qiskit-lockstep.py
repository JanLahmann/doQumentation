#!/usr/bin/env python3
"""Assert the Binder backend's default Qiskit image tag stays in lockstep with
the qiskit[all] pin the CE/Docker image is actually built from.

Two places encode the Qiskit version, and they drifted once (Binder stayed on
2.3-xl after the dep-sync bumped the pin to 2.4.1):

  1. binder/jupyter-requirements.txt  ->  qiskit[all]~=X.Y.Z   (drives CE/Docker)
  2. src/config/jupyter.ts            ->  DEFAULT_QISKIT_TAG = 'X.Y-xl'  (Binder)

This check fails the build if their X.Y don't match, so the next dep-sync PR that
bumps the pin can't silently leave the public Binder backend on an older Qiskit.
Run by CI (ci.yml). Exit 0 = in lockstep, exit 1 = drift.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "binder" / "jupyter-requirements.txt"
JUP = ROOT / "src" / "config" / "jupyter.ts"


def fail(msg: str) -> "None":
    print(f"❌ qiskit-lockstep: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    req_txt = REQ.read_text(encoding="utf-8")
    m = re.search(r"^qiskit\[all\]\s*[~>=]=\s*(\d+)\.(\d+)", req_txt, re.MULTILINE)
    if not m:
        fail(f"could not find a qiskit[all] pin in {REQ.relative_to(ROOT)}")
    req_minor = f"{m.group(1)}.{m.group(2)}"  # e.g. "2.4"

    jup_txt = JUP.read_text(encoding="utf-8")
    m2 = re.search(r"DEFAULT_QISKIT_TAG\s*:\s*QiskitTag\s*=\s*'(\d+)\.(\d+)-xl'", jup_txt)
    if not m2:
        fail(f"could not find DEFAULT_QISKIT_TAG = 'X.Y-xl' in {JUP.relative_to(ROOT)}")
    tag_minor = f"{m2.group(1)}.{m2.group(2)}"

    if req_minor != tag_minor:
        fail(
            f"Binder default tag is '{tag_minor}-xl' but binder/jupyter-requirements.txt "
            f"pins qiskit[all]~={req_minor}.x.\n"
            f"   Bump DEFAULT_QISKIT_TAG in src/config/jupyter.ts to '{req_minor}-xl' "
            f"(and add it to SUPPORTED_QISKIT_TAGS) so the public Binder backend "
            f"matches the dependency the CE/Docker image is built from.\n"
            f"   A matching QuBins image must exist: "
            f"https://github.com/QuBins/qiskit-images (branch '{req_minor}-xl')."
        )

    print(f"✅ qiskit-lockstep: Binder default '{tag_minor}-xl' matches "
          f"qiskit[all]~={req_minor}.x")


if __name__ == "__main__":
    main()
