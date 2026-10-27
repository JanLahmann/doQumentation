#!/usr/bin/env python3
"""
Compare two Pass S sweep reports of the same platform: a baseline (the image
the site uses now) and a candidate (a new QuBins tag, a Qiskit release
candidate, ...). Lists what got worse first, so an image bump does not ship a
regression that only shows as a changed page label.

  python3 scripts/notebook-sweep/diff_reports.py \\
      --base <baseline>/amd64/passS-aer/report.json \\
      --new <candidate>/amd64/passS-aer/report.json [--out diff.md]

Reported, per notebook in both reports:

  label worse    runs -> heavy/issue/needs-ibm, or needs-ibm -> heavy/issue
                 (labels as make_page_status.py gives them)
  slower         still runs, but took --ratio times as long as before and at
                 least --min-seconds longer
  cell slower    a cell took --ratio times as long and --min-seconds longer
                 (needs `cell_times` from run_all.py; older reports have none)
  label better   the reverse of "label worse", for completeness

Timings come from CI runners and vary by about 20 %, so the defaults (2x and
30 s) only catch real changes. Exits 1 with --fail-on-regression when anything
got worse, else 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_page_status import classify  # noqa: E402

# Higher is worse. needs-ibm is a property of the page, not of the image, so a
# page moving into it from "runs" is still worth a look.
RANK = {"runs": 0, "needs-ibm": 1, "issue": 2, "heavy": 2}


def load(path: Path) -> dict[str, dict]:
    return {r["notebook"]: r for r in json.loads(path.read_text())}


def short(nb: str) -> str:
    return nb.removeprefix("/repo/").removesuffix(".ipynb")


def why(rec: dict) -> str:
    fail = rec.get("failure") or {}
    text = f"{fail.get('ename', '')}: {fail.get('evalue', '')}".strip(": ")
    text = text.splitlines()[0] if text else ""
    cell = rec.get("slowest_cell")
    if cell and cell.get("stopped_here"):
        text += f" (cell {cell['index']}: `{cell['first_line'][:60]}`)"
    return text[:200]


def compare(base: dict[str, dict], new: dict[str, dict], ratio: float, min_s: float) -> dict:
    out = {"worse": [], "slower": [], "cells": [], "better": [],
           "only_base": sorted(set(base) - set(new)), "only_new": sorted(set(new) - set(base))}
    for nb in sorted(set(base) & set(new)):
        b, n = base[nb], new[nb]
        lb, ln = classify(b), classify(n)
        if RANK[ln] > RANK[lb]:
            out["worse"].append((nb, lb, ln, why(n)))
        elif RANK[ln] < RANK[lb]:
            out["better"].append((nb, lb, ln))
        if lb == ln == "runs":
            tb, tn = b.get("duration_s", 0.0), n.get("duration_s", 0.0)
            if tn >= tb * ratio and tn - tb >= min_s:
                out["slower"].append((nb, tb, tn))
        cb, cn = b.get("cell_times") or {}, n.get("cell_times") or {}
        for idx in sorted(set(cn), key=int):
            tb, tn = cb.get(idx, 0.0), cn[idx]
            if tn >= max(tb, 1.0) * ratio and tn - tb >= min_s:
                out["cells"].append((nb, int(idx), tb, tn))
    return out


def markdown(d: dict, base_name: str, new_name: str) -> str:
    lines = [f"# Sweep comparison: `{new_name}` against `{base_name}`", ""]
    worse = len(d["worse"]) + len(d["slower"]) + len(d["cells"])
    lines.append(f"**{worse} regression(s)**, {len(d['better'])} improvement(s).")
    if d["worse"]:
        lines += ["", "## Label worse", "", "| Notebook | Before | Now | Why |", "|---|---|---|---|"]
        lines += [f"| {short(nb)} | {lb} | {ln} | {w} |" for nb, lb, ln, w in d["worse"]]
    if d["slower"]:
        lines += ["", "## Slower (still runs)", "", "| Notebook | Before | Now |", "|---|---|---|"]
        lines += [f"| {short(nb)} | {tb:.0f} s | {tn:.0f} s |" for nb, tb, tn in d["slower"]]
    if d["cells"]:
        lines += ["", "## Cells slower", "", "| Notebook | Cell | Before | Now |", "|---|---|---|---|"]
        lines += [f"| {short(nb)} | {i} | {tb:.0f} s | {tn:.0f} s |" for nb, i, tb, tn in d["cells"]]
    if d["better"]:
        lines += ["", "## Label better", "", "| Notebook | Before | Now |", "|---|---|---|"]
        lines += [f"| {short(nb)} | {lb} | {ln} |" for nb, lb, ln in d["better"]]
    for key, title in (("only_new", "Only in the candidate"), ("only_base", "Only in the baseline")):
        if d[key]:
            lines += ["", f"## {title}", ""] + [f"- {short(nb)}" for nb in d[key]]
    return "\n".join(lines) + "\n"


def image_of(report: Path) -> str:
    meta = report.parent / "meta.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        return m.get("image") or str(report)
    return str(report)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", type=Path, required=True, help="baseline report.json")
    ap.add_argument("--new", type=Path, required=True, help="candidate report.json")
    ap.add_argument("--ratio", type=float, default=2.0)
    ap.add_argument("--min-seconds", type=float, default=30.0)
    ap.add_argument("--out", type=Path, help="also write the Markdown here")
    ap.add_argument("--fail-on-regression", action="store_true")
    args = ap.parse_args()

    d = compare(load(args.base), load(args.new), args.ratio, args.min_seconds)
    text = markdown(d, image_of(args.base), image_of(args.new))
    print(text)
    if args.out:
        args.out.write_text(text)
    regressed = d["worse"] or d["slower"] or d["cells"]
    return 1 if args.fail_on_regression and regressed else 0


if __name__ == "__main__":
    raise SystemExit(main())
