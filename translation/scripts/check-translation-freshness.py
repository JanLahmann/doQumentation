#!/usr/bin/env python3
"""
Check translation freshness by comparing embedded source hashes against
current EN source files.

Each genuine translation can embed a hash of its EN source:
    {/* doqumentation-source-hash: a1b2c3d4 */}

When the EN file changes, the hash mismatches and the translation is flagged.
Missing imports or components in stale translations are flagged as CRITICAL.

Usage:
    # Check all locales (default: report mode)
    python translation/scripts/check-translation-freshness.py --all-locales

    # Check one locale
    python translation/scripts/check-translation-freshness.py --locale de

    # Add/update source hashes in all genuine translations
    python translation/scripts/check-translation-freshness.py --stamp --all-locales

    # Stamp one locale
    python translation/scripts/check-translation-freshness.py --stamp --locale de
"""

import argparse
import hashlib
import re
import sys
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

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"
HASH_PATTERN = re.compile(r"\{/\* doqumentation-source-hash: ([a-f0-9]{8}) \*/\}")
HASH_TEMPLATE = "{{/* doqumentation-source-hash: {} */}}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_source_hash(content: str) -> str:
    """Return first 8 hex chars of SHA-256 of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]


def extract_embedded_hash(content: str) -> str | None:
    """Extract the source hash from a translation file, or None."""
    m = HASH_PATTERN.search(content)
    return m.group(1) if m else None


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


def extract_imports(content: str) -> set[str]:
    """Extract import statements from MDX content."""
    imports = set()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            imports.add(stripped)
    return imports


def extract_jsx_components(content: str) -> set[str]:
    """Extract JSX self-closing component tags (e.g. <BetaNotice />)."""
    return set(re.findall(r"<([A-Z][A-Za-z0-9]+)\s*/\s*>", content))


def insert_hash_after_frontmatter(content: str, hash_val: str) -> str:
    """Insert or update the source hash comment after frontmatter."""
    hash_line = HASH_TEMPLATE.format(hash_val)

    # Update existing hash
    if HASH_PATTERN.search(content):
        return HASH_PATTERN.sub(
            f"{{/* doqumentation-source-hash: {hash_val} */}}", content
        )

    # Insert after frontmatter closing ---
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_end = end + 4  # position after "\n---"
            return content[:fm_end] + "\n" + hash_line + content[fm_end:]

    # Fallback: prepend
    return hash_line + "\n" + content


# ---------------------------------------------------------------------------
# Check mode
# ---------------------------------------------------------------------------

FRESH = "FRESH"
STALE = "STALE"
CRITICAL = "CRITICAL"
UNKNOWN = "UNKNOWN"


def check_file(en_path: Path, tr_path: Path, locale: str) -> tuple[str, str, str]:
    """Check one translation file against its EN source.
    Returns (status, locale, rel_path, detail).
    """
    en_content = en_path.read_text(encoding="utf-8")
    tr_content = tr_path.read_text(encoding="utf-8")

    locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"
    rel = str(tr_path.relative_to(locale_dir))

    current_hash = compute_source_hash(en_content)
    embedded_hash = extract_embedded_hash(tr_content)

    if embedded_hash is None:
        return UNKNOWN, locale, rel, "no source hash (run --stamp)"

    if embedded_hash == current_hash:
        return FRESH, locale, rel, ""

    # Hash mismatch — do detailed analysis
    en_imports = extract_imports(en_content)
    tr_imports = extract_imports(tr_content)
    missing_imports = en_imports - tr_imports

    en_components = extract_jsx_components(en_content)
    tr_components = extract_jsx_components(tr_content)
    missing_components = en_components - tr_components

    if missing_imports:
        names = ", ".join(sorted(missing_imports))
        return CRITICAL, locale, rel, f"missing import: {names}"

    if missing_components:
        names = ", ".join(sorted(missing_components))
        return CRITICAL, locale, rel, f"missing component: {names}"

    return STALE, locale, rel, f"source changed ({embedded_hash} → {current_hash})"


def run_check(locales: list[str], verbose: bool = False) -> int:
    """Check translations for given locales. Returns exit code."""
    counts = {FRESH: 0, STALE: 0, CRITICAL: 0, UNKNOWN: 0}
    critical_files = []

    for locale in locales:
        pairs = find_genuine_translations(locale)
        if not pairs:
            continue

        for en_path, tr_path in pairs:
            status, loc, rel, detail = check_file(en_path, tr_path, locale)
            counts[status] += 1

            if status == CRITICAL:
                critical_files.append((loc, rel, detail))
                print(f"CRITICAL {loc:4s} {rel} — {detail}")
            elif status == STALE:
                print(f"STALE    {loc:4s} {rel} — {detail}")
            elif status == UNKNOWN:
                if verbose:
                    print(f"UNKNOWN  {loc:4s} {rel} — {detail}")
            elif verbose:
                print(f"FRESH    {loc:4s} {rel}")

    # Summary
    total = sum(counts.values())
    print(f"\n--- Summary: {total} files checked ---")
    print(f"  FRESH:    {counts[FRESH]}")
    print(f"  STALE:    {counts[STALE]}")
    print(f"  CRITICAL: {counts[CRITICAL]}")
    print(f"  UNKNOWN:  {counts[UNKNOWN]}")

    if critical_files:
        print(f"\n⚠ {len(critical_files)} CRITICAL file(s) need immediate attention:")
        for loc, rel, detail in critical_files:
            print(f"  {loc}/{rel} — {detail}")
        return 1

    return 0


# ---------------------------------------------------------------------------
# Stamp mode
# ---------------------------------------------------------------------------


def run_stamp(locales: list[str]) -> None:
    """Add or update source hashes in genuine translations."""
    total_stamped = 0
    total_unchanged = 0

    for locale in locales:
        pairs = find_genuine_translations(locale)
        if not pairs:
            continue

        stamped = 0
        for en_path, tr_path in pairs:
            en_content = en_path.read_text(encoding="utf-8")
            tr_content = tr_path.read_text(encoding="utf-8")

            current_hash = compute_source_hash(en_content)
            embedded_hash = extract_embedded_hash(tr_content)

            if embedded_hash == current_hash:
                total_unchanged += 1
                continue

            new_content = insert_hash_after_frontmatter(tr_content, current_hash)
            tr_path.write_text(new_content, encoding="utf-8")
            stamped += 1

        total_stamped += stamped
        if stamped:
            print(f"{locale}: {stamped} file(s) stamped")

    print(f"\nTotal: {total_stamped} stamped, {total_unchanged} already up-to-date")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Check translation freshness via embedded source hashes"
    )
    parser.add_argument("--locale", help="Check/stamp a single locale")
    parser.add_argument(
        "--all-locales", action="store_true", help="Check/stamp all locales"
    )
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="Add/update source hashes in genuine translations",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all files")

    args = parser.parse_args()

    if not args.locale and not args.all_locales:
        parser.error("Specify --locale XX or --all-locales")

    locales = ALL_LOCALES if args.all_locales else [args.locale]

    if args.stamp:
        run_stamp(locales)
    else:
        sys.exit(run_check(locales, verbose=args.verbose))


if __name__ == "__main__":
    main()
