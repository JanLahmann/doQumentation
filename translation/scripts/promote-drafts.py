#!/usr/bin/env python3
"""
Promote validated translation drafts to the live i18n directory.

For each draft file in scope:
1. Runs structural validation against the English source
2. PASS → copies to i18n/{locale}/docusaurus-plugin-content-docs/current/{path}
3. FAIL → skips (draft stays for fixing)
4. Updates translation/status.json with results

Usage:
    python translation/scripts/promote-drafts.py --locale de                    # all drafts
    python translation/scripts/promote-drafts.py --locale de --section guides   # only guides
    python translation/scripts/promote-drafts.py --locale de --file guides/bit-ordering.mdx
    python translation/scripts/promote-drafts.py --locale de --force            # skip validation
    python translation/scripts/promote-drafts.py --locale de --keep             # don't delete drafts
"""

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

# Import validation functions from sibling script (hyphenated filename)
import importlib
_script_dir = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "validate_translation", _script_dir / "validate-translation.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DOCS_DIR = _mod.DOCS_DIR
FALLBACK_MARKER = _mod.FALLBACK_MARKER
I18N_DIR = _mod.I18N_DIR
REPO_ROOT = _mod.REPO_ROOT
validate_file = _mod.validate_file

DRAFTS_DIR = REPO_ROOT / "translation" / "drafts"
STATUS_FILE = REPO_ROOT / "translation" / "status.json"

ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "th", "ar", "he",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]


def load_status() -> dict:
    """Load translation/status.json, creating empty dict if missing."""
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding='utf-8'))
    return {}


def save_status(status: dict) -> None:
    """Write translation/status.json with sorted keys."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + '\n',
        encoding='utf-8')


def find_drafts(locale: str, section: str = None,
                single_file: str = None) -> list[Path]:
    """Find draft files for a locale, optionally filtered by section or file."""
    locale_dir = DRAFTS_DIR / locale
    if not locale_dir.exists():
        return []

    if single_file:
        draft = locale_dir / single_file
        return [draft] if draft.exists() else []

    search_dir = locale_dir / section if section else locale_dir
    if not search_dir.exists():
        return []

    drafts = []
    for path in sorted(search_dir.rglob("*.mdx")):
        # Skip feedback reports and other non-translation files
        if path.name.startswith('_'):
            continue
        # Skip fallback files
        content = path.read_text(encoding='utf-8')
        if FALLBACK_MARKER in content:
            continue
        drafts.append(path)

    return drafts


def promote_file(draft_path: Path, locale: str, force: bool = False,
                 keep: bool = False) -> dict:
    """Promote a single draft file.

    Returns dict with result info:
        {rel_path, action, validation, failures}
    """
    locale_dir = DRAFTS_DIR / locale
    rel_path = str(draft_path.relative_to(locale_dir))
    en_path = DOCS_DIR / rel_path
    i18n_target = (I18N_DIR / locale / "docusaurus-plugin-content-docs" /
                   "current" / rel_path)

    result = {"rel_path": rel_path, "action": None,
              "validation": None, "failures": []}

    # Check EN source exists
    if not en_path.exists():
        result["action"] = "skipped"
        result["failures"] = [f"English source not found: {rel_path}"]
        return result

    # Validate unless --force
    if not force:
        report = validate_file(en_path, draft_path, locale, locale_dir)
        result["validation"] = "PASS" if report.passed else "FAIL"
        if not report.passed:
            result["action"] = "skipped"
            result["failures"] = [
                c.name for c in report.checks if not c.passed
            ]
            return result

    # Promote: copy draft → i18n target
    i18n_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(draft_path, i18n_target)
    result["action"] = "promoted"
    result["validation"] = result["validation"] or "skipped"

    # Delete draft unless --keep
    if not keep:
        draft_path.unlink()
        # Clean up empty parent directories
        parent = draft_path.parent
        while parent != locale_dir:
            if not any(parent.iterdir()):
                parent.rmdir()
            else:
                break
            parent = parent.parent

    return result


def update_status(status: dict, locale: str, results: list[dict]) -> None:
    """Update status.json with promote results."""
    if locale not in status:
        status[locale] = {}

    today = date.today().isoformat()

    for r in results:
        entry = status[locale].get(r["rel_path"], {})

        if r["action"] == "promoted":
            entry["status"] = "promoted"
            entry["validation"] = r["validation"]
            entry["promoted"] = today
            entry.pop("failures", None)
        elif r["action"] == "skipped":
            entry["status"] = "needs-fix"
            entry["validation"] = r["validation"] or "FAIL"
            entry["failures"] = r["failures"]
            entry["validated"] = today

        # Preserve existing fields (contributor, drafted)
        status[locale][r["rel_path"]] = entry


def main():
    parser = argparse.ArgumentParser(
        description="Promote validated translation drafts to i18n/")
    parser.add_argument("--locale", required=True,
                        help=f"Locale ({', '.join(ALL_LOCALES)})")
    parser.add_argument("--section",
                        help="Filter to section: guides, tutorials, "
                             "learning/courses, learning/modules")
    parser.add_argument("--file",
                        help="Single file (relative to drafts/{locale}/)")
    parser.add_argument("--force", action="store_true",
                        help="Promote regardless of validation result")
    parser.add_argument("--keep", action="store_true",
                        help="Keep draft files after promoting")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show per-file details")
    args = parser.parse_args()

    if args.locale not in ALL_LOCALES:
        print(f"Error: Unknown locale '{args.locale}'. "
              f"Available: {', '.join(ALL_LOCALES)}")
        sys.exit(2)

    drafts = find_drafts(args.locale, args.section, args.file)

    if not drafts:
        scope = ""
        if args.section:
            scope = f" in {args.section}"
        if args.file:
            scope = f" for {args.file}"
        print(f"No drafts found for locale '{args.locale}'{scope}")
        sys.exit(0)

    print(f"Processing {len(drafts)} draft(s) for {args.locale}...")
    if args.force:
        print("  --force: skipping validation")

    results = []
    promoted = 0
    skipped = 0

    for draft_path in drafts:
        result = promote_file(draft_path, args.locale,
                              force=args.force, keep=args.keep)
        results.append(result)

        if result["action"] == "promoted":
            promoted += 1
            if args.verbose:
                print(f"  PROMOTED: {result['rel_path']}")
        elif result["action"] == "skipped":
            skipped += 1
            if args.verbose:
                print(f"  SKIPPED:  {result['rel_path']} "
                      f"({', '.join(result['failures'])})")

    # Update status.json
    status = load_status()
    update_status(status, args.locale, results)
    save_status(status)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Promoted: {promoted}, Skipped: {skipped} (FAIL)")
    if args.keep:
        print("  --keep: draft files preserved")

    if skipped:
        print(f"\nFailed files:")
        for r in results:
            if r["action"] == "skipped":
                print(f"  {r['rel_path']}: {', '.join(r['failures'])}")

    sys.exit(1 if skipped and not promoted else 0)


if __name__ == "__main__":
    main()
