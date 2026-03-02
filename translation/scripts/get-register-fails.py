#!/usr/bin/env python3
"""
List all translation files that failed linguistic review due to register issues.

Reads translation/status.json and outputs files with review="FAIL" grouped by locale,
with line counts for planning chunked register-fix sessions.

Usage:
    python translation/scripts/get-register-fails.py [--locale XX] [--json]
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
I18N_DIR = REPO_ROOT / "i18n"

# Priority order matching review-translations.py
LOCALE_PRIORITY = [
    "de", "fr", "es", "uk", "it",
    "swg", "bad", "sax", "aut",
    # NDS and TL have 1 FAIL each but not register issues
]

# Files that failed for non-register reasons — skip these
SKIP_FILES = {
    ("nds", "tutorials/pauli-correlation-experiment-on-a-quantum-computer.mdx"),
    ("tl", "tutorials/grovers-algorithm.mdx"),
}


def get_line_count(locale: str, rel_path: str) -> int:
    """Get line count of a translated file."""
    p = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel_path
    if p.exists():
        return len(p.read_text(encoding="utf-8").splitlines())
    return 0


def main():
    parser = argparse.ArgumentParser(description="List register-FAIL translation files")
    parser.add_argument("--locale", help="Filter to a single locale")
    parser.add_argument("--json", action="store_true", help="Output as JSON array")
    args = parser.parse_args()

    status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))

    locales = [args.locale] if args.locale else LOCALE_PRIORITY
    results = []

    for locale in locales:
        entries = status.get(locale, {})
        fails = []
        for rel_path, entry in sorted(entries.items()):
            if entry.get("review") != "FAIL":
                continue
            if (locale, rel_path) in SKIP_FILES:
                continue
            lines = get_line_count(locale, rel_path)
            fails.append((rel_path, lines))

        if not fails:
            continue

        if args.json:
            for rel_path, lines in fails:
                results.append({
                    "locale": locale,
                    "file": rel_path,
                    "lines": lines,
                })
        else:
            total_lines = sum(lines for _, lines in fails)
            print(f"\n[{locale.upper()}] {len(fails)} files ({total_lines} total lines)")
            for rel_path, lines in fails:
                print(f"  {rel_path} ({lines} lines)")

    if args.json:
        print(json.dumps(results, indent=2))
    elif not results and not args.json:
        grand = sum(
            1 for loc in locales
            for entry in status.get(loc, {}).values()
            if entry.get("review") == "FAIL"
            and (loc, next(
                (k for k, v in status.get(loc, {}).items() if v is entry), ""
            )) not in SKIP_FILES
        )
        if grand == 0:
            total = sum(
                1 for loc_entries in status.values()
                for entry in loc_entries.values()
                if entry.get("review") == "FAIL"
            )
            skip_count = len(SKIP_FILES)
            print(f"\nTotal: {total - skip_count} register-FAIL files (+ {skip_count} skipped non-register)")


if __name__ == "__main__":
    main()
