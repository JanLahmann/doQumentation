#!/usr/bin/env python3
"""
Collect a deep-review round's records from its workflow journals.

The opus-deep-review workflow returns only tallies; every reader's verdict is
in the run's journal.jsonl (one `{"type": "result", ...}` line per agent).
This gathers them, last verdict per page wins, adds the sample's `mode` /
`delta_indices`, and writes the records file the recipe commits:

    python3 translation/scripts/collect-opus-run.py --run wf_… [--run wf_…] \\
        --sample /tmp/round-<SEED>.json --out translation/reviews/opus-<SEED>-<HANDLE>.json

Journals live under ~/.claude/projects/<project>/<session>/subagents/workflows/<run>/;
--journal-root overrides the search root.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path


def find_journal(run: str, root: Path) -> Path | None:
    hits = sorted(root.glob(f"**/subagents/workflows/{run}/journal.jsonl"))
    return hits[-1] if hits else None


def collect(journals: list[Path]) -> dict[tuple[str, str], dict]:
    recs: dict[tuple[str, str], dict] = {}
    for j in journals:
        for line in j.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "result":
                continue
            r = d.get("result") or d.get("value") or {}
            if isinstance(r, str):
                try:
                    r = json.loads(r)
                except json.JSONDecodeError:
                    continue
            if isinstance(r, dict) and r.get("locale") and r.get("file") and r.get("verdict"):
                recs[(r["locale"], r["file"])] = r
    return recs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, help="workflow run id (repeatable)")
    ap.add_argument("--sample", help="the sample .json the run was baked from (adds mode / delta_indices)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--journal-root", default=str(Path.home() / ".claude" / "projects"))
    a = ap.parse_args()
    journals = []
    for run in a.run:
        j = find_journal(run, Path(a.journal_root))
        if not j:
            print(f"no journal for {run} under {a.journal_root}", file=sys.stderr)
            return 1
        journals.append(j)
    recs = collect(journals)
    if a.sample:
        info = {f["rel"]: f for f in json.loads(Path(a.sample).read_text(encoding="utf-8"))["files"]}
        for r in recs.values():
            f = info.get(r["file"], {})
            r["mode"] = f.get("mode", "full")
            if r["mode"] == "delta":
                r["delta_indices"] = [d["index"] for d in f.get("delta_entries", [])]
    rows = sorted(recs.values(), key=lambda r: (r["locale"], r["file"]))
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tally = collections.Counter(r["verdict"] for r in rows)
    print(f"{len(rows)} records → {a.out}; {dict(tally)}")
    fails = [r["file"] for r in rows if r["verdict"] == "FAIL"]
    if fails:
        print("FAIL:", ", ".join(fails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
