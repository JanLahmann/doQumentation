#!/usr/bin/env python3
"""
Turn a Pass S sweep report into src/config/pageRunStatus.json: the label the
"Open in" banner shows on each notebook page (does this page's code run here?).

  python3 scripts/notebook-sweep/make_page_status.py \\
      --report .sweep-out/passS-aer/report.json

Pass S runs every notebook with the site's own Simulator Mode patch, which is
what a visitor without an IBM Quantum account gets. Four honest categories:

  runs       every cell ran
  needs-ibm  a cell raised the site's "needs IBM Quantum" message (Qiskit
             Functions, Serverless, fetching real jobs, ...)
  heavy      a cell ran past the sweep's per-cell timeout or ran out of memory
  issue      anything else: a missing package, an API newer than the image,
             an upstream notebook bug (the label links to the issue form)

Never guesses: a page not in the report, or whose code cells changed on the
notebooks branch since the swept commit, gets no label. The swept commit,
date and image come from the pass's meta.json (sweep.py writes it); give them
with --notebooks-ref / --date / --image for an older report without one.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
OUT = REPO / "src" / "config" / "pageRunStatus.json"

NEEDS_IBM_MARK = "needs IBM Quantum and has no offline equivalent"
HEAVY_ENAMES = {"DeadKernelError", "BrokenProcessPool"}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def classify(rec: dict) -> str:
    if rec["status"] == "ok":
        return "runs"
    fail = rec.get("failure") or {}
    if NEEDS_IBM_MARK in (fail.get("evalue") or ""):
        return "needs-ibm"
    if rec["status"] == "timeout" or fail.get("ename") in HEAVY_ENAMES:
        return "heavy"
    return "issue"


def detail(rec: dict) -> str:
    fail = rec.get("failure") or {}
    text = ANSI.sub("", f"{fail.get('ename', '')}: {fail.get('evalue', '')}").strip()
    text = text.splitlines()[0] if text else ""
    return text if len(text) <= 160 else text[:157] + "..."


def code_cells(ref: str, path: str) -> list[str] | None:
    """The code cells' sources of a notebook at a git ref, or None if absent."""
    shown = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{path}"],
                           capture_output=True, text=True)
    if shown.returncode != 0:
        return None
    cells = json.loads(shown.stdout).get("cells", [])
    return ["".join(c.get("source", "")) for c in cells if c.get("cell_type") == "code"]


def banner_notebooks() -> set[str]:
    """notebookPath of every page that shows the Open-in banner (pages with code)."""
    found = set()
    for mdx in DOCS.rglob("*.mdx"):
        found.update(re.findall(r'<OpenInLabBanner notebookPath="([^"]+)"', mdx.read_text(encoding="utf-8")))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", required=True, type=Path, help="a Pass S report.json")
    ap.add_argument("--date", help="sweep date YYYY-MM-DD (default: meta.json)")
    ap.add_argument("--image", help="image the sweep ran in (default: meta.json)")
    ap.add_argument("--notebooks-ref", help="notebooks-branch commit the sweep ran against (default: meta.json)")
    ap.add_argument("--current-ref", default="origin/notebooks",
                    help="what the site serves now (default: origin/notebooks; fetch first)")
    ap.add_argument("--drop-matching", action="append", default=[], metavar="REGEX",
                    help="no label for a failure whose 'ename: evalue' matches REGEX, e.g. one "
                         "fixed in the image since the sweep (repeatable)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    meta_file = args.report.parent / "meta.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    if meta.get("pass") not in (None, "S"):
        sys.exit(f"{args.report} is a Pass {meta['pass']} report; labels describe Simulator Mode, use Pass S")
    date = args.date or meta.get("date")
    image = args.image or meta.get("image")
    swept_ref = args.notebooks_ref or meta.get("notebooks_ref")
    if not (date and image and swept_ref):
        sys.exit("need --date, --image and --notebooks-ref (no meta.json next to the report)")
    for ref in (swept_ref, args.current_ref):
        if subprocess.run(["git", "-C", str(REPO), "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"],
                          capture_output=True).returncode != 0:
            sys.exit(f"unknown git ref {ref} (git fetch origin notebooks?)")
    swept_ref = subprocess.run(["git", "-C", str(REPO), "rev-parse", swept_ref],
                               capture_output=True, text=True).stdout.strip()

    shown = banner_notebooks()
    pages: dict[str, str] = {}
    details: dict[str, str] = {}
    skipped = {"no banner": 0, "changed since sweep": 0, "gone": 0, "dropped by --drop-matching": 0}
    drop = [re.compile(p) for p in args.drop_matching]
    for rec in json.loads(args.report.read_text()):
        path = rec["notebook"].removeprefix("/repo/")
        if path not in shown:
            skipped["no banner"] += 1
            continue
        if rec["status"] != "ok" and any(p.search(detail(rec)) for p in drop):
            skipped["dropped by --drop-matching"] += 1
            continue
        now = code_cells(args.current_ref, path)
        if now is None:
            skipped["gone"] += 1
            continue
        if now != code_cells(swept_ref, path):
            skipped["changed since sweep"] += 1
            continue
        pages[path] = classify(rec)
        if pages[path] == "issue":
            details[path] = detail(rec)

    data = {
        "_generated_by": "scripts/notebook-sweep/make_page_status.py from a Pass S sweep; do not edit by hand",
        "sweepDate": date,
        "image": image,
        "notebooksRef": swept_ref[:10],
        "droppedPatterns": args.drop_matching,
        "pages": dict(sorted(pages.items())),
        "details": dict(sorted(details.items())),
    }
    args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for cat in pages.values():
        counts[cat] = counts.get(cat, 0) + 1
    print(f"{args.out.relative_to(REPO)}: {len(pages)} pages {dict(sorted(counts.items()))}")
    print(f"  no label: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
