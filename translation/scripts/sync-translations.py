#!/usr/bin/env python3
"""
Sync structural elements (code blocks, survey URLs, index.mdx) from English
source files into translated MDX files.

Fixes the most common validation failures mechanically — no retranslation needed:
  1. Missing pip install code blocks (added by sync-content.py after translation)
  2. Differing code blocks (translated comments, updated EN code)
  3. Missing survey/feedback URLs
  4. Duplicate trailing EN sections (appended by earlier sync runs)
  5. Missing content lines from EN (e.g., new backends added after translation)
  6. Missing reference URLs from EN

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
    """If EN has a survey URL section that TR is missing, insert the URL."""
    en_survey = find_survey_section(en_content)
    if en_survey is None:
        return None

    survey_text, _ = en_survey

    # Check if TR already has a survey URL
    if SURVEY_URL_PATTERN.search(tr_content):
        return None

    # Extract just the survey URL line from EN
    survey_url_line = None
    for line in survey_text.split('\n'):
        if SURVEY_URL_PATTERN.search(line):
            survey_url_line = line
            break

    if survey_url_line is None:
        return None

    tr_lines = tr_content.split('\n')

    # Check if TR has a translated survey heading — if so, insert the URL
    # line after the translated survey paragraph, not the whole EN section
    survey_heading_idx = None
    for i, line in enumerate(tr_lines):
        stripped = line.strip()
        if re.match(r'^##\s+.*\{#tutorial-survey\}', stripped):
            survey_heading_idx = i
            break

    if survey_heading_idx is not None:
        # Insert the URL after the survey paragraph (find end of paragraph)
        insert_at = survey_heading_idx + 1
        while insert_at < len(tr_lines) and tr_lines[insert_at].strip() != '':
            insert_at += 1
        new_tr_lines = (
            tr_lines[:insert_at]
            + [survey_url_line]
            + tr_lines[insert_at:]
        )
        return '\n'.join(new_tr_lines)

    # No translated survey heading — insert whole EN survey section at end
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
# Fix: Remove duplicate trailing EN sections
# ---------------------------------------------------------------------------

def extract_headings(content: str) -> list[tuple[int, str, str]]:
    """Extract headings with line numbers. Returns [(line_idx, level_markers, text)]."""
    headings = []
    in_code = False
    for i, line in enumerate(content.split('\n')):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if m:
            headings.append((i, m.group(1), m.group(2)))
    return headings


def fix_duplicate_trailing_section(en_content: str, tr_content: str) -> str | None:
    """Remove duplicate EN section appended at end of translation.

    A section is duplicate when the file has MORE headings than EN, and
    the trailing EN headings (without {#anchor}) cover topics that already
    have a translated heading (with {#anchor}) earlier in the file.
    The anchor ID is used to match: e.g., {#references} in the translated
    heading matches "## References" in the duplicate EN heading.
    """
    en_headings = extract_headings(en_content)
    tr_headings = extract_headings(tr_content)
    tr_lines = tr_content.split('\n')

    if len(tr_headings) <= len(en_headings):
        return None  # No extra headings

    # Build a map: EN heading text -> anchor ID used in translations
    en_text_to_anchor = {}
    for _, _, text in en_headings:
        clean = re.sub(r'\s*\{#[^}]+\}', '', text).strip()
        # The anchor is typically the slugified EN heading
        en_text_to_anchor[clean] = clean.lower().replace(' ', '-')

    # Collect anchors from translated headings (with {#...})
    tr_anchors = {}  # anchor_id -> line_idx
    for line_idx, _, text in tr_headings:
        m = re.search(r'\{#([^}]+)\}', text)
        if m:
            tr_anchors[m.group(1)] = line_idx

    # Walk from end: find EN headings without {#anchor} whose topic
    # is already covered by a translated heading with matching anchor
    first_dup_line = None
    for i in range(len(tr_headings) - 1, -1, -1):
        line_idx, _, tr_text = tr_headings[i]
        has_anchor = '{#' in tr_text
        clean = re.sub(r'\s*\{#[^}]+\}', '', tr_text).strip()

        if not has_anchor and clean in en_text_to_anchor:
            expected_anchor = en_text_to_anchor[clean]
            # Check if a translated heading with this anchor exists earlier
            if expected_anchor in tr_anchors and tr_anchors[expected_anchor] < line_idx:
                first_dup_line = line_idx
            else:
                break
        else:
            break

    if first_dup_line is None:
        return None

    # Now scan backwards from the EN heading to find where the duplicate
    # content actually starts (there may be duplicate non-heading content
    # like reference entries before the heading)
    cut_line = first_en_dup_heading

    # Walk backwards over non-empty lines that look like duplicate EN content
    # (references, paragraphs that appear earlier in the file)
    while cut_line > 0:
        prev_line = tr_lines[cut_line - 1].strip()
        if prev_line == '':
            cut_line -= 1
            continue
        # Check if this line is a duplicate of an earlier line in the file
        is_duplicate = False
        for j in range(cut_line - 2):
            if tr_lines[j].strip() == prev_line and prev_line:
                is_duplicate = True
                break
        if is_duplicate:
            cut_line -= 1
        else:
            break

    # Skip blank lines before the cut point
    while cut_line > 0 and tr_lines[cut_line - 1].strip() == '':
        cut_line -= 1

    # Verify we're not cutting too much (at least half the file should remain)
    if cut_line < len(tr_lines) // 3:
        return None

    new_lines = tr_lines[:cut_line]
    # Ensure file ends with single newline
    while new_lines and new_lines[-1].strip() == '':
        new_lines.pop()
    new_lines.append('')

    result = '\n'.join(new_lines)
    if result == tr_content:
        return None
    return result

# ---------------------------------------------------------------------------
# Fix: Insert missing content lines from EN (e.g., new backends in index.mdx)
# ---------------------------------------------------------------------------

def fix_missing_en_lines(en_content: str, tr_content: str) -> str | None:
    """Insert specific missing content lines from EN into TR.

    Handles cases where EN was updated after translation (new backends,
    new links) and the translation is missing those lines. Uses context
    matching to find insertion points.
    """
    en_lines = en_content.split('\n')
    tr_lines = tr_content.split('\n')
    fixes_applied = []

    # Pattern: missing numbered list items (e.g., "2. **IBM Code Engine**")
    # Find numbered lists in EN and check if TR has fewer items
    en_urls = extract_link_urls(en_content)
    tr_urls = extract_link_urls(tr_content)
    missing_urls = en_urls - tr_urls

    if not missing_urls:
        return None

    current_lines = list(tr_lines)
    changed = False

    # For each missing URL, find the EN line containing it and try to insert
    for url in sorted(missing_urls):
        # Find the EN line(s) containing this URL
        en_url_lines = []
        for i, line in enumerate(en_lines):
            if url in line:
                en_url_lines.append((i, line))

        if not en_url_lines:
            continue

        for en_idx, en_line in en_url_lines:
            # Skip if URL is in a code block
            in_code = False
            for l in en_lines[:en_idx]:
                if l.strip().startswith('```'):
                    in_code = not in_code
            if in_code:
                continue

            # Already in TR?
            if any(url in l for l in current_lines):
                continue

            # Strategy: find the EN line BEFORE this one in TR, insert after it
            # Look for context: the line before in EN
            if en_idx > 0:
                prev_en = en_lines[en_idx - 1].strip()
                # Find this context in TR
                for j, tr_line in enumerate(current_lines):
                    # Match by URL content in the previous line
                    prev_urls = re.findall(r'https?://\S+', prev_en)
                    if prev_urls and any(pu in tr_line for pu in prev_urls):
                        current_lines.insert(j + 1, en_line)
                        changed = True
                        fixes_applied.append(url)
                        break
                    # Match by numbered list pattern (e.g., "1. **Binder**")
                    prev_num = re.match(r'^(\d+)\.\s+\*\*', prev_en)
                    tr_num = re.match(r'^(\d+)\.\s+\*\*', tr_line.strip())
                    if prev_num and tr_num and prev_num.group(1) == tr_num.group(1):
                        current_lines.insert(j + 1, en_line)
                        changed = True
                        fixes_applied.append(url)
                        break

            # Strategy 2: find the EN line AFTER this one in TR, insert before it
            if url not in '\n'.join(current_lines) and en_idx < len(en_lines) - 1:
                next_en = en_lines[en_idx + 1].strip()
                if next_en:
                    next_urls = re.findall(r'https?://\S+', next_en)
                    for j, tr_line in enumerate(current_lines):
                        if next_urls and any(nu in tr_line for nu in next_urls):
                            current_lines.insert(j, en_line)
                            changed = True
                            fixes_applied.append(url)
                            break
                        next_num = re.match(r'^(\d+)\.\s+\*\*', next_en)
                        tr_num = re.match(r'^(\d+)\.\s+\*\*', tr_line.strip())
                        if next_num and tr_num and next_num.group(1) == tr_num.group(1):
                            current_lines.insert(j, en_line)
                            changed = True
                            fixes_applied.append(url)
                            break

            # Strategy 3: standalone line (like "When multiple backends...")
            # Insert after the last numbered list item or before </details>
            if url not in '\n'.join(current_lines):
                for j in range(len(current_lines) - 1, -1, -1):
                    if re.match(r'^\d+\.\s+\*\*', current_lines[j].strip()):
                        current_lines.insert(j + 1, '')
                        current_lines.insert(j + 2, en_line)
                        changed = True
                        fixes_applied.append(url)
                        break

    if not changed:
        return None

    return '\n'.join(current_lines)

# ---------------------------------------------------------------------------
# Fix: Insert missing reference URLs from EN
# ---------------------------------------------------------------------------

def fix_missing_reference_urls(en_content: str, tr_content: str) -> str | None:
    """Insert missing reference list entries from EN into TR.

    When EN has reference entries (numbered citations) that TR is missing,
    insert them at the correct position in TR's reference list.
    """
    # Find reference sections in both
    en_lines = en_content.split('\n')
    tr_lines = tr_content.split('\n')

    # Find reference heading in TR
    ref_heading_idx = None
    for i, line in enumerate(tr_lines):
        stripped = line.strip()
        # Match ## References or translated variants with anchor
        if re.match(r'^##\s+.*\{#references\}', stripped) or stripped == '## References':
            ref_heading_idx = i
            # Use the LAST one (in case of duplicates that weren't caught)
            # Actually use the FIRST translated one
            break

    if ref_heading_idx is None:
        return None

    # Extract reference entries from EN (numbered: "1. Author...")
    en_ref_entries = {}
    en_ref_heading = None
    for i, line in enumerate(en_lines):
        if re.match(r'^##\s+References', line.strip()):
            en_ref_heading = i
    if en_ref_heading is None:
        return None

    ref_re = re.compile(r'^(\d+)\.\s+(.+)')
    for i in range(en_ref_heading + 1, len(en_lines)):
        m = ref_re.match(en_lines[i].strip())
        if m:
            en_ref_entries[int(m.group(1))] = en_lines[i]
        elif en_lines[i].strip().startswith('##'):
            break

    # Extract TR reference entries
    tr_ref_entries = {}
    for i in range(ref_heading_idx + 1, len(tr_lines)):
        m = ref_re.match(tr_lines[i].strip())
        if m:
            tr_ref_entries[int(m.group(1))] = i
        elif tr_lines[i].strip().startswith('##'):
            break

    # Find missing entries
    missing = set(en_ref_entries.keys()) - set(tr_ref_entries.keys())
    if not missing:
        return None

    # Insert missing entries at the right position
    current = list(tr_lines)
    offset = 0
    for num in sorted(missing):
        # Find insertion point: after the previous numbered entry
        insert_after = ref_heading_idx + offset
        for existing_num in sorted(tr_ref_entries.keys()):
            if existing_num < num:
                insert_after = tr_ref_entries[existing_num] + offset

        current.insert(insert_after + 1, en_ref_entries[num])
        offset += 1

    result = '\n'.join(current)
    if result == tr_content:
        return None
    return result

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

    # Fix 3: Duplicate trailing EN sections (must run BEFORE survey URL fix)
    result = fix_duplicate_trailing_section(en_content, current)
    if result is not None:
        current = result
        fixes.append("removed duplicate trailing EN section")

    # Fix 4: Missing survey URLs (runs after duplicate removal)
    result = fix_missing_survey_url(en_content, current)
    if result is not None:
        current = result
        fixes.append("inserted missing survey URL section")

    # Fix 5: Missing content lines from EN (new backends, links)
    result = fix_missing_en_lines(en_content, current)
    if result is not None:
        current = result
        fixes.append("inserted missing EN content lines")

    # Fix 6: Missing reference URLs
    result = fix_missing_reference_urls(en_content, current)
    if result is not None:
        current = result
        fixes.append("inserted missing reference entries")

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
