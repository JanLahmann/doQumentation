#!/usr/bin/env python3
"""
Validate translated MDX files against their English source.

Performs strict structural checks to ensure translations preserve code blocks,
LaTeX, headings, image paths, JSX tags, link URLs, and frontmatter exactly.
Also detects paragraph inflation (word salad) and fallback markers.

Every check is binary PASS/FAIL — no warnings. Any single FAIL = file FAIL.

Usage:
    python translation/scripts/validate-translation.py --locale es                          # all genuine translations
    python translation/scripts/validate-translation.py --locale es --file guides/foo.mdx    # single file
    python translation/scripts/validate-translation.py --locale es -v                       # verbose output
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "th", "ar", "he",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

# Locales where word-count heuristics don't work (no space-delimited words)
NO_WORDCOUNT_LOCALES = {"ja", "th"}

# JSX/React components used in the docs
JSX_COMPONENTS = [
    "Admonition", "OpenInLabBanner", "CodeAssistantAdmonition",
    "Tabs", "TabItem", "Card", "CardGroup", "OperatingSystemTabs",
    "IBMVideo", "DefinitionTooltip", "Figure", "LaunchExamButton",
]

# Frontmatter keys that MUST be preserved byte-identical
FRONTMATTER_PRESERVE_KEYS = ["notebook_path", "slug", "platform"]
# Frontmatter keys that SHOULD be translated (differ from EN)
FRONTMATTER_TRANSLATE_KEYS = ["title", "description", "sidebar_label"]
# Frontmatter values that are legitimately the same across languages
# (brand names, universal phrases, proper nouns)
FRONTMATTER_SAME_ALLOWED = {
    "doqumentation", "hello world", "guides", "tutorials", "courses", "modules",
    "overview",
}

# Regex from fix-heading-anchors.py
EXISTING_ANCHOR_RE = re.compile(r'\s*\{#[\w-]+\}\s*$')

# Paragraph inflation threshold
MAX_WORD_RATIO = 1.8

# Line count tolerance
MAX_LINE_DELTA_PCT = 5

# ---------------------------------------------------------------------------
# slugify() — copied from fix-heading-anchors.py for standalone use
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert heading text to Docusaurus-style anchor slug."""
    s = EXISTING_ANCHOR_RE.sub('', text)
    s = s.replace('`', '')
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'<\w+[^>]*/>', '', s)
    s = s.replace('$', '')
    s = re.sub(r'&\w+;', ' ', s)
    s = s.replace('**', '').replace('*', '')
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    s = re.sub(r'-{2,}', '-', s)
    s = s.strip('-')
    return s

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class FileReport:
    rel_path: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract frontmatter key-value pairs from MDX content."""
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        return {}
    fm = {}
    for line in lines[1:]:
        if line.strip() == '---':
            break
        m = re.match(r'^(\w[\w_-]*)\s*:\s*(.+)$', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            fm[key] = val
    return fm


def extract_code_blocks(content: str) -> list[tuple[int, str]]:
    """Extract fenced code blocks. Returns [(line_number, full_block_content)]."""
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
                blocks.append((block_start, '\n'.join(block_lines)))
                in_block = False
                block_lines = []
        elif in_block:
            block_lines.append(line)

    return blocks


def extract_headings(content: str) -> list[tuple[int, str, str]]:
    """Extract headings outside code blocks. Returns [(line_num, prefix, text)]."""
    lines = content.split('\n')
    headings = []
    in_code = False

    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            headings.append((i + 1, m.group(1), m.group(2).rstrip()))

    return headings


def extract_image_paths(content: str) -> list[tuple[int, str]]:
    """Extract image paths from markdown image syntax. Returns [(line_num, path)]."""
    lines = content.split('\n')
    results = []
    in_code = False
    img_re = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in img_re.finditer(line):
            # Extract just the path (strip optional title)
            path = m.group(2).split(' ')[0].strip('"').strip("'")
            results.append((i + 1, path))

    return results


def extract_link_urls(content: str) -> list[tuple[int, str]]:
    """Extract URLs from markdown links and JSX href. Returns [(line_num, url)]."""
    lines = content.split('\n')
    results = []
    in_code = False
    md_link_re = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    jsx_href_re = re.compile(r'href="([^"]+)"')

    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in md_link_re.finditer(line):
            url = m.group(2).split(' ')[0].strip('"').strip("'")
            # Skip anchor-only links (may change with translated headings)
            if not url.startswith('#'):
                results.append((i + 1, url))
        for m in jsx_href_re.finditer(line):
            url = m.group(1)
            if not url.startswith('#'):
                results.append((i + 1, url))

    return results


def count_jsx_tags(content: str) -> dict[str, int]:
    """Count occurrences of JSX component tags."""
    counts = {}
    in_code = False
    for line in content.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for tag in JSX_COMPONENTS:
            # Count opening tags: <Tag or <Tag> or <Tag ...> or <Tag/>
            counts[tag] = counts.get(tag, 0) + len(
                re.findall(rf'<{tag}[\s>/]', line)
            )
    return counts


def count_latex_display(content: str) -> int:
    """Count display math blocks (lines with standalone $$)."""
    count = 0
    in_code = False
    for line in content.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.strip() == '$$':
            count += 1
    return count


def count_latex_inline(content: str) -> int:
    """Count inline math $...$ occurrences (outside code blocks)."""
    count = 0
    in_code = False
    for line in content.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        # Skip display math lines
        if line.strip() == '$$':
            continue
        # Count $...$ pairs — simple heuristic: count unescaped $ signs
        # that aren't part of $$
        stripped = re.sub(r'\$\$', '', line)  # Remove $$
        stripped = re.sub(r'\\\$', '', stripped)  # Remove escaped \$
        dollars = stripped.count('$')
        count += dollars
    return count


def extract_prose_paragraphs(content: str) -> list[tuple[int, str]]:
    """Extract prose paragraphs (skipping code, frontmatter, images, JSX, imports).

    Returns [(start_line_1based, paragraph_text)].
    """
    lines = content.split('\n')
    paragraphs = []
    in_code = False
    in_frontmatter = False
    current_para: list[str] = []
    para_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track frontmatter
        if i == 0 and stripped == '---':
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == '---':
                in_frontmatter = False
            continue

        # Track code blocks
        if stripped.startswith('```'):
            if current_para:
                paragraphs.append((para_start + 1, ' '.join(current_para)))
                current_para = []
            in_code = not in_code
            continue
        if in_code:
            continue

        # Skip non-prose lines
        is_prose = (
            stripped
            and not stripped.startswith('#')           # headings
            and not stripped.startswith('!')           # images
            and not stripped.startswith('<')            # JSX/HTML tags
            and not stripped.startswith('import ')      # imports
            and not stripped.startswith('{/*')          # JSX comments
            and not stripped.startswith('```')          # code fence
            and not stripped == '---'                   # horizontal rule
            and not stripped == '$$'                    # display math
            and not re.match(r'^:::',  stripped)        # directives
            and not re.match(r'^\|', stripped)          # table rows
        )

        if is_prose:
            if not current_para:
                para_start = i
            current_para.append(stripped)
        else:
            if current_para:
                paragraphs.append((para_start + 1, ' '.join(current_para)))
                current_para = []

    if current_para:
        paragraphs.append((para_start + 1, ' '.join(current_para)))

    return paragraphs

# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_fallback_marker(tr_content: str) -> CheckResult:
    if FALLBACK_MARKER in tr_content:
        return CheckResult("Fallback marker", False,
                           "File contains fallback marker — not a genuine translation")
    return CheckResult("Fallback marker", True, "No fallback marker")


def check_line_count(en_content: str, tr_content: str) -> CheckResult:
    en_lines = en_content.count('\n') + 1
    tr_lines = tr_content.count('\n') + 1
    if en_lines == 0:
        return CheckResult("Line count", True, "Empty file")
    delta_pct = abs(en_lines - tr_lines) / en_lines * 100
    if delta_pct > MAX_LINE_DELTA_PCT:
        return CheckResult("Line count", False,
                           f"EN={en_lines}, TR={tr_lines} ({delta_pct:.1f}% delta, max {MAX_LINE_DELTA_PCT}%)")
    return CheckResult("Line count", True,
                       f"EN={en_lines}, TR={tr_lines} ({delta_pct:.1f}% delta)")


def check_code_blocks(en_content: str, tr_content: str) -> CheckResult:
    en_blocks = extract_code_blocks(en_content)
    tr_blocks = extract_code_blocks(tr_content)
    details = []

    if len(en_blocks) != len(tr_blocks):
        return CheckResult("Code blocks", False,
                           f"Count mismatch: EN={len(en_blocks)}, TR={len(tr_blocks)}")

    for idx, ((en_line, en_block), (tr_line, tr_block)) in enumerate(
            zip(en_blocks, tr_blocks)):
        # Normalize trailing whitespace per line before comparing
        en_block_norm = '\n'.join(l.rstrip() for l in en_block.split('\n'))
        tr_block_norm = '\n'.join(l.rstrip() for l in tr_block.split('\n'))
        if en_block_norm != tr_block_norm:
            # Find first differing line
            en_blines = en_block.split('\n')
            tr_blines = tr_block.split('\n')
            for j, (el, tl) in enumerate(zip(en_blines, tr_blines)):
                if el != tl:
                    details.append(
                        f"Block {idx + 1} (EN line {en_line + 1}, TR line {tr_line + 1}): "
                        f"diff at line {j + 1}: EN='{el[:60]}' TR='{tl[:60]}'")
                    break
            else:
                if len(en_blines) != len(tr_blines):
                    details.append(
                        f"Block {idx + 1}: line count differs "
                        f"(EN={len(en_blines)}, TR={len(tr_blines)})")

    if details:
        return CheckResult("Code blocks", False,
                           f"{len(details)} block(s) differ", details)
    return CheckResult("Code blocks", True,
                       f"{len(en_blocks)} blocks, all identical")


def check_latex_display(en_content: str, tr_content: str) -> CheckResult:
    en_count = count_latex_display(en_content)
    tr_count = count_latex_display(tr_content)
    if en_count != tr_count:
        return CheckResult("LaTeX blocks ($$)", False,
                           f"EN={en_count}, TR={tr_count}")
    return CheckResult("LaTeX blocks ($$)", True, f"{en_count} blocks match")


def check_latex_inline(en_content: str, tr_content: str) -> CheckResult:
    en_count = count_latex_inline(en_content)
    tr_count = count_latex_inline(tr_content)
    if en_count != tr_count:
        return CheckResult("Inline LaTeX ($)", False,
                           f"EN={en_count}, TR={tr_count}")
    return CheckResult("Inline LaTeX ($)", True, f"{en_count} delimiters match")


def check_heading_count(en_content: str, tr_content: str) -> CheckResult:
    en_headings = extract_headings(en_content)
    tr_headings = extract_headings(tr_content)
    if len(en_headings) != len(tr_headings):
        return CheckResult("Heading count", False,
                           f"EN={len(en_headings)}, TR={len(tr_headings)}")
    # Also check levels match
    details = []
    for idx, (en_h, tr_h) in enumerate(zip(en_headings, tr_headings)):
        if en_h[1] != tr_h[1]:
            details.append(
                f"Heading {idx + 1}: level mismatch EN='{en_h[1]}' TR='{tr_h[1]}'")
    if details:
        return CheckResult("Heading count", False,
                           f"Level mismatch in {len(details)} heading(s)", details)
    return CheckResult("Heading count", True,
                       f"{len(en_headings)} headings match")


def check_heading_anchors(en_content: str, tr_content: str) -> CheckResult:
    en_headings = extract_headings(en_content)
    tr_headings = extract_headings(tr_content)
    details = []

    for idx, (en_h, tr_h) in enumerate(
            zip(en_headings, tr_headings)):
        en_slug = slugify(en_h[2])
        tr_text = tr_h[2]
        tr_slug = slugify(tr_text)

        # If slugs differ, translation needs explicit {#anchor}
        if en_slug != tr_slug:
            if not EXISTING_ANCHOR_RE.search(tr_text):
                details.append(
                    f"Line {tr_h[0]}: \"{tr_text}\" needs {{#{en_slug}}}")

    if details:
        return CheckResult("Heading anchors", False,
                           f"{len(details)} anchor(s) missing", details)
    return CheckResult("Heading anchors", True, "All anchors present")


def check_image_paths(en_content: str, tr_content: str) -> CheckResult:
    en_imgs = extract_image_paths(en_content)
    tr_imgs = extract_image_paths(tr_content)
    details = []

    if len(en_imgs) != len(tr_imgs):
        return CheckResult("Image paths", False,
                           f"Count mismatch: EN={len(en_imgs)}, TR={len(tr_imgs)}")

    for (en_line, en_path), (tr_line, tr_path) in zip(en_imgs, tr_imgs):
        if en_path != tr_path:
            details.append(
                f"Line {tr_line}: '{tr_path}' (expected '{en_path}')")

    if details:
        return CheckResult("Image paths", False,
                           f"{len(details)} path(s) changed", details)
    return CheckResult("Image paths", True,
                       f"{len(en_imgs)} paths, all identical")


def check_frontmatter(en_content: str, tr_content: str) -> CheckResult:
    en_fm = parse_frontmatter(en_content)
    tr_fm = parse_frontmatter(tr_content)
    details = []

    # Check preserved keys are identical
    for key in FRONTMATTER_PRESERVE_KEYS:
        if key in en_fm:
            if key not in tr_fm:
                details.append(f"Missing key: {key}")
            elif en_fm[key] != tr_fm[key]:
                details.append(
                    f"{key} changed: '{en_fm[key]}' → '{tr_fm[key]}'")

    # Check translated keys differ from EN (skip allowed same-value titles)
    for key in FRONTMATTER_TRANSLATE_KEYS:
        if key in en_fm and key in tr_fm:
            if en_fm[key] == tr_fm[key]:
                if en_fm[key].lower() not in FRONTMATTER_SAME_ALLOWED:
                    details.append(f"{key} appears untranslated: '{en_fm[key]}'")

    if details:
        return CheckResult("Frontmatter", False,
                           f"{len(details)} issue(s)", details)
    return CheckResult("Frontmatter", True, "Keys preserved, values translated")


def check_jsx_tags(en_content: str, tr_content: str) -> CheckResult:
    en_counts = count_jsx_tags(en_content)
    tr_counts = count_jsx_tags(tr_content)
    details = []

    all_tags = set(en_counts.keys()) | set(tr_counts.keys())
    for tag in sorted(all_tags):
        en_n = en_counts.get(tag, 0)
        tr_n = tr_counts.get(tag, 0)
        if en_n != tr_n and (en_n > 0 or tr_n > 0):
            details.append(f"{tag}: EN={en_n}, TR={tr_n}")

    if details:
        return CheckResult("JSX tags", False,
                           f"{len(details)} tag count mismatch(es)", details)

    # Summarize non-zero tags
    present = {t: n for t, n in en_counts.items() if n > 0}
    summary = ", ".join(f"{t}={n}" for t, n in sorted(present.items()))
    return CheckResult("JSX tags", True, summary or "No JSX tags")


def check_link_urls(en_content: str, tr_content: str) -> CheckResult:
    en_urls = {url for _, url in extract_link_urls(en_content)}
    tr_urls = {url for _, url in extract_link_urls(tr_content)}
    details = []

    missing = en_urls - tr_urls
    extra = tr_urls - en_urls

    for url in sorted(missing):
        details.append(f"Missing URL: {url}")
    for url in sorted(extra):
        details.append(f"Extra URL: {url}")

    if details:
        return CheckResult("Link URLs", False,
                           f"{len(details)} URL difference(s)", details)
    return CheckResult("Link URLs", True,
                       f"{len(en_urls)} URLs, all preserved")


def check_paragraph_inflation(en_content: str, tr_content: str,
                               locale: str) -> CheckResult:
    if locale in NO_WORDCOUNT_LOCALES:
        return CheckResult("Paragraph inflation", True,
                           f"Skipped for {locale} (non-space-delimited)")

    en_paras = extract_prose_paragraphs(en_content)
    tr_paras = extract_prose_paragraphs(tr_content)
    details = []

    # Match by position
    for idx, (en_p, tr_p) in enumerate(
            zip(en_paras, tr_paras)):
        en_words = len(en_p[1].split())
        tr_words = len(tr_p[1].split())
        if en_words < 10:
            continue  # Skip short paragraphs
        ratio = tr_words / en_words
        if ratio > MAX_WORD_RATIO:
            details.append(
                f"Line {tr_p[0]}: {en_words} EN words → {tr_words} TR words "
                f"(ratio {ratio:.1f}x, max {MAX_WORD_RATIO}x)")

    if details:
        return CheckResult("Paragraph inflation", False,
                           f"{len(details)} inflated paragraph(s)", details)
    return CheckResult("Paragraph inflation", True, "No inflation detected")

# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def validate_file(en_path: Path, tr_path: Path, locale: str,
                   locale_dir: Path = None) -> FileReport:
    """Run all checks on a single file pair."""
    if locale_dir is None:
        locale_dir = (I18N_DIR / locale /
                      "docusaurus-plugin-content-docs" / "current")
    rel = tr_path.relative_to(locale_dir)
    report = FileReport(rel_path=str(rel))

    en_content = en_path.read_text(encoding='utf-8')
    tr_content = tr_path.read_text(encoding='utf-8')

    report.checks.append(check_fallback_marker(tr_content))
    # If fallback, skip remaining checks
    if not report.checks[-1].passed:
        return report

    report.checks.append(check_line_count(en_content, tr_content))
    report.checks.append(check_code_blocks(en_content, tr_content))
    report.checks.append(check_latex_display(en_content, tr_content))
    report.checks.append(check_latex_inline(en_content, tr_content))
    report.checks.append(check_heading_count(en_content, tr_content))
    report.checks.append(check_heading_anchors(en_content, tr_content))
    report.checks.append(check_image_paths(en_content, tr_content))
    report.checks.append(check_frontmatter(en_content, tr_content))
    report.checks.append(check_jsx_tags(en_content, tr_content))
    report.checks.append(check_link_urls(en_content, tr_content))
    report.checks.append(check_paragraph_inflation(en_content, tr_content,
                                                    locale))

    return report


def find_genuine_translations(locale: str, locale_dir: Path = None,
                               section: str = None) -> list[tuple[Path, Path]]:
    """Find all genuine (non-fallback) translations for a locale.

    Returns [(en_path, tr_path)] pairs.
    """
    if locale_dir is None:
        locale_dir = (I18N_DIR / locale / "docusaurus-plugin-content-docs" /
                      "current")
    if not locale_dir.exists():
        return []

    # If section specified, search only that subdirectory
    search_dir = locale_dir / section if section else locale_dir

    pairs = []
    for tr_path in sorted(search_dir.rglob("*.mdx")):
        content = tr_path.read_text(encoding='utf-8')
        if FALLBACK_MARKER in content:
            continue
        rel = tr_path.relative_to(locale_dir)
        en_path = DOCS_DIR / rel
        if en_path.exists():
            pairs.append((en_path, tr_path))

    return pairs

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_report(report: FileReport, verbose: bool = False) -> None:
    """Print results for a single file."""
    status = "PASS" if report.passed else "FAIL"
    icon = "\033[32m✓\033[0m" if report.passed else "\033[31m✗\033[0m"
    print(f"\n{icon} {report.rel_path}  [{status}]")

    for check in report.checks:
        c_icon = "  ✓" if check.passed else "  ✗"
        if not check.passed or verbose:
            print(f"  {c_icon} {check.name}: {check.message}")
            if check.details and (not check.passed or verbose):
                for d in check.details[:10]:  # Limit detail output
                    print(f"      {d}")
                if len(check.details) > 10:
                    print(f"      ... and {len(check.details) - 10} more")


def print_summary(reports: list[FileReport], locale: str) -> None:
    """Print batch summary."""
    passed = sum(1 for r in reports if r.passed)
    failed = sum(1 for r in reports if not r.passed)
    total = len(reports)

    print(f"\n{'=' * 60}")
    print(f"Locale: {locale} — {total} genuine translation(s)")
    print(f"  PASS: {passed}")
    print(f"  FAIL: {failed}")

    if failed:
        print(f"\nFailed files:")
        for r in reports:
            if not r.passed:
                failures = [c.name for c in r.checks if not c.passed]
                print(f"  ✗ {r.rel_path}: {', '.join(failures)}")

    print(f"{'=' * 60}")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def write_feedback_report(reports: list[FileReport], locale: str,
                          output_path: Path) -> None:
    """Write a markdown feedback report for contributors."""
    passed = sum(1 for r in reports if r.passed)
    failed = sum(1 for r in reports if not r.passed)
    total = len(reports)

    lines = [
        f"# Translation Feedback — {locale}",
        "",
        f"**{total} files** validated: {passed} PASS, {failed} FAIL",
        "",
    ]

    if failed:
        lines.append("## Files needing fixes")
        lines.append("")
        for r in reports:
            if not r.passed:
                failures = [c for c in r.checks if not c.passed]
                lines.append(f"### `{r.rel_path}` — FAIL")
                lines.append("")
                for c in failures:
                    lines.append(f"- **{c.name}**: {c.message}")
                    for d in c.details[:5]:
                        lines.append(f"  - {d}")
                    if len(c.details) > 5:
                        lines.append(f"  - ... and {len(c.details) - 5} more")
                lines.append("")

    if passed:
        lines.append("## Passing files")
        lines.append("")
        for r in reports:
            if r.passed:
                lines.append(f"- `{r.rel_path}`")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Feedback report written to: {output_path}")


STATUS_FILE = REPO_ROOT / "translation" / "status.json"


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


def record_results(reports: list["FileReport"], locale: str,
                   is_drafts: bool = False) -> None:
    """Record validation results to status.json."""
    status = load_status()
    if locale not in status:
        status[locale] = {}

    today = date.today().isoformat()

    for report in reports:
        rel = report.rel_path
        entry = status[locale].get(rel, {})

        entry["validation"] = "PASS" if report.passed else "FAIL"
        entry["validated"] = today

        if report.passed:
            entry.pop("failures", None)
        else:
            entry["failures"] = [c.name for c in report.checks if not c.passed]

        # Set status if not already tracked
        if "status" not in entry:
            entry["status"] = "draft" if is_drafts else "promoted"

        # Compute source hash from EN file
        en_path = DOCS_DIR / rel
        if en_path.exists():
            en_content = en_path.read_text(encoding="utf-8")
            entry["source_hash"] = compute_source_hash(en_content)

        status[locale][rel] = entry

    save_status(status)


def resolve_locale_dir(locale: str, custom_dir: str = None) -> Path:
    """Resolve the locale directory from --dir flag or default i18n/ path."""
    if custom_dir:
        return REPO_ROOT / custom_dir / locale
    return (I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current")


def main():
    parser = argparse.ArgumentParser(
        description="Validate translated MDX files against English source.")
    parser.add_argument("--locale", required=True,
                        help=f"Locale to validate ({', '.join(ALL_LOCALES)})")
    parser.add_argument("--file",
                        help="Single file (relative to docs/), e.g. guides/foo.mdx")
    parser.add_argument("--dir",
                        help="Translation source directory (default: i18n/). "
                             "E.g. --dir translation/drafts")
    parser.add_argument("--section",
                        help="Filter to section: guides, tutorials, learning/courses, "
                             "learning/modules")
    parser.add_argument("--report", action="store_true",
                        help="Write markdown feedback report to {dir}/{locale}/_feedback.md")
    parser.add_argument("--record", action="store_true",
                        help="Record validation results to translation/status.json")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show details for passing checks too")
    args = parser.parse_args()

    if args.locale not in ALL_LOCALES:
        print(f"Error: Unknown locale '{args.locale}'. "
              f"Available: {', '.join(ALL_LOCALES)}")
        sys.exit(2)

    locale_dir = resolve_locale_dir(args.locale, args.dir)

    if args.file:
        en_path = DOCS_DIR / args.file
        tr_path = locale_dir / args.file
        if not en_path.exists():
            print(f"Error: English source not found: {en_path}")
            sys.exit(2)
        if not tr_path.exists():
            print(f"Error: Translation not found: {tr_path}")
            sys.exit(2)

        report = validate_file(en_path, tr_path, args.locale, locale_dir)
        print_report(report, args.verbose)
        if args.record:
            record_results([report], args.locale,
                           is_drafts=bool(args.dir))
        sys.exit(0 if report.passed else 1)
    else:
        pairs = find_genuine_translations(args.locale, locale_dir, args.section)
        if not pairs:
            scope = f" in {args.section}" if args.section else ""
            print(f"No genuine translations found for locale "
                  f"'{args.locale}'{scope}")
            sys.exit(0)

        reports = []
        for en_path, tr_path in pairs:
            report = validate_file(en_path, tr_path, args.locale, locale_dir)
            reports.append(report)
            print_report(report, args.verbose)

        print_summary(reports, args.locale)

        if args.record:
            record_results(reports, args.locale,
                           is_drafts=bool(args.dir))

        if args.report:
            report_dir = (REPO_ROOT / args.dir / args.locale
                          if args.dir else locale_dir)
            write_feedback_report(reports, args.locale,
                                  report_dir / "_feedback.md")

        any_failed = any(not r.passed for r in reports)
        sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
