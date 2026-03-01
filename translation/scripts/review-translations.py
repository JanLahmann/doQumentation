#!/usr/bin/env python3
"""
Orchestrate systematic review of all existing translations.

Manages three tiers of review:
  1. Structural validation (validate-translation.py --record)
  2. MDX lint (lint-translation.py --record)
  3. Linguistic review (manual, tracked via --record-review)

Usage:
    # Run automated checks (Tier 1 + 2) for all locales
    python translation/scripts/review-translations.py --auto-check

    # Show review progress dashboard
    python translation/scripts/review-translations.py --progress

    # Get next chunk of files needing linguistic review
    python translation/scripts/review-translations.py --next-chunk [--size 20]

    # Record linguistic review results
    python translation/scripts/review-translations.py --record-review --locale de --file guides/foo.mdx --verdict PASS
    python translation/scripts/review-translations.py --record-review --from-json results.json
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]

# Priority order for linguistic review
LOCALE_PRIORITY = [
    "de", "es", "fr", "ja", "uk", "it", "pt", "he", "tl",
    # AR skipped (needs re-translation)
    "ksh", "nds", "gsw", "sax", "bln", "aut", "swg", "bad", "bar",
]

SECTION_PRIORITY = [
    "tutorials/",
    "guides/",
    "learning/courses/",
    "learning/modules/",
]

SKIP_LOCALES = {"ar"}  # Known broken, needs full re-translation

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

VALID_VERDICTS = {"PASS", "MINOR_ISSUES", "FAIL", "SKIPPED"}

# ---------------------------------------------------------------------------
# Status I/O
# ---------------------------------------------------------------------------


def load_status() -> dict:
    """Load translation/status.json."""
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {}


def save_status(status: dict) -> None:
    """Write translation/status.json with sorted keys."""
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def count_genuine(locale: str) -> int:
    """Count genuine (non-fallback) translations for a locale."""
    locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"
    if not locale_dir.exists():
        return 0
    count = 0
    for p in locale_dir.rglob("*.mdx"):
        content = p.read_text(encoding="utf-8")
        if FALLBACK_MARKER not in content:
            count += 1
    return count


def get_file_line_count(locale: str, rel_path: str) -> int:
    """Get the line count of a translated file."""
    p = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel_path
    if p.exists():
        return len(p.read_text(encoding="utf-8").splitlines())
    return 0


def get_section(rel_path: str) -> str:
    """Get the section prefix for a file path."""
    for sec in SECTION_PRIORITY:
        if rel_path.startswith(sec):
            return sec
    return ""


# ---------------------------------------------------------------------------
# --auto-check: Run Tier 1 + Tier 2 automated checks
# ---------------------------------------------------------------------------


def auto_check(locales: list[str]) -> None:
    """Run validate-translation.py --record and lint-translation.py --record."""
    validate_script = SCRIPTS_DIR / "validate-translation.py"
    lint_script = SCRIPTS_DIR / "lint-translation.py"

    print("=" * 60)
    print("Phase 1: Structural validation (validate-translation.py)")
    print("=" * 60)

    for locale in locales:
        print(f"\n--- Validating {locale} ---")
        result = subprocess.run(
            [sys.executable, str(validate_script),
             "--locale", locale, "--record"],
            cwd=str(REPO_ROOT),
        )
        if result.returncode not in (0, 1):
            print(f"  WARNING: validate-translation.py exited with {result.returncode}")

    print("\n" + "=" * 60)
    print("Phase 2: MDX lint (lint-translation.py)")
    print("=" * 60)

    lint_args = [sys.executable, str(lint_script), "--all-locales", "--record"]
    if len(locales) == 1:
        lint_args = [sys.executable, str(lint_script),
                     "--locale", locales[0], "--record"]
    subprocess.run(lint_args, cwd=str(REPO_ROOT))

    # Mark AR files as review=SKIPPED
    status = load_status()
    today = date.today().isoformat()
    for locale in SKIP_LOCALES:
        if locale in status:
            for rel, entry in status[locale].items():
                if "review" not in entry:
                    entry["review"] = "SKIPPED"
                    entry["reviewed"] = today
                    entry["review_notes"] = "structural failures — needs re-translation"
    save_status(status)

    print("\n" + "=" * 60)
    print("Done. Run --progress to see results.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# --progress: Review progress dashboard
# ---------------------------------------------------------------------------


def show_progress(locale_filter: str | None = None) -> None:
    """Show review progress across all tiers."""
    status = load_status()

    locales = [locale_filter] if locale_filter else ALL_LOCALES

    # Header
    print(f"{'Locale':<6} {'Files':>5}  {'Struct':>12}  {'Lint':>12}  {'Review':>16}")
    print("-" * 60)

    grand_files = 0
    grand_val_pass = 0
    grand_lint_clean = 0
    grand_reviewed = 0
    grand_reviewable = 0

    for locale in locales:
        entries = status.get(locale, {})
        genuine = count_genuine(locale)
        n_tracked = len(entries)

        # Structural validation
        val_pass = sum(1 for e in entries.values() if e.get("validation") == "PASS")
        val_fail = sum(1 for e in entries.values() if e.get("validation") == "FAIL")
        val_none = n_tracked - val_pass - val_fail

        # Lint
        lint_clean = sum(1 for e in entries.values() if e.get("lint") == "CLEAN")
        lint_warn = sum(1 for e in entries.values() if e.get("lint") == "WARNINGS")
        lint_err = sum(1 for e in entries.values() if e.get("lint") == "ERRORS")

        # Review
        reviewed = sum(1 for e in entries.values() if e.get("review") is not None)
        reviewable = sum(
            1 for e in entries.values()
            if e.get("validation") == "PASS"
            and e.get("lint") in ("CLEAN", "WARNINGS")
            and e.get("review") is None
        )

        skip = " (skip)" if locale in SKIP_LOCALES else ""

        if genuine == 0 and n_tracked == 0:
            continue

        # Use genuine count if we haven't tracked all files yet
        file_count = max(genuine, n_tracked)

        val_str = f"{val_pass} PASS" if val_pass else "—"
        if val_fail:
            val_str += f" {val_fail} FAIL"
        if val_none and n_tracked < genuine:
            val_str = f"{val_pass}P/{val_fail}F/{genuine - n_tracked}?"

        lint_str = f"{lint_clean} CLEAN" if lint_clean else "—"
        if lint_err:
            lint_str += f" {lint_err} ERR"

        rev_str = f"{reviewed}/{val_pass} reviewed"
        if reviewable:
            rev_str += f" ({reviewable} todo)"

        print(f"{locale}{skip:<6} {file_count:>5}  {val_str:>12}  {lint_str:>12}  {rev_str:>16}")

        grand_files += file_count
        grand_val_pass += val_pass
        grand_lint_clean += lint_clean
        grand_reviewed += reviewed
        grand_reviewable += reviewable

    print("-" * 60)
    print(f"{'Total':<6} {grand_files:>5}  {grand_val_pass:>5} PASS    {grand_lint_clean:>5} CLEAN   {grand_reviewed}/{grand_val_pass} reviewed")
    if grand_reviewable:
        print(f"  → {grand_reviewable} files ready for linguistic review")

    # Show per-review-verdict breakdown if any reviews exist
    if grand_reviewed > 0:
        verdicts: dict[str, int] = {}
        for locale_entries in status.values():
            for entry in locale_entries.values():
                v = entry.get("review")
                if v:
                    verdicts[v] = verdicts.get(v, 0) + 1
        print(f"\n  Review verdicts: " + ", ".join(
            f"{v}={c}" for v, c in sorted(verdicts.items())
        ))


# ---------------------------------------------------------------------------
# --next-chunk: Get next batch for linguistic review
# ---------------------------------------------------------------------------


def next_chunk(size: int = 20, locale_filter: str | None = None) -> None:
    """Print the next chunk of files needing linguistic review."""
    status = load_status()

    candidates: list[tuple[str, str, int]] = []  # (locale, rel_path, line_count)

    locales = [locale_filter] if locale_filter else LOCALE_PRIORITY

    for locale in locales:
        if locale in SKIP_LOCALES and not locale_filter:
            continue

        entries = status.get(locale, {})

        for rel, entry in entries.items():
            # Only files that pass structural + lint
            if entry.get("validation") != "PASS":
                continue
            if entry.get("lint") not in ("CLEAN", "WARNINGS"):
                continue
            # Not already reviewed
            if entry.get("review") is not None:
                continue

            lines = get_file_line_count(locale, rel)
            candidates.append((locale, rel, lines))

    if not candidates:
        print("No files pending linguistic review.")
        if not locale_filter:
            # Check if there are unvalidated files
            total_genuine = sum(count_genuine(loc) for loc in ALL_LOCALES)
            total_tracked = sum(len(status.get(loc, {})) for loc in ALL_LOCALES)
            if total_tracked < total_genuine:
                print(f"  ({total_genuine - total_tracked} files not yet auto-checked — run --auto-check first)")
        return

    # Sort by: locale priority, then section priority, then line count (ascending)
    locale_order = {loc: i for i, loc in enumerate(LOCALE_PRIORITY)}

    def sort_key(item: tuple[str, str, int]) -> tuple[int, int, int]:
        locale, rel, lines = item
        loc_idx = locale_order.get(locale, 99)
        sec_idx = next(
            (i for i, sec in enumerate(SECTION_PRIORITY) if rel.startswith(sec)),
            99
        )
        return (loc_idx, sec_idx, lines)

    candidates.sort(key=sort_key)

    chunk = candidates[:size]

    print(f"Next {len(chunk)} files for linguistic review:\n")
    current_locale = None
    for i, (locale, rel, lines) in enumerate(chunk, 1):
        if locale != current_locale:
            if current_locale is not None:
                print()
            current_locale = locale
            print(f"  [{locale.upper()}]")
        print(f"  {i:3d}. {rel} ({lines} lines)")

    remaining = len(candidates) - len(chunk)
    if remaining > 0:
        print(f"\n  ... {remaining} more files pending after this chunk")

    # Print summary of what to do
    print(f"\n  Review each file for: register, word salad, verbosity, accuracy")
    print(f"  Record: --record-review --locale XX --file PATH --verdict PASS|MINOR_ISSUES|FAIL")


# ---------------------------------------------------------------------------
# --record-review: Record linguistic review results
# ---------------------------------------------------------------------------


def record_review(locale: str, file_path: str, verdict: str,
                  issues: int = 0, notes: str = "") -> None:
    """Record a single linguistic review result."""
    if verdict not in VALID_VERDICTS:
        print(f"Error: Invalid verdict '{verdict}'. Use: {', '.join(sorted(VALID_VERDICTS))}")
        sys.exit(2)

    status = load_status()
    if locale not in status:
        status[locale] = {}

    entry = status[locale].get(file_path, {})
    entry["reviewed"] = date.today().isoformat()
    entry["review"] = verdict
    entry["review_issues"] = issues
    if notes:
        entry["review_notes"] = notes
    elif "review_notes" in entry:
        del entry["review_notes"]

    if "status" not in entry:
        entry["status"] = "promoted"

    status[locale][file_path] = entry
    save_status(status)

    print(f"Recorded: {locale}/{file_path} → {verdict}")


def record_review_from_json(json_path: str) -> None:
    """Record multiple review results from a JSON file or stdin."""
    if json_path == "-":
        data = json.loads(sys.stdin.read())
    else:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    if not isinstance(data, list):
        print("Error: JSON must be an array of {locale, file, verdict, issues?, notes?}")
        sys.exit(2)

    status = load_status()
    today = date.today().isoformat()

    for item in data:
        locale = item["locale"]
        file_path = item["file"]
        verdict = item["verdict"]

        if verdict not in VALID_VERDICTS:
            print(f"  Error: Invalid verdict '{verdict}' for {locale}/{file_path}")
            continue

        if locale not in status:
            status[locale] = {}

        entry = status[locale].get(file_path, {})
        entry["reviewed"] = today
        entry["review"] = verdict
        entry["review_issues"] = item.get("issues", 0)
        if item.get("notes"):
            entry["review_notes"] = item["notes"]
        elif "review_notes" in entry:
            del entry["review_notes"]

        if "status" not in entry:
            entry["status"] = "promoted"

        status[locale][file_path] = entry
        print(f"  {locale}/{file_path} → {verdict}")

    save_status(status)
    print(f"\nRecorded {len(data)} review result(s)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate systematic review of all translations"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--auto-check", action="store_true",
        help="Run structural validation + MDX lint for all locales"
    )
    group.add_argument(
        "--progress", action="store_true",
        help="Show review progress dashboard"
    )
    group.add_argument(
        "--next-chunk", action="store_true",
        help="Get next batch of files for linguistic review"
    )
    group.add_argument(
        "--record-review", action="store_true",
        help="Record linguistic review result"
    )

    parser.add_argument("--locale", help="Filter to a single locale")
    parser.add_argument(
        "--size", type=int, default=20,
        help="Chunk size for --next-chunk (default: 20)"
    )
    parser.add_argument("--file", help="File path for --record-review")
    parser.add_argument(
        "--verdict",
        help="Review verdict: PASS, MINOR_ISSUES, FAIL, SKIPPED"
    )
    parser.add_argument("--issues", type=int, default=0, help="Issue count")
    parser.add_argument("--notes", default="", help="Review notes")
    parser.add_argument(
        "--from-json", metavar="PATH",
        help="Record reviews from JSON file (or - for stdin)"
    )

    args = parser.parse_args()

    if args.auto_check:
        locales = [args.locale] if args.locale else ALL_LOCALES
        auto_check(locales)

    elif args.progress:
        show_progress(args.locale)

    elif args.next_chunk:
        next_chunk(size=args.size, locale_filter=args.locale)

    elif args.record_review:
        if args.from_json:
            record_review_from_json(args.from_json)
        elif args.locale and args.file and args.verdict:
            record_review(args.locale, args.file, args.verdict,
                          args.issues, args.notes)
        else:
            parser.error(
                "--record-review requires (--locale + --file + --verdict) or --from-json"
            )


if __name__ == "__main__":
    main()
