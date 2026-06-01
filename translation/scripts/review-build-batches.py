#!/usr/bin/env python3
"""Build line-balanced Tier-3 review batches from pre-filter triage output.

Replaces the ad-hoc "15 files per agent" split (which left agent token use
swinging 90k-760k because a batch of short guides costs far less than a batch of
long tutorials). Bin-packs REVIEW files by line count so each agent's batch is
roughly equal work, attaches the pre-filter hint flags per file, and prints a
ready-to-use launch recipe that pins the review model to Haiku.

Usage:
  # 1. triage first
  python translation/scripts/review-prefilter.py --locale ms --unreviewed-only --json /tmp/ms_triage.json
  # 2. build a wave of 5 balanced batches (priority files first)
  python translation/scripts/review-build-batches.py --triage /tmp/ms_triage.json --agents 5 --max-lines 1800

Batches are written to /tmp/review/<locale>_<wave>_b<N>.json as
  [{"file": "<REL>", "hints": [...]}, ...]
ready for the rubric's agent to consume.
"""

import argparse
import json
from pathlib import Path

RUBRIC = "translation/review-tier3-rubric.md"


def greedy_balance(items: list[dict], n: int) -> list[list[dict]]:
    """Longest-processing-time bin-packing: even out total lines per bin."""
    bins: list[list[dict]] = [[] for _ in range(n)]
    loads = [0] * n
    for it in sorted(items, key=lambda x: x["tr_lines"], reverse=True):
        i = loads.index(min(loads))
        bins[i].append(it)
        loads[i] += max(it["tr_lines"], 1)
    return bins


def main() -> int:
    ap = argparse.ArgumentParser(description="Build line-balanced review batches")
    ap.add_argument("--triage", required=True, help="prefilter --json output")
    ap.add_argument("--agents", type=int, default=5)
    ap.add_argument("--max-lines", type=int, default=1800,
                    help="soft cap of total translated lines per batch (caps wave size)")
    ap.add_argument("--wave", default="w1")
    ap.add_argument("--include-sample", action="store_true",
                    help="also queue SAMPLE (stub) files; default reviews a sample only")
    ap.add_argument("--out-dir", default="/tmp/review")
    args = ap.parse_args()

    triage = json.loads(Path(args.triage).read_text(encoding="utf-8"))
    if not triage:
        print("Empty triage."); return 0
    locale = triage[0]["locale"]

    review = [r for r in triage if r["triage"] == "REVIEW"]
    sample = [r for r in triage if r["triage"] == "SAMPLE"]
    skipped = [r for r in triage if r["triage"].startswith("SKIP")]
    if args.include_sample:
        review += sample

    # Priority (structural-completeness) files first, then fill by line-balance
    # up to the wave's total-line budget.
    review.sort(key=lambda r: (not r["priority"], -r["tr_lines"]))
    budget = args.max_lines * args.agents
    wave, used = [], 0
    for r in review:
        if used and used + r["tr_lines"] > budget:
            break
        wave.append(r); used += r["tr_lines"]

    n_agents = max(1, min(args.agents, len(wave)))
    bins = [b for b in greedy_balance(wave, n_agents) if b]
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{locale}] triage: REVIEW={len(review)} (priority="
          f"{sum(1 for r in review if r['priority'])}), SAMPLE={len(sample)}, "
          f"SKIP={len(skipped)}")
    if skipped:
        from collections import Counter
        print("  skipped: " + ", ".join(f"{k}={v}" for k, v in
              Counter(r['triage'] for r in skipped).items()) +
              "  (fix lint/validation or re-stamp these before they're reviewable)")
    print(f"  this wave: {len(wave)} files / {used} lines across {n_agents} agents")

    paths = []
    for i, b in enumerate(bins, 1):
        p = out_dir / f"{locale}_{args.wave}_b{i}.json"
        p.write_text(json.dumps(
            [{"file": r["file"], "hints": r["flags"]} for r in b],
            ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(p)
        lines = sum(r["tr_lines"] for r in b)
        prio = sum(1 for r in b if r["priority"])
        print(f"  batch {i}: {len(b):2} files, {lines:5} lines, {prio} priority → {p}")

    print(f"\nLaunch recipe — {len(bins)} agents, MODEL=haiku, rubric={RUBRIC}:")
    for i, p in enumerate(paths, 1):
        out = str(p).replace(".json", "_verdicts.json")
        print(f"  agent {i} (model=haiku): review files in {p} using {RUBRIC} "
              f"({locale}); write verdicts to {out}; reply one-line tally.")
    print(f"\nAfter all agents return:\n"
          f"  cat {args.out_dir}/{locale}_{args.wave}_b*_verdicts.json | (merge to one array) \\\n"
          f"  | python translation/scripts/review-translations.py --record-review --from-json -")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
