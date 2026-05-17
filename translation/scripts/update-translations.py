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

# passage_units has a valid (non-hyphenated) module name — import normally so
# it's the *same* object the rest of the toolchain uses (validate-translation,
# bootstrap-passage-hashes, review-translations). The baseline-hashes.json
# sidecar is keyed by hashes this module produces; we MUST hash with it.
sys.path.insert(0, str(SCRIPT_DIR))
import passage_units  # noqa: E402

# Re-export key functions
compute_source_hash = freshness.compute_source_hash
extract_embedded_hash = freshness.extract_embedded_hash
insert_hash_after_frontmatter = freshness.insert_hash_after_frontmatter
find_genuine_translations = freshness.find_genuine_translations
slugify = validator.slugify

# ── Constants ──

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
I18N_DIR = Path(__file__).resolve().parents[2] / "i18n"
BASELINE_FILE = Path(__file__).resolve().parents[1] / "baseline-hashes.json"

FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"
HASH_COMMENT_RE = re.compile(r'\{/\*\s*doqumentation-source-hash:\s*([a-f0-9]+)\s*\*/\}')


# ── Exact EN change detection via git diff ──
#
# The earlier implementation inferred prose changes from a passage-hash set
# difference vs baseline-hashes.json. That is indirect reconstruction of a
# diff git already computes exactly, and it produced 7 distinct bug classes
# (false positives, truncation, premature hash bump, restructure blindness,
# structural-drift blindness). Instead, recover the EXACT old EN and let git
# diff it against the current EN.
#
# Old-EN recovery (see memory project_en_static_until_sync):
#   1. baseline-hashes.json records the commit the translation was made at.
#      `git show <commit>:docs/<path>` gives that exact old EN.
#   2. ~38% of baseline commits predate docs/ being git-tracked (2026-03-11,
#      commit 5893de729). For those the blob is missing — but EN content was
#      byte-identical from 2026-03-11 until the single sync commit
#      9f2948310 (verified: git diff 5893de729 9f2948310^ -- docs/... is
#      empty). So the exact old EN is `git show <PRE_SYNC>:docs/<path>`.
#
# This inherently captures structural changes (Admonition→:::, heading
# renames, added/removed sections) because they are literally in the diff.

_BASELINE_CACHE: dict | None = None

# Parent of the upstream-sync commit (#62, 6f006d7a7 → 833ab77dc). EN was
# byte-static from first-tracked (5893de729, 2026-03-11) through this commit,
# so it is the exact old-EN for any baseline that predates docs/ tracking.
SYNC_COMMIT = "9f29483105b21a91d0b3abf0ba9cfd735a084b9b"
PRE_SYNC_REF = f"{SYNC_COMMIT}^"

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_baselines() -> dict:
    global _BASELINE_CACHE
    if _BASELINE_CACHE is None:
        if BASELINE_FILE.exists():
            _BASELINE_CACHE = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        else:
            _BASELINE_CACHE = {}
    return _BASELINE_CACHE


