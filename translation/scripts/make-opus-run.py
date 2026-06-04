#!/usr/bin/env python3
"""
Bake a deep-review sample into a runnable copy of the opus-deep-review workflow.

The Workflow runner does not reliably pass a large `args` payload through when a
workflow is invoked by scriptPath. Rather than fight that, this helper embeds
the sample directly into a standalone copy of the workflow as a `SAMPLE`
constant, which the workflow reads as a fallback when `args` is empty.

Usage:
    python3 translation/scripts/sample-deep-review.py --per-locale 3 --seed S --out /tmp/opus-sample.json
    python3 translation/scripts/make-opus-run.py --sample /tmp/opus-sample.json --out /tmp/opus-run.js
    # then:  Workflow({ scriptPath: "/tmp/opus-run.js" })
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO_ROOT / ".claude" / "workflows" / "opus-deep-review.js"
NEEDLE = "const SAMPLE = null"


def main():
    ap = argparse.ArgumentParser(description="Bake a sample into a runnable opus-deep-review copy")
    ap.add_argument("--sample", required=True, help="sample JSON from sample-deep-review.py")
    ap.add_argument("--out", required=True, help="output runnable .js path")
    args = ap.parse_args()

    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    template = TEMPLATE.read_text(encoding="utf-8")
    if NEEDLE not in template:
        raise SystemExit(f"template marker not found: {NEEDLE!r} in {TEMPLATE}")

    # JSON is valid JS object-literal syntax; embed it directly.
    embedded = "const SAMPLE = " + json.dumps(sample, ensure_ascii=False)
    out = template.replace(NEEDLE, embedded, 1)
    Path(args.out).write_text(out, encoding="utf-8")
    print(f"Wrote runnable workflow → {args.out}")
    print(f"  baked {sample.get('sample_size', len(sample.get('files', [])))} files, "
          f"seed={sample.get('seed')}")
    print(f"  run:  Workflow({{ scriptPath: \"{args.out}\" }})")


if __name__ == "__main__":
    main()
