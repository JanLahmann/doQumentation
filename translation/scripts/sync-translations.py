#!/usr/bin/env python3
"""
Sync structural elements (code blocks, survey URLs, index.mdx) from English
source files into translated MDX files.

Fixes the most common validation failures mechanically — no retranslation needed:
  1. Missing pip install code blocks (added by sync-content.py after translation)
  2. Differing code blocks (translated comments, updated EN code)
  3. Missing survey/feedback URLs
  4. index.mdx code blocks + URLs

Usage:
    python translation/scripts/sync-translations.py --locale fr                    # all genuine translations
    python translation/scripts/sync-translations.py --locale fr --section tutorials # just tutorials
    python translation/scripts/sync-translations.py --locale fr --dry-run           # preview changes
    python translation/scripts/sync-translations.py --all-locales                   # all locales
    python translation/scripts/sync-translations.py --all-locales --dry-run         # preview all
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"
PIP_INSTALL_MARKER = "Added by doQumentation"
SURVEY_URL_PATTERN = re.compile(r'https?://(?:your\.feedback\.ibm\.com|qisk\.it)/\S+')

# ---------------------------------------------------------------------------
# Parsers (shared with validate-translation.py)
# ---------------------------------------------------------------------------

def extract_code_blocks(content: str) -> list[tuple[int, int, str]]:
    """Extract fenced code blocks. Returns [(start_line, end_line, full_block_text)]."""
    lines = content.split('\n')
    blocks = []
    in_block = False
    block_start = 0
    block_lines: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('```'):
            if not in_block:
                in_block = True
                block_start = i
                block_lines = [line]
            else:
                block_lines.append(line)
                blocks.append((block_start, i, '\n'.join(block_lines)))
                in_block = False
                block_lines = []
        elif in_block:
            block_lines.append(line)

    return blocks


def normalize_block(block: str) -> str:
    """Normalize a code block for comparison (strip trailing whitespace per line)."""
    return '\n'.join(l.rstrip() for l in block.split('\n'))

# ---------------------------------------------------------------------------
# Fix: Insert missing pip install block
# ---------------------------------------------------------------------------

def find_pip_install_block(blocks: list[tuple[int, int, str]]) -> int | None:
    """Return index of the pip install block with doQumentation marker, or None."""
    for i, (start, end, text) in enumerate(blocks):
        if PIP_INSTALL_MARKER in text and '!pip install' in text:
            return i
    return None


def fix_missing_pip_install(en_content: str, tr_content: str) -> str | None:
    """If EN has exactly 1 more code block than TR and it's a pip install block,
    insert it into TR at the correct position. Returns fixed content or None."""
    en_blocks = extract_code_blocks(en_content)
    tr_blocks = extract_code_blocks(tr_content)

    if len(en_blocks) != len(tr_blocks) + 1:
        return None

    pip_idx = find_pip_install_block(en_blocks)
    if pip_idx is None:
        return None

    # Get the pip install block text from EN
    pip_start, pip_end, pip_text = en_blocks[pip_idx]

    # We need to find the context around the pip block in EN to locate
    # the insertion point in TR.
    en_lines = en_content.split('\n')
    tr_lines = tr_content.split('\n')

    # Strategy: find the text that comes AFTER the pip block in EN,
    # then find that same text in TR and insert before it.
    # The pip install block is usually the first code block, right after
    # the OpenInLabBanner import and component.

    # Look for the line after the pip block's closing fence
    after_pip_line = pip_end + 1
    if after_pip_line < len(en_lines):
        # Find the next code block after pip in EN
        next_en_block_idx = pip_idx + 1
        if next_en_block_idx < len(en_blocks):
            next_en_start = en_blocks[next_en_block_idx][0]
            # The corresponding block in TR is at index pip_idx (since pip is missing)
            if pip_idx < len(tr_blocks):
                tr_insert_line = tr_blocks[pip_idx][0]
                # Insert the pip block before this TR block
                # Include a blank line before and after for proper spacing
                pip_block_lines = pip_text.split('\n')
                new_tr_lines = (
                    tr_lines[:tr_insert_line]
                    + pip_block_lines
                    + ['']
                    + tr_lines[tr_insert_line:]
                )
                return '\n'.join(new_tr_lines)

    # Fallback: insert after OpenInLabBanner component or after frontmatter
    for i, line in enumerate(tr_lines):
        if '<OpenInLabBanner' in line:
            insert_at = i + 1
            # Skip blank lines after banner
            while insert_at < len(tr_lines) and tr_lines[insert_at].strip() == '':
                insert_at += 1
            pip_block_lines = pip_text.split('\n')
            new_tr_lines = (
                tr_lines[:insert_at]
                + ['']
                + pip_block_lines
                + ['']
                + tr_lines[insert_at:]
            )
            return '\n'.join(new_tr_lines)

    return None

# ---------------------------------------------------------------------------
# Fix: Restore differing code blocks from EN
# ---------------------------------------------------------------------------

def fix_differing_code_blocks(en_content: str, tr_content: str) -> str | None:
    """Replace TR code blocks with EN code blocks where they differ.
    Only operates when block counts match. Returns fixed content or None."""
    en_blocks = extract_code_blocks(en_content)
    tr_blocks = extract_code_blocks(tr_content)

    if len(en_blocks) != len(tr_blocks):
        return None

    tr_lines = tr_content.split('\n')
    fixes = []

    for idx, ((en_start, en_end, en_text), (tr_start, tr_end, tr_text)) in enumerate(
            zip(en_blocks, tr_blocks)):
        if normalize_block(en_text) != normalize_block(tr_text):
            fixes.append((tr_start, tr_end, en_text))

    if not fixes:
        return None

    # Apply fixes in reverse order to preserve line numbers
    for tr_start, tr_end, en_text in reversed(fixes):
        en_block_lines = en_text.split('\n')
        tr_lines[tr_start:tr_end + 1] = en_block_lines

    return '\n'.join(tr_lines)

# ---------------------------------------------------------------------------
# Fix: Insert missing survey/feedback URLs
# ---------------------------------------------------------------------------

def find_survey_section(content: str) -> tuple[str, int] | None:
    """Find survey URL and its surrounding context in content."""
    lines = content.split('\n')
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if SURVEY_URL_PATTERN.search(line):
            # Return the paragraph containing the survey URL
            # Look backwards for the start of the paragraph
            start = i
            while start > 0 and lines[start - 1].strip() != '':
                start -= 1
            # Look forward for end of paragraph
            end = i
            while end < len(lines) - 1 and lines[end + 1].strip() != '':
                end += 1
            return '\n'.join(lines[start:end + 1]), start
    return None


def fix_missing_survey_url(en_content: str, tr_content: str) -> str | None:
    """If EN has a survey URL section that TR is missing, insert it."""
    en_survey = find_survey_section(en_content)
    if en_survey is None:
        return None

    survey_text, _ = en_survey

    # Check if TR already has a survey URL
    if SURVEY_URL_PATTERN.search(tr_content):
        return None

    # Insert survey section at end of TR, before any trailing blank lines
    tr_lines = tr_content.split('\n')
    # Find last non-empty line
    insert_at = len(tr_lines)
    while insert_at > 0 and tr_lines[insert_at - 1].strip() == '':
        insert_at -= 1

    new_tr_lines = (
        tr_lines[:insert_at]
        + ['', '']
        + survey_text.split('\n')
        + ['']
    )
    return '\n'.join(new_tr_lines)

# ---------------------------------------------------------------------------
# Fix: Restore missing link URLs
# ---------------------------------------------------------------------------

def extract_link_urls(content: str) -> set[str]:
    """Extract all URLs from markdown links and JSX href (outside code blocks)."""
    urls = set()
    in_code = False
    md_re = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    jsx_re = re.compile(r'href="([^"]+)"')
    for line in content.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in md_re.finditer(line):
            url = m.group(2).split(' ')[0].strip('"').strip("'")
            if not url.startswith('#'):
                urls.add(url)
        for m in jsx_re.finditer(line):
            url = m.group(1)
            if not url.startswith('#'):
                urls.add(url)
    return urls

# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def get_en_path(rel_path: str) -> Path:
    """Get the English source path for a relative translation path."""
    return DOCS_DIR / rel_path


def get_tr_dir(locale: str) -> Path:
    """Get the translation directory for a locale."""
    return I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"


def sync_file(en_path: Path, tr_path: Path, dry_run: bool = False) -> list[str]:
    """Sync structural elements from EN to TR. Returns list of fixes applied."""
    if not en_path.exists() or not tr_path.exists():
        return []

    en_content = en_path.read_text(encoding='utf-8')
    tr_content = tr_path.read_text(encoding='utf-8')

    # Skip fallback files
    if FALLBACK_MARKER in tr_content:
        return []

    fixes = []
    current = tr_content

    # Fix 1: Missing pip install block
    result = fix_missing_pip_install(en_content, current)
    if result is not None:
        current = result
        fixes.append("inserted missing pip install block")

    # Fix 2: Differing code blocks (only if counts now match)
    result = fix_differing_code_blocks(en_content, current)
    if result is not None:
        count = len([1 for (_, _, et), (_, _, tt) in zip(
            extract_code_blocks(en_content), extract_code_blocks(current))
            if normalize_block(et) != normalize_block(tt)])
        current = result
        fixes.append(f"restored {count} differing code block(s)")

    # Fix 3: Missing survey URLs
    result = fix_missing_survey_url(en_content, current)
    if result is not None:
        current = result
        fixes.append("inserted missing survey URL section")

    if fixes and not dry_run:
        tr_path.write_text(current, encoding='utf-8')

    return fixes


def sync_locale(locale: str, section: str | None = None,
                dry_run: bool = False) -> dict[str, list[str]]:
    """Sync all genuine translations for a locale. Returns {rel_path: [fixes]}."""
    tr_dir = get_tr_dir(locale)
    if not tr_dir.exists():
        print(f"  No translations found for {locale}")
        return {}

    results = {}

    # Find all .mdx files in the translation directory
    for tr_path in sorted(tr_dir.rglob('*.mdx')):
        rel_path = str(tr_path.relative_to(tr_dir))

        # Filter by section if specified
        if section:
            if not rel_path.startswith(section):
                continue

        en_path = get_en_path(rel_path)
        if not en_path.exists():
            continue

        fixes = sync_file(en_path, tr_path, dry_run=dry_run)
        if fixes:
            results[rel_path] = fixes

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Sync structural elements from EN to translated MDX files')
    parser.add_argument('--locale', type=str,
                        help='Locale to sync (e.g., fr, de, es)')
    parser.add_argument('--all-locales', action='store_true',
                        help='Sync all locales')
    parser.add_argument('--section', type=str,
                        help='Filter by section (tutorials, guides, learning)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would change without modifying files')
    args = parser.parse_args()

    if not args.locale and not args.all_locales:
        parser.error("Either --locale or --all-locales is required")

    locales = ALL_LOCALES if args.all_locales else [args.locale]

    total_files = 0
    total_fixes = 0

    for locale in locales:
        print(f"\n{'=' * 60}")
        print(f"Syncing {locale.upper()}{'  (dry run)' if args.dry_run else ''}")
        print(f"{'=' * 60}")

        results = sync_locale(locale, section=args.section, dry_run=args.dry_run)

        if results:
            for rel_path, fixes in results.items():
                fix_str = '; '.join(fixes)
                print(f"  {'[DRY] ' if args.dry_run else ''}✓ {rel_path}: {fix_str}")
            total_files += len(results)
            total_fixes += sum(len(f) for f in results.values())
        else:
            print("  No fixes needed")

    print(f"\n{'=' * 60}")
    print(f"Summary: {total_fixes} fix(es) across {total_files} file(s)")
    if args.dry_run:
        print("  (dry run — no files modified)")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
