#!/usr/bin/env python3
"""
Translation status dashboard.

Combines on-the-fly file scanning with persistent status.json data to show
a complete picture of translation progress across all locales.

Usage:
    python translation/scripts/translation-status.py                          # overview
    python translation/scripts/translation-status.py --locale de              # single locale
    python translation/scripts/translation-status.py --locale de --backlog    # prioritized backlog
    python translation/scripts/translation-status.py --validate               # run + record validation
    python translation/scripts/translation-status.py --markdown               # markdown table
    python translation/scripts/translation-status.py --json                   # JSON output
    python translation/scripts/translation-status.py --update-contributing    # update CONTRIBUTING table
    python translation/scripts/translation-status.py --all                    # include dialect locales
"""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"
DRAFTS_DIR = REPO_ROOT / "translation" / "drafts"
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
CONTRIBUTING_FILE = REPO_ROOT / "CONTRIBUTING-TRANSLATIONS.md"

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

MAIN_LOCALES = ["de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he"]
DIALECT_LOCALES = ["swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut"]
ALL_LOCALES = MAIN_LOCALES + DIALECT_LOCALES

LOCALE_NAMES = {
    "de": "German", "es": "Spanish", "uk": "Ukrainian", "ja": "Japanese",
    "fr": "French", "it": "Italian", "pt": "Portuguese", "tl": "Tagalog",
    "ar": "Arabic", "he": "Hebrew",
    "swg": "Swabian", "bad": "Badisch", "bar": "Bavarian", "ksh": "Kölsch",
    "nds": "Low German", "gsw": "Swiss German", "sax": "Saxon",
    "bln": "Berlinerisch", "aut": "Austrian",
}