def _git_show(ref: str, repo_rel: str) -> str | None:
    """Return file content at a git ref, or None if the blob doesn't exist."""
    import subprocess
    r = subprocess.run(
        ["git", "show", f"{ref}:{repo_rel}"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    return r.stdout if r.returncode == 0 else None


def old_en_content(locale: str, rel_path: str) -> tuple[str | None, str]:
    """Recover the exact EN the translation was made against.

    Returns (content, source) where source describes provenance for logs.
    content is None only if neither the baseline commit nor the pre-sync
    snapshot has the blob (genuinely new file → caller full-retranslates).
    """
    docs_rel = f"docs/{rel_path}"
    sidecar = _load_baselines().get(f"{locale}/{rel_path}")
    commit = sidecar.get("commit") if sidecar else None
    if commit:
        c = _git_show(commit, docs_rel)
        if c is not None:
            return c, f"baseline {commit[:8]}"
    # Fallback: pre-sync snapshot (exact — EN was static pre-sync).
    c = _git_show(PRE_SYNC_REF, docs_rel)
    if c is not None:
        return c, f"pre-sync {PRE_SYNC_REF[:8]}"
    return None, "no historical EN (new file)"


def en_change(locale: str, rel_path: str, en_content: str):
    """Return (hunks, old_found, n_changed_lines).

    hunks: list of unified-diff hunk strings (old EN → current EN). Empty
           list with old_found=True means EN is unchanged (NOOP — only
           structural/whitespace drift handled by auto-fix).
    old_found: False when no historical EN exists (new file / rename) —
           caller treats as full retranslation.
    n_changed_lines: count of +/- content lines across all hunks (drives
           severity).
    """
    old_en, _src = old_en_content(locale, rel_path)
    if old_en is None:
        return [], False, 0
    if old_en == en_content:
        return [], True, 0
    import difflib
    # n=5: more context than the default 3 so a sub-agent can uniquely
    # locate the target-language region even when a changed sentence is
    # near-duplicated (lists, tables, repeated boilerplate).
    diff = list(difflib.unified_diff(
        old_en.splitlines(), en_content.splitlines(),
        lineterm="", n=5,
    ))
    # Group into hunks (each starts at an @@ line).
    hunks: list[str] = []
    cur: list[str] = []
    n_changed = 0
    for line in diff:
        if line.startswith("@@"):
            if cur:
                hunks.append("\n".join(cur))
            cur = [line]
        elif line.startswith(("---", "+++")):
            continue
        else:
            if cur:
                cur.append(line)
            if line[:1] in "+-" and line[:2] not in ("+ ", "- "):
                n_changed += 1
    if cur:
        hunks.append("\n".join(cur))
    return hunks, True, n_changed

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

        # Other comments {/* ... */} — single-line or multi-line
        if stripped.startswith('{/*'):
            start = i
            # Single-line comment closes on the same line
            if stripped.endswith('*/}'):
                blocks.append(Block(BlockType.COMMENT, stripped, i, i))
                i += 1
                continue
            # Multi-line comment: consume until the closing */}
            i += 1
            while i < n and not lines[i].strip().endswith('*/}'):
                i += 1
            if i < n:  # include the closing line
                i += 1
            blocks.append(Block(BlockType.COMMENT, '\n'.join(lines[start:i]), start, i - 1))
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
        # Defensive: never emit a zero-length prose block — that would leave i
        # unchanged and spin the outer loop forever. If the first line already
        # hit a break condition, consume it as a 1-line prose block.
        if i == start:
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

    # NOTE: severity is NOT decided here. classify_changes can only see
    # structural deltas (code/imports), not prose change — the old prose-
    # line heuristic that lived here produced 7 bug classes (see git log
    # for the #71-#75 fixes) and was superseded by the exact git-diff in
    # en_change(). process_file OVERWRITES report.severity from the git
    # diff. This placeholder keeps the dataclass valid; nothing reads it.
    severity = Severity.NOOP

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

    # NOTE: the source-hash bump is intentionally NOT done here. Bumping the
    # hash marks the file fresh; doing that during auto-fix would mark a file
    # done while its prose is still stale, so next week's freshness check
    # skips it and the genuine prose changes are silently lost. The hash is
    # advanced in process_file ONLY when the file is fully synced (no
    # remaining changed passages, no full retranslation) — see bump_source_hash.
    return fixed, fixes


def bump_source_hash(content: str, en_content: str) -> str:
    """Advance the embedded source-hash marker to the current EN hash.

    Call this ONLY when the translation is fully in sync with EN — i.e.
    after prose updates are applied (or when the only drift was structural
    and already auto-fixed). Bumping prematurely hides stale prose from the
    weekly freshness check.
    """
    new_hash = compute_source_hash(en_content)
    if extract_embedded_hash(content):
        return re.sub(
            r'\{/\*\s*doqumentation-source-hash:\s*[a-f0-9]+\s*\*/\}',
            f'{{/* doqumentation-source-hash: {new_hash} */}}',
            content,
        )
    return insert_hash_after_frontmatter(content, new_hash)


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


def locale_of(tr_path: Path) -> str:
    """Extract the locale from a translation path (.../i18n/{locale}/...)."""
    parts = tr_path.resolve().parts
    return parts[parts.index("i18n") + 1]


def _paths_in_open_pr_branches(locale: str) -> set[str]:
    """Rel paths already touched by an unmerged refresh branch for this locale.

    Parallel batches branch from different main states and force-add i18n/
    paths. A file already refreshed in an open PR branch still reads as STALE
    on the current branch (freshness checks i18n/ on disk), so re-translating
    it duplicates work and causes rebase conflicts (this bit batch #80). Skip
    those paths.
    """
    import subprocess
    try:
        br = subprocess.run(
            ["git", "branch", "-r", "--list", "origin/i18n/*refresh*"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        ).stdout.split()
    except Exception:
        return set()
    prefix = f"i18n/{locale}/docusaurus-plugin-content-docs/current/"
    touched: set[str] = set()
    for b in br:
        b = b.strip()
        if not b:
            continue
        try:
            files = subprocess.run(
                ["git", "diff", "--name-only", f"origin/main...{b}"],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            ).stdout.splitlines()
        except Exception:
            continue
        for f in files:
            if f.startswith(prefix):
                touched.add(f[len(prefix):])
    return touched


def _manifest_finalized(locale: str) -> set[str]:
    """Rel paths already marked 'finalized' in the durable batch manifest
    (item G) — skip them so multi-session scaling is resumable."""
    mpath = MANIFEST_DIR / f"{locale}.json"
    if not mpath.exists():
        return set()
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {r for r, v in data.get("files", {}).items()
            if v.get("status") == "finalized"}


def find_stale_translations(locale: str, section: str | None = None,
                            exclude_open_prs: bool = False,
                            skip_manifest_done: bool = False) -> list[tuple[str, Path, Path]]:
    """Find translations whose source hash doesn't match current EN.

    exclude_open_prs: skip files already refreshed in an open PR branch for
    this locale (prevents duplicate work / rebase conflicts in parallel
    batches).
    skip_manifest_done: also skip files already 'finalized' in the durable
    manifest (resumable multi-session scaling).
    """
    pairs = find_genuine_translations(locale)
    skip = _paths_in_open_pr_branches(locale) if exclude_open_prs else set()
    if skip_manifest_done:
        skip |= _manifest_finalized(locale)
    stale = []
    for en_path, tr_path in pairs:
        # Filter by section if specified
        rel = str(tr_path.relative_to(I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"))
        if section and not rel.startswith(section):
            continue
        if rel in skip:
            continue

        en_content = en_path.read_text(encoding='utf-8')
        tr_content = tr_path.read_text(encoding='utf-8')

        current_hash = compute_source_hash(en_content)
        embedded_hash = extract_embedded_hash(tr_content)

        if embedded_hash and embedded_hash != current_hash:
            stale.append((rel, en_path, tr_path))

    return stale


_anchor_fixer = None
_file_validator = None


def _lazy_finalize_helpers():
    """Import fix-heading-anchors + validate-translation once (hyphenated)."""
    global _anchor_fixer, _file_validator
    if _anchor_fixer is None:
        _anchor_fixer = _import_module("anchor_fixer", "fix-heading-anchors.py")
    if _file_validator is None:
        _file_validator = validator  # already imported at top (validate-translation.py)
    return _anchor_fixer, _file_validator


def finalize_files(locale: str, rel_paths: list[str], output_dir: Path,
                   verbose: bool = False) -> tuple[list[str], list[str]]:
    """Per file: pin English-derived heading anchors, validate, and bump the
    source hash ONLY if validation passes.

    Returns (finalized, failed). Failures are written to
    <output_dir>/_finalize_failures.txt so they can be reworked by an agent
    instead of silently shipping broken. This is what makes the weekly cron
    self-policing — the manual validate loop is no longer required.
    """
    anchor_fixer, fv = _lazy_finalize_helpers()
    finalized: list[str] = []
    failed: list[tuple[str, str]] = []
    for rel in rel_paths:
        en_path = get_en_path(rel)
        tr_path = get_tr_path(locale, rel)
        if not en_path.exists() or not tr_path.exists():
            failed.append((rel, "missing en/tr file"))
            continue
        # 1. Deterministically pin English-derived {#anchor} on every heading.
        try:
            anchor_fixer.fix_file(en_path, tr_path, apply=True)
        except Exception as e:
            failed.append((rel, f"anchor-fix error: {e}"))
            continue
        # 2. Validate.
        try:
            report = fv.validate_file(en_path, tr_path, locale)
        except Exception as e:
            failed.append((rel, f"validate error: {e}"))
            continue
        if not report.passed:
            reasons = "; ".join(
                f"{c.name}" for c in report.checks if not c.passed
            )
            failed.append((rel, f"FAIL: {reasons}"))
            if verbose:
                print(f"  ✗ {rel}: {reasons}")
            continue
        # 2b. CONTENT GATE (item F): structural PASS is not enough. A
        # sub-agent can claim "Done" yet silently miss a prose hunk — the
        # file then validates structurally but stays STALE, and bumping the
        # hash would lock that staleness in forever (the #73 silent-data-
        # loss class, re-entering through the agent layer). Defend against
        # it: for every non-cosmetic removed EN line in the diff, that exact
        # OLD English text must NOT still be present verbatim in the
        # translation (its presence means the hunk was never applied — the
        # translator left the old English in place or didn't touch it).
        tr_content = tr_path.read_text(encoding="utf-8")
        en_content = en_path.read_text(encoding="utf-8")
        hunks, old_found, _ = en_change(locale, rel, en_content)
        if old_found and hunks:
            stale_evidence = []
            for h in hunks:
                # Track code-fence state WITHIN the hunk. A `-` line inside a
                # code block is byte-identical English in the translation by
                # design (code is never translated) — its presence in TR is
                # correct, not an unapplied hunk. Only PROSE removals count.
                in_code = False
                for ln in h.splitlines():
                    body = ln[1:] if ln[:1] in "+- " else ln
                    if body.lstrip().startswith("```"):
                        # fence toggles on context/added/removed alike
                        in_code = not in_code
                        continue
                    if ln[:1] != "-" or ln[:2] == "- ":
                        continue
                    if in_code:
                        continue
                    removed = ln[1:].strip()
                    # ignore trivial/cosmetic lines (blank, pure markup,
                    # very short) — those legitimately need no TR change
                    if len(removed) < 12:
                        continue
                    if removed.startswith(("```", "$$", "import ", "<", "|", "{/*")):
                        continue
                    # CRITICAL: only flag a line that is GENUINELY removed —
                    # absent from the current EN. unified_diff also emits a
                    # line as `-` when it's merely relocated/reformatted
                    # context; if it still exists in current EN it was never
                    # really removed, so its presence in TR (as kept English
                    # or as the basis of an unchanged translation) is not
                    # evidence of a skipped hunk. This was a real false
                    # positive on code lines like `from qiskit import ...`.
                    if removed in en_content:
                        continue
                    if removed in tr_content:
                        stale_evidence.append(removed[:60])
                        break
                if stale_evidence:
                    break
            if stale_evidence:
                failed.append((
                    rel,
                    f"CONTENT: old EN still present (hunk not applied): "
                    f"{stale_evidence[0]!r}",
                ))
                if verbose:
                    print(f"  ✗ {rel}: stale — old EN still in file")
                continue
        # 3. PASS (structure + content) → bump source hash → reads FRESH.
        bumped = bump_source_hash(tr_content, en_content)
        if bumped != tr_content:
            tr_path.write_text(bumped, encoding="utf-8")
        finalized.append(rel)
        if verbose:
            print(f"  ✓ {rel}")
    if failed:
        fpath = output_dir / "_finalize_failures.txt"
        output_dir.mkdir(parents=True, exist_ok=True)
        fpath.write_text(
            "\n".join(f"{r}\t{why}" for r, why in failed) + "\n",
            encoding="utf-8",
        )
        print(f"\n⚠ {len(failed)} file(s) failed finalize → {fpath}")

    # Item G: durable batch manifest. Merge into translation/manifests/
    # {locale}.json so multi-session / weekly-cron scaling is resumable
    # and doesn't rely on /tmp scratch files. Records per-file status +
    # the timestamp; PR number can be patched in by the caller.
    _write_manifest(locale, finalized, dict(failed))
    return finalized, [r for r, _ in failed]


MANIFEST_DIR = Path(__file__).resolve().parents[1] / "manifests"


def _write_manifest(locale: str, finalized: list[str],
                    failed: dict[str, str]) -> None:
    from datetime import datetime, timezone
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    mpath = MANIFEST_DIR / f"{locale}.json"
    data: dict = {}
    if mpath.exists():
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    files = data.setdefault("files", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for rel in finalized:
        files[rel] = {"status": "finalized", "ts": now,
                      "pr": files.get(rel, {}).get("pr")}
    for rel, why in failed.items():
        files[rel] = {"status": "failed", "reason": why, "ts": now,
                      "pr": files.get(rel, {}).get("pr")}
    data["locale"] = locale
    data["updated"] = now
    mpath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"  manifest → {mpath} "
          f"({sum(1 for v in files.values() if v['status']=='finalized')} finalized, "
          f"{sum(1 for v in files.values() if v['status']=='failed')} failed total)")


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

    # Auto-fix (structural only: code blocks, imports, source hash). This part
    # of classify_changes is correct — it compares structural blocks directly.
    fixes = []
    if auto_fix and report.deltas:
        fixed_content, fixes = apply_auto_fixes(en_content, tr_content, report)
        if fixes:
            tr_path.write_text(fixed_content, encoding='utf-8')
            if verbose:
                print(f"    Auto-fixed: {', '.join(fixes)}")
            tr_content = fixed_content

    # ── Exact EN change via git diff (old EN → current EN) ──
    # No inference: recover the precise EN the translation was made against
    # and diff it. Hunks include structural changes (Admonition→:::, heading
    # renames, added/removed sections) verbatim, so the sub-agent mirrors
    # exactly what changed.
    hunks, old_found, n_changed = en_change(locale_of(tr_path), rel_path, en_content)

    updates = []
    full_retranslation = False

    if not old_found:
        # No historical EN (new file / rename) → can't diff. Whole-file
        # translate via translation-prompt.md.
        full_retranslation = True
        report.severity = Severity.MAJOR
    elif not hunks:
        # EN identical to the old snapshot → only structural/whitespace
        # drift, already handled by auto-fix. Nothing for a translator.
        report.severity = Severity.NOOP
    elif n_changed > 120:
        # Very large EN change → splicing dozens of hunks is error-prone and
        # the page likely restructured. Whole-file retranslate.
        full_retranslation = True
        report.severity = Severity.MAJOR
    else:
        # Each hunk is one work item: the exact old→new EN region. The
        # sub-agent finds the corresponding translated region (by the
        # context lines + removed EN lines) and rewrites it to match the
        # added EN lines, in the target language.
        report.severity = (
            Severity.MINOR if n_changed <= 12 else Severity.MODERATE
        )
        updates = [
            UpdateInstruction(
                section_anchor="",
                paragraph_index=idx,
                new_en_prose=hunk,        # the unified-diff hunk itself
                current_translation="",   # sub-agent locates via hunk context
                context_before="",
                context_after="",
            )
            for idx, hunk in enumerate(hunks)
        ]

    # Advance the source hash ONLY when the file is now fully in sync with
    # EN: structural drift was auto-fixed and there is no remaining prose to
    # translate. If prose updates remain (or whole-file retranslation is
    # needed), leave the old hash so the weekly freshness check keeps
    # flagging this file until a translator actually refreshes it. The hash
    # is bumped post-prose in the workflow's finalize step instead.
    if auto_fix and not updates and not full_retranslation:
        synced = bump_source_hash(tr_content, en_content)
        if synced != tr_content:
            tr_path.write_text(synced, encoding='utf-8')
            tr_content = synced
            fixes.append(f"bumped source hash (file fully synced)")
            if verbose:
                print(f"    Source hash advanced (no prose drift remaining)")

    if verbose:
        tag = "MAJOR/full" if full_retranslation else report.severity.value
        nupd = "n/a" if not old_found else f"{len(hunks)} hunk(s), {n_changed} lines"
        print(f"    -> {tag}: {nupd}")

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
    parser.add_argument("--exclude-open-prs", action="store_true",
                        help="Skip files already refreshed in an open i18n/*refresh* PR branch")
    parser.add_argument("--finalize", action="store_true",
                        help="Per file: pin English-derived heading anchors, validate "
                             "(structure + content), and bump the source hash ONLY if "
                             "both pass. Writes failures to "
                             "<output-dir>/_finalize_failures.txt and a durable "
                             "translation/manifests/<locale>.json.")
    parser.add_argument("--skip-manifest-done", action="store_true",
                        help="Skip files already 'finalized' in "
                             "translation/manifests/<locale>.json (resumable scaling)")
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
        stale = find_stale_translations(args.locale, args.section,
                                        exclude_open_prs=args.exclude_open_prs,
                                        skip_manifest_done=args.skip_manifest_done)
        print(f"Found {len(stale)} stale file(s)")

    if not stale:
        print("No stale translations found.")
        return

    # Finalize mode: pin anchors → validate → bump hash only if PASS.
    if args.finalize:
        out_dir = Path(args.output).parent if args.output else Path("translation/workfiles")
        rels = [rel for rel, _, _ in stale]
        finalized, failed = finalize_files(args.locale, rels, out_dir,
                                           verbose=args.verbose)
        print(f"\n{'═' * 60}")
        print(f"Finalize: {len(finalized)} passed & hash-bumped, "
              f"{len(failed)} failed (see _finalize_failures.txt)")
        print(f"{'═' * 60}")
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
