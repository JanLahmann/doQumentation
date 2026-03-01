#!/usr/bin/env python3
"""
Lint translated MDX files for build-breaking syntax errors.

Catches MDX compilation issues that validate-translation.py (structural checks)
does not detect. These patterns cause `docusaurus build` failures.

Usage:
    # Lint all genuine translations for one locale
    python translation/scripts/lint-translation.py --locale ksh

    # Lint all locales
    python translation/scripts/lint-translation.py --all-locales

    # Lint a single file (with EN source for import check)
    python translation/scripts/lint-translation.py --file <translated.mdx> --en-file <source.mdx>
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]

STATUS_FILE = REPO_ROOT / "translation" / "status.json"
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

ERROR = "ERROR"
WARN = "WARN"


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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_genuine_translations(locale: str) -> list[tuple[Path, Path]]:
    """Find all genuine (non-fallback) translations for a locale.
    Returns [(en_path, tr_path)] pairs.
    """
    locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"
    if not locale_dir.exists():
        return []

    pairs = []
    for tr_path in sorted(locale_dir.rglob("*.mdx")):
        content = tr_path.read_text(encoding="utf-8")
        if FALLBACK_MARKER in content:
            continue
        rel = tr_path.relative_to(locale_dir)
        en_path = DOCS_DIR / rel
        if en_path.exists():
            pairs.append((en_path, tr_path))
    return pairs


def is_inside_code_block(lines: list[str], line_idx: int) -> bool:
    """Check if a line is inside a fenced code block."""
    fence_count = 0
    for i in range(line_idx):
        if lines[i].strip().startswith("```"):
            fence_count += 1
    return fence_count % 2 == 1


# ---------------------------------------------------------------------------
# Lint checks
# ---------------------------------------------------------------------------


def check_duplicate_anchors(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for multiple {#anchor} on the same heading line."""
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        anchors = re.findall(r"\{#[^}]+\}", line)
        if len(anchors) > 1:
            findings.append((
                ERROR, i + 1,
                f"duplicate heading anchor: {' '.join(anchors)}"
            ))
    return findings


