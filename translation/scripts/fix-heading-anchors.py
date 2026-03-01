#!/usr/bin/env python3
"""
Fix heading anchors in translated MDX files.

For each translated file, finds the corresponding English source,
extracts headings from both, and appends {#english-anchor} to
translated headings that differ from the English ones.

Usage:
    python translation/scripts/fix-heading-anchors.py                    # dry-run
    python translation/scripts/fix-heading-anchors.py --apply            # apply changes
    python translation/scripts/fix-heading-anchors.py --locale de        # single locale
    python translation/scripts/fix-heading-anchors.py --file guides/bit-ordering.mdx --locale de  # single file
"""

import argparse
import os
import re
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

# Locales to process
ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "th", "ar", "he",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]

# Regex to match markdown headings (not inside code blocks)
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

# Regex to detect existing anchor syntax {#anchor-id}
EXISTING_ANCHOR_RE = re.compile(r'\s*\{#[\w-]+\}\s*$')


def slugify(text: str) -> str:
    """Convert heading text to Docusaurus-style anchor slug.

    Matches Docusaurus/GitHub heading ID generation:
    - Strip inline code backticks, HTML tags, JSX components
    - Strip math delimiters but keep content
    - Lowercase, replace spaces with hyphens
    - Remove non-alphanumeric chars (except hyphens)
    - Collapse multiple hyphens
    """
    # Remove {#existing-anchor} if present
    s = EXISTING_ANCHOR_RE.sub('', text)

    # Remove inline code backticks but keep content
    s = s.replace('`', '')

    # Remove HTML tags like <br/>, <sub>, etc.
    s = re.sub(r'<[^>]+>', '', s)

    # Remove JSX components
    s = re.sub(r'<\w+[^>]*/>', '', s)

    # Remove math delimiters but keep content
    s = s.replace('$', '')

    # Remove HTML entities and replace with space
    s = re.sub(r'&\w+;', ' ', s)

    # Remove bold/italic markers
    s = s.replace('**', '').replace('*', '')

    # Normalize unicode (NFD decomposition, strip combining marks)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')

    # Lowercase
    s = s.lower()

    # Replace spaces and underscores with hyphens
    s = re.sub(r'[\s_]+', '-', s)

    # Remove non-alphanumeric characters (keep hyphens)
    s = re.sub(r'[^a-z0-9-]', '', s)

    # Collapse multiple hyphens
    s = re.sub(r'-{2,}', '-', s)

    # Strip leading/trailing hyphens
    s = s.strip('-')

    return s


def extract_headings_with_positions(content: str) -> list[tuple[int, int, str, str, str]]:
    """Extract headings from MDX content, skipping those inside code blocks.

    Returns list of (line_start, line_end, prefix, heading_text, full_line).
    """
    lines = content.split('\n')
    headings = []
    in_code_block = False

    for i, line in enumerate(lines):
        # Track code blocks
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Match heading lines
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            prefix = m.group(1)
            text = m.group(2).rstrip()
            headings.append((i, i, prefix, text, line))

    return headings


def heading_needs_anchor(en_text: str, translated_text: str) -> bool:
    """Determine if a translated heading needs an explicit anchor.

    If the slugified versions differ, the translated heading needs
    an explicit {#english-anchor} to preserve link targets.
    """
    # Already has an explicit anchor
    if EXISTING_ANCHOR_RE.search(translated_text):
        return False

    en_slug = slugify(en_text)
    tr_slug = slugify(translated_text)

    return en_slug != tr_slug


