#!/usr/bin/env python3
"""Snapshot every EN MDX file's prose units to translation/en-passage-hashes.json.

This is the *current* EN state. Pair it with the per-translation baseline
recorded in translation/status.json (key `en_hashes_at_translation`) to
detect EN drift since each translation was made.

Usage:
    python translation/scripts/update-en-passage-hashes.py
        # Rewrites translation/en-passage-hashes.json from docs/ MDX state

    python translation/scripts/update-en-passage-hashes.py --diff
        # Shows units that have changed vs the on-disk manifest. Useful in
        # CI / pre-commit to surface drift introduced by a docs sync.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import passage_units

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
MANIFEST_FILE = REPO_ROOT / "translation" / "en-passage-hashes.json"


def build_manifest() -> dict[str, dict]:
    """Walk docs/ and produce {rel_path: {hash: preview}}."""
    out: dict[str, dict] = {}
    for path in sorted(DOCS_DIR.rglob("*.mdx")):
        rel = str(path.relative_to(DOCS_DIR))
        content = path.read_text(encoding="utf-8")
        hashes = passage_units.hash_units(content, mode="lenient")
        if hashes:
            out[rel] = hashes
    return out


def load_existing_manifest() -> dict[str, dict]:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def diff(old: dict, new: dict) -> int:
    """Print per-file content-addressed diffs. Return total drift events.

    With content-addressed hashes the diff is a set difference:
      added   = hashes in new but not in old
      removed = hashes in old but not in new
    A modified paragraph shows up as one removed + one added.
    """
    drift_count = 0
    all_paths = sorted(set(old) | set(new))
    for rel in all_paths:
        old_units = old.get(rel, {})
        new_units = new.get(rel, {})
        if old_units == new_units:
            continue
        added = [(h, p) for h, p in new_units.items() if h not in old_units]
        removed = [(h, p) for h, p in old_units.items() if h not in new_units]
        if not (added or removed):
            continue
        drift_count += len(added) + len(removed)
        print(f"\n{rel}")
        for h, preview in removed:
            print(f"  - {h}: {preview[:100]}")
        for h, preview in added:
            print(f"  + {h}: {preview[:100]}")
    return drift_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot EN MDX prose units to translation/en-passage-hashes.json"
    )
    parser.add_argument(
        "--diff", action="store_true",
        help="Show unit-level diff vs the on-disk manifest (does not write)"
    )
    args = parser.parse_args()

    new = build_manifest()

    if args.diff:
        old = load_existing_manifest()
        events = diff(old, new)
        print(f"\nTotal drift events: {events}")
        print(f"Files in manifest: {len(new)}")
        return 1 if events else 0

    total_units = sum(len(u) for u in new.values())
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(
        json.dumps(new, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {MANIFEST_FILE.relative_to(REPO_ROOT)}")
    print(f"  Files: {len(new)}")
    print(f"  Total units: {total_units}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