def check_garbled_xml_tags(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for garbled XML namespace tags like <bcp47:setzongen."""
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        # Match <word:word patterns that aren't valid JSX
        matches = re.findall(r"<([a-z][a-z0-9]*):([a-z])", line, re.IGNORECASE)
        for ns, _ in matches:
            # Skip known valid patterns (e.g. https: in URLs)
            if ns.lower() in ("https", "http", "mailto"):
                continue
            findings.append((
                ERROR, i + 1,
                f"garbled XML namespace tag: <{ns}:..."
            ))
    return findings


def check_heading_mid_line(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for heading markers glued to preceding text on the same line.

    Catches: `...some text.#### Heading` (heading mid-line, causes acorn parse error).
    Does NOT flag headings on their own line (even without preceding blank line).
    """
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        # Look for ## heading markers that don't start at position 0.
        # A real heading starts at col 0; mid-line ones have text before them.
        m = re.search(r"(?<=\S)#{2,6}\s", line)
        if m and m.start() > 0:
            # Skip heading anchors {#...} — the char before ## would be {
            if line[m.start() - 1] == "{":
                continue
            # Skip if ## is part of a normal heading at start of line
            if line.lstrip().startswith("#"):
                continue
            findings.append((
                ERROR, i + 1,
                "heading marker glued to preceding text (needs blank line + own line)"
            ))
    return findings


def check_invalid_anchor_chars(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for heading anchors with special characters that cause issues."""
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        for m in re.finditer(r"\{#([^}]+)\}", line):
            anchor = m.group(1)
            bad_chars = re.findall(r"[.:?()!,;]", anchor)
            if bad_chars:
                findings.append((
                    WARN, i + 1,
                    f"anchor contains special characters: {{#{anchor}}} — chars: {''.join(set(bad_chars))}"
                ))
    return findings


def check_code_fence_balance(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for unmatched code fences."""
    findings = []
    fence_count = 0
    last_fence_line = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            fence_count += 1
            last_fence_line = i + 1
    if fence_count % 2 != 0:
        findings.append((
            ERROR, last_fence_line,
            f"unmatched code fence ({fence_count} total, expected even)"
        ))
    return findings


def check_missing_imports(
    lines: list[str], en_lines: list[str] | None
) -> list[tuple[str, int, str]]:
    """Check that import statements from EN source exist in translation."""
    if en_lines is None:
        return []

    findings = []

    # Extract imports from EN (outside code blocks)
    en_imports = set()
    en_fence = 0
    for line in en_lines:
        if line.strip().startswith("```"):
            en_fence += 1
        if en_fence % 2 == 0 and line.strip().startswith("import "):
            en_imports.add(line.strip())

    # Extract imports from translation
    tr_imports = set()
    tr_fence = 0
    for line in lines:
        if line.strip().startswith("```"):
            tr_fence += 1
        if tr_fence % 2 == 0 and line.strip().startswith("import "):
            tr_imports.add(line.strip())

    missing = en_imports - tr_imports
    for imp in sorted(missing):
        findings.append((
            ERROR, 0,
            f"missing import: {imp}"
        ))

    return findings


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_duplicate_anchors,
    check_garbled_xml_tags,
    check_heading_mid_line,
    check_invalid_anchor_chars,
    check_code_fence_balance,
]


def lint_file(
    tr_path: Path,
    en_path: Path | None = None,
    label: str = "",
) -> list[tuple[str, int, str]]:
    """Run all lint checks on a single file."""
    content = tr_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    en_lines = None
    if en_path and en_path.exists():
        en_lines = en_path.read_text(encoding="utf-8").splitlines()

    findings = []
    for check in ALL_CHECKS:
        findings.extend(check(lines))
    findings.extend(check_missing_imports(lines, en_lines))

    return findings


def record_lint_results(
    results: dict[str, dict[str, tuple[int, int]]],
) -> None:
    """Record lint results to status.json.

    results: {locale: {rel_path: (error_count, warning_count)}}
    """
    status = load_status()
    today = date.today().isoformat()

    for locale, files in results.items():
        if locale not in status:
            status[locale] = {}
        for rel, (errors, warnings) in files.items():
            entry = status[locale].get(rel, {})
            entry["linted"] = today
            if errors > 0:
                entry["lint"] = "ERRORS"
            elif warnings > 0:
                entry["lint"] = "WARNINGS"
            else:
                entry["lint"] = "CLEAN"
            entry["lint_errors"] = errors
            entry["lint_warnings"] = warnings
            if "status" not in entry:
                entry["status"] = "promoted"
            status[locale][rel] = entry

    save_status(status)


def run_lint(locales: list[str], verbose: bool = False,
             record: bool = False) -> int:
    """Lint translations for given locales. Returns exit code."""
    total_errors = 0
    total_warnings = 0
    total_files = 0
    error_files = []
    all_results: dict[str, dict[str, tuple[int, int]]] = {}

    for locale in locales:
        pairs = find_genuine_translations(locale)
        if not pairs:
            continue

        locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"
        locale_results: dict[str, tuple[int, int]] = {}

        for en_path, tr_path in pairs:
            rel = str(tr_path.relative_to(locale_dir))
            findings = lint_file(tr_path, en_path, f"{locale} {rel}")
            total_files += 1

            errors = [f for f in findings if f[0] == ERROR]
            warnings = [f for f in findings if f[0] == WARN]

            locale_results[rel] = (len(errors), len(warnings))

            if errors:
                total_errors += len(errors)
                error_files.append((locale, rel))
            total_warnings += len(warnings)

            for severity, line_no, message in findings:
                loc = f":{line_no}" if line_no else ""
                print(f"{severity:5s} {locale:4s} {rel}{loc} — {message}")

            if verbose and not findings:
                print(f"OK    {locale:4s} {rel}")

        if locale_results:
            all_results[locale] = locale_results

    # Summary
    print(f"\n--- Summary: {total_files} files linted ---")
    print(f"  Errors:   {total_errors}")
    print(f"  Warnings: {total_warnings}")

    if error_files:
        print(f"\n{len(error_files)} file(s) with errors:")
        for loc, rel in error_files:
            print(f"  {loc}/{rel}")

    if record and all_results:
        record_lint_results(all_results)
        print(f"\n  Recorded lint results for {total_files} files to status.json")

    return 1 if error_files else 0


def run_single_file(tr_path: Path, en_path: Path | None) -> int:
    """Lint a single file. Returns exit code."""
    findings = lint_file(tr_path, en_path)

    for severity, line_no, message in findings:
        loc = f":{line_no}" if line_no else ""
        print(f"{severity:5s} {tr_path.name}{loc} — {message}")

    errors = [f for f in findings if f[0] == ERROR]
    if not findings:
        print("OK — no issues found")
    elif not errors:
        print(f"\n{len(findings)} warning(s), 0 errors")

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Lint translated MDX files for build-breaking syntax errors"
    )
    parser.add_argument("--locale", help="Lint a single locale")
    parser.add_argument(
        "--all-locales", action="store_true", help="Lint all locales"
    )
    parser.add_argument("--file", type=Path, help="Lint a single file")
    parser.add_argument(
        "--en-file", type=Path, help="EN source file (for --file mode)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all files")
    parser.add_argument(
        "--record", action="store_true",
        help="Record lint results to translation/status.json"
    )

    args = parser.parse_args()

    if args.file:
        if not args.file.exists():
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_single_file(args.file, args.en_file))

    if not args.locale and not args.all_locales:
        parser.error("Specify --locale XX, --all-locales, or --file PATH")

    locales = ALL_LOCALES if args.all_locales else [args.locale]
    sys.exit(run_lint(locales, verbose=args.verbose, record=args.record))


if __name__ == "__main__":
    main()
