#!/usr/bin/env python3
"""Baseline every promoted translation against the EN at its last-touch commit.

For each (locale, path) in translation/status.json with status="promoted":
  1. Find the git commit that most recently modified i18n/<locale>/<path>.
  2. Read docs/<path> at that commit (the EN the translator/last editor saw).
  3. Hash the EN's lenient-mode prose units.
  4. Record those hashes as `en_hashes_at_translation` in status.json.

After running this, --check-drift can compare current EN against each
translation's baseline to flag stale content.

Usage:
    # Bootstrap every promoted translation that doesn't already have a baseline
    python translation/scripts/bootstrap-passage-hashes.py

    # Force re-bootstrap (overwrite existing baselines)
    python translation/scripts/bootstrap-passage-hashes.py --force

    # Only one locale
    python translation/scripts/bootstrap-passage-hashes.py --locale ko

    # Dry-run: show what would change without writing
    python translation/scripts/bootstrap-passage-hashes.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import passage_units

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
BASELINE_FILE = REPO_ROOT / "translation" / "baseline-hashes.json"

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"


def git_last_touch_commit(tr_rel_path: Path) -> str | None:
    """Return the SHA of the commit that most recently modified tr_rel_path.

    Uses --follow so renames are traced. Returns None if the file has no
    history (e.g. untracked).
    """
    full = REPO_ROOT / tr_rel_path
    try:
        out = subprocess.run(
            ["git", "log", "--follow", "-1", "--format=%H", "--", str(tr_rel_path)],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return None
    sha = out.stdout.strip()
    return sha or None


def git_show_blob(sha: str, rel_path: str) -> str | None:
    """Return the file content at the given commit, or None if it didn't exist."""
    try:
        out = subprocess.run(
            ["git", "show", f"{sha}:{rel_path}"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout
    except subprocess.CalledProcessError:
        return None


def load_status() -> dict:
    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))


def save_status(status: dict) -> None:
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_baselines() -> dict:
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return {}


def save_baselines(baselines: dict) -> None:
    BASELINE_FILE.write_text(
        json.dumps(baselines, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bootstrap_entry(
    locale: str, rel_path: str, entry: dict, baselines: dict,
    *, force: bool = False, verbose: bool = False
) -> tuple[bool, str]:
    """Bootstrap a single entry. Returns (changed, reason).

    Writes the baseline hash list into `baselines` (which is the
    translation/baseline-hashes.json sidecar) so status.json stays small.
    The status entry only flags `has_baseline=True`.
    """
    sidecar_key = f"{locale}/{rel_path}"

    if not force and sidecar_key in baselines:
        return False, "already baselined"

    if entry.get("status") != "promoted":
        return False, f"status={entry.get('status')!r}, skipping"

    tr_disk = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel_path
    if not tr_disk.exists():
        return False, "translation file missing on disk"

    # Skip fallback files — they're not real translations
    try:
        if FALLBACK_MARKER in tr_disk.read_text(encoding="utf-8"):
            return False, "fallback marker present"
    except UnicodeDecodeError:
        return False, "non-UTF-8 content"

    tr_repo_rel = Path("i18n") / locale / "docusaurus-plugin-content-docs" / "current" / rel_path
    sha = git_last_touch_commit(tr_repo_rel)
    if not sha:
        return False, "no git history for translation"

    en_repo_rel = f"docs/{rel_path}"
    en_content = git_show_blob(sha, en_repo_rel)
    if en_content is None:
        en_disk = DOCS_DIR / rel_path
        if not en_disk.exists():
            return False, "EN file not found at commit or on disk"
        en_content = en_disk.read_text(encoding="utf-8")
        baseline_source = "current EN (no historical match)"
    else:
        baseline_source = f"EN at {sha[:8]}"

    en_hashes = passage_units.hash_units(en_content, mode="lenient")
    if not en_hashes:
        return False, "no extractable units in EN"

    baselines[sidecar_key] = {
        "commit": sha,
        "hashes": sorted(en_hashes.keys()),
    }
    if verbose:
        print(f"  {locale}/{rel_path}: {len(en_hashes)} units baselined from {baseline_source}")
    return True, f"baselined ({len(en_hashes)} units)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baseline every promoted translation against its historical EN snapshot"
    )
    parser.add_argument("--locale", help="Only process this locale")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-baseline entries that already have en_hashes_at_translation"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would change without writing status.json"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print per-file progress"
    )
    args = parser.parse_args()

    status = load_status()
    baselines = load_baselines()

    locales = [args.locale] if args.locale else sorted(status.keys())

    total_done = 0
    total_skipped = 0
    skip_reasons: dict[str, int] = {}

    for locale in locales:
        if locale not in status:
            continue
        entries = status[locale]
        if not isinstance(entries, dict):
            continue
        n_done = 0
        n_skip = 0
        for rel_path in sorted(entries.keys()):
            entry = entries[rel_path]
            if not isinstance(entry, dict):
                continue
            changed, reason = bootstrap_entry(
                locale, rel_path, entry, baselines,
                force=args.force, verbose=args.verbose,
            )
            if changed:
                n_done += 1
                total_done += 1
            else:
                n_skip += 1
                total_skipped += 1
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        print(f"{locale}: {n_done} baselined, {n_skip} skipped ({len(entries)} total)")

    print(f"\nTotal: {total_done} baselined, {total_skipped} skipped")
    if skip_reasons:
        print("Skip reasons:")
        for reason, count in sorted(skip_reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {count:5d}  {reason}")

    if args.dry_run:
        print("\n(dry-run: baseline-hashes.json not written)")
        return 0

    if total_done > 0:
        save_baselines(baselines)
        print(f"\nWrote translation/baseline-hashes.json ({len(baselines)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
