#!/usr/bin/env python3
"""
Diff-based translation update tool.

Detects stale translations, classifies change severity, auto-fixes structural
elements (code blocks, imports, links, images), and generates targeted
retranslation workfiles for translation agents.

Three-phase pipeline:
  1. DETECT:  Parse EN + translation → align blocks → classify severity
  2. AUTO-FIX: Sync code, imports, links, images, JSX → update source hash
  3. WORKFILE: Generate JSON with per-paragraph update instructions

Usage:
  # Analyze stale files for a locale
  python update-translations.py --locale de --analyze

  # Auto-fix + generate workfile
  python update-translations.py --locale de --auto-fix --generate-workfile

  # Single file analysis
  python update-translations.py --locale de --file guides/hello-world.mdx --analyze -v
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path

# ── Imports from sibling scripts ──
# Use importlib to handle hyphenated filenames
import importlib.util

SCRIPT_DIR = Path(__file__).resolve().parent

def _import_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

freshness = _import_module("freshness", "check-translation-freshness.py")
validator = _import_module("validator", "validate-translation.py")
syncer = _import_module("syncer", "sync-translations.py")

# Re-export key functions
compute_source_hash = freshness.compute_source_hash
extract_embedded_hash = freshness.extract_embedded_hash
insert_hash_after_frontmatter = freshness.insert_hash_after_frontmatter
find_genuine_translations = freshness.find_genuine_translations
slugify = validator.slugify

# ── Constants ──

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
I18N_DIR = Path(__file__).resolve().parents[2] / "i18n"

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"
HASH_COMMENT_RE = re.compile(r'\{/\*\s*doqumentation-source-hash:\s*([a-f0-9]+)\s*\*/\}')

# ── Data structures ──

class Severity(Enum):
    NOOP = "noop"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"

class BlockType(Enum):
    FRONTMATTER = "frontmatter"
    HEADING = "heading"
    CODE = "code"
    PROSE = "prose"
    IMPORT = "import"
    COMMENT = "comment"
    IMAGE = "image"
    BLANK = "blank"
    MATH = "math"
    JSX = "jsx"
    TABLE = "table"
    ADMONITION_FENCE = "adm_fence"  # ::: markers

@dataclass
class Block:
    type: BlockType
    content: str
    start_line: int
    end_line: int
    anchor: str | None = None  # For headings
    lang: str | None = None    # For code blocks

@dataclass
class Delta:
    kind: str          # "code_changed", "prose_changed", "heading_changed",
                       # "added", "removed", "import_changed", "link_changed",
                       # "image_changed", "frontmatter_changed"
    en_block: Block | None
    tr_block: Block | None
    section_anchor: str
    auto_fixable: bool

@dataclass
class ChangeReport:
    rel_path: str
    severity: Severity
    deltas: list[Delta]
    prose_lines_changed: int
    headings_added: list[str] = field(default_factory=list)
    headings_removed: list[str] = field(default_factory=list)
    en_hash: str = ""

@dataclass
class UpdateInstruction:
    section_anchor: str
    paragraph_index: int
    new_en_prose: str
    current_translation: str
    context_before: str
    context_after: str

@dataclass
class FileWorkItem:
    rel_path: str
    severity: str
    auto_fixes: list[str]
    updates: list[UpdateInstruction]
    full_retranslation: bool


# ══════════════════════════════════════════════════════════════
# Phase 1: MDX Parser
# ══════════════════════════════════════════════════════════════

def parse_blocks(content: str) -> list[Block]:
    """Parse MDX content into a list of typed blocks."""
    lines = content.split('\n')
    blocks: list[Block] = []
    i = 0
    n = len(lines)

    # Frontmatter
    if i < n and lines[i].strip() == '---':
        start = i
        i += 1
        while i < n and lines[i].strip() != '---':
            i += 1
        if i < n:
            i += 1
        blocks.append(Block(BlockType.FRONTMATTER, '\n'.join(lines[start:i]), start, i - 1))

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line
        if not stripped:
            blocks.append(Block(BlockType.BLANK, '', i, i))
            i += 1
            continue

        # Source hash comment
        if HASH_COMMENT_RE.search(stripped):
            blocks.append(Block(BlockType.COMMENT, stripped, i, i))
            i += 1
            continue

        # Other comments {/* ... */}
        if stripped.startswith('{/*') and stripped.endswith('*/}'):
            blocks.append(Block(BlockType.COMMENT, stripped, i, i))
            i += 1
            continue

        # Code fence
        fence_match = re.match(r'^(\s*)(```+|~~~+)(.*)', line)
        if fence_match:
            indent, fence_chars, meta = fence_match.groups()
            lang = meta.strip().split()[0] if meta.strip() else None
            start = i
            i += 1
            # Find closing fence
            while i < n:
                close_match = re.match(r'^(\s*)(```+|~~~+)\s*$', lines[i])
                if close_match and len(close_match.group(2)) >= len(fence_chars):
                    i += 1
                    break
                i += 1
            blocks.append(Block(BlockType.CODE, '\n'.join(lines[start:i]), start, i - 1, lang=lang))
            continue

        # Display math $$
        if stripped.startswith('$$'):
            start = i
            if stripped == '$$':
                i += 1
                while i < n and lines[i].strip() != '$$':
                    i += 1
                if i < n:
                    i += 1
            else:
                i += 1
            blocks.append(Block(BlockType.MATH, '\n'.join(lines[start:i]), start, i - 1))
            continue

        # Import
        if stripped.startswith('import ') or stripped.startswith('import{'):
            blocks.append(Block(BlockType.IMPORT, stripped, i, i))
            i += 1
            continue

        # Heading
        heading_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            # Extract explicit anchor {#slug}
            anchor_match = re.search(r'\{#([^}]+)\}\s*$', text)
            if anchor_match:
                anchor = anchor_match.group(1)
            else:
                anchor = slugify(text)
            blocks.append(Block(BlockType.HEADING, stripped, i, i, anchor=anchor))
            i += 1
            continue

        # Admonition fence :::
        if stripped.startswith(':::'):
            blocks.append(Block(BlockType.ADMONITION_FENCE, stripped, i, i))
            i += 1
            continue

        # Image ![...](...)
        if re.match(r'^!\[', stripped):
            blocks.append(Block(BlockType.IMAGE, stripped, i, i))
            i += 1
            continue

        # JSX self-closing or opening/closing tag
        if stripped.startswith('<') and not stripped.startswith('<!'):
            # Collect multi-line JSX
            start = i
            jsx_content = stripped
            if not (stripped.endswith('/>') or stripped.endswith('>') or re.search(r'</\w+>\s*$', stripped)):
                i += 1
                while i < n and not (lines[i].strip().endswith('/>') or lines[i].strip().endswith('>') or re.search(r'</\w+>\s*$', lines[i].strip())):
                    i += 1
                if i < n:
                    jsx_content = '\n'.join(lines[start:i + 1])
                    i += 1
                else:
                    jsx_content = '\n'.join(lines[start:i])
            else:
                i += 1
            blocks.append(Block(BlockType.JSX, jsx_content, start, i - 1))
            continue

        # Table row
        if stripped.startswith('|') and stripped.endswith('|'):
            start = i
            while i < n and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                i += 1
            blocks.append(Block(BlockType.TABLE, '\n'.join(lines[start:i]), start, i - 1))
            continue

        # Prose — collect consecutive non-structural lines
        start = i
        while i < n:
            l = lines[i].strip()
            if not l:
                break
            if l.startswith('```') or l.startswith('~~~'):
                break
            if l.startswith('$$'):
                break
            if re.match(r'^#{1,6}\s', l):
                break
            if l.startswith(':::'):
                break
            if l.startswith('import '):
                break
            if l.startswith('<') and not l.startswith('<!'):
                break
            if l.startswith('{/*'):
                break
            if re.match(r'^!\[', l):
                break
            if l.startswith('|') and l.endswith('|'):
                break
            i += 1
        blocks.append(Block(BlockType.PROSE, '\n'.join(lines[start:i]), start, i - 1))

    return blocks


# ══════════════════════════════════════════════════════════════
# Phase 1: Block Alignment
# ══════════════════════════════════════════════════════════════

STRUCTURAL_TYPES = {
    BlockType.HEADING, BlockType.CODE, BlockType.IMPORT,
    BlockType.JSX, BlockType.IMAGE, BlockType.MATH,
    BlockType.COMMENT, BlockType.ADMONITION_FENCE,
}

def align_blocks(en_blocks: list[Block], tr_blocks: list[Block]) -> list[tuple[Block | None, Block | None]]:
    """Align EN and TR blocks using heading anchors as section boundaries,
    then positional matching within sections."""

    # Extract heading indices by anchor
    en_headings = [(i, b) for i, b in enumerate(en_blocks) if b.type == BlockType.HEADING]
    tr_headings = [(i, b) for i, b in enumerate(tr_blocks) if b.type == BlockType.HEADING]

    en_anchor_idx = {b.anchor: i for i, b in en_headings}
    tr_anchor_idx = {b.anchor: i for i, b in tr_headings}

    # Common anchors in EN order
    common = [a for a, _ in en_headings if a in tr_anchor_idx]

    aligned: list[tuple[Block | None, Block | None]] = []

    # Build section boundaries: (en_start, en_end, tr_start, tr_end) pairs
    boundaries = []
    if common:
        # Preamble
        boundaries.append((0, en_anchor_idx[common[0]], 0, tr_anchor_idx[common[0]]))
        for j in range(len(common)):
            en_s = en_anchor_idx[common[j]]
            tr_s = tr_anchor_idx[common[j]]
            if j + 1 < len(common):
                en_e = en_anchor_idx[common[j + 1]]
                tr_e = tr_anchor_idx[common[j + 1]]
            else:
                en_e = len(en_blocks)
                tr_e = len(tr_blocks)
            boundaries.append((en_s, en_e, tr_s, tr_e))
    else:
        boundaries.append((0, len(en_blocks), 0, len(tr_blocks)))

    for en_s, en_e, tr_s, tr_e in boundaries:
        en_sec = en_blocks[en_s:en_e]
        tr_sec = tr_blocks[tr_s:tr_e]
        aligned.extend(_align_section(en_sec, tr_sec))

    # Headings only in EN (added)
    for anchor, idx in en_anchor_idx.items():
        if anchor not in tr_anchor_idx:
            aligned.append((en_blocks[idx], None))

    # Headings only in TR (removed from EN)
    for anchor, idx in tr_anchor_idx.items():
        if anchor not in en_anchor_idx:
            aligned.append((None, tr_blocks[idx]))

    return aligned


def _align_section(en_sec: list[Block], tr_sec: list[Block]) -> list[tuple[Block | None, Block | None]]:
    """Align blocks within a section by type + position."""
    result = []

    # Separate by type
    en_by_type: dict[BlockType, list[Block]] = {}
    tr_by_type: dict[BlockType, list[Block]] = {}
    for b in en_sec:
        en_by_type.setdefault(b.type, []).append(b)
    for b in tr_sec:
        tr_by_type.setdefault(b.type, []).append(b)

    # Match each type by position
    all_types = set(en_by_type) | set(tr_by_type)
    for bt in all_types:
        if bt == BlockType.BLANK:
            continue  # skip blank alignment
        en_list = en_by_type.get(bt, [])
        tr_list = tr_by_type.get(bt, [])
        for j in range(max(len(en_list), len(tr_list))):
            en_b = en_list[j] if j < len(en_list) else None
            tr_b = tr_list[j] if j < len(tr_list) else None
            result.append((en_b, tr_b))

    return result


# ══════════════════════════════════════════════════════════════
# Phase 1: Change Classification
# ══════════════════════════════════════════════════════════════

def _normalize_for_compare(text: str) -> str:
    """Normalize text for comparison — strip whitespace, normalize links."""
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def classify_changes(en_content: str, tr_content: str, rel_path: str) -> ChangeReport:
    """Classify changes between current EN and translation."""
    en_blocks = parse_blocks(en_content)
    tr_blocks = parse_blocks(tr_content)
    aligned = align_blocks(en_blocks, tr_blocks)

    deltas: list[Delta] = []
    prose_lines = 0
    headings_added = []
    headings_removed = []
    current_section = ""

    for en_b, tr_b in aligned:
        # Track current section
        if en_b and en_b.type == BlockType.HEADING:
            current_section = en_b.anchor or ""
        elif tr_b and tr_b.type == BlockType.HEADING:
            current_section = tr_b.anchor or ""

        # Both exist — check for differences
        if en_b and tr_b:
            if en_b.type == BlockType.CODE:
                en_norm = _normalize_for_compare(en_b.content)
                tr_norm = _normalize_for_compare(tr_b.content)
                if en_norm != tr_norm:
                    deltas.append(Delta("code_changed", en_b, tr_b, current_section, auto_fixable=True))

            elif en_b.type == BlockType.IMPORT:
                if en_b.content.strip() != tr_b.content.strip():
                    deltas.append(Delta("import_changed", en_b, tr_b, current_section, auto_fixable=True))

            elif en_b.type == BlockType.IMAGE:
                if en_b.content != tr_b.content:
                    deltas.append(Delta("image_changed", en_b, tr_b, current_section, auto_fixable=True))

            elif en_b.type == BlockType.HEADING:
                # Headings are always translated — we can't easily detect EN heading text change
                # without old EN. Skip unless anchor differs.
                pass

            elif en_b.type == BlockType.PROSE:
                # Prose: we can't directly compare (TR is in another language).
                # But if EN prose is identical to TR prose, it means it was never translated
                # (fallback). Otherwise we can't detect change without old EN.
                # For now: prose blocks are NOT flagged as changed unless adjacent to
                # a structural change.
                pass

            elif en_b.type == BlockType.FRONTMATTER:
                # Compare preserved keys
                en_fm = validator.parse_frontmatter(en_b.content + '\n')
                tr_fm = validator.parse_frontmatter(tr_b.content + '\n')
                for key in ('notebook_path', 'slug', 'platform'):
                    if en_fm.get(key) != tr_fm.get(key):
                        deltas.append(Delta("frontmatter_changed", en_b, tr_b, current_section, auto_fixable=True))
                        break

            elif en_b.type == BlockType.JSX:
                if _normalize_for_compare(en_b.content) != _normalize_for_compare(tr_b.content):
                    # JSX structural change — may be auto-fixable if only attributes changed
                    deltas.append(Delta("jsx_changed", en_b, tr_b, current_section, auto_fixable=True))

        # Only in EN — added content
        elif en_b and not tr_b:
            if en_b.type == BlockType.HEADING:
                headings_added.append(en_b.anchor or en_b.content)
            if en_b.type in (BlockType.PROSE, BlockType.HEADING):
                prose_lines += len(en_b.content.split('\n'))
                deltas.append(Delta("added", en_b, None, current_section, auto_fixable=False))
            else:
                deltas.append(Delta("added", en_b, None, current_section, auto_fixable=True))

        # Only in TR — removed from EN
        elif tr_b and not en_b:
            if tr_b.type == BlockType.HEADING:
                headings_removed.append(tr_b.anchor or tr_b.content)
            deltas.append(Delta("removed", None, tr_b, current_section, auto_fixable=False))

    # Now use a heuristic: sections containing structural changes likely have prose changes too.
    # Mark prose blocks in those sections as potentially stale.
    changed_sections = {d.section_anchor for d in deltas}
    for en_b, tr_b in aligned:
        if en_b and tr_b and en_b.type == BlockType.PROSE:
            section = ""
            # Find containing section
            for d in deltas:
                if d.section_anchor:
                    section = d.section_anchor
                    break
            # If this prose is in a section with structural changes, flag it
            if en_b.anchor in changed_sections or section in changed_sections:
                # Only flag if not already counted
                if not any(d.en_block is en_b for d in deltas):
                    prose_lines += len(en_b.content.split('\n'))
                    deltas.append(Delta("prose_changed", en_b, tr_b, section, auto_fixable=False))

    # Compute severity
    if not deltas:
        severity = Severity.NOOP
    elif all(d.auto_fixable for d in deltas):
        severity = Severity.NOOP
    elif headings_added or headings_removed:
        severity = Severity.MAJOR if prose_lines > 100 else Severity.MODERATE
    elif prose_lines <= 5:
        severity = Severity.MINOR
    elif prose_lines <= 100:
        severity = Severity.MODERATE
    else:
        severity = Severity.MAJOR

    return ChangeReport(
        rel_path=rel_path,
        severity=severity,
        deltas=deltas,
        prose_lines_changed=prose_lines,
        headings_added=headings_added,
        headings_removed=headings_removed,
        en_hash=compute_source_hash(en_content),
    )


# ══════════════════════════════════════════════════════════════
# Phase 2: Auto-Fixer
# ══════════════════════════════════════════════════════════════

def apply_auto_fixes(en_content: str, tr_content: str, report: ChangeReport) -> tuple[str, list[str]]:
    """Apply automatic fixes. Returns (fixed_content, list_of_descriptions)."""
    fixed = tr_content
    fixes = []

    # 1. Sync code blocks
    result = syncer.fix_differing_code_blocks(en_content, fixed)
    if result:
        fixed = result
        fixes.append("synced code blocks")

    # 2. Sync pip install
    result = syncer.fix_missing_pip_install(en_content, fixed)
    if result:
        fixed = result
        fixes.append("synced pip install block")

    # 3. Sync imports
    en_imports = set(re.findall(r'^import\s+.+$', en_content, re.MULTILINE))
    tr_imports = set(re.findall(r'^import\s+.+$', fixed, re.MULTILINE))
    missing = en_imports - tr_imports
    extra = tr_imports - en_imports
    if missing or extra:
        # Add missing imports after frontmatter
        for imp in missing:
            # Insert after the last import or after frontmatter
            last_import = -1
            for m in re.finditer(r'^import\s+.+$', fixed, re.MULTILINE):
                last_import = m.end()
            if last_import >= 0:
                fixed = fixed[:last_import] + '\n' + imp + fixed[last_import:]
            else:
                # After frontmatter
                fm_end = fixed.find('---', fixed.find('---') + 1)
                if fm_end >= 0:
                    fm_end = fixed.index('\n', fm_end) + 1
                    fixed = fixed[:fm_end] + imp + '\n' + fixed[fm_end:]
        # Remove extra imports
        for imp in extra:
            fixed = fixed.replace(imp + '\n', '')
        if missing:
            fixes.append(f"added {len(missing)} import(s)")
        if extra:
            fixes.append(f"removed {len(extra)} import(s)")

    # 4. Sync image paths
    en_images = dict(validator.extract_image_paths(en_content))
    tr_images = dict(validator.extract_image_paths(fixed))
    for line_num, path in tr_images.items():
        # Find corresponding EN image by position
        pass  # TODO: positional image sync

    # 5. Update link URLs (keep translated text, replace URL)
    en_links = validator.extract_link_urls(en_content)
    tr_links = validator.extract_link_urls(fixed)
    # Link sync is complex — skip for now, handle in validate step

    # 6. Update source hash
    new_hash = compute_source_hash(en_content)
    embedded = extract_embedded_hash(fixed)
    if embedded:
        fixed = re.sub(
            r'\{/\*\s*doqumentation-source-hash:\s*[a-f0-9]+\s*\*/\}',
            f'{{/* doqumentation-source-hash: {new_hash} */}}',
            fixed
        )
        fixes.append(f"updated source hash to {new_hash}")
    elif fixes:  # Only add hash if we made other fixes
        fixed = insert_hash_after_frontmatter(fixed, new_hash)
        fixes.append(f"added source hash {new_hash}")

    return fixed, fixes


# ══════════════════════════════════════════════════════════════
# Phase 3: Workfile Generator
# ══════════════════════════════════════════════════════════════

def generate_update_instructions(en_content: str, tr_content: str, report: ChangeReport) -> list[UpdateInstruction]:
    """Generate per-paragraph update instructions for translation agents."""
    instructions = []

    for delta in report.deltas:
        if delta.auto_fixable:
            continue
        if delta.kind in ("added", "prose_changed") and delta.en_block:
            en_block = delta.en_block
            tr_text = delta.tr_block.content if delta.tr_block else "(new — no existing translation)"

            instructions.append(UpdateInstruction(
                section_anchor=delta.section_anchor,
                paragraph_index=0,
                new_en_prose=en_block.content,
                current_translation=tr_text,
                context_before="",  # TODO: extract surrounding context
                context_after="",
            ))

    return instructions


def build_workfile(items: list[FileWorkItem], locale: str) -> dict:
    """Build the JSON workfile structure."""
    minor_moderate = [i for i in items if not i.full_retranslation and i.updates]
    major = [i for i in items if i.full_retranslation]
    noop = [i for i in items if not i.updates and not i.full_retranslation]

    return {
        "locale": locale,
        "generated": str(date.today()),
        "files": [
            {
                "path": item.rel_path,
                "severity": item.severity,
                "auto_fixes_applied": item.auto_fixes,
                "updates": [
                    {
                        "section": u.section_anchor,
                        "paragraph_index": u.paragraph_index,
                        "new_en": u.new_en_prose,
                        "current_translation": u.current_translation,
                        "context_before": u.context_before,
                        "context_after": u.context_after,
                    }
                    for u in item.updates
                ],
            }
            for item in minor_moderate
        ],
        "full_retranslation": [item.rel_path for item in major],
        "stats": {
            "total_stale": len(items),
            "noop_auto_fixed": len(noop),
            "minor_updates": len([i for i in items if i.severity == "minor"]),
            "moderate_updates": len([i for i in items if i.severity == "moderate"]),
            "major_retranslation": len(major),
        },
    }


# ══════════════════════════════════════════════════════════════
# Orchestration
# ══════════════════════════════════════════════════════════════

def get_en_path(rel_path: str) -> Path:
    """Get the English source path for a relative path."""
    # Content is in docs/ (generated by sync-content.py)
    candidates = [
        DOCS_DIR / rel_path,
        DOCS_DIR / "tutorials" / rel_path,
        DOCS_DIR / "guides" / rel_path,
        DOCS_DIR / "learning" / rel_path,
    ]
    for p in candidates:
        if p.exists():
            return p
    return DOCS_DIR / rel_path


def get_tr_path(locale: str, rel_path: str) -> Path:
    """Get the translation path."""
    return I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel_path


def find_stale_translations(locale: str, section: str | None = None) -> list[tuple[str, Path, Path]]:
    """Find translations whose source hash doesn't match current EN."""
    pairs = find_genuine_translations(locale)
    stale = []
    for en_path, tr_path in pairs:
        # Filter by section if specified
        rel = str(tr_path.relative_to(I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"))
        if section and not rel.startswith(section):
            continue

        en_content = en_path.read_text(encoding='utf-8')
        tr_content = tr_path.read_text(encoding='utf-8')

        current_hash = compute_source_hash(en_content)
        embedded_hash = extract_embedded_hash(tr_content)

        if embedded_hash and embedded_hash != current_hash:
            stale.append((rel, en_path, tr_path))

    return stale


def process_file(en_path: Path, tr_path: Path, rel_path: str,
                 auto_fix: bool = False, verbose: bool = False) -> FileWorkItem:
    """Process a single stale translation file."""
    en_content = en_path.read_text(encoding='utf-8')
    tr_content = tr_path.read_text(encoding='utf-8')

    # Classify changes
    report = classify_changes(en_content, tr_content, rel_path)

    if verbose:
        print(f"  {rel_path}: {report.severity.value} "
              f"({len(report.deltas)} deltas, {report.prose_lines_changed} prose lines)")
        if report.headings_added:
            print(f"    Headings added: {report.headings_added}")
        if report.headings_removed:
            print(f"    Headings removed: {report.headings_removed}")
        for d in report.deltas:
            fix_tag = " [auto-fix]" if d.auto_fixable else ""
            print(f"    {d.kind}{fix_tag} in §{d.section_anchor}")

    # Auto-fix
    fixes = []
    if auto_fix and report.deltas:
        fixed_content, fixes = apply_auto_fixes(en_content, tr_content, report)
        if fixes:
            tr_path.write_text(fixed_content, encoding='utf-8')
            if verbose:
                print(f"    Auto-fixed: {', '.join(fixes)}")
            # Re-classify after fixes
            tr_content = fixed_content
            report = classify_changes(en_content, tr_content, rel_path)

    # Generate update instructions for non-NOOP files
    updates = []
    full_retranslation = False
    if report.severity == Severity.MAJOR:
        full_retranslation = True
    elif report.severity in (Severity.MINOR, Severity.MODERATE):
        updates = generate_update_instructions(en_content, tr_content, report)

    return FileWorkItem(
        rel_path=rel_path,
        severity=report.severity.value,
        auto_fixes=fixes,
        updates=updates,
        full_retranslation=full_retranslation,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Detect and process stale translations with minimal retranslation"
    )
    parser.add_argument("--locale", required=True, help="Locale code (e.g. de, es)")
    parser.add_argument("--file", help="Process a single file (relative path)")
    parser.add_argument("--section", help="Filter by section (guides, tutorials, learning)")

    parser.add_argument("--analyze", action="store_true", help="Analyze and report (no modifications)")
    parser.add_argument("--auto-fix", action="store_true", help="Apply auto-fixes (code, imports, links)")
    parser.add_argument("--generate-workfile", action="store_true", help="Generate workfile for agents")

    parser.add_argument("--output", help="Output path for workfile JSON")
    parser.add_argument("--dry-run", action="store_true", help="Don't write any files")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    if not any([args.analyze, args.auto_fix, args.generate_workfile]):
        args.analyze = True

    # Find stale files
    if args.file:
        en_path = get_en_path(args.file)
        tr_path = get_tr_path(args.locale, args.file)
        if not en_path.exists():
            print(f"EN file not found: {en_path}", file=sys.stderr)
            sys.exit(1)
        if not tr_path.exists():
            print(f"Translation not found: {tr_path}", file=sys.stderr)
            sys.exit(1)
        stale = [(args.file, en_path, tr_path)]
    else:
        print(f"Scanning {args.locale} for stale translations...")
        stale = find_stale_translations(args.locale, args.section)
        print(f"Found {len(stale)} stale file(s)")

    if not stale:
        print("No stale translations found.")
        return

    # Process each file
    items: list[FileWorkItem] = []
    counts = {"noop": 0, "minor": 0, "moderate": 0, "major": 0}

    for rel_path, en_path, tr_path in stale:
        item = process_file(
            en_path, tr_path, rel_path,
            auto_fix=args.auto_fix and not args.dry_run,
            verbose=args.verbose,
        )
        items.append(item)
        counts[item.severity] += 1

    # Summary
    print(f"\n{'═' * 60}")
    print(f"Locale: {args.locale}  |  Total stale: {len(stale)}")
    print(f"  NOOP (auto-fixable):  {counts['noop']}")
    print(f"  MINOR (≤5 lines):     {counts['minor']}")
    print(f"  MODERATE (6-100):     {counts['moderate']}")
    print(f"  MAJOR (>100/struct):  {counts['major']}")
    print(f"{'═' * 60}")

    # Generate workfile
    if args.generate_workfile:
        workfile = build_workfile(items, args.locale)
        output_path = args.output or f"translation/workfiles/{args.locale}.json"
        if not args.dry_run:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(workfile, f, indent=2, ensure_ascii=False)
            print(f"\nWorkfile written to {output_path}")
        else:
            print(f"\n[dry-run] Would write workfile to {output_path}")
            print(json.dumps(workfile["stats"], indent=2))


if __name__ == "__main__":
    main()
