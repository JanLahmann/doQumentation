#!/usr/bin/env python3
"""
Turn a Pass S sweep report into src/config/pageRunStatus.json: the label the
"Open in" banner shows on each notebook page (does this page's code run here?).

  python3 scripts/notebook-sweep/make_page_status.py \\
      --report <artifact>/amd64/passS-aer/report.json \\
      --report-arm64 <artifact>/arm64/passS-aer/report.json

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
    ap.add_argument("--report-arm64", type=Path,
                    help="the same sweep's arm64 report: labels where arm64 differs")
    ap.add_argument("--any-arch", action="store_true",
                    help="accept reports from another arch than named (not for the published labels)")
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

    def load(report: Path, want: str) -> list[dict]:
        records = json.loads(report.read_text())
        archs = sorted({rec.get("arch", "unknown") for rec in records})
        if archs != [want] and not args.any_arch:
            sys.exit(f"{report} ran on {', '.join(archs)}, not {want}. The labels say where the "
                     "code runs, and an arm64 image lacks packages without arm64 wheels. Use "
                     ".github/workflows/notebook-sweep.yml, or pass --any-arch to look anyway.")
        return records

    shown = banner_notebooks()
    drop = [re.compile(p) for p in args.drop_matching]

    def labels(records: list[dict]) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
        pages: dict[str, str] = {}
        details: dict[str, str] = {}
        skipped = {"no banner": 0, "changed since sweep": 0, "gone": 0, "dropped by --drop-matching": 0}
        for rec in records:
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
        return pages, details, skipped

    pages, details, skipped = labels(load(args.report, "x86_64"))
    data = {
        "_generated_by": "scripts/notebook-sweep/make_page_status.py from a Pass S sweep; do not edit by hand",
        "sweepDate": date,
        "image": image,
        # The exact image (the tag moves when QuBins rebuilds), when the sweep recorded it.
        **({"imageDigest": meta["image_digest"]} if meta.get("image_digest") else {}),
        "notebooksRef": swept_ref[:10],
        "droppedPatterns": args.drop_matching,
        # amd64: Binder, Code Engine and Intel/AMD computers.
        "pages": dict(sorted(pages.items())),
        "details": dict(sorted(details.items())),
    }
    if args.report_arm64:
        arm_meta_file = args.report_arm64.parent / "meta.json"
        arm_meta = json.loads(arm_meta_file.read_text()) if arm_meta_file.exists() else {}
        if arm_meta.get("notebooks_ref", swept_ref) != swept_ref and subprocess.run(
                ["git", "-C", str(REPO), "rev-parse", arm_meta["notebooks_ref"]],
                capture_output=True, text=True).stdout.strip() != swept_ref:
            sys.exit(f"{args.report_arm64} swept other notebooks ({arm_meta['notebooks_ref'][:10]}) "
                     f"than {args.report} ({swept_ref[:10]})")
        arm_pages, arm_details, _ = labels(load(args.report_arm64, "aarch64"))
        # arm64 (Apple silicon Macs, Raspberry Pi): only where it differs.
        data["arm64"] = {
            "pages": {k: v for k, v in sorted(arm_pages.items()) if pages.get(k) != v},
            "details": {k: v for k, v in sorted(arm_details.items())
                        if pages.get(k) != arm_pages[k] or details.get(k) != v},
        }
    args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for cat in pages.values():
        counts[cat] = counts.get(cat, 0) + 1
    print(f"{args.out.relative_to(REPO) if args.out.is_relative_to(REPO) else args.out}: {len(pages)} pages {dict(sorted(counts.items()))}")
    print(f"  no label: {skipped}")
    if "arm64" in data:
        print(f"  arm64 differs on {len(data['arm64']['pages'])} pages: {data['arm64']['pages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
