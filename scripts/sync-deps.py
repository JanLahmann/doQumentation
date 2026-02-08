#!/usr/bin/env python3
"""Sync binder/jupyter-requirements*.txt from upstream.

Reads the canonical requirements from
JanLahmann/Qiskit-documentation/scripts/nb-tester/requirements.txt
and applies exception rules for our multi-arch Docker images:
  - Drop sys.platform markers (Linux-only containers)
  - Add pylatexenc (needed for LaTeX in Qiskit visualizations)
  - Move to amd64-only: gem-suite, qiskit-ibm-transpiler[ai-local-mode],
    qiskit-addon-aqc-tensor[quimb-jax] (no arm64 wheels)
  - Split qiskit-addon-aqc-tensor extras: [aer] cross-platform, [quimb-jax] amd64-only

Usage:
    python scripts/sync-deps.py [upstream-requirements.txt]

If no file is given, fetches from GitHub directly.
"""

import re
import sys
import urllib.request
from pathlib import Path

UPSTREAM_URL = (
    "https://raw.githubusercontent.com/JanLahmann/Qiskit-documentation"
    "/main/scripts/nb-tester/requirements.txt"
)

# Packages that go to amd64-only file (no arm64 wheels)
AMD64_ONLY = {"gem-suite", "qiskit-ibm-transpiler"}

# Extra split: qiskit-addon-aqc-tensor[aer] is cross-platform,
# [quimb-jax] is amd64-only (kahypar has no arm64 wheel)
AQC_TENSOR = "qiskit-addon-aqc-tensor"

# Packages we add that aren't in upstream
EXTRA_CROSS_PLATFORM = ["pylatexenc"]

CROSS_PLATFORM_HEADER = """\
# Full Qiskit dependencies for Docker / local Jupyter (both amd64 and arm64).
# Synced with JanLahmann/Qiskit-documentation/scripts/nb-tester/requirements.txt.
# amd64-only extras are in jupyter-requirements-amd64.txt.
# Exceptions vs upstream:
#   - pylatexenc added (needed for LaTeX in Qiskit visualizations)
#   - gem-suite moved to amd64-only (no arm64 prebuilt wheel)
#   - sys.platform markers dropped (Linux-only container)
"""

AMD64_HEADER = """\
# Extra packages for amd64 only (no Linux arm64 wheels available).
# Installed conditionally in Dockerfile.jupyter.
"""

# Regex: package[extras]~=version; marker
LINE_RE = re.compile(
    r"^(?P<name>[a-zA-Z0-9_-]+)"
    r"(?:\[(?P<extras>[^\]]+)\])?"
    r"(?P<version>[^;#\s]+)?"
    r"(?:\s*;\s*(?P<marker>[^#]+))?"
    r"\s*(?:#.*)?$"
)


def parse_upstream(text: str) -> list[dict]:
    """Parse upstream requirements.txt into structured entries."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RE.match(line)
        if not m:
            print(f"  Warning: could not parse line: {line}")
            continue
        entries.append({
            "name": m.group("name"),
            "extras": m.group("extras") or "",
            "version": (m.group("version") or "").strip(),
            "marker": (m.group("marker") or "").strip(),
        })
    return entries


def apply_rules(entries: list[dict]) -> tuple[list[str], list[str]]:
    """Apply exception rules, return (cross_platform_lines, amd64_lines)."""
    cross = []
    amd64 = []

    for e in entries:
        name, extras, version = e["name"], e["extras"], e["version"]

        # Special case: qiskit-addon-aqc-tensor — split extras
        if name == AQC_TENSOR:
            extra_list = [x.strip() for x in extras.split(",")]
            cross_extras = [x for x in extra_list if x != "quimb-jax"]
            amd64_extras = [x for x in extra_list if x == "quimb-jax"]
            if cross_extras:
                cross.append(f"{name}[{','.join(cross_extras)}]{version}")
            if amd64_extras:
                amd64.append(
                    f"{name}[{','.join(amd64_extras)}]{version}"
                    "   # adds kahypar (no arm64 wheel)"
                )
            continue

        # amd64-only packages
        if name in AMD64_ONLY:
            fmt = f"{name}{version}" if not extras else f"{name}[{extras}]{version}"
            amd64.append(fmt)
            if name == "gem-suite":
                cross.append(
                    "# gem-suite: amd64 only (see jupyter-requirements-amd64.txt)"
                )
            continue

        # Regular package — drop markers, add to cross-platform
        fmt = f"{name}{version}" if not extras else f"{name}[{extras}]{version}"
        cross.append(fmt)

    # Add our extras not in upstream
    for pkg in EXTRA_CROSS_PLATFORM:
        cross.append(pkg)

    return cross, amd64


def write_file(path: Path, header: str, lines: list[str]) -> bool:
    """Write requirements file. Returns True if content changed."""
    content = header + "\n" + "\n".join(lines) + "\n"
    try:
        old = path.read_text()
    except FileNotFoundError:
        old = ""
    if content == old:
        return False
    path.write_text(content)
    return True


def main():
    # Get upstream requirements
    if len(sys.argv) > 1:
        upstream_text = Path(sys.argv[1]).read_text()
        print(f"Reading upstream from {sys.argv[1]}")
    else:
        print(f"Fetching upstream from {UPSTREAM_URL}")
        with urllib.request.urlopen(UPSTREAM_URL) as resp:
            upstream_text = resp.read().decode()

    entries = parse_upstream(upstream_text)
    print(f"  Parsed {len(entries)} packages from upstream")

    cross_lines, amd64_lines = apply_rules(entries)

    binder_dir = Path(__file__).resolve().parent.parent / "binder"
    cross_path = binder_dir / "jupyter-requirements.txt"
    amd64_path = binder_dir / "jupyter-requirements-amd64.txt"

    cross_changed = write_file(cross_path, CROSS_PLATFORM_HEADER, cross_lines)
    amd64_changed = write_file(amd64_path, AMD64_HEADER, amd64_lines)

    if cross_changed or amd64_changed:
        print("\nFiles updated:")
        if cross_changed:
            print(f"  {cross_path}")
        if amd64_changed:
            print(f"  {amd64_path}")
    else:
        print("\nNo changes — already in sync with upstream.")


if __name__ == "__main__":
    main()
