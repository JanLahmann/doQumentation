#!/usr/bin/env python3
"""Assert the Binder backend's default Qiskit image tag stays in lockstep with
the QuBins image the CE/Docker image is built from.

Two places encode the Qiskit version, and they drifted once (Binder stayed on
2.3-xl after the CE/Docker pin moved to 2.4.1):

  1. Dockerfile.jupyter    ->  FROM ghcr.io/qubins/images:X.Y-xl  (drives CE/Docker)
  2. src/config/jupyter.ts ->  DEFAULT_QISKIT_TAG = 'X.Y-xl'      (Binder)

This check fails the build if they differ, so a bump of one can't silently
leave the other on an older Qiskit.

It also fails when a hard-coded QuBins tag elsewhere differs from the default:
the daily Binder warm-up kept 2.3-xl hot (and the admin page linked to it) long
after the site had moved to 2.5-xl, because "bump in lockstep" was a comment.
Run by CI (ci.yml). Exit 0 = in lockstep, exit 1 = drift.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile.jupyter"
JUP = ROOT / "src" / "config" / "jupyter.ts"
# Files that name the default QuBins tag literally; every tag they name must be it.
TAG_USERS = [
    ROOT / ".github" / "workflows" / "binder-warmup.yml",
    ROOT / "src" / "pages" / "admin.tsx",
]


def fail(msg: str) -> "None":
    print(f"❌ qiskit-lockstep: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    df_txt = DOCKERFILE.read_text(encoding="utf-8")
    m = re.search(r"^FROM\s+ghcr\.io/qubins/images:(\d+\.\d+-xl)\b", df_txt, re.MULTILINE)
    if not m:
        fail(f"could not find FROM ghcr.io/qubins/images:X.Y-xl in {DOCKERFILE.relative_to(ROOT)}")
    image_tag = m.group(1)  # e.g. "2.5-xl"

    jup_txt = JUP.read_text(encoding="utf-8")
    m2 = re.search(r"DEFAULT_QISKIT_TAG\s*:\s*QiskitTag\s*=\s*'(\d+)\.(\d+)-xl'", jup_txt)
    if not m2:
        fail(f"could not find DEFAULT_QISKIT_TAG = 'X.Y-xl' in {JUP.relative_to(ROOT)}")
    default = f"{m2.group(1)}.{m2.group(2)}-xl"

    if image_tag != default:
        fail(
            f"Binder default tag is '{default}' but Dockerfile.jupyter builds on "
            f"ghcr.io/qubins/images:{image_tag}.\n"
            f"   Move both to the same tag: DEFAULT_QISKIT_TAG in src/config/jupyter.ts "
            f"(and SUPPORTED_QISKIT_TAGS) and the FROM line, with its digest.\n"
            f"   A matching QuBins image must exist: "
            f"https://github.com/QuBins/qiskit-images (branch '{default}')."
        )
    for f in TAG_USERS:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for tag in re.findall(r"QuBins/qiskit-images/(\d+\.\d+-\w+)", line):
                if tag != default:
                    fail(f"{f.relative_to(ROOT)}:{n} names QuBins tag '{tag}' but "
                         f"DEFAULT_QISKIT_TAG is '{default}'. Point it at '{default}'.")

    print(f"✅ qiskit-lockstep: Binder default '{default}' matches "
          f"the CE/Docker base ghcr.io/qubins/images:{image_tag}")


if __name__ == "__main__":
    main()