def fix_file(en_path: Path, translated_path: Path, apply: bool = False) -> dict:
    """Fix heading anchors in a single translated file.

    Returns dict with stats: {fixed, skipped, already_anchored, mismatched, errors}.
    """
    stats = {"fixed": 0, "skipped": 0, "already_anchored": 0, "errors": []}

    if not en_path.exists():
        stats["errors"].append(f"English source not found: {en_path}")
        return stats

    if not translated_path.exists():
        stats["errors"].append(f"Translated file not found: {translated_path}")
        return stats

    en_content = en_path.read_text(encoding='utf-8')
    tr_content = translated_path.read_text(encoding='utf-8')

    # Skip fallback files
    if 'doqumentation-untranslated-fallback' in tr_content:
        stats["skipped"] = 1
        return stats

    en_headings = extract_headings_with_positions(en_content)
    tr_headings = extract_headings_with_positions(tr_content)

    if len(en_headings) != len(tr_headings):
        stats["errors"].append(
            f"Heading count mismatch: EN has {len(en_headings)}, "
            f"translated has {len(tr_headings)}"
        )
        # Try to fix what we can by matching heading levels
        # Fall through — we'll match by position where possible

    # Process in reverse order so line numbers don't shift
    tr_lines = tr_content.split('\n')
    changes_made = False

    # Match headings by position (1:1 correspondence)
    pairs = list(zip(en_headings, tr_headings))

    for en_h, tr_h in reversed(pairs):
        en_line_idx, _, en_prefix, en_text, _ = en_h
        tr_line_idx, _, tr_prefix, tr_text, tr_full_line = tr_h

        # Check level match
        if en_prefix != tr_prefix:
            stats["errors"].append(
                f"Level mismatch at line {tr_line_idx + 1}: "
                f"EN '{en_prefix}' vs TR '{tr_prefix}'"
            )
            continue

        # Already has an anchor
        if EXISTING_ANCHOR_RE.search(tr_text):
            stats["already_anchored"] += 1
            continue

        # Check if anchor is needed
        en_slug = slugify(en_text)
        tr_slug = slugify(tr_text)

        if en_slug == tr_slug:
            stats["skipped"] += 1
            continue

        if not en_slug:
            stats["errors"].append(
                f"Empty slug for EN heading at line {en_line_idx + 1}: '{en_text}'"
            )
            continue

        # Add anchor
        new_line = f"{tr_prefix} {tr_text} {{#{en_slug}}}"
        tr_lines[tr_line_idx] = new_line
        stats["fixed"] += 1
        changes_made = True

    if changes_made and apply:
        translated_path.write_text('\n'.join(tr_lines), encoding='utf-8')

    return stats


def main():
    parser = argparse.ArgumentParser(description="Fix heading anchors in translated MDX files")
    parser.add_argument('--apply', action='store_true', help='Apply changes (default: dry-run)')
    parser.add_argument('--locale', type=str, help='Process single locale (e.g., de)')
    parser.add_argument('--file', type=str, help='Process single file (relative to docs/)')
    parser.add_argument('--dir', type=str,
                        help='Translation source directory (default: i18n/). '
                             'E.g. --dir translation/drafts')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show per-file details')
    args = parser.parse_args()

    locales = [args.locale] if args.locale else ALL_LOCALES

    total_stats = {"fixed": 0, "skipped": 0, "already_anchored": 0, "files": 0, "errors": []}

    for locale in locales:
        if args.dir:
            locale_dir = REPO_ROOT / args.dir / locale
        else:
            locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"

        if not locale_dir.exists():
            print(f"  Skipping {locale}: directory not found")
            continue

        if args.file:
            files = [Path(args.file)]
        else:
            # Find all MDX files in the locale directory
            files = sorted(locale_dir.rglob("*.mdx"))
            files = [f.relative_to(locale_dir) for f in files]

        locale_fixed = 0
        locale_errors = []

        for rel_path in files:
            en_path = DOCS_DIR / rel_path
            tr_path = locale_dir / rel_path

            stats = fix_file(en_path, tr_path, apply=args.apply)

            total_stats["fixed"] += stats["fixed"]
            total_stats["skipped"] += stats.get("skipped", 0)
            total_stats["already_anchored"] += stats["already_anchored"]
            total_stats["files"] += 1
            locale_fixed += stats["fixed"]

            if stats["errors"]:
                for err in stats["errors"]:
                    error_msg = f"  [{locale}] {rel_path}: {err}"
                    total_stats["errors"].append(error_msg)
                    locale_errors.append(error_msg)

            if args.verbose and (stats["fixed"] > 0 or stats["errors"]):
                status = "FIXED" if stats["fixed"] > 0 else "ERROR"
                print(f"  [{locale}] {rel_path}: {status} "
                      f"(fixed={stats['fixed']}, skipped={stats.get('skipped', 0)}, "
                      f"anchored={stats['already_anchored']})")

        print(f"[{locale}] {locale_fixed} headings fixed across {len(files)} files"
              + (f", {len(locale_errors)} errors" if locale_errors else ""))

    print(f"\n{'=' * 60}")
    print(f"Total: {total_stats['fixed']} headings fixed in {total_stats['files']} files")
    print(f"  Already anchored: {total_stats['already_anchored']}")
    print(f"  Skipped (identical slug): {total_stats['skipped']}")

    if total_stats["errors"]:
        print(f"\nErrors ({len(total_stats['errors'])}):")
        for err in total_stats["errors"][:20]:
            print(err)
        if len(total_stats["errors"]) > 20:
            print(f"  ... and {len(total_stats['errors']) - 20} more")

    if not args.apply:
        print(f"\nDry run — no files modified. Use --apply to write changes.")


if __name__ == "__main__":
    main()
