#!/usr/bin/env python3
"""
One-shot backfill of `en_base_commit_date` in translation/status.json.

For every promoted entry that lacks `en_base_commit_date`, look up the
exact EN revision the translation was based on by matching the entry's
stored `source_hash` against the SHA-256 prefix of the EN file's content
at each historical commit. The matched commit's date becomes the EN
base date.

Per-EN-path history is walked once and cached, so the cost is
O(EN paths * commits per path), not O(status entries * commits).

Usage:
    python translation/scripts/backfill-en-base-date.py             # all locales
    python translation/scripts/backfill-en-base-date.py --dry-run   # report only
    python translation/scripts/backfill-en-base-date.py --locale de # one locale
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
DOCS_DIR = REPO_ROOT / "docs"


def git_log_history(git_path: str) -> list[Tuple[str, str]]:
    """Return [(sha, YYYY-MM-DD), ...] newest-first for commits touching path."""
    result = subprocess.run(
        ["git", "log", "--format=%H %cs", "--follow", "--", git_path],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    out = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, cdate = line.partition(" ")
        out.append((sha, cdate))
    return out


def blob_hash_at(sha: str, git_path: str) -> Optional[str]:
    """Return 8-char SHA-256 prefix of the file's content at the given commit."""
    blob = subprocess.run(
        ["git", "show", f"{sha}:{git_path}"],
        cwd=REPO_ROOT, capture_output=True, check=False,
    )
    if blob.returncode != 0:
        return None
    return hashlib.sha256(blob.stdout).hexdigest()[:8]


def build_hash_index(rel_path: str) -> Dict[str, str]:
    """Walk an EN file's git history and build {source_hash: commit_date}.

    Earliest commit wins when the same content reappears (the commit where
    the content first existed, not a later no-op revert).
    """
    git_path = f"docs/{rel_path}"
    history = git_log_history(git_path)
    if not history:
        return {}
    # Walk oldest → newest so first occurrence of a hash wins
    index: Dict[str, str] = {}
    for sha, cdate in reversed(history):
        h = blob_hash_at(sha, git_path)
        if h is None:
            continue
        index.setdefault(h, cdate)
    return index


def collect_targets(status: dict, locale_filter: Optional[str]) -> list[Tuple[str, str, str]]:
    """Return [(locale, rel_path, source_hash), ...] for entries needing backfill."""
    targets = []
    for locale, entries in status.items():
        if locale_filter and locale != locale_filter:
            continue
        for rel_path, entry in entries.items():
            if entry.get("status") != "promoted":
                continue
            if entry.get("en_base_commit_date"):
                continue
            sh = entry.get("source_hash")
            if not sh:
                continue
            targets.append((locale, rel_path, sh))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change; don't write status.json")
    parser.add_argument("--locale", help="Backfill only this locale")
    parser.add_argument("--fallback-to-promoted", action="store_true",
                        help="For entries whose source_hash is not found in "
                             "the EN file's git history, fall back to the "
                             "entry's `promoted` date and tag "
                             "`en_base_source=\"promoted-fallback\"` so the "
                             "footer can show '(approx.)'")
    args = parser.parse_args()

    if not STATUS_FILE.exists():
        print(f"❌ {STATUS_FILE} not found", file=sys.stderr)
        return 1

    status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    targets = collect_targets(status, args.locale)
    if not targets:
        print("Nothing to backfill — all promoted entries already have en_base_commit_date.")
        return 0

    paths_needed = sorted({rel_path for _, rel_path, _ in targets})
    print(f"📅 Backfill plan: {len(targets)} entries across {len(paths_needed)} EN paths"
          f"{f' (locale={args.locale})' if args.locale else ''}")

    # Build per-path hash → date index
    indexes: Dict[str, Dict[str, str]] = {}
    for i, rel_path in enumerate(paths_needed, 1):
        if i % 25 == 0 or i == len(paths_needed):
            print(f"  walking history: {i}/{len(paths_needed)} ({rel_path})")
        indexes[rel_path] = build_hash_index(rel_path)

    from collections import Counter
    matched = 0
    unmatched = 0
    no_history = 0
    fallback_filled = 0
    unmatched_by_section: Counter = Counter()
    no_history_by_section: Counter = Counter()
    unmatched_by_locale: Counter = Counter()
    no_history_paths: set = set()

    for locale, rel_path, source_hash in targets:
        section = rel_path.split("/", 1)[0]
        idx = indexes.get(rel_path, {})
        entry = status[locale][rel_path]
        if not idx:
            no_history += 1
            no_history_by_section[section] += 1
            no_history_paths.add(rel_path)
            if args.fallback_to_promoted and entry.get("promoted"):
                entry["en_base_commit_date"] = entry["promoted"]
                entry["en_base_source"] = "promoted-fallback"
                fallback_filled += 1
            continue
        cdate = idx.get(source_hash)
        if cdate is None:
            unmatched += 1
            unmatched_by_section[section] += 1
            unmatched_by_locale[locale] += 1
            if args.fallback_to_promoted and entry.get("promoted"):
                entry["en_base_commit_date"] = entry["promoted"]
                entry["en_base_source"] = "promoted-fallback"
                fallback_filled += 1
            continue
        entry["en_base_commit_date"] = cdate
        matched += 1

    print(f"\n✅ matched (will set en_base_commit_date): {matched}")
    print(f"⚠️  unmatched (source_hash not in EN history): {unmatched}")
    print(f"⚠️  no EN git history at all: {no_history}")
    if args.fallback_to_promoted:
        print(f"↩️  fallback-to-promoted filled: {fallback_filled}")
    if unmatched_by_section:
        print("\n  unmatched by section:")
        for k, v in unmatched_by_section.most_common():
            print(f"    {v:5}  {k}")
    if no_history_by_section:
        print("\n  no-history by section:")
        for k, v in no_history_by_section.most_common():
            print(f"    {v:5}  {k}")
    if unmatched_by_locale:
        print("\n  unmatched by locale (top 10):")
        for k, v in unmatched_by_locale.most_common(10):
            print(f"    {v:5}  {k}")
    if no_history_paths:
        print(f"\n  no-history EN paths ({len(no_history_paths)} unique):")
        for p in sorted(no_history_paths)[:8]:
            print(f"    - {p}")

    if args.dry_run:
        print("\n(dry-run — status.json not written)")
        return 0

    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\n✏️  wrote {STATUS_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