# Sections in priority order for backlog
SECTIONS = [
    ("tutorials", "Tutorials", "tutorials"),
    ("guides", "Guides", "guides"),
    ("courses", "Courses", "learning/courses"),
    ("modules", "Modules", "learning/modules"),
]

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
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def compute_source_hash(content: str) -> str:
    """Return first 8 hex chars of SHA-256 of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------


def get_en_files() -> dict[str, list[str]]:
    """Get English source files grouped by section.

    Returns {section_key: [rel_paths]} where rel_paths are relative to docs/.
    """
    result = {"tutorials": [], "guides": [], "courses": [], "modules": [], "other": []}

    if not DOCS_DIR.exists():
        return result

    for mdx in sorted(DOCS_DIR.rglob("*.mdx")):
        rel = str(mdx.relative_to(DOCS_DIR))
        if rel.startswith("tutorials/"):
            result["tutorials"].append(rel)
        elif rel.startswith("guides/"):
            result["guides"].append(rel)
        elif rel.startswith("learning/courses/"):
            result["courses"].append(rel)
        elif rel.startswith("learning/modules/"):
            result["modules"].append(rel)
        else:
            result["other"].append(rel)

    return result


def get_locale_translations(locale: str) -> dict[str, list[str]]:
    """Get genuine (non-fallback) translations for a locale, grouped by section."""
    result = {"tutorials": [], "guides": [], "courses": [], "modules": [], "other": []}
    locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"

    if not locale_dir.exists():
        return result

    for mdx in sorted(locale_dir.rglob("*.mdx")):
        content = mdx.read_text(encoding="utf-8")
        if FALLBACK_MARKER in content:
            continue
        rel = str(mdx.relative_to(locale_dir))
        if rel.startswith("tutorials/"):
            result["tutorials"].append(rel)
        elif rel.startswith("guides/"):
            result["guides"].append(rel)
        elif rel.startswith("learning/courses/"):
            result["courses"].append(rel)
        elif rel.startswith("learning/modules/"):
            result["modules"].append(rel)
        else:
            result["other"].append(rel)

    return result


def get_locale_drafts(locale: str) -> dict[str, list[str]]:
    """Get draft files for a locale, grouped by section."""
    result = {"tutorials": [], "guides": [], "courses": [], "modules": [], "other": []}
    locale_dir = DRAFTS_DIR / locale

    if not locale_dir.exists():
        return result

    for mdx in sorted(locale_dir.rglob("*.mdx")):
        if mdx.name.startswith("_"):
            continue
        content = mdx.read_text(encoding="utf-8")
        if FALLBACK_MARKER in content:
            continue
        rel = str(mdx.relative_to(locale_dir))
        if rel.startswith("tutorials/"):
            result["tutorials"].append(rel)
        elif rel.startswith("guides/"):
            result["guides"].append(rel)
        elif rel.startswith("learning/courses/"):
            result["courses"].append(rel)
        elif rel.startswith("learning/modules/"):
            result["modules"].append(rel)
        else:
            result["other"].append(rel)

    return result


def get_validation_summary(locale: str, status: dict) -> tuple[int, int]:
    """Get PASS/FAIL counts from status.json for a locale.

    Returns (pass_count, fail_count) or (-1, -1) if no data.
    """
    locale_data = status.get(locale, {})
    if not locale_data:
        return -1, -1
    passed = sum(1 for e in locale_data.values()
                 if e.get("validation") == "PASS")
    failed = sum(1 for e in locale_data.values()
                 if e.get("validation") == "FAIL")
    return passed, failed


# ---------------------------------------------------------------------------
# Validation (optional, slow)
# ---------------------------------------------------------------------------


def run_validation_for_locale(locale: str, status: dict) -> tuple[int, int]:
    """Run structural validation on all genuine translations for a locale.

    Updates status dict in-place. Returns (pass_count, fail_count).
    """
    # Import validation functions
    import importlib.util
    script = Path(__file__).resolve().parent / "validate-translation.py"
    spec = importlib.util.spec_from_file_location("validate_translation", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pairs = mod.find_genuine_translations(locale)
    if not pairs:
        return 0, 0

    if locale not in status:
        status[locale] = {}

    today = date.today().isoformat()
    passed = 0
    failed = 0

    for en_path, tr_path in pairs:
        report = mod.validate_file(en_path, tr_path, locale)
        rel = report.rel_path

        entry = status[locale].get(rel, {})
        entry["validation"] = "PASS" if report.passed else "FAIL"
        entry["validated"] = today
        if report.passed:
            passed += 1
            entry.pop("failures", None)
        else:
            failed += 1
            entry["failures"] = [c.name for c in report.checks if not c.passed]

        # Set status if not already tracked
        if "status" not in entry:
            entry["status"] = "promoted"

        # Compute source hash
        en_content = en_path.read_text(encoding="utf-8")
        entry["source_hash"] = compute_source_hash(en_content)

        status[locale][rel] = entry

    return passed, failed


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_overview(en_files: dict, locales: list[str], status: dict,
                    validation_results: dict = None) -> str:
    """Format the overview table."""
    lines = []
    today = date.today().isoformat()
    lines.append(f"Translation Status — {today}")
    lines.append("")

    totals = {
        "tutorials": len(en_files["tutorials"]),
        "guides": len(en_files["guides"]),
        "courses": len(en_files["courses"]),
        "modules": len(en_files["modules"]),
    }
    total_all = sum(totals.values()) + len(en_files["other"])

    # Header
    has_val = validation_results is not None
    header = f"{'Locale':<8} {'Tutorials':>10} {'Guides':>10} {'Courses':>10} {'Modules':>10} {'Total':>10} {'Drafts':>6}"
    if has_val:
        header += f"  {'Validated':>12}"
    lines.append(header)
    lines.append("─" * len(header))

    for locale in locales:
        trans = get_locale_translations(locale)
        drafts = get_locale_drafts(locale)

        t_tut = len(trans["tutorials"])
        t_gui = len(trans["guides"])
        t_crs = len(trans["courses"])
        t_mod = len(trans["modules"])
        t_oth = len(trans["other"])
        t_total = t_tut + t_gui + t_crs + t_mod + t_oth

        d_total = sum(len(v) for v in drafts.values())

        def frac(n, d):
            return f"{n}/{d}"

        row = (f"{locale.upper():<8} "
               f"{frac(t_tut, totals['tutorials']):>10} "
               f"{frac(t_gui, totals['guides']):>10} "
               f"{frac(t_crs, totals['courses']):>10} "
               f"{frac(t_mod, totals['modules']):>10} "
               f"{frac(t_total, total_all):>10} "
               f"{d_total:>6}")

        if has_val:
            p, f_ = validation_results.get(locale, (-1, -1))
            if p >= 0:
                row += f"  {p:>4}✓ {f_}✗"
            else:
                row += f"  {'—':>12}"
        lines.append(row)

    lines.append("─" * len(header))

    if validation_results is None:
        lines.append("")
        lines.append('Validation column: run with --validate to populate (slow)')
    lines.append("")
    return "\n".join(lines)


def format_locale_detail(locale: str, en_files: dict, status: dict) -> str:
    """Format detailed view for a single locale."""
    lines = []
    name = LOCALE_NAMES.get(locale, locale)
    lines.append(f"Translation Status — {locale.upper()} ({name})")
    lines.append("")

    trans = get_locale_translations(locale)
    drafts = get_locale_drafts(locale)
    locale_status = status.get(locale, {})

    header = f"{'Section':<12} {'Translated':>12} {'Drafts':>6} {'PASS':>6} {'FAIL':>6} {'Remaining':>10}"
    lines.append(header)
    lines.append("─" * len(header))

    grand_trans = 0
    grand_drafts = 0
    grand_pass = 0
    grand_fail = 0
    grand_remaining = 0
    grand_total = 0

    section_keys = [("tutorials", "Tutorials"), ("guides", "Guides"),
                    ("courses", "Courses"), ("modules", "Modules"),
                    ("other", "Other")]

    for key, label in section_keys:
        en_count = len(en_files.get(key, []))
        if en_count == 0:
            continue

        t_count = len(trans.get(key, []))
        d_count = len(drafts.get(key, []))

        # Count PASS/FAIL from status.json for this section
        p_count = 0
        f_count = 0
        for rel in trans.get(key, []):
            entry = locale_status.get(rel, {})
            if entry.get("validation") == "PASS":
                p_count += 1
            elif entry.get("validation") == "FAIL":
                f_count += 1

        remaining = en_count - t_count - d_count

        p_str = str(p_count) if (p_count or f_count) else "—"
        f_str = str(f_count) if (p_count or f_count) else "—"
        frac = f"{t_count}/{en_count}"

        row = (f"{label:<12} "
               f"{frac:>12} "
               f"{d_count:>6} "
               f"{p_str:>6} "
               f"{f_str:>6} "
               f"{remaining:>10}")
        lines.append(row)

        grand_trans += t_count
        grand_drafts += d_count
        grand_pass += p_count
        grand_fail += f_count
        grand_remaining += remaining
        grand_total += en_count

    lines.append("─" * len(header))

    gp_str = str(grand_pass) if (grand_pass or grand_fail) else "—"
    gf_str = str(grand_fail) if (grand_pass or grand_fail) else "—"
    grand_frac = f"{grand_trans}/{grand_total}"
    lines.append(f"{'Total':<12} "
                 f"{grand_frac:>12} "
                 f"{grand_drafts:>6} "
                 f"{gp_str:>6} "
                 f"{gf_str:>6} "
                 f"{grand_remaining:>10}")

    # Pipeline history from status.json
    if locale_status:
        lines.append("")
        lines.append("Pipeline history (from status.json):")
        for rel in sorted(locale_status.keys()):
            entry = locale_status[rel]
            s = entry.get("status", "?")
            v = entry.get("validation", "?")
            d = entry.get("promoted") or entry.get("validated") or "?"
            lines.append(f"  {rel:<50} {s:<12} {v:<6} {d}")

    lines.append("")
    return "\n".join(lines)


def format_backlog(locale: str, en_files: dict) -> str:
    """Format prioritized backlog for a locale."""
    trans = get_locale_translations(locale)
    drafts = get_locale_drafts(locale)

    lines = []
    name = LOCALE_NAMES.get(locale, locale)

    total_remaining = 0

    # Priority order: Guides → Courses → Modules → Tutorials
    priority = [
        ("guides", "Guides"),
        ("courses", "Courses"),
        ("modules", "Modules"),
        ("tutorials", "Tutorials"),
    ]

    sections_output = []
    for key, label in priority:
        en_set = set(en_files.get(key, []))
        tr_set = set(trans.get(key, []))
        dr_set = set(drafts.get(key, []))
        remaining = sorted(en_set - tr_set - dr_set)
        total_remaining += len(remaining)

        if remaining:
            section_lines = [f"{label} ({len(remaining)} remaining):"]
            for rel in remaining:
                section_lines.append(f"  {rel}")
            sections_output.append("\n".join(section_lines))

    lines.append(f"Backlog for {locale.upper()} ({name}) — {total_remaining} untranslated pages")
    lines.append("Priority: Guides → Courses → Modules → Tutorials")
    lines.append("")

    if sections_output:
        lines.append("\n\n".join(sections_output))
    else:
        lines.append("All pages translated!")

    lines.append("")
    return "\n".join(lines)


def format_markdown(en_files: dict, locales: list[str]) -> str:
    """Format markdown table for CONTRIBUTING-TRANSLATIONS.md."""
    lines = []

    totals = {
        "tutorials": len(en_files["tutorials"]),
        "guides": len(en_files["guides"]),
        "courses": len(en_files["courses"]),
        "modules": len(en_files["modules"]),
    }
    total_all = sum(totals.values()) + len(en_files["other"])

    lines.append("| Locale | Code | Tutorials | Guides | Courses | Modules | Total |")
    lines.append("|--------|------|-----------|--------|---------|---------|-------|")

    for locale in locales:
        trans = get_locale_translations(locale)
        t_tut = len(trans["tutorials"])
        t_gui = len(trans["guides"])
        t_crs = len(trans["courses"])
        t_mod = len(trans["modules"])
        t_oth = len(trans["other"])
        t_total = t_tut + t_gui + t_crs + t_mod + t_oth

        name = LOCALE_NAMES.get(locale, locale)
        lines.append(
            f"| {name} | `{locale}` "
            f"| {t_tut}/{totals['tutorials']} "
            f"| {t_gui}/{totals['guides']} "
            f"| {t_crs}/{totals['courses']} "
            f"| {t_mod}/{totals['modules']} "
            f"| {t_total}/{total_all} |"
        )

    return "\n".join(lines)


def format_json_output(en_files: dict, locales: list[str],
                       status: dict) -> str:
    """Format JSON output."""
    totals = {
        "tutorials": len(en_files["tutorials"]),
        "guides": len(en_files["guides"]),
        "courses": len(en_files["courses"]),
        "modules": len(en_files["modules"]),
        "other": len(en_files["other"]),
    }
    total_all = sum(totals.values())

    data = {
        "date": date.today().isoformat(),
        "totals": {**totals, "all": total_all},
        "locales": {},
    }

    for locale in locales:
        trans = get_locale_translations(locale)
        drafts = get_locale_drafts(locale)
        locale_status = status.get(locale, {})

        translated = {}
        draft_counts = {}
        for key in ["tutorials", "guides", "courses", "modules", "other"]:
            translated[key] = len(trans.get(key, []))
            draft_counts[key] = len(drafts.get(key, []))

        translated["all"] = sum(translated.values())
        draft_counts["all"] = sum(draft_counts.values())

        # Validation from status.json
        p = sum(1 for e in locale_status.values()
                if e.get("validation") == "PASS")
        f_ = sum(1 for e in locale_status.values()
                 if e.get("validation") == "FAIL")

        data["locales"][locale] = {
            "name": LOCALE_NAMES.get(locale, locale),
            "translated": translated,
            "drafts": draft_counts,
            "validation": {"pass": p, "fail": f_} if locale_status else None,
            "status_entries": len(locale_status),
        }

    return json.dumps(data, indent=2, ensure_ascii=False)


def update_contributing(en_files: dict, locales: list[str]) -> bool:
    """Update the status table in CONTRIBUTING-TRANSLATIONS.md.

    Returns True if file was updated, False if markers not found.
    """
    START_MARKER = "<!-- translation-status-start -->"
    END_MARKER = "<!-- translation-status-end -->"

    content = CONTRIBUTING_FILE.read_text(encoding="utf-8")
    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        return False

    table = format_markdown(en_files, locales)
    new_content = (
        content[:start_idx + len(START_MARKER)]
        + "\n"
        + table
        + "\n"
        + content[end_idx:]
    )

    CONTRIBUTING_FILE.write_text(new_content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Translation status dashboard")
    parser.add_argument("--locale",
                        help="Show detail for a single locale")
    parser.add_argument("--all", action="store_true",
                        help="Include dialect locales (KSH, NDS, etc.)")
    parser.add_argument("--backlog", action="store_true",
                        help="Show prioritized untranslated files (requires --locale)")
    parser.add_argument("--validate", action="store_true",
                        help="Run structural validation and record results (slow)")
    parser.add_argument("--markdown", action="store_true",
                        help="Output markdown table")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON")
    parser.add_argument("--update-contributing", action="store_true",
                        help="Update the table in CONTRIBUTING-TRANSLATIONS.md")
    args = parser.parse_args()

    # Check docs/ exists
    if not DOCS_DIR.exists():
        print("Error: docs/ directory not found. Run: python scripts/sync-content.py",
              file=sys.stderr)
        sys.exit(1)

    en_files = get_en_files()
    status = load_status()

    # Determine locale list
    if args.locale:
        if args.locale not in ALL_LOCALES:
            print(f"Error: Unknown locale '{args.locale}'. "
                  f"Available: {', '.join(ALL_LOCALES)}", file=sys.stderr)
            sys.exit(2)
        locales = [args.locale]
    elif args.all:
        locales = ALL_LOCALES
    else:
        locales = MAIN_LOCALES

    # Run validation if requested
    validation_results = None
    if args.validate:
        validation_results = {}
        for locale in locales:
            print(f"Validating {locale.upper()}...", file=sys.stderr)
            p, f_ = run_validation_for_locale(locale, status)
            validation_results[locale] = (p, f_)
        save_status(status)
        print("", file=sys.stderr)

    # Output
    if args.json:
        print(format_json_output(en_files, locales, status))
    elif args.markdown:
        print(format_markdown(en_files, locales))
    elif args.update_contributing:
        # Always use main locales for CONTRIBUTING table
        if update_contributing(en_files, MAIN_LOCALES):
            print(f"Updated {CONTRIBUTING_FILE}")
        else:
            print("Error: Marker comments not found in CONTRIBUTING-TRANSLATIONS.md")
            print("Add <!-- translation-status-start --> and <!-- translation-status-end -->")
            sys.exit(1)
    elif args.backlog:
        if not args.locale:
            print("Error: --backlog requires --locale", file=sys.stderr)
            sys.exit(2)
        print(format_backlog(args.locale, en_files))
    elif args.locale:
        print(format_locale_detail(args.locale, en_files, status))
    else:
        # Check if status.json has validation data (even without --validate)
        if not args.validate:
            # Show cached validation from status.json
            validation_results = {}
            for locale in locales:
                p, f_ = get_validation_summary(locale, status)
                if p >= 0:
                    validation_results[locale] = (p, f_)
            if not validation_results:
                validation_results = None
        print(format_overview(en_files, locales, status, validation_results))


if __name__ == "__main__":
    main()
