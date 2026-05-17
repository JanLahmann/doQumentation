#!/usr/bin/env python3
"""Merge per-batch report.json files into one pass-level report.{json,md}.

Usage: merge_reports.py <pass_out_dir>
Reads <dir>/batch-*/report.json, writes <dir>/report.json + report.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(d: str) -> int:
    base = Path(d)
    merged: list[dict] = []
    for bj in sorted(base.glob("batch-*/report.json")):
        try:
            merged.extend(json.loads(bj.read_text()))
        except Exception as e:  # noqa: BLE001
            print(f"  warn: {bj}: {e}", file=sys.stderr)
    merged.sort(key=lambda r: r.get("notebook", ""))
    (base / "report.json").write_text(json.dumps(merged, indent=2))

    by_status: dict[str, int] = {}
    for r in merged:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    lines = ["# Notebook sweep — merged report", ""]
    lines.append(f"- Total: **{len(merged)}**")
    for st in ("ok", "fail", "timeout", "error"):
        if st in by_status:
            lines.append(f"- {st}: **{by_status[st]}**")
    lines += ["", "## Not-ok, grouped by error class", ""]

    cls: dict[str, list] = {}
    for r in merged:
        if r["status"] == "ok":
            continue
        key = (r.get("failure") or {}).get("ename", r["status"])
        cls.setdefault(key, []).append(r)
    for key in sorted(cls, key=lambda k: -len(cls[k])):
        lines.append(f"### {key} ({len(cls[key])})")
        for r in sorted(cls[key], key=lambda x: x["notebook"]):
            f = r.get("failure") or {}
            ev = (f.get("evalue", "") or "").replace("\n", " ")[:200]
            lines.append(f"- `{r['notebook']}` — {ev}")
        lines.append("")
    (base / "report.md").write_text("\n".join(lines))
    print(f"  merged {len(merged)} -> {base/'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
