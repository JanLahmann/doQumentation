#!/usr/bin/env python3
"""
check-simulator-mode.py — run doc pages against the exact kernel patches the
site injects (src/kernel/), in each Simulator Mode, and fail on any error.

The notebook sweep uses its own shim (scripts/notebook-sweep/sim_shim.py), so
it never exercised the site's stand-in; #965 (CHSH crashed on the ideal
AerSimulator) and #966 (Hello World saved placeholder credentials) both
shipped unseen. This check closes that gap for the pages learners land on.

Two checks:
  1. Every token="..." literal in docs/ is classified as a placeholder by
     src/kernel/save_account_guard.py, and a real-shaped key is not.
  2. Each page in PAGES runs cell by cell in a fresh interpreter, in both
     Simulator Modes, with HOME pointing at an empty folder:
       - a page with Simulator Mode on must run every cell without error;
       - an exempt page (pages.json "exempt") gets only the guard, the way the
         site injects it without credentials; its hardware cells may fail,
         but nothing may be written to ~/.qiskit.

Needs the Qiskit stack: run it inside the QuBins image the site uses
(.github/workflows/simulator-mode.yml does).

Usage: python3 scripts/check-simulator-mode.py [page ...]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get("DOQ_KERNEL_DIR") or ROOT / "src" / "kernel")  # the sweep mounts it elsewhere
DOCS = ROOT / "docs"

# The "Get started" pages; every page with a rule in pages.json is added too.
PAGES = ["tutorials/chsh-inequality", "tutorials/hello-world"]
DEFAULT_FAKE_DEVICE = "FakeSherbrooke"  # getFakeDevice() default, src/config/jupyter.ts
CELL_TIMEOUT_S = 600

RUNNER = textwrap.dedent('''
    import json, sys, traceback
    cells = json.load(open(sys.argv[1]))
    g = {"__name__": "__main__"}
    for i, code in enumerate(cells):
        try:
            exec(compile(code, f"<cell {i}>", "exec"), g)
            print(f"@@CELL {i} ok", flush=True)
        except BaseException as e:
            print(f"@@CELL {i} FAIL {type(e).__name__}: {str(e)[:300]}", flush=True)
''')


def pages_config() -> dict:
    return json.loads((KERNEL / "pages.json").read_text())


def page_matches(path: str, page: str) -> bool:
    """Mirror of pageMatches() in src/kernel/index.ts."""
    p = path.rstrip("/")
    return p == page or p.endswith(page)


def simulator_patch_code(device: str | None) -> str:
    """Mirror of simulatorPatchCode() in src/kernel/index.ts."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "", device or "")
    return (f'_DQ_DEVICE = {json.dumps(safe) if safe else "None"}\n'
            f"_DQ_SUPPRESS_WARNINGS = True\n"
            + (KERNEL / "simulator_patch.py").read_text())


def device_for(mode: str, path: str, cfg: dict) -> str | None:
    """Mirror of getSimulatorDevice() for a user who never picked a device."""
    page_device = next((d for p, d in cfg["device"].items() if page_matches(path, p)), None)
    if mode == "fake":
        return page_device or DEFAULT_FAKE_DEVICE
    return page_device


def page_cells(page: str) -> list[str]:
    """The executable python blocks of a page, with shell/magic lines dropped."""
    src = (DOCS / f"{page}.mdx").read_text()
    cells = []
    for meta, body in re.findall(r"```python([^\n]*)\n(.*?)```", src, re.S):
        if "noexec" in meta:
            continue
        body = textwrap.dedent(body)  # blocks inside <Tabs> are indented
        body = "\n".join("pass  # " + ln if ln.lstrip().startswith(("!", "%")) else ln
                         for ln in body.splitlines())
        cells.append(body)
    return cells


def check_placeholders() -> list[str]:
    g: dict = {}
    exec((KERNEL / "save_account_guard.py").read_text(), g)
    is_placeholder = g["_dq_is_placeholder"]
    errors = []
    tokens = set()
    for f in DOCS.rglob("*.mdx"):
        tokens.update(re.findall(r'\btoken\s*=\s*"([^"]*)"', f.read_text()))
    for t in sorted(tokens):
        if not is_placeholder(t):
            errors.append(f'placeholder token="{t}" in docs/ would be saved by the guard')
    real = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v2"  # 44 chars, IBM Cloud key shape
    if is_placeholder(real):
        errors.append("a real-shaped 44-character API key is treated as a placeholder")
    print(f"placeholders: {len(tokens)} distinct token literals in docs/, "
          f"{'all' if not errors else 'NOT all'} recognised")
    return errors


def run_page(page: str, mode: str, cfg: dict) -> list[str]:
    path = "/" + page
    exempt = any(page_matches(path, p) for p in cfg["exempt"])
    prelude = [(KERNEL / "save_account_guard.py").read_text()]
    device = None
    if not exempt:
        device = device_for(mode, path, cfg)
        prelude.append(simulator_patch_code(device))
    cells = page_cells(page)
    label = f"{page} [{mode}, {'exempt' if exempt else device or 'AerSimulator'}]"

    with tempfile.TemporaryDirectory() as home:
        cells_file = Path(home) / "cells.json"
        cells_file.write_text(json.dumps(prelude + cells))
        env = dict(os.environ, HOME=home, MPLBACKEND="Agg", PYTHONWARNINGS="ignore")
        try:
            out = subprocess.run([sys.executable, "-c", RUNNER, str(cells_file)], env=env,
                                 capture_output=True, text=True,
                                 timeout=CELL_TIMEOUT_S * len(cells)).stdout
        except subprocess.TimeoutExpired:
            return [f"{label}: timed out"]
        # QiskitRuntimeService() itself leaves an empty {} file behind.
        accounts = Path(home) / ".qiskit" / "qiskit-ibm.json"
        saved = accounts.exists() and bool(json.loads(accounts.read_text() or "{}"))

    results = re.findall(r"^@@CELL (\d+) (ok|FAIL.*)$", out, re.M)
    errors = []
    for i, status in results:
        n = int(i) - len(prelude)
        if n < 0 and status != "ok":
            errors.append(f"{label}: kernel patch failed: {status}")
        elif n >= 0 and status != "ok" and not exempt:
            errors.append(f"{label}: cell {n + 1} {status}")
    if len(results) < len(prelude) + len(cells):
        errors.append(f"{label}: stopped after {len(results)} of {len(prelude) + len(cells)} steps")
    if saved:
        errors.append(f"{label}: an account was saved to ~/.qiskit")
    ok = sum(1 for i, s in results if int(i) >= len(prelude) and s == "ok")
    print(f"{label}: {ok}/{len(cells)} cells ok{' (exempt: hardware cells may fail)' if exempt else ''}"
          f"{', account SAVED' if saved else ''}")
    return errors


def main() -> int:
    cfg = pages_config()
    pages = sys.argv[1:] or sorted(set(PAGES) | {p.lstrip("/") for p in cfg["exempt"]}
                                   | {p.lstrip("/") for p in cfg["device"]})
    errors = check_placeholders()
    for page in pages:
        for mode in ("aer", "fake"):
            errors += run_page(page, mode, cfg)
    if errors:
        print("\nFAIL")
        for e in errors:
            print(f"  {e}")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
