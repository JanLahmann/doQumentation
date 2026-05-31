#!/usr/bin/env python3
"""
sync-content.py - Sync and transform Qiskit content for Docusaurus

This script:
1. Clones/updates the Qiskit/documentation repository
2. Converts Jupyter notebooks to MDX (code blocks auto-wrapped by CodeBlock swizzle)
3. Transforms upstream MDX files for Docusaurus compatibility
4. Parses _toc.json to generate structured sidebar configuration
5. Copies original notebooks for "Open in Lab" feature

Content types: tutorials, guides, courses, modules

Usage:
    python scripts/sync-content.py [--tutorials-only] [--no-clone] [--sample-only]
    python scripts/sync-content.py --skip guides --skip modules
"""

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Set

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
UPSTREAM_DIR = PROJECT_ROOT / "upstream-docs"
DOCS_OUTPUT = PROJECT_ROOT / "docs"
NOTEBOOKS_OUTPUT = PROJECT_ROOT / "notebooks"
STATIC_DIR = PROJECT_ROOT / "static"
ADDONS_DIR = PROJECT_ROOT / "upstream-addons"
WORKSHOP_DIR = PROJECT_ROOT / "workshop-notebooks"
LOCAL_CONTENT_DIR = PROJECT_ROOT / "local-content"

# Qiskit Addon sources — Phase 1: core addons with docs/tutorials/
# Each entry: display name → {submodule dir name, notebook path within repo, pip package}
ADDON_SOURCES = {
    "Circuit Cutting":    {"repo": "qiskit-addon-cutting",    "path": "docs/tutorials", "pip": "qiskit-addon-cutting"},
    "SQD":                {"repo": "qiskit-addon-sqd",        "path": "docs/tutorials", "pip": "qiskit-addon-sqd"},
    "OBP":                {"repo": "qiskit-addon-obp",        "path": "docs/tutorials", "pip": "qiskit-addon-obp"},
    "MPF":                {"repo": "qiskit-addon-mpf",        "path": "docs/tutorials", "pip": "qiskit-addon-mpf"},
    "AQC-Tensor":         {"repo": "qiskit-addon-aqc-tensor", "path": "docs/tutorials", "pip": "qiskit-addon-aqc-tensor"},
    "PNA":                {"repo": "qiskit-addon-pna",        "path": "docs/tutorials", "pip": "qiskit-addon-pna"},
    "SLC":                {"repo": "qiskit-addon-slc",        "path": "docs/tutorials", "pip": "qiskit-addon-slc"},
}

# What to sync from upstream (content + images)
CONTENT_PATHS = [
    "docs/tutorials",
    "docs/guides",
    "learning/courses",
    "learning/modules",
    "public/docs/images/tutorials",
    "public/docs/images/guides",
    "public/docs/open-source",
    "public/learning/images",
]

_ADMONITION_TYPE_MAP = {"attention": "warning", "Note": "note", "information": "info"}


def _normalize_admonition(attrs: str, body: str) -> str:
    """Normalize a top-level <Admonition>…</Admonition> match for Docusaurus
    3.9.x's strict MDX parser. Used by the regex rule in MDX_TRANSFORMS.

    - Dedent uniformly 4-space-indented body lines (upstream often indents
      inner content; IBM's Next.js MDX tolerates it but ours parses it as
      a code block and rejects the closing tag).
    - If the body contains a fenced code block, return Docusaurus' `:::type[title]`
      admonition syntax instead — JSX <Admonition> wrapping fenced ```python``` reliably
      breaks MDX 3 ("Unexpected closing slash `/` in tag, expected an open tag first").
    """
    dedented = re.sub(r'^[ \t]{4}', '', body, flags=re.MULTILINE)
    if '```' not in dedented:
        return f'<Admonition{attrs}>\n{dedented}\n</Admonition>'
    type_m = re.search(r'\btype="([^"]+)"', attrs)
    title_m = re.search(r'\btitle="([^"]*)"', attrs)
    a_type = type_m.group(1) if type_m else 'note'
    a_type = _ADMONITION_TYPE_MAP.get(a_type, a_type).lower()
    title = title_m.group(1).strip() if title_m else ''
    title_part = f'[{title}]' if title else ''
    return f':::{a_type}{title_part}\n\n{dedented}\n\n:::'


# MDX Transformations for upstream .mdx files
MDX_TRANSFORMS = [
    # Normalize Admonition types to Docusaurus-supported values
    (r'<Admonition(\s+)type="attention"', r'<Admonition\1type="warning"'),
    (r'<Admonition(\s+)type="Note"', r'<Admonition\1type="note"'),
    (r'<Admonition(\s+)type="information"', r'<Admonition\1type="info"'),
    # Bare <Admonition> without type → default to note
    (r'<Admonition\s*>', '<Admonition type="note">'),
    # Normalize top-level <Admonition>…</Admonition> blocks (column-0 only —
    # nested admonitions inside list items are left alone because their
    # leading whitespace is structural). See _normalize_admonition for why.
    (r'(?ms)^<Admonition([^>]*)>\n((?:(?!</Admonition>).)*?)\n</Admonition>',
     lambda m: _normalize_admonition(m.group(1), m.group(2))),
    # Strip IBM-specific components that we don't implement
    (r'<CodeCellPlaceholder[^>]*/>', ''),
    # Render <CodeTitle title="X" /> as a bold filename caption
    (r'<CodeTitle\s+title="([^"]+)"\s*/>', r'**`\1`**'),
    # Convert IBM's custom Table components to standard HTML
    (r'<Table>', '<table>'), (r'</Table>', '</table>'),
    (r'<THead>', '<thead>'), (r'</THead>', '</thead>'),
    (r'<TBody>', '<tbody>'), (r'</TBody>', '</tbody>'),
    (r'<TFoot>', '<tfoot>'), (r'</TFoot>', '</tfoot>'),
    (r'<Tr>', '<tr>'), (r'</Tr>', '</tr>'),
    (r'<Th\b', '<th'), (r'</Th>', '</th>'),
    (r'<Td\b', '<td'), (r'</Td>', '</td>'),
    # Simplify CodeAssistantAdmonition: strip prompts prop (JSX array breaks MDX escaping)
    (r'<CodeAssistantAdmonition\s+tagLine="([^"]*)"[\s\S]*?/>', r'<CodeAssistantAdmonition tagLine="\1" />'),
    # Rewrite upstream IBM image URLs to local paths (images are synced to static/)
    (r'https://docs\.quantum\.ibm\.com(/learning/images/)', r'\1'),
    (r'https://docs\.quantum\.ibm\.com(/docs/images/)', r'\1'),
    # Fix link paths: /docs/tutorials/foo → /tutorials/foo (local)
    (r'\(/docs/tutorials/', '(/tutorials/'),
    # Fix link paths: /docs/guides/foo → /guides/foo (local)
    (r'\(/docs/guides/', '(/guides/'),
    # Rewrite other /docs/ links to upstream IBM Quantum docs
    # (negative lookahead to skip local paths: tutorials, guides, images)
    (r'\(/docs/(?!tutorials/|guides/|images/)', '(https://docs.quantum.ibm.com/'),
    # Fix link paths: /learning/courses/ and /learning/modules/ are local
    (r'\(/learning/(?!courses/|modules/|images/)', '(https://docs.quantum.ibm.com/learning/'),
    # JSX href equivalents (Card components use href="/docs/..." not markdown links)
    (r'href="/docs/tutorials', 'href="/tutorials'),
    (r'href="/docs/guides/', 'href="/guides/'),
    (r'href="/docs/(?!tutorials|guides/|images/)', 'href="https://docs.quantum.ibm.com/'),
    # Clean up triple+ newlines
    (r'\n{3,}', '\n\n'),
]


def run_command(cmd: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def clone_or_update_upstream():
    """Clone or update the upstream repository (submodule or sparse clone)."""
    print("\n📥 Syncing upstream repository...")

    # Prefer submodule if configured
    gitmodules = PROJECT_ROOT / ".gitmodules"
    if gitmodules.exists() and UPSTREAM_DIR.exists() and (UPSTREAM_DIR / ".git").exists():
        print("  Updating submodule...")
        result = run_command(
            ["git", "submodule", "update", "--remote", "upstream-docs"],
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            print("  Warning: submodule update failed, using current state")
        _ensure_ibm_history(UPSTREAM_DIR)
        print("  ✓ Upstream sync complete (submodule)")
        return

    # Fallback: sparse clone (for forks without the submodule)
    if UPSTREAM_DIR.exists():
        print("  Updating existing clone...")
        result = run_command(["git", "pull", "--ff-only"], cwd=UPSTREAM_DIR)
        if result.returncode != 0:
            print("  Warning: git pull failed, continuing with existing content")
    else:
        print("  Cloning repository (this may take a moment)...")
        result = run_command([
            "git", "clone",
            "--filter=blob:none",
            "--sparse",
            "--depth", "1",
            "https://github.com/Qiskit/documentation.git",
            str(UPSTREAM_DIR)
        ])
        if result.returncode != 0:
            print(f"  Error: Clone failed: {result.stderr}")
            sys.exit(1)

        run_command(
            ["git", "sparse-checkout", "set"] + CONTENT_PATHS,
            cwd=UPSTREAM_DIR
        )

    _ensure_ibm_history(UPSTREAM_DIR)
    print("  ✓ Upstream sync complete")


def _ensure_ibm_history(upstream_repo: Path):
    """Ensure full per-file history is available (for the page-dates manifest).

    Historically the upstream-docs submodule pointed at JanLahmann/Qiskit-
    documentation, a fork that merged upstream as single sync commits — so
    per-file `git log` against its HEAD returned identical dates for every
    file, and we had to add a separate `ibm` remote pointing at
    Qiskit/documentation to recover real per-file modification dates.

    As of 2026-05 the submodule points at Qiskit/documentation directly, so
    `origin` already carries the real history. This function is now a
    no-op when origin is on Qiskit/documentation, and keeps the legacy
    `ibm` remote dance for environments that still have the old fork
    clone on disk (e.g. a long-lived developer checkout that hasn't
    re-cloned since the migration).
    """
    origin_url = run_command(["git", "remote", "get-url", "origin"], cwd=upstream_repo)
    if origin_url.returncode == 0 and "Qiskit/documentation" in origin_url.stdout:
        return  # origin is already upstream — no shim needed
    remotes = run_command(["git", "remote"], cwd=upstream_repo)
    if remotes.returncode != 0:
        return
    if "ibm" not in remotes.stdout.split():
        run_command(
            ["git", "remote", "add", "ibm", "https://github.com/Qiskit/documentation.git"],
            cwd=upstream_repo,
        )
    run_command(
        ["git", "fetch", "--filter=blob:none", "--no-tags", "ibm", "main"],
        cwd=upstream_repo,
    )


_ADDON_IMG_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')
_ADDON_MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
_ADDON_HTML_IMG_RE = re.compile(r"""<img\b([^>]*?)src=(['"])([^'"]+)\2([^>]*)>""")


def rewrite_addon_relative_refs(content: str, output_path: Path) -> str:
    """Rewrite `./foo.png` / `../images/foo.png` / `exp_data/foo.png` etc. in
    addon MDX to absolute `/img/qiskit-addons/<rel>` URLs. Lets every locale
    share one image copy (matches the pattern used by all other docs)."""
    addon_root = (DOCS_OUTPUT / 'qiskit-addons').resolve()
    out_dir = output_path.parent.resolve()

    def _resolve(ref: str) -> Optional[str]:
        head = ref.split('#', 1)[0].split('?', 1)[0]
        if not head or head[0] in '/#' or head.startswith(('http://', 'https://', 'data:', 'mailto:', 'tel:')):
            return None
        if not head.lower().endswith(_ADDON_IMG_EXTS):
            return None
        target = (out_dir / head).resolve()
        try:
            rel = target.relative_to(addon_root)
        except ValueError:
            return None
        return f"/img/qiskit-addons/{rel.as_posix()}"

    def md_repl(m: re.Match) -> str:
        alt, ref, title = m.group(1), m.group(2), m.group(3) or ''
        new = _resolve(ref)
        return f"![{alt}]({new}{title})" if new else m.group(0)

    def html_repl(m: re.Match) -> str:
        pre, quote, ref, post = m.group(1), m.group(2), m.group(3), m.group(4)
        new = _resolve(ref)
        return f"<img{pre}src={quote}{new}{quote}{post}>" if new else m.group(0)

    content = _ADDON_MD_IMG_RE.sub(md_repl, content)
    content = _ADDON_HTML_IMG_RE.sub(html_repl, content)
    return content


def transform_mdx(content: str, source_path: Path) -> str:
    """Transform upstream MDX to Docusaurus-compatible format."""
    for pattern, replacement in MDX_TRANSFORMS:
        if callable(replacement):
            content = re.sub(pattern, replacement, content)
        else:
            content = re.sub(pattern, replacement, content)

    # #37: Fix heading hierarchy — "Check your understanding" should be H3, not H4+
    content = re.sub(r'^#{4,}\s+(Check your understanding)', r'### \1', content, flags=re.MULTILINE)

    # Fix stray leading whitespace on headings in kipu-optimization.mdx (upstream bug).
    # Targeted to this file only — other files (e.g. notebook-style courses) intentionally
    # have indented headings.
    if source_path.name == 'kipu-optimization.mdx':
        content = re.sub(r'^\s+(#{1,6}\s)', r'\1', content, flags=re.MULTILINE)

    # Add Tabs/TabItem imports if used but not imported
    if '<Tabs>' in content or '<TabItem' in content:
        if "import Tabs from" not in content and "import TabItem from" not in content:
            import_stmt = (
                "import Tabs from '@theme/Tabs';\n"
                "import TabItem from '@theme/TabItem';\n\n"
            )
            if content.startswith('---'):
                end_fm = re.search(r'^---\s*$', content[3:], re.MULTILINE)
                if end_fm:
                    pos = 3 + end_fm.end()
                    content = content[:pos] + '\n\n' + import_stmt + content[pos:]
            else:
                content = import_stmt + content

    # #41: Tag untagged code blocks with language hints based on content
    content = _tag_untagged_code_blocks(content)

    # Add doQumentation context to IBM's "Tutorial survey" section:
    # Clarify the survey belongs to IBM, and point to GitHub Issues for our feedback.
    content = re.sub(
        r'(## Tutorial survey\n\nPlease take this short survey to provide feedback on this tutorial\.'
        r' Your insights will help us improve our content offerings and user experience\.)',
        r'\1\n\n'
        r'> **Note:** This survey is by **IBM Quantum** and covers the **tutorial content** (written by IBM). '
        r'doQumentation provides the website, translations, and code execution — '
        r'for feedback on those, please [open a GitHub issue](https://github.com/JanLahmann/doQumentation/issues).',
        content,
    )

    # Append doQumentation feedback widget (Umami-tracked thumbs up/down).
    # Only for tutorials (identified by path containing 'tutorials/').
    is_tutorial = 'tutorials' in str(source_path)
    if is_tutorial:
        feedback_import = "import TutorialFeedback from '@site/src/components/TutorialFeedback';\n"
        if feedback_import.strip() not in content:
            if content.startswith('---'):
                end_fm = re.search(r'^---\s*$', content[3:], re.MULTILINE)
                if end_fm:
                    pos = 3 + end_fm.end()
                    content = content[:pos] + '\n\n' + feedback_import + content[pos:]
            else:
                content = feedback_import + '\n' + content
        content = content.rstrip() + '\n\n<TutorialFeedback />\n'

    return content


def escape_mdx_outside_code(content: str) -> str:
    """Escape { and } in markdown text that would break MDX parsing.

    Leaves code blocks (``` ... ```), inline code (` ... `),
    math blocks ($$ ... $$ and $ ... $), and JSX comments ({/* ... */}) untouched.
    """
    parts = re.split(r'(\$\$[\s\S]*?\$\$|```[\s\S]*?```|`[^`]+`|\$(?:[^$\n]|\n(?!\n))+\$|\{/\*[\s\S]*?\*/\})', content)
    for i in range(0, len(parts), 2):  # even indices are outside code
        # Escape lone { } that aren't JSX expressions
        # Skip patterns like {' '} which are valid JSX
        parts[i] = re.sub(r'(?<!\{)\{(?![\'"])', r'\\{', parts[i])
        parts[i] = re.sub(r'(?<![\'"])\}(?!\})', r'\\}', parts[i])
    return ''.join(parts)


def _tag_untagged_code_blocks(content: str) -> str:
    """Add language tags to untagged code fences based on content heuristics."""
    def _replace_block(m):
        code = m.group(1)
        # Skip false matches that span across LaTeX math output boundaries
        # (regex matches closing fence of one block across bare $$...$$ to
        # the opening fence of the next block)
        if '$$' in code:
            return m.group(0)
        first_line = code.strip().split('\n')[0] if code.strip() else ''
        if (first_line.startswith('$') and not first_line.startswith('$$')) or first_line.startswith('%'):
            return f'```bash\n{code}```'
        if any(first_line.startswith(kw) for kw in ('import ', 'from ', 'def ', 'class ', 'print(')):
            return f'```python\n{code}```'
        if first_line.startswith('{'):
            return f'```json\n{code}```'
        if first_line.startswith('pip ') or first_line.startswith('pip3 '):
            return f'```bash\n{code}```'
        return m.group(0)
    return re.sub(r'```\n(.*?)```', _replace_block, content, flags=re.DOTALL)


def cell_source(cell: dict) -> str:
    """Extract source text from a notebook cell (handles list or string)."""
    src = cell.get('source', '')
    if isinstance(src, list):
        return ''.join(src)
    return src


def _infer_alt_text(source: str) -> str:
    """Infer alt text for cell output images based on source code patterns."""
    s = source.lower()
    if '.draw(' in s or 'circuit' in s:
        return 'Quantum circuit diagram'
    if 'plot(' in s or 'hist(' in s or 'bar(' in s or 'scatter(' in s:
        return 'Plot output'
    if 'imshow(' in s:
        return 'Image output'
    return 'Code output'


def _text_to_output(text: str) -> str:
    """Convert a text output to markdown.

    Detects <Image> JSX tags (from IBM's pre-extracted notebook outputs) and
    converts them to standard markdown images instead of wrapping in code blocks.
    """
    text = text.strip()
    if not text:
        return ''
    # IBM's build system extracts notebook output images and replaces the output
    # cell with an <Image src="..." alt="..." /> JSX component.  Convert to markdown.
    m = re.match(r'^<Image\s+src="([^"]+)"(?:\s+alt="([^"]*)")?\s*/?>$', text)
    if m:
        src, alt = m.group(1), m.group(2) or 'output'
        return f'\n![{alt}]({src})\n'
    return f'\n```text\n{text}\n```\n'


def extract_cell_outputs(cell: dict, output_dir: Path, img_counter: list, img_ref_prefix: str = '') -> str:
    """Convert notebook cell outputs to markdown text.

    Handles text/plain, image/png (saved as files), and stderr/stdout streams.
    """
    source = cell_source(cell)
    alt = _infer_alt_text(source)
    parts = []
    for output in cell.get('outputs', []):
        output_type = output.get('output_type', '')

        if output_type in ('stream', 'execute_result', 'display_data'):
            # Text output
            if 'text' in output:
                text = output['text']
                if isinstance(text, list):
                    text = ''.join(text)
                if text.strip():
                    parts.append(_text_to_output(text))

            # Check data dict for richer outputs
            data = output.get('data', {})
            if 'image/png' in data:
                img_counter[0] += 1
                img_name = f'output_{img_counter[0]}.png'
                img_bytes = base64.b64decode(data['image/png'])
                img_path = output_dir / img_name
                img_path.parent.mkdir(parents=True, exist_ok=True)
                img_path.write_bytes(img_bytes)
                parts.append(f'\n![{alt}]({img_ref_prefix}{img_name})\n')
            elif 'text/latex' in data:
                latex = data['text/latex']
                if isinstance(latex, list):
                    latex = ''.join(latex)
                latex = latex.strip()
                if latex:
                    parts.append(f'\n{latex}\n')
            elif 'text/plain' in data and 'text' not in output:
                text = data['text/plain']
                if isinstance(text, list):
                    text = ''.join(text)
                if text.strip():
                    parts.append(_text_to_output(text))

        elif output_type == 'error':
            # Skip traceback noise — users will see errors when they run the code
            pass

    return ''.join(parts)


# ── Notebook dependency scan ─────────────────────────────────────────────────
# Maps import names to pip package names where they differ.
IMPORT_TO_PIP = {
    'sklearn': 'scikit-learn',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'yaml': 'pyyaml',
    'attr': 'attrs',
    'bs4': 'beautifulsoup4',
    'Crypto': 'pycryptodome',
    'Bio': 'biopython',
    'gi': 'PyGObject',
    'serial': 'pyserial',
    'usb': 'pyusb',
    'wx': 'wxPython',
    'skimage': 'scikit-image',
    'cv': 'opencv-python',
    'pylatex': 'PyLaTeX',
    # Quantum / scientific ecosystem
    'imblearn': 'imbalanced-learn',
    'pysat': 'python-sat',
    'github': 'PyGithub',
    'oqs': 'liboqs-python',
}

def analyze_notebook_imports(cells: list[dict]) -> list[str]:
    """Extract all third-party imports from notebook code cells.

    Scans code cells for import statements, filters out:
    - Python stdlib modules
    - Packages the notebook itself installs (via !pip install / %pip install)

    Returns a sorted list of pip package names (stdlib-only filtering — no
    platform-specific baseline). This ensures the prerequisites cell is
    complete for both Colab and Binder.
    """
    import_names: set[str] = set()
    already_installed: set[str] = set()

    for cell in cells:
        if cell.get('cell_type') != 'code':
            continue
        source = cell_source(cell)
        if not source.strip():
            continue

        # Detect packages the notebook already installs
        for m in re.finditer(
            r'(?:^|\n)\s*[!%]pip\s+install\s+(.+)',
            source,
        ):
            for token in m.group(1).split():
                # Skip flags like -q, --quiet, --upgrade
                if token.startswith('-'):
                    continue
                # Strip version specifiers: pkg>=1.0 → pkg
                pkg = re.split(r'[><=!~\[]', token)[0].strip()
                if pkg:
                    # Normalize: both hyphens and underscores
                    already_installed.add(pkg.lower().replace('_', '-'))

        # Extract import statements
        for line in source.split('\n'):
            stripped = line.strip()
            # import X, import X.Y, import X as Z
            m = re.match(r'^import\s+([\w.]+)', stripped)
            if m:
                import_names.add(m.group(1).split('.')[0])
                continue
            # from X import ..., from X.Y import ...
            m = re.match(r'^from\s+([\w.]+)\s+import\b', stripped)
            if m:
                import_names.add(m.group(1).split('.')[0])

    # Filter out stdlib
    stdlib = sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else set()

    missing: list[str] = []
    for name in sorted(import_names):
        if name in stdlib:
            continue
        # Map import name → pip name
        pip_name = IMPORT_TO_PIP.get(name, name)
        # General rule: underscores → hyphens for pip names (e.g. qiskit_ibm_catalog → qiskit-ibm-catalog)
        pip_name = pip_name.replace('_', '-')
        # Skip if notebook already installs it
        if pip_name.lower() in already_installed or name.lower() in already_installed:
            continue
        missing.append(pip_name)

    return missing


def convert_notebook(ipynb_path: Path, output_path: Path,
                     notebook_path: Optional[str] = None,
                     slug: Optional[str] = None,
                     banner_description: Optional[str] = None) -> bool:
    """
    Convert a Jupyter notebook to MDX by parsing the .ipynb JSON directly.

    No external dependencies needed (no nbconvert). Python code blocks are
    output as standard ```python fenced blocks — the CodeBlock swizzle
    auto-wraps them in ExecutableCode at render time.

    If notebook_path is provided, an OpenInLabBanner is injected after the
    frontmatter for the "Open in JupyterLab" feature.
    """
    try:
        nb = json.loads(ipynb_path.read_text())
        cells = nb.get('cells', [])
        if not cells:
            print(f"    Warning: Empty notebook {ipynb_path.name}")
            return False

        # Extracted output images go into static/img/<section>/<stem-slug>/
        # (one canonical copy, served at /img/...). Absolute URLs in MDX let
        # all locales reference the same files — no per-locale duplication.
        # See PROJECT_HANDOFF.md "Image asset placement" for the convention.
        section = output_path.parent.relative_to(DOCS_OUTPUT).as_posix()
        stem_slug = re.sub(r'[^a-z0-9]+', '-', output_path.stem.lower()).strip('-')
        img_dir = STATIC_DIR / 'img' / section / stem_slug
        img_ref_prefix = f'/img/{section}/{stem_slug}/'
        img_counter = [0]  # mutable counter for image filenames

        title = None
        description = None
        body_parts = []
        first_markdown_seen = False

        for cell in cells:
            cell_type = cell.get('cell_type', '')
            source = cell_source(cell)

            if cell_type == 'markdown':
                # Check first markdown cell for title/metadata
                if not first_markdown_seen:
                    first_markdown_seen = True
                    # Check for YAML frontmatter in first cell
                    if source.lstrip().startswith('---'):
                        fm_match = re.match(r'\s*---\n(.*?)\n---\n?', source, re.DOTALL)
                        if fm_match:
                            fm_text = fm_match.group(1)
                            t_match = re.search(r'^title:\s*(.+)$', fm_text, re.MULTILINE)
                            if t_match:
                                title = t_match.group(1).strip().strip('"\'')
                            d_match = re.search(r'^description:\s*(.+)$', fm_text, re.MULTILINE)
                            if d_match:
                                description = d_match.group(1).strip().strip('"\'')
                            source = source[fm_match.end():]

                    # Extract title from first heading if not found in frontmatter
                    if not title:
                        h1_match = re.match(r'^#\s+(.+)$', source.lstrip(), re.MULTILINE)
                        if h1_match:
                            title = h1_match.group(1).strip()

                body_parts.append(source)

            elif cell_type == 'code':
                if not source.strip():
                    continue
                # Determine language from notebook metadata
                lang = nb.get('metadata', {}).get('kernelspec', {}).get('language', 'python')
                body_parts.append(f'\n```{lang}\n{source.rstrip()}\n```\n')

                # Include cell outputs (images, text)
                output_text = extract_cell_outputs(cell, img_dir, img_counter, img_ref_prefix)
                if output_text:
                    body_parts.append(output_text)

            elif cell_type == 'raw':
                body_parts.append(f'\n```\n{source}\n```\n')

        # Inject %pip install cell for all third-party dependencies
        missing_pkgs = analyze_notebook_imports(cells)
        if missing_pkgs:
            install_line = f'# Added by doQumentation — required packages for this notebook\n!pip install -q {" ".join(missing_pkgs)}'
            install_block = f'\n```python\n{install_line}\n```\n'
            # Insert before the first code block
            first_code_idx = None
            for i, part in enumerate(body_parts):
                if re.search(r'```\w+\n', part):
                    first_code_idx = i
                    break
            if first_code_idx is not None:
                body_parts.insert(first_code_idx, install_block)
            else:
                body_parts.insert(0, install_block)

        content = '\n'.join(body_parts)

        # Fallback title from filename
        if not title:
            title = ipynb_path.stem.replace('-', ' ').replace('_', ' ').title()

        # Strip duplicate # Title heading if it matches frontmatter title
        if title:
            escaped = re.escape(title)
            content = re.sub(rf'^#\s+{escaped}\s*\n', '', content, count=1, flags=re.MULTILINE)

        # Apply MDX transforms (Admonition → :::, link fixes, strip custom components)
        content = transform_mdx(content, ipynb_path)

        # Addon notebooks reference siblings via relative URLs; rewrite them
        # to absolute /img/qiskit-addons/... so locales share one image copy.
        try:
            if 'qiskit-addons' in output_path.relative_to(DOCS_OUTPUT).parts:
                content = rewrite_addon_relative_refs(content, output_path)
        except ValueError:
            pass  # output_path is not under DOCS_OUTPUT (defensive)

        # Escape characters that break MDX: curly braces in text (not in code blocks)
        content = escape_mdx_outside_code(content)

        # Build frontmatter
        # Escape quotes in title for YAML
        safe_title = title.replace('"', '\\"')
        fm_lines = ['---', f'title: "{safe_title}"', f'sidebar_label: "{safe_title}"']
        if description:
            safe_desc = description.replace('"', '\\"')
            fm_lines.append(f'description: "{safe_desc}"')
        if notebook_path:
            fm_lines.append(f'notebook_path: "{notebook_path}"')
        if slug:
            fm_lines.append(f'slug: "{slug}"')
        fm_lines.append('---\n')
        frontmatter = '\n'.join(fm_lines)

        # Inject OpenInLabBanner only if notebook has executable code cells
        banner = ''
        has_code_cells = any(
            c.get('cell_type') == 'code' and cell_source(c).strip()
            for c in cells
        )
        if notebook_path and has_code_cells:
            desc_prop = f' description="{banner_description}"' if banner_description else ''
            banner = f'\n<OpenInLabBanner notebookPath="{notebook_path}"{desc_prop} />\n'

        # Write output.
        # Extract any import statements from content (added by transform_mdx)
        # and place them before the banner JSX to satisfy MDX import ordering.
        import_lines = []
        body_lines = []
        for line in content.split('\n'):
            if line.strip().startswith('import ') and ' from ' in line:
                import_lines.append(line)
            else:
                body_lines.append(line)
        imports_block = '\n'.join(import_lines) + '\n' if import_lines else ''
        body = '\n'.join(body_lines)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(frontmatter + '\n' + imports_block + banner + '\n' + body)

        return True

    except Exception as e:
        print(f"    Error converting {ipynb_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def transform_tutorials_index(tutorials_src: Path, tutorials_dst: Path):
    """Transform the upstream tutorials index.mdx for Docusaurus."""
    index_src = tutorials_src / "index.mdx"
    if not index_src.exists():
        print("  Warning: No upstream index.mdx found")
        return

    content = index_src.read_text()

    # Add our site-specific header before the upstream content
    header = """---
title: Tutorials
sidebar_label: Overview
sidebar_position: 1
description: Browse IBM Quantum tutorials — executable on RasQberry, via Binder, or on your own Jupyter server.
---

"""

    # Strip upstream frontmatter (we use our own)
    if content.startswith('---'):
        fm_end = re.search(r'^---\s*$', content[3:], re.MULTILINE)
        if fm_end:
            content = content[3 + fm_end.end():].lstrip()

    # Apply MDX transforms (fixes link paths, admonitions, etc.)
    content = transform_mdx(content, index_src)

    index_dst = tutorials_dst / "index.mdx"
    index_dst.parent.mkdir(parents=True, exist_ok=True)
    index_dst.write_text(header + content)
    print("  ✓ index.mdx (transformed)")


def process_tutorials():
    """Process all tutorial files from upstream."""
    print("\n📝 Processing tutorials...")

    tutorials_src = UPSTREAM_DIR / "docs" / "tutorials"
    tutorials_dst = DOCS_OUTPUT / "tutorials"
    notebooks_dst = NOTEBOOKS_OUTPUT / "tutorials"

    if not tutorials_src.exists():
        print(f"  Warning: Tutorials directory not found at {tutorials_src}")
        return

    # Clean output directories
    if tutorials_dst.exists():
        shutil.rmtree(tutorials_dst)
    tutorials_dst.mkdir(parents=True)

    if notebooks_dst.exists():
        shutil.rmtree(notebooks_dst)
    notebooks_dst.mkdir(parents=True)

    # Transform the tutorials index page separately
    transform_tutorials_index(tutorials_src, tutorials_dst)

    # Track statistics
    stats = {"mdx": 0, "ipynb": 0, "images": 0, "skipped": 0}

    for src_path in tutorials_src.rglob('*'):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(tutorials_src)

        # Skip files handled separately
        if rel_path.name in ('index.mdx', '_toc.json'):
            stats["skipped"] += 1
            continue

        if src_path.suffix == '.mdx':
            dst_path = tutorials_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            content = src_path.read_text()
            transformed = transform_mdx(content, src_path)
            dst_path.write_text(transformed)
            stats["mdx"] += 1
            print(f"  ✓ {rel_path}")

        elif src_path.suffix == '.ipynb':
            dst_path = tutorials_dst / rel_path.with_suffix('.mdx')
            # Notebook path matching the notebooks branch layout
            upstream_nb_path = f"tutorials/{rel_path}"
            if convert_notebook(src_path, dst_path, notebook_path=upstream_nb_path):
                stats["ipynb"] += 1
                print(f"  ✓ {rel_path} → .mdx")
            else:
                stats["skipped"] += 1

            # Copy original notebook for "Open in Lab" (rewrite image paths)
            nb_dst = notebooks_dst / rel_path
            nb_rel = Path('tutorials') / rel_path
            copy_notebook_with_rewrite(src_path, nb_dst, nb_rel)

        elif src_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
            dst_path = tutorials_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, dst_path)
            stats["images"] += 1

        else:
            stats["skipped"] += 1

    # Import custom Hello World — doQumentation's own intro tutorial.
    # Lives at local-content/hello-world.ipynb (source of truth, in this repo).
    # Falls back to upstream-docs/hello-world.ipynb for environments still on
    # the legacy fork submodule where the file lived at the fork's root.
    custom_hw = LOCAL_CONTENT_DIR / "hello-world.ipynb"
    if not custom_hw.exists():
        custom_hw = UPSTREAM_DIR / "hello-world.ipynb"
    if custom_hw.exists():
        hw_dst = tutorials_dst / "hello-world.mdx"
        if convert_notebook(custom_hw, hw_dst, notebook_path="hello-world.ipynb",
                           banner_description="This tutorial was created for doQumentation."):
            stats["ipynb"] += 1
            print(f"  ✓ hello-world.ipynb → .mdx (custom)")
        # Copy notebook for "Open in Lab"
        hw_nb_dst = notebooks_dst / "hello-world.ipynb"
        copy_notebook_with_rewrite(custom_hw, hw_nb_dst, Path("tutorials/hello-world.ipynb"))

    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, "
          f"{stats['images']} images, {stats['skipped']} skipped")


def transform_guides_index(guides_src: Path, guides_dst: Path):
    """Transform the upstream guides index.mdx for Docusaurus."""
    index_src = guides_src / "index.mdx"
    if not index_src.exists():
        print("  Warning: No upstream guides index.mdx found")
        return

    content = index_src.read_text()

    # Add our site-specific header before the upstream content
    header = """---
title: Guides
sidebar_label: Overview
sidebar_position: 1
description: How-to guides for Qiskit — circuit building, transpilation, error mitigation, execution, and more.
---

"""

    # Strip upstream frontmatter (we use our own)
    if content.startswith('---'):
        fm_end = re.search(r'^---\s*$', content[3:], re.MULTILINE)
        if fm_end:
            content = content[3 + fm_end.end():].lstrip()

    # Apply MDX transforms (fixes link paths, admonitions, etc.)
    content = transform_mdx(content, index_src)

    index_dst = guides_dst / "index.mdx"
    index_dst.parent.mkdir(parents=True, exist_ok=True)
    index_dst.write_text(header + content)
    print("  ✓ index.mdx (transformed)")


def process_guides():
    """Process all guide files from upstream."""
    print("\n📖 Processing guides...")

    guides_src = UPSTREAM_DIR / "docs" / "guides"
    guides_dst = DOCS_OUTPUT / "guides"
    notebooks_dst = NOTEBOOKS_OUTPUT / "guides"

    if not guides_src.exists():
        print(f"  Warning: Guides directory not found at {guides_src}")
        return

    # Clean output directories
    if guides_dst.exists():
        shutil.rmtree(guides_dst)
    guides_dst.mkdir(parents=True)

    if notebooks_dst.exists():
        shutil.rmtree(notebooks_dst)
    notebooks_dst.mkdir(parents=True)

    # Transform the guides index page separately
    transform_guides_index(guides_src, guides_dst)

    # Track statistics
    stats = {"mdx": 0, "ipynb": 0, "images": 0, "skipped": 0}

    for src_path in guides_src.rglob('*'):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(guides_src)

        # Skip files handled separately
        if rel_path.name in ('index.mdx', '_toc.json'):
            stats["skipped"] += 1
            continue

        if src_path.suffix == '.mdx':
            dst_path = guides_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            content = src_path.read_text()
            transformed = transform_mdx(content, src_path)
            dst_path.write_text(transformed)
            stats["mdx"] += 1
            print(f"  ✓ {rel_path}")

        elif src_path.suffix == '.ipynb':
            dst_path = guides_dst / rel_path.with_suffix('.mdx')
            # Notebook path matching the notebooks branch layout
            upstream_nb_path = f"guides/{rel_path}"
            if convert_notebook(src_path, dst_path, notebook_path=upstream_nb_path):
                stats["ipynb"] += 1
                print(f"  ✓ {rel_path} → .mdx")
            else:
                stats["skipped"] += 1

            # Copy original notebook for "Open in Lab" (rewrite image paths)
            nb_dst = notebooks_dst / rel_path
            nb_rel = Path('guides') / rel_path
            copy_notebook_with_rewrite(src_path, nb_dst, nb_rel)

        elif src_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'):
            dst_path = guides_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, dst_path)
            stats["images"] += 1

        else:
            stats["skipped"] += 1

    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, "
          f"{stats['images']} images, {stats['skipped']} skipped")


def generate_guides_sidebar():
    """Parse guides _toc.json and generate structured sidebar configuration."""
    print("\n📋 Generating guides sidebar from _toc.json...")

    toc_path = UPSTREAM_DIR / "docs" / "guides" / "_toc.json"
    if not toc_path.exists():
        print("  Warning: guides _toc.json not found")
        return

    toc = json.loads(toc_path.read_text())
    children = toc.get('children', [])

    sidebar_items = toc_children_to_sidebar(children)

    sidebar_json = PROJECT_ROOT / "sidebar-guides.json"
    sidebar_json.write_text(json.dumps(sidebar_items, indent=2))

    # Count guides
    def count_docs(items):
        n = 0
        for item in items:
            if isinstance(item, str):
                n += 1
            elif isinstance(item, dict) and item.get('type') == 'doc':
                n += 1
            elif isinstance(item, dict) and 'items' in item:
                n += count_docs(item['items'])
        return n

    print(f"  Found {count_docs(sidebar_items)} guides in {len(sidebar_items)} categories")
    print(f"  ✓ Generated {sidebar_json}")


def url_to_doc_id(url: str) -> str:
    """Convert upstream URL to Docusaurus doc ID.

    /docs/tutorials/foo → tutorials/foo
    /learning/courses/foo/bar → learning/courses/foo/bar
    """
    url = url.lstrip('/')
    if url.startswith('docs/'):
        url = url[5:]
    return url


def is_notebook_page(doc_id: str) -> bool:
    """Check if a doc ID corresponds to a page with executable code cells.

    Looks for OpenInLabBanner which is only injected when the notebook has
    non-empty code cells (not just notebook_path frontmatter, which is set
    for all notebook-derived pages including text-only ones)."""
    mdx_path = DOCS_OUTPUT / f"{doc_id}.mdx"
    if not mdx_path.exists():
        return False
    try:
        content = mdx_path.read_text()
        return '<OpenInLabBanner' in content
    except OSError:
        return False


def sidebar_doc_item(doc_id: str) -> object:
    """Return a sidebar item for a doc ID — with customProps.notebook if it's a notebook page."""
    if is_notebook_page(doc_id):
        return {'type': 'doc', 'id': doc_id, 'customProps': {'notebook': True}}
    return doc_id


def toc_children_to_sidebar(children: list, parent_key: str = "") -> list:
    """Recursively convert _toc.json children to Docusaurus sidebar items.

    `parent_key` accumulates the breadcrumb path through nested categories so
    duplicate category labels (e.g. "Install" appearing under both "Qiskit"
    and "IBM Quantum Compute" in upstream's guides _toc.json) get distinct
    Docusaurus translation keys.
    """
    items = []
    for child in children:
        if 'children' in child and child['children']:
            # "Lessons"/"Modules" are wrappers in upstream _toc.json — unwrap children directly
            if child.get('title') in ('Lessons', 'Modules'):
                items.extend(toc_children_to_sidebar(child['children'], parent_key))
                continue
            # Category with sub-items
            label = child['title']
            cat_key = f"{parent_key}/{label}" if parent_key else label
            sub_items = toc_children_to_sidebar(child['children'], cat_key)
            if sub_items:
                cat = {
                    'type': 'category',
                    'label': label,
                    'key': cat_key,
                    'collapsed': child.get('collapsed', True),
                    'items': sub_items,
                }
                # If this category also has a URL, make it a link
                if 'url' in child:
                    cat['link'] = {'type': 'doc', 'id': url_to_doc_id(child['url'])}
                items.append(cat)
        elif 'url' in child:
            url = child['url']
            # External URLs → Docusaurus link items
            if url.startswith('http://') or url.startswith('https://'):
                items.append({
                    'type': 'link',
                    'label': child.get('title', url),
                    'href': url,
                })
                continue
            doc_id = url_to_doc_id(url)
            # Skip non-doc resources (PDFs, etc.) — but not version numbers like qiskit-2.0
            last_part = doc_id.split('/')[-1]
            ext_parts = last_part.rsplit('.', 1)
            has_file_ext = len(ext_parts) == 2 and ext_parts[1].isalpha() and ext_parts[1] != 'mdx'
            if has_file_ext:
                items.append({
                    'type': 'link',
                    'label': child.get('title', doc_id),
                    'href': f'/{url.lstrip("/")}',
                })
                continue
            # Skip overview entries (handled as category links)
            # tutorials overview = 'tutorials', course overviews = 'learning/courses/{name}',
            # guide overview = 'guides', module overviews = 'learning/modules/{name}'
            if doc_id in ('tutorials', 'guides'):
                continue
            if doc_id.startswith('learning/courses/') and doc_id.count('/') == 2:
                continue
            if doc_id.startswith('learning/modules/') and doc_id.count('/') == 2:
                continue
            # Skip toc entries pointing at files that don't exist locally —
            # upstream's _toc.json occasionally references pages that have
            # been renamed or unbuilt (e.g. guides/get-qpu-information after
            # the May 2026 upstream restructure). Including them would fail
            # Docusaurus' sidebar validation. Better to log and drop than
            # to break the build.
            if not (DOCS_OUTPUT / f"{doc_id}.mdx").exists():
                print(f"  ⚠ Skipping sidebar entry for missing doc: {doc_id}")
                continue
            items.append(sidebar_doc_item(doc_id))
    return items


def rewrite_notebook_image_paths(content: str, nb_rel_path: Path) -> str:
    """Rewrite absolute image paths in a notebook to relative paths.

    Jupyter can't serve absolute paths like /docs/images/... — the images
    need to be referenced relative to the notebook so JupyterLab resolves
    them through its contents API.

    Args:
        content: Raw notebook JSON content
        nb_rel_path: Notebook path relative to NOTEBOOKS_OUTPUT,
                     e.g. Path('tutorials/foo.ipynb')
    """
    depth = len(nb_rel_path.parent.parts)  # e.g. tutorials/ → 1
    prefix = '../' * depth

    # Markdown: ![alt](/docs/images/...) → ![alt](../docs/images/...)
    content = content.replace('(/docs/images/', f'({prefix}docs/images/')
    content = content.replace('(/learning/images/', f'({prefix}learning/images/')

    # JSX/HTML: src="/docs/images/..." → in JSON: src=\"/docs/images/...\"
    content = content.replace('\\"/docs/images/', f'\\"{prefix}docs/images/')
    content = content.replace('\\"/learning/images/', f'\\"{prefix}learning/images/')

    return content


# Base packages always needed for Colab (skipped on Binder/CE where pre-installed)
COLAB_BASE_PKGS = ['qiskit', 'qiskit-aer', 'qiskit-ibm-runtime', 'pylatexenc']


def _make_prereq_cell(all_pkgs: list) -> dict:
    """Build the prerequisites cell injected at top of notebook copies.

    Uses importlib.util.find_spec to skip pip install when packages are
    already present (Binder/CE). On Colab/fresh environments, installs normally.
    """
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Install required packages (auto-skipped if already installed)\n",
            "import importlib\n",
            f"if importlib.util.find_spec('qiskit') is None:\n",
            f"    !pip install -q {' '.join(all_pkgs)}\n",
            "else:\n",
            '    print("\\u2713 Packages already installed")\n',
            "\n",
            "# To run on real quantum hardware, uncomment and fill in your credentials:\n",
            "# from qiskit_ibm_runtime import QiskitRuntimeService\n",
            "# QiskitRuntimeService.save_account(\n",
            '#     channel="ibm_quantum_platform",\n',
            '#     token="<your-api-key>",\n',
            '#     # instance="<IBM Cloud CRN or instance name>",  # optional\n',
            "#     set_as_default=True,\n",
            "#     overwrite=True,\n",
            "# )"
        ]
    }


def copy_notebook_with_rewrite(src_path: Path, dst_path: Path, nb_rel_path: Path):
    """Copy a notebook, rewriting image paths and injecting a prerequisites cell.

    Injects a single comprehensive cell at the top listing ALL required
    packages (base Qiskit stack + per-notebook extras detected by import
    scanning). Auto-runs on Colab via cell_execution_strategy metadata;
    skipped entirely on Binder/CE where packages are pre-installed.
    """
    content = src_path.read_text()
    content = rewrite_notebook_image_paths(content, nb_rel_path)

    # Parse notebook JSON to inject install cell + Colab metadata
    nb = json.loads(content)
    cells = nb.get('cells', [])

    # Build complete package list: base + all detected third-party imports
    all_pkgs = list(COLAB_BASE_PKGS)
    for p in analyze_notebook_imports(cells):
        if p not in all_pkgs:
            all_pkgs.append(p)

    prereq_cell = _make_prereq_cell(all_pkgs)

    # Strip MDX-specific syntax from markdown cells (frontmatter, JSX comments,
    # heading anchors, <Admonition> blocks) so notebooks render cleanly in
    # JupyterLab/Colab without raw Docusaurus directives showing as literal text.
    first_md = True
    for cell in cells:
        if cell.get('cell_type') != 'markdown':
            continue
        src = cell_source(cell)
        if first_md:
            # Remove YAML frontmatter block at top of first markdown cell
            src = re.sub(r'^---\n.*?\n---\n?', '', src, count=1, flags=re.DOTALL)
            first_md = False
        src = clean_notebook_markdown(src)
        cell['source'] = src

    # Markdown cell explaining the injected setup — transparency for users
    setup_notice = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "> **\u2699\ufe0f Setup cell added by [doQumentation](https://doqumentation.org)**\n",
            ">\n",
            "> The code cell below was added automatically to install required packages\n",
            "> (skipped if already installed, e.g. on Binder/Code Engine).\n",
            "> It also contains a commented-out template for IBM Quantum credentials.\n",
            "> [Learn more about automatic modifications.](https://doqumentation.org/about/code-modifications)"
        ]
    }

    nb['cells'] = [setup_notice, prereq_cell] + cells

    # Colab notebook metadata: auto-run the first cell on open
    colab_meta = nb.setdefault('metadata', {}).setdefault('colab', {})
    colab_meta['cell_execution_strategy'] = 'setup'

    content = json.dumps(nb, indent=1, ensure_ascii=False)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(content)


def publish_notebooks_to_static():
    """Copy notebooks/ into static/notebooks/ for GitHub Pages deployment.

    This makes dependency-ready notebook copies available on gh-pages so that
    "Open in Colab" and "Open in Binder Lab" links can point to them.
    """
    print("\n📦 Publishing notebooks to static/notebooks/...")
    static_nb = STATIC_DIR / "notebooks"
    if static_nb.exists():
        shutil.rmtree(static_nb)
    if NOTEBOOKS_OUTPUT.exists():
        shutil.copytree(NOTEBOOKS_OUTPUT, static_nb)
        count = sum(1 for f in static_nb.rglob('*') if f.is_file())
        print(f"  ✓ {count} files copied to static/notebooks/")
    else:
        print("  ⚠️  No notebooks/ directory found, skipping")


# ---------------------------------------------------------------------------
# Translated notebook generation
# ---------------------------------------------------------------------------

FALLBACK_MARKER = '{/* doqumentation-untranslated-fallback */}'


def parse_mdx_segments(mdx_text: str) -> list:
    """Parse MDX into alternating text/code segments.

    Returns a list of dicts: {'type': 'text'|'code', 'content': str, 'lang': str|None}
    Code segments include the language tag (e.g. 'python').
    The frontmatter and <OpenInLabBanner> are stripped from the first text segment.
    """
    segments = []
    # Split on code fences: ```lang ... ```
    # We need to handle ``` with and without language tags
    parts = re.split(r'^(```\w*)\s*$', mdx_text, flags=re.MULTILINE)

    # parts alternates: [text, fence_open, code_content_until_close, ...]
    # But the regex split is trickier. Let me use a line-by-line parser instead.
    segments = []
    lines = mdx_text.split('\n')
    current_text = []
    current_code = []
    in_code = False
    code_lang = None

    for line in lines:
        if not in_code:
            fence_match = re.match(r'^```(\w+)\s*$', line)
            if fence_match:
                # Save accumulated text
                text = '\n'.join(current_text)
                if text.strip():
                    segments.append({'type': 'text', 'content': text})
                current_text = []
                in_code = True
                code_lang = fence_match.group(1)
                current_code = []
            else:
                current_text.append(line)
        else:
            if line.strip() == '```':
                # End of code block
                code = '\n'.join(current_code)
                segments.append({'type': 'code', 'content': code, 'lang': code_lang})
                in_code = False
                current_code = []
                code_lang = None
            else:
                current_code.append(line)

    # Remaining text
    text = '\n'.join(current_text)
    if text.strip():
        segments.append({'type': 'text', 'content': text})

    # Strip frontmatter and OpenInLabBanner from first text segment
    if segments and segments[0]['type'] == 'text':
        content = segments[0]['content']
        # Remove YAML frontmatter
        content = re.sub(r'^---\n.*?\n---\n?', '', content, count=1, flags=re.DOTALL)
        # Remove OpenInLabBanner
        content = re.sub(r'<OpenInLabBanner[^>]*/>\s*\n?', '', content)
        # Remove fallback marker
        content = content.replace(FALLBACK_MARKER, '')
        segments[0]['content'] = content

    return segments


def clean_notebook_markdown(text: str) -> str:
    """Clean translated MDX text for use in a Jupyter notebook markdown cell.

    Strips Docusaurus-specific syntax and reverses MDX escaping.
    """
    # Strip heading anchors: ## Title {#english-anchor} → ## Title
    text = re.sub(r'\s*\{#[a-z0-9_-]+\}\s*$', '', text, flags=re.MULTILINE)

    # Unescape MDX characters
    text = text.replace('\\{', '{').replace('\\}', '}')

    # Remove JSX comments (single- and multi-line)
    text = re.sub(r'\{/\*.*?\*/\}', '', text, flags=re.DOTALL)

    # Convert <Admonition> to blockquote
    def admonition_to_blockquote(m):
        atype = m.group(1) or 'note'
        body = m.group(2).strip()
        label = atype.capitalize()
        # Indent body lines with >
        lines = body.split('\n')
        quoted = '\n'.join(f'> {l}' for l in lines)
        return f'> **{label}:** {quoted.lstrip("> ")}'

    text = re.sub(
        r'<Admonition\s+type="(\w+)"[^>]*>\s*(.*?)\s*</Admonition>',
        admonition_to_blockquote, text, flags=re.DOTALL
    )
    # Handle <Admonition> without type
    text = re.sub(
        r'<Admonition[^>]*>\s*(.*?)\s*</Admonition>',
        lambda m: f'> **Note:** {m.group(1).strip()}', text, flags=re.DOTALL
    )

    # Strip <OpenInLabBanner> if somehow still present
    text = re.sub(r'<OpenInLabBanner[^/]*/>\s*', '', text)

    return text.strip()


def _is_output_content(text: str) -> bool:
    """Check if a text segment looks like code cell output rather than markdown."""
    stripped = text.strip()
    if not stripped:
        return True
    # Image output: ![alt](./output_N.png)
    if re.match(r'^!\[.*\]\(.*output.*\)$', stripped):
        return True
    # LaTeX block output
    if stripped.startswith('$$') and stripped.endswith('$$'):
        return True
    return False


def generate_translated_notebook(english_ipynb_path: Path,
                                  translated_mdx_path: Path,
                                  output_path: Path,
                                  nb_rel_path: Path) -> bool:
    """Generate a translated notebook by merging English .ipynb with translated MDX.

    Uses the English notebook as a skeleton: code cells and outputs stay unchanged,
    markdown cells are replaced with translated text from the MDX.

    Args:
        english_ipynb_path: Path to the original English .ipynb
        translated_mdx_path: Path to the translated .mdx file
        output_path: Where to write the translated .ipynb
        nb_rel_path: Notebook path relative to notebooks root (for image path rewriting)
    """
    try:
        nb = json.loads(english_ipynb_path.read_text())
        mdx_text = translated_mdx_path.read_text()
        cells = nb.get('cells', [])
        if not cells:
            return False

        # Extract translated title from MDX frontmatter
        title_match = re.search(r'^title:\s*"(.+)"', mdx_text, re.MULTILINE)
        translated_title = title_match.group(1).replace('\\"', '"') if title_match else None

        # Parse MDX into segments
        segments = parse_mdx_segments(mdx_text)
        mdx_code_blocks = [s for s in segments if s['type'] == 'code']
        mdx_text_blocks = [s for s in segments if s['type'] == 'text']

        # Filter out pip install blocks from MDX code blocks (injected by sync-content.py)
        mdx_code_blocks = [
            b for b in mdx_code_blocks
            if 'Added by doQumentation' not in b['content']
        ]

        # Group notebook cells into spans between code cells
        # Each span: (start_idx, end_idx) of markdown cells, followed by a code cell
        nb_code_indices = [i for i, c in enumerate(cells) if c.get('cell_type') == 'code']

        # Build text segments between code blocks from MDX
        # Walk segments in order, collecting text blocks between code blocks
        text_spans = []  # list of joined text for each gap between code blocks
        current_texts = []

        for seg in segments:
            if seg['type'] == 'text':
                cleaned = seg['content'].strip()
                if cleaned and not _is_output_content(cleaned):
                    current_texts.append(cleaned)
            elif seg['type'] == 'code':
                # Skip pip install blocks
                if 'Added by doQumentation' in seg['content']:
                    continue
                text_spans.append('\n\n'.join(current_texts) if current_texts else '')
                current_texts = []

        # Trailing text after last code block
        text_spans.append('\n\n'.join(current_texts) if current_texts else '')

        # Now map text_spans to markdown cells between code cells in the notebook
        # Span 0: before first code cell
        # Span i: between code cell i-1 and code cell i
        # Last span: after last code cell
        boundaries = [-1] + nb_code_indices + [len(cells)]

        for span_idx in range(len(boundaries) - 1):
            start = boundaries[span_idx] + 1
            end = boundaries[span_idx + 1]

            # Collect markdown cells in this span
            md_indices = [i for i in range(start, end)
                          if cells[i].get('cell_type') == 'markdown']

            if not md_indices or span_idx >= len(text_spans):
                continue

            translated_text = text_spans[span_idx]
            if not translated_text:
                continue

            translated_text = clean_notebook_markdown(translated_text)

            if len(md_indices) == 1:
                # Simple case: one markdown cell ↔ one text block
                cell_text = translated_text
                # For the very first cell, prepend the title if it was stripped
                if span_idx == 0 and translated_title:
                    # Check if the original cell started with a heading
                    orig_src = cell_source(cells[md_indices[0]])
                    if orig_src.lstrip().startswith('#'):
                        cell_text = f'# {translated_title}\n\n{translated_text}'
                cells[md_indices[0]]['source'] = cell_text
            else:
                # Multiple markdown cells → split by heading boundaries
                heading_pattern = re.compile(r'^(#{1,4}\s+.+)$', re.MULTILINE)
                parts = heading_pattern.split(translated_text)

                # Reconstruct: group heading + following text
                chunks = []
                current_chunk = []
                for part in parts:
                    if heading_pattern.match(part):
                        if current_chunk:
                            chunks.append('\n'.join(current_chunk).strip())
                        current_chunk = [part]
                    else:
                        current_chunk.append(part)
                if current_chunk:
                    chunks.append('\n'.join(current_chunk).strip())

                # Remove empty chunks
                chunks = [c for c in chunks if c.strip()]

                # For the first cell in span 0, prepend title
                if span_idx == 0 and translated_title and chunks:
                    orig_src = cell_source(cells[md_indices[0]])
                    if orig_src.lstrip().startswith('#'):
                        chunks[0] = f'# {translated_title}\n\n{chunks[0]}'

                if len(chunks) == len(md_indices):
                    # Perfect match — assign 1:1
                    for i, idx in enumerate(md_indices):
                        cells[idx]['source'] = chunks[i]
                else:
                    # Can't split cleanly — merge all into first cell
                    cells[md_indices[0]]['source'] = translated_text
                    if span_idx == 0 and translated_title:
                        orig_src = cell_source(cells[md_indices[0]])
                        if not translated_text.lstrip().startswith('#'):
                            cells[md_indices[0]]['source'] = f'# {translated_title}\n\n{translated_text}'
                    for idx in md_indices[1:]:
                        cells[idx]['source'] = ''

        # Apply the same post-processing as copy_notebook_with_rewrite():
        # image path rewriting, pip install injection, Colab metadata
        content = json.dumps(nb, indent=1, ensure_ascii=False)
        content = rewrite_notebook_image_paths(content, nb_rel_path)
        nb = json.loads(content)
        cells = nb.get('cells', [])

        # Inject single prerequisites cell (same as copy_notebook_with_rewrite)
        all_pkgs = list(COLAB_BASE_PKGS)
        for p in analyze_notebook_imports(cells):
            if p not in all_pkgs:
                all_pkgs.append(p)

        prereq_cell = _make_prereq_cell(all_pkgs)

        nb['cells'] = [prereq_cell] + cells

        # Colab metadata
        colab_meta = nb.setdefault('metadata', {}).setdefault('colab', {})
        colab_meta['cell_execution_strategy'] = 'setup'

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False))
        return True

    except Exception as e:
        print(f"    Error generating translated notebook: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_locale_notebooks(locale: str):
    """Generate translated notebooks for a locale from its translated MDX files.

    For each translated MDX that has a notebook_path in frontmatter (and is not
    an untranslated fallback), merge the translated text into the English notebook
    to produce a translated .ipynb in static/notebooks/.
    """
    i18n_dir = PROJECT_ROOT / "i18n" / locale / "docusaurus-plugin-content-docs" / "current"
    static_nb = STATIC_DIR / "notebooks"

    if not i18n_dir.exists():
        print(f"  ⚠️  No i18n directory for locale '{locale}'")
        return

    print(f"\n📓 Generating translated notebooks for '{locale}'...")
    count = 0
    skipped = 0
    errors = 0

    for mdx_path in sorted(i18n_dir.rglob('*.mdx')):
        mdx_text = mdx_path.read_text()

        # Skip untranslated fallbacks
        if FALLBACK_MARKER in mdx_text:
            continue

        # Extract notebook_path from frontmatter
        nb_match = re.search(r'^notebook_path:\s*"(.+)"', mdx_text, re.MULTILINE)
        if not nb_match:
            continue  # Not a notebook-based page

        notebook_path = nb_match.group(1)  # e.g. "tutorials/foo.ipynb"

        # Find the upstream English notebook (upstream stores under docs/)
        english_nb = UPSTREAM_DIR / "docs" / notebook_path
        if not english_nb.exists():
            # doQumentation custom Hello World — local-content first, then
            # upstream root (legacy fork submodule layout).
            english_nb = LOCAL_CONTENT_DIR / Path(notebook_path).name
            if not english_nb.exists():
                english_nb = UPSTREAM_DIR / Path(notebook_path).name
            if not english_nb.exists():
                skipped += 1
                continue

        # Determine output path from MDX location (mirrors the docs/ structure)
        # e.g. i18n/de/.../tutorials/hello-world.mdx → tutorials/hello-world.ipynb
        mdx_rel = mdx_path.relative_to(i18n_dir)
        nb_rel = mdx_rel.with_suffix('.ipynb')
        output_path = static_nb / nb_rel
        nb_rel_path = nb_rel

        if generate_translated_notebook(english_nb, mdx_path, output_path, nb_rel_path):
            count += 1
        else:
            errors += 1

    print(f"  ✓ {count} translated notebooks generated, {skipped} skipped, {errors} errors")


def sync_upstream_images():
    """Copy upstream images from public/ to static/ for Docusaurus.

    Upstream stores images in public/docs/images/ and public/learning/images/.
    Docusaurus serves static/ at the site root, so:
      public/docs/images/tutorials/foo.avif → static/docs/images/tutorials/foo.avif
      (served at /docs/images/tutorials/foo.avif)
    """
    print("\n🖼  Syncing upstream images...")

    image_mappings = [
        ("public/docs/images/tutorials", "docs/images/tutorials"),
        ("public/docs/images/guides", "docs/images/guides"),
        ("public/docs/open-source", "docs/open-source"),
        ("public/learning/images", "learning/images"),
    ]

    total = 0
    for src_rel, dst_rel in image_mappings:
        src_dir = UPSTREAM_DIR / src_rel
        dst_dir = STATIC_DIR / dst_rel

        if not src_dir.exists():
            print(f"  Warning: {src_rel} not found in upstream")
            continue

        # Clean and recreate
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)

        # Overlay local-content images (e.g. courses added to this repo only)
        overlay = LOCAL_CONTENT_DIR / src_rel
        if overlay.exists():
            shutil.copytree(overlay, dst_dir, dirs_exist_ok=True)
            print(f"  ✓ {src_rel} (local-content overlay merged)")

        count = sum(1 for _ in dst_dir.rglob('*') if _.is_file())
        total += count
        print(f"  ✓ {src_rel} → static/{dst_rel} ({count} files)")

    print(f"  Total: {total} images synced")

    # Also copy images to notebooks/ so Jupyter can serve them
    print("\n🖼  Copying images to notebooks/ for Jupyter...")
    nb_image_mappings = [
        (STATIC_DIR / "docs/images/tutorials", NOTEBOOKS_OUTPUT / "docs/images/tutorials"),
        (STATIC_DIR / "docs/images/guides", NOTEBOOKS_OUTPUT / "docs/images/guides"),
        (STATIC_DIR / "learning/images", NOTEBOOKS_OUTPUT / "learning/images"),
    ]

    nb_total = 0
    for src_dir, dst_dir in nb_image_mappings:
        if not src_dir.exists():
            continue

        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)

        count = sum(1 for _ in dst_dir.rglob('*') if _.is_file())
        nb_total += count
        print(f"  ✓ {src_dir.relative_to(STATIC_DIR)} → notebooks/{dst_dir.relative_to(NOTEBOOKS_OUTPUT)} ({count} files)")

    print(f"  Total: {nb_total} images copied for Jupyter")


def generate_sidebar_from_toc():
    """Parse _toc.json and generate structured sidebar configuration."""
    print("\n📋 Generating sidebar from _toc.json...")

    toc_path = UPSTREAM_DIR / "docs" / "tutorials" / "_toc.json"
    if not toc_path.exists():
        print("  Warning: _toc.json not found, falling back to flat list")
        generate_sidebar_flat()
        return

    toc = json.loads(toc_path.read_text())
    children = toc.get('children', [])

    sidebar_items = toc_children_to_sidebar(children)

    # Prepend custom Hello World (doQumentation's own intro). Same source
    # precedence as process_tutorials: local-content/ first, upstream fallback.
    custom_hw = LOCAL_CONTENT_DIR / "hello-world.ipynb"
    if not custom_hw.exists():
        custom_hw = UPSTREAM_DIR / "hello-world.ipynb"
    if custom_hw.exists():
        sidebar_items.insert(0, sidebar_doc_item("tutorials/hello-world"))

    sidebar_json = PROJECT_ROOT / "sidebar-generated.json"
    sidebar_json.write_text(json.dumps(sidebar_items, indent=2))

    # Count tutorials
    def count_docs(items):
        n = 0
        for item in items:
            if isinstance(item, str):
                n += 1
            elif isinstance(item, dict) and item.get('type') == 'doc':
                n += 1
            elif isinstance(item, dict) and 'items' in item:
                n += count_docs(item['items'])
        return n

    print(f"  Found {count_docs(sidebar_items)} tutorials in {len(sidebar_items)} categories")
    print(f"  ✓ Generated {sidebar_json}")


def generate_sidebar_flat():
    """Fallback: generate a flat sidebar from docs/tutorials/*.mdx files."""
    tutorials_dir = DOCS_OUTPUT / "tutorials"
    if not tutorials_dir.exists():
        print("  Warning: No tutorials directory found")
        return

    tutorials = []
    for mdx_file in sorted(tutorials_dir.glob("*.mdx")):
        if mdx_file.name == 'index.mdx':
            continue
        tutorials.append(sidebar_doc_item(f"tutorials/{mdx_file.stem}"))

    print(f"  Found {len(tutorials)} tutorials (flat)")

    sidebar_json = PROJECT_ROOT / "sidebar-generated.json"
    sidebar_json.write_text(json.dumps(tutorials, indent=2))
    print(f"  ✓ Generated {sidebar_json}")


def process_courses():
    """Process all course files from upstream and local-content overlay."""
    print("\n📚 Processing courses...")

    courses_dst = DOCS_OUTPUT / "learning" / "courses"
    notebooks_dst = NOTEBOOKS_OUTPUT / "learning" / "courses"

    # Source roots: upstream submodule + optional in-repo overlay
    course_roots = [
        UPSTREAM_DIR / "learning" / "courses",
        LOCAL_CONTENT_DIR / "learning" / "courses",
    ]
    course_roots = [r for r in course_roots if r.exists()]
    if not course_roots:
        print(f"  Warning: No course source directories found")
        return

    # Clean output directories
    if courses_dst.exists():
        shutil.rmtree(courses_dst)
    courses_dst.mkdir(parents=True)

    if notebooks_dst.exists():
        shutil.rmtree(notebooks_dst)
    notebooks_dst.mkdir(parents=True)

    # Track statistics
    stats = {"mdx": 0, "ipynb": 0, "images": 0, "skipped": 0}

    # When the same course name appears in both upstream and local-content,
    # prefer upstream — local-content is meant as a cherry-pick workaround for
    # courses upstream hasn't shipped yet, not a parallel source of truth. The
    # ordering of course_roots above puts upstream first, so a name we've
    # already seen wins. (The original example, "use-a-qc-today" from PR #37,
    # was retired once upstream caught up — see commit removing its overlay.)
    course_dirs = []
    seen_names: Set[str] = set()
    for root in course_roots:
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            if d.name in seen_names:
                print(f"  ⚠ Skipping local-content overlay for '{d.name}' — upstream version takes precedence")
                continue
            seen_names.add(d.name)
            course_dirs.append((d, root))

    for course_dir, courses_src in course_dirs:
        course_name = course_dir.name
        print(f"\n  Course: {course_name}")

        for src_path in course_dir.rglob('*'):
            if src_path.is_dir():
                continue

            rel_path = src_path.relative_to(courses_src)

            # Skip _toc.json (used for sidebar generation, not content)
            if src_path.name == '_toc.json':
                stats["skipped"] += 1
                continue

            if src_path.suffix == '.mdx':
                dst_path = courses_dst / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                content = src_path.read_text()

                # Strip upstream frontmatter and replace with ours
                title = None
                description = None
                if content.startswith('---'):
                    fm_end = re.search(r'^---\s*$', content[3:], re.MULTILINE)
                    if fm_end:
                        fm_text = content[3:3 + fm_end.start()]
                        t_match = re.search(r'^title:\s*(.+)$', fm_text, re.MULTILINE)
                        if t_match:
                            title = t_match.group(1).strip().strip('"\'')
                        d_match = re.search(r'^description:\s*(.+)$', fm_text, re.MULTILINE)
                        if d_match:
                            description = d_match.group(1).strip().strip('"\'')
                        content = content[3 + fm_end.end():].lstrip()

                # Extract title from first heading if not in frontmatter
                if not title:
                    h1_match = re.match(r'^#\s+(.+)$', content.lstrip(), re.MULTILINE)
                    if h1_match:
                        title = h1_match.group(1).strip()
                if not title:
                    title = src_path.stem.replace('-', ' ').replace('_', ' ').title()

                transformed = transform_mdx(content, src_path)

                # Build new frontmatter
                safe_title = title.replace('"', '\\"')
                fm = f'---\ntitle: "{safe_title}"'
                if description:
                    safe_desc = description.replace('"', '\\"')
                    fm += f'\ndescription: "{safe_desc}"'
                fm += '\n---\n\n'

                dst_path.write_text(fm + transformed)
                stats["mdx"] += 1
                print(f"    ✓ {rel_path}")

            elif src_path.suffix == '.ipynb':
                dst_path = courses_dst / rel_path.with_suffix('.mdx')
                # Upstream path for Binder/Lab
                upstream_nb_path = f"learning/courses/{rel_path}"
                # Avoid duplicate route when file stem == parent dir name
                # (Docusaurus treats foo/foo.mdx as category index, conflicting with foo/index.mdx)
                nb_slug = None
                if src_path.stem == src_path.parent.name:
                    nb_slug = f"./{src_path.stem}"
                if convert_notebook(src_path, dst_path, notebook_path=upstream_nb_path, slug=nb_slug):
                    stats["ipynb"] += 1
                    print(f"    ✓ {rel_path} → .mdx")
                else:
                    stats["skipped"] += 1

                # Copy original notebook for "Open in Lab" (rewrite image paths)
                nb_dst = notebooks_dst / rel_path
                nb_rel = Path('learning/courses') / rel_path
                copy_notebook_with_rewrite(src_path, nb_dst, nb_rel)

            elif src_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'):
                dst_path = courses_dst / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_path, dst_path)
                stats["images"] += 1

            else:
                stats["skipped"] += 1

    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, "
          f"{stats['images']} images, {stats['skipped']} skipped")


def generate_course_sidebar():
    """Generate sidebar configuration for courses from per-course _toc.json files."""
    print("\n📋 Generating course sidebar...")

    course_roots = [
        UPSTREAM_DIR / "learning" / "courses",
        LOCAL_CONTENT_DIR / "learning" / "courses",
    ]
    course_roots = [r for r in course_roots if r.exists()]
    if not course_roots:
        print("  Warning: No courses directories found")
        return

    # Same dedup policy as process_courses(): upstream wins over local-content
    # for same-named courses. Keeps sidebar in sync with the docs that were
    # actually written.
    course_items = []
    course_dirs = []
    seen_names: Set[str] = set()
    for root in course_roots:
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            if d.name in seen_names:
                continue
            seen_names.add(d.name)
            course_dirs.append(d)

    for course_dir in course_dirs:
        toc_path = course_dir / "_toc.json"
        if not toc_path.exists():
            print(f"  Warning: No _toc.json for {course_dir.name}")
            continue

        toc = json.loads(toc_path.read_text())
        course_title = toc.get('title', course_dir.name.replace('-', ' ').title())
        children = toc.get('children', [])

        # Build sidebar items for this course
        sub_items = toc_children_to_sidebar(children)
        if not sub_items:
            continue

        # Find the overview entry to use as category link
        overview_id = f"learning/courses/{course_dir.name}/index"
        course_cat = {
            'type': 'category',
            'label': course_title,
            'collapsed': True,
            'link': {'type': 'doc', 'id': overview_id},
            'items': sub_items,
        }
        course_items.append(course_cat)

    sidebar_json = PROJECT_ROOT / "sidebar-courses.json"
    sidebar_json.write_text(json.dumps(course_items, indent=2))

    print(f"  Found {len(course_items)} courses")
    print(f"  ✓ Generated {sidebar_json}")


def process_modules():
    """Process all module files from upstream."""
    print("\n🎓 Processing modules...")

    modules_src = UPSTREAM_DIR / "learning" / "modules"
    modules_dst = DOCS_OUTPUT / "learning" / "modules"
    notebooks_dst = NOTEBOOKS_OUTPUT / "learning" / "modules"

    if not modules_src.exists():
        print(f"  Warning: Modules directory not found at {modules_src}")
        return

    # Clean output directories
    if modules_dst.exists():
        shutil.rmtree(modules_dst)
    modules_dst.mkdir(parents=True)

    if notebooks_dst.exists():
        shutil.rmtree(notebooks_dst)
    notebooks_dst.mkdir(parents=True)

    # Track statistics
    stats = {"mdx": 0, "ipynb": 0, "images": 0, "skipped": 0}

    for module_dir in sorted(modules_src.iterdir()):
        if not module_dir.is_dir():
            continue

        module_name = module_dir.name
        print(f"\n  Module: {module_name}")

        for src_path in module_dir.rglob('*'):
            if src_path.is_dir():
                continue

            rel_path = src_path.relative_to(modules_src)

            # Skip _toc.json (used for sidebar generation, not content)
            if src_path.name == '_toc.json':
                stats["skipped"] += 1
                continue

            if src_path.suffix == '.mdx':
                dst_path = modules_dst / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                content = src_path.read_text()

                # Strip upstream frontmatter and replace with ours
                title = None
                description = None
                if content.startswith('---'):
                    fm_end = re.search(r'^---\s*$', content[3:], re.MULTILINE)
                    if fm_end:
                        fm_text = content[3:3 + fm_end.start()]
                        t_match = re.search(r'^title:\s*(.+)$', fm_text, re.MULTILINE)
                        if t_match:
                            title = t_match.group(1).strip().strip('"\'')
                        d_match = re.search(r'^description:\s*(.+)$', fm_text, re.MULTILINE)
                        if d_match:
                            description = d_match.group(1).strip().strip('"\'')
                        content = content[3 + fm_end.end():].lstrip()

                # Extract title from first heading if not in frontmatter
                if not title:
                    h1_match = re.match(r'^#\s+(.+)$', content.lstrip(), re.MULTILINE)
                    if h1_match:
                        title = h1_match.group(1).strip()
                if not title:
                    title = src_path.stem.replace('-', ' ').replace('_', ' ').title()

                transformed = transform_mdx(content, src_path)

                # Build new frontmatter
                safe_title = title.replace('"', '\\"')
                fm = f'---\ntitle: "{safe_title}"'
                if description:
                    safe_desc = description.replace('"', '\\"')
                    fm += f'\ndescription: "{safe_desc}"'
                fm += '\n---\n\n'

                dst_path.write_text(fm + transformed)
                stats["mdx"] += 1
                print(f"    ✓ {rel_path}")

            elif src_path.suffix == '.ipynb':
                dst_path = modules_dst / rel_path.with_suffix('.mdx')
                # Upstream path for Binder/Lab
                upstream_nb_path = f"learning/modules/{rel_path}"
                # Avoid duplicate route when file stem == parent dir name
                nb_slug = None
                if src_path.stem == src_path.parent.name:
                    nb_slug = f"./{src_path.stem}"
                if convert_notebook(src_path, dst_path, notebook_path=upstream_nb_path, slug=nb_slug):
                    stats["ipynb"] += 1
                    print(f"    ✓ {rel_path} → .mdx")
                else:
                    stats["skipped"] += 1

                # Copy original notebook for "Open in Lab" (rewrite image paths)
                nb_dst = notebooks_dst / rel_path
                nb_rel = Path('learning/modules') / rel_path
                copy_notebook_with_rewrite(src_path, nb_dst, nb_rel)

            elif src_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'):
                dst_path = modules_dst / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_path, dst_path)
                stats["images"] += 1

            else:
                stats["skipped"] += 1

    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, "
          f"{stats['images']} images, {stats['skipped']} skipped")


def process_workshops():
    """Convert workshop notebooks from workshop-notebooks/ to docs/workshop/."""
    print("\n🛠️  Processing workshop notebooks...")

    if not WORKSHOP_DIR.exists():
        print(f"  No workshop-notebooks/ directory found — skipping")
        return

    workshop_dst = DOCS_OUTPUT / "workshop"
    notebooks_dst = NOTEBOOKS_OUTPUT / "workshop"

    # Clean stale generated files — keep only index.mdx (manually maintained).
    # Removes stale converted .mdx + extracted image dirs from previous runs
    # (e.g. after notebooks are renamed/renumbered, old files would otherwise
    # remain and serve their old images to renamed notebooks via filename
    # collision on shared output_N.png).
    if workshop_dst.exists():
        import shutil
        workshop_src_files = {p.stem for p in WORKSHOP_DIR.rglob('*.ipynb')}
        for existing in workshop_dst.iterdir():
            if existing.name == 'index.mdx':
                continue
            if existing.suffix == '.mdx' and existing.stem not in workshop_src_files:
                existing.unlink()
            elif existing.is_dir() and existing.name.startswith('_') and existing.name.endswith('_imgs'):
                # Legacy per-notebook image dir from pre-migration layout — always remove.
                shutil.rmtree(existing)
            elif existing.name.startswith('output_') and existing.suffix == '.png':
                # Old flat-layout images from before per-notebook subdirs
                existing.unlink()
        # Prune stale slugs under static/img/workshop/ for renamed/removed notebooks.
        valid_slugs = {re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-') for stem in workshop_src_files}
        static_workshop = STATIC_DIR / 'img' / 'workshop'
        if static_workshop.exists():
            for d in static_workshop.iterdir():
                if d.is_dir() and d.name not in valid_slugs:
                    shutil.rmtree(d)
    notebooks_dst.mkdir(parents=True, exist_ok=True)

    stats = {"ipynb": 0, "mdx": 0, "images": 0, "skipped": 0}

    for src_path in sorted(WORKSHOP_DIR.rglob('*')):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(WORKSHOP_DIR)

        if src_path.suffix == '.ipynb':
            dst_path = workshop_dst / rel_path.with_suffix('.mdx')
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            nb_path = f"workshop/{rel_path}"
            nb_slug = None
            if src_path.stem == src_path.parent.name:
                nb_slug = f"./{src_path.stem}"
            if convert_notebook(src_path, dst_path, notebook_path=nb_path, slug=nb_slug):
                stats["ipynb"] += 1
                # Post-process: fix common MDX issues in workshop notebooks
                content = dst_path.read_text()
                # Fix non-self-closing <img> tags (MDX requires <img ... />)
                content = re.sub(r'<img\b(.*?)(?<!\/)>', r'<img\1 />', content)
                # Add onError fallback for external images (JSX syntax for MDX)
                content = re.sub(
                    r'<img\b(.*?src="https?://[^"]*".*?)\s*/>',
                    r'<img\1 onError={(e) => e.target.style.display="none"} />',
                    content
                )
                # Fix LaTeX math in workshop notebooks:
                # 1. Undo brace escaping inside LaTeX environments
                def unescape_math_env(m):
                    return m.group(0).replace('\\{', '{').replace('\\}', '}')
                content = re.sub(
                    r'\\begin\\\{.*?\\end\\\{[^}]*\\\}',
                    unescape_math_env, content, flags=re.DOTALL
                )
                # 2. Wrap bare \begin{env}...\end{env} in $$ if not already in math
                lines = content.split('\n')
                out_lines = []
                i = 0
                in_math = False
                while i < len(lines):
                    line = lines[i]
                    if line.strip() == '$$':
                        in_math = not in_math
                    if not in_math and re.match(r'^\s*\\begin\{', line):
                        out_lines.append('$$')
                        while i < len(lines):
                            out_lines.append(lines[i])
                            if re.match(r'^\s*\\end\{', lines[i]):
                                i += 1
                                break
                            i += 1
                        out_lines.append('$$')
                    else:
                        out_lines.append(line)
                    i += 1
                content = '\n'.join(out_lines)
                # 3. Fix $$$ (triple dollar) → $$ + newline
                content = content.replace('$$$', '$$\n$$')
                # Add source filename and description to frontmatter
                if content.startswith('---'):
                    fm_end = content.index('\n---', 3)
                    fm = content[3:fm_end]
                    body = content[fm_end + 4:]
                    extra_fm = ''
                    # Source filename
                    extra_fm += f'\nsource_file: "{src_path.name}"'
                    # Extract description if missing
                    if 'description:' not in fm:
                        # Scan body for first substantive paragraph (>30 chars, starts with letter)
                        desc = ''
                        for para in re.split(r'\n\n+', body):
                            text = para.strip()
                            # Skip headings, code blocks, imports, images, frontmatter-like lines
                            if (text and not text.startswith('#') and not text.startswith('```')
                                and not text.startswith('<') and not text.startswith('import ')
                                and not text.startswith('$$') and not text.startswith('---')
                                and len(text) > 30 and text[0].isalpha()):
                                # Truncate at 160 chars
                                desc = text[:160].replace('"', '\\"')
                                if len(text) > 160:
                                    desc = desc.rsplit(' ', 1)[0] + '...'
                                break
                        if desc:
                            extra_fm += f'\ndescription: "{desc}"'
                    content = f'---{fm}{extra_fm}\n---{body}'
                # Hide notebooks with _solution or _hidden in filename
                # unlisted: true hides from generated-index cards and search
                # sidebar_class_name: hidden hides from sidebar navigation
                stem_lower = src_path.stem.lower()
                # Strip broken image references for notebooks whose extracted
                # outputs don't exist in the open-source repo (e.g. IBM course
                # notebooks where images are generated by IBM's build pipeline)
                STRIP_IMAGES_NOTEBOOKS = {
                    '01_build-and-run-your-first-quantum-program',
                    '02_quantum-mechanics-basics',
                }
                if src_path.stem in STRIP_IMAGES_NOTEBOOKS:
                    before = content.count('\n')
                    content = re.sub(r'^!\[[^\]]*\]\(/learning/images/[^\)]+\)\s*\n?', '', content, flags=re.MULTILINE)
                    stripped = before - content.count('\n')
                    if stripped:
                        print(f"    ⚠ Stripped {stripped} broken image reference(s) from {rel_path}")

                if '_solution' in stem_lower or '_hidden' in stem_lower:
                    if content.startswith('---'):
                        content = content.replace('---\n', '---\nunlisted: true\nsidebar_class_name: hidden\n', 1)
                    print(f"    ✓ {rel_path} → .mdx (unlisted — direct URL only)")
                else:
                    print(f"    ✓ {rel_path} → .mdx")
                dst_path.write_text(content)
            else:
                stats["skipped"] += 1

            # Copy original notebook for "Open in Lab"
            nb_dst = notebooks_dst / rel_path
            nb_dst.parent.mkdir(parents=True, exist_ok=True)
            copy_notebook_with_rewrite(src_path, nb_dst, Path('workshop') / rel_path)

        elif src_path.suffix == '.mdx':
            dst_path = workshop_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            content = src_path.read_text()
            transformed = transform_mdx(content, src_path)
            dst_path.write_text(transformed)
            stats["mdx"] += 1
            print(f"    ✓ {rel_path}")

        elif src_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'):
            dst_path = workshop_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, dst_path)
            stats["images"] += 1

        else:
            stats["skipped"] += 1

    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, "
          f"{stats['images']} images, {stats['skipped']} skipped")


def generate_module_sidebar():
    """Generate sidebar configuration for modules from per-module _toc.json files."""
    print("\n📋 Generating module sidebar...")

    modules_src = UPSTREAM_DIR / "learning" / "modules"
    if not modules_src.exists():
        print("  Warning: No modules directory found")
        return

    module_items = []
    for module_dir in sorted(modules_src.iterdir()):
        if not module_dir.is_dir():
            continue

        toc_path = module_dir / "_toc.json"
        if not toc_path.exists():
            print(f"  Warning: No _toc.json for {module_dir.name}")
            continue

        toc = json.loads(toc_path.read_text())
        module_title = toc.get('title', module_dir.name.replace('-', ' ').title())
        children = toc.get('children', [])

        # Build sidebar items for this module
        sub_items = toc_children_to_sidebar(children)
        if not sub_items:
            continue

        # Find the overview entry to use as category link
        overview_id = f"learning/modules/{module_dir.name}/index"
        module_cat = {
            'type': 'category',
            'label': module_title,
            'collapsed': True,
            'link': {'type': 'doc', 'id': overview_id},
            'items': sub_items,
        }
        module_items.append(module_cat)

    sidebar_json = PROJECT_ROOT / "sidebar-modules.json"
    sidebar_json.write_text(json.dumps(module_items, indent=2))

    print(f"  Found {len(module_items)} modules")
    print(f"  ✓ Generated {sidebar_json}")


def create_index_page():
    """Ensure the site home page (docs/index.mdx) exists.

    The committed docs/index.mdx is the source of truth.  If it already
    exists (normal repo checkout), leave it untouched.  Only generate a
    minimal fallback when the file is missing (e.g. fresh --sample-only).
    """
    index_path = DOCS_OUTPUT / "index.mdx"
    if index_path.exists():
        print(f"\n📄 Home page already exists: {index_path} (keeping as-is)")
        return

    print("\n📄 Creating fallback home page...")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("""\
---
title: doQumentation
sidebar_position: 1
slug: /
---

# doQumentation

Home page placeholder — run a full content sync to populate.
""")
    print(f"  ✓ Created fallback {index_path}")


def create_learning_landing_pages():
    """Generate landing pages for /learning/ and /learning/modules/.

    These are index pages that list available courses and modules with links.
    Generated dynamically based on what directories exist after content sync.
    """
    learning_dir = DOCS_OUTPUT / "learning"
    if not learning_dir.exists():
        return

    # --- /learning/index.mdx ---
    courses_dir = learning_dir / "courses"
    modules_dir = learning_dir / "modules"

    course_links = []
    if courses_dir.exists():
        for d in sorted(courses_dir.iterdir()):
            if d.is_dir():
                title = d.name.replace("-", " ").title()
                course_links.append(f"- [{title}](/learning/courses/{d.name})")

    module_links = []
    if modules_dir.exists():
        for d in sorted(modules_dir.iterdir()):
            if d.is_dir():
                title = d.name.replace("-", " ").title()
                module_links.append(f"- [{title}](/learning/modules/{d.name})")

    learning_index = learning_dir / "index.mdx"
    parts = ["---", "title: Learning", "---", "", "# Learning", ""]
    if course_links:
        parts += ["## Courses", ""] + course_links + [""]
    if module_links:
        parts += ["## Modules", ""] + module_links + [""]
    learning_index.write_text("\n".join(parts))
    print(f"  ✓ Created {learning_index}")

    # --- /learning/modules/index.mdx ---
    if modules_dir.exists() and module_links:
        modules_index = modules_dir / "index.mdx"
        parts = ["---", "title: Modules", "---", "", "# Modules", ""]
        parts += module_links + [""]
        modules_index.write_text("\n".join(parts))
        print(f"  ✓ Created {modules_index}")


def create_sample_tutorial():
    """Create a sample tutorial for testing when upstream is not available."""
    print("\n📝 Creating sample tutorial...")

    sample_content = """---
title: Hello World
sidebar_label: Hello World
description: Create your first quantum circuit
---

# Hello World

This tutorial demonstrates how to create and run a simple quantum circuit using Qiskit.

## Prerequisites

Make sure you have Qiskit installed:

```bash noexec
pip install qiskit qiskit-aer
```

## Create a Quantum Circuit

Let's create a simple Bell state circuit:

```python
from qiskit import QuantumCircuit

# Create a circuit with 2 qubits and 2 classical bits
qc = QuantumCircuit(2, 2)

# Apply Hadamard gate to qubit 0
qc.h(0)

# Apply CNOT gate with qubit 0 as control and qubit 1 as target
qc.cx(0, 1)

# Measure both qubits
qc.measure([0, 1], [0, 1])

# Display the circuit
print(qc)
```

## Run on a Simulator

Now let's run the circuit on a local simulator:

```python
from qiskit_aer import AerSimulator

# Create a simulator backend
simulator = AerSimulator()

# Run the circuit
job = simulator.run(qc, shots=1000)
result = job.result()

# Get the counts
counts = result.get_counts(qc)
print(f"Measurement results: {counts}")
```

## Visualize the Results

```python
from qiskit.visualization import plot_histogram

# Plot the histogram of results
plot_histogram(counts)
```

## Next Steps

- Learn about [CHSH inequality](/tutorials/chsh-inequality)
- Explore [Grover's algorithm](/tutorials/grovers-algorithm)
- Try running on real quantum hardware via IBM Quantum

:::note
This tutorial uses a local simulator. To run on real quantum hardware,
you'll need an IBM Quantum account.
:::
"""

    tutorial_path = DOCS_OUTPUT / "tutorials" / "hello-world.mdx"
    tutorial_path.parent.mkdir(parents=True, exist_ok=True)
    tutorial_path.write_text(sample_content)
    print(f"  ✓ Created {tutorial_path}")


def scan_notebook_deps():
    """Scan all notebooks for missing dependencies and print a report.

    Does NOT convert notebooks — just reads .ipynb files and analyzes imports.
    """
    if not UPSTREAM_DIR.exists():
        print("Error: upstream-docs not found. Run sync-content.py first (or with --no-clone).")
        sys.exit(1)

    notebook_dirs = [
        ("tutorials", UPSTREAM_DIR / "docs" / "tutorials"),
        ("guides", UPSTREAM_DIR / "docs" / "guides"),
        ("courses", UPSTREAM_DIR / "learning" / "courses"),
        ("modules", UPSTREAM_DIR / "learning" / "modules"),
    ]

    # {notebook_rel_path: [missing_packages]}
    results: dict[str, list[str]] = {}
    # {package: count}
    package_counts: dict[str, int] = {}
    total_notebooks = 0
    notebooks_with_deps = 0

    for category, base_dir in notebook_dirs:
        if not base_dir.exists():
            continue
        for ipynb_path in sorted(base_dir.rglob('*.ipynb')):
            total_notebooks += 1
            rel_path = ipynb_path.relative_to(UPSTREAM_DIR)
            try:
                nb = json.loads(ipynb_path.read_text())
                cells = nb.get('cells', [])
                missing = analyze_notebook_imports(cells)
                if missing:
                    notebooks_with_deps += 1
                    results[str(rel_path)] = missing
                    for pkg in missing:
                        package_counts[pkg] = package_counts.get(pkg, 0) + 1
            except Exception as e:
                print(f"  Warning: Could not parse {rel_path}: {e}")

    # Print report
    print("=" * 60)
    print("Notebook Dependency Scan Report")
    print("=" * 60)
    print(f"\n{total_notebooks} notebooks scanned")
    print(f"{total_notebooks - notebooks_with_deps} notebooks: all deps satisfied by Binder baseline")
    print(f"{notebooks_with_deps} notebooks: need additional packages")

    if package_counts:
        print(f"\nTop missing packages ({len(package_counts)} unique):")
        for pkg, count in sorted(package_counts.items(), key=lambda x: -x[1]):
            # Check if it's in the Docker full deps
            docker_note = ""
            print(f"  {pkg:30s} {count:3d} notebooks{docker_note}")

    if results:
        print(f"\nPer-notebook details:")
        for nb_path, pkgs in sorted(results.items()):
            print(f"  {nb_path}: {', '.join(pkgs)}")

    # Save report
    report_path = PROJECT_ROOT / ".claude" / "notebook-deps-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Notebook Dependency Scan Report",
        "",
        f"Generated by `sync-content.py --scan-deps`",
        "",
        f"- **{total_notebooks}** notebooks scanned",
        f"- **{total_notebooks - notebooks_with_deps}** all deps satisfied by Binder baseline",
        f"- **{notebooks_with_deps}** need additional packages",
        "",
        "## Top Missing Packages",
        "",
        "| Package | Notebooks |",
        "|---------|-----------|",
    ]
    for pkg, count in sorted(package_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {pkg} | {count} |")

    lines += ["", "## Per-Notebook Details", ""]
    for nb_path, pkgs in sorted(results.items()):
        lines.append(f"- **{nb_path}**: {', '.join(pkgs)}")

    report_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport saved to: {report_path}")


def process_addons():
    """Process Jupyter notebooks from Qiskit addon submodules."""
    print("\n🧩 Processing Qiskit Addons...")

    addons_dst = DOCS_OUTPUT / "qiskit-addons"
    notebooks_dst = NOTEBOOKS_OUTPUT / "qiskit-addons"

    # Clean output directories
    if addons_dst.exists():
        shutil.rmtree(addons_dst)
    addons_dst.mkdir(parents=True)

    if notebooks_dst.exists():
        shutil.rmtree(notebooks_dst)
    notebooks_dst.mkdir(parents=True)

    # Generate the Qiskit Addons index page
    addon_rows = []
    for display_name, config in ADDON_SOURCES.items():
        pip_pkg = config["pip"]
        desc_map = {
            "Circuit Cutting": "Reduce circuit width and depth by cutting gates and wires",
            "SQD": "Sample-based Quantum Diagonalization for ground state estimation",
            "OBP": "Operator Back-Propagation to reduce circuit depth",
            "MPF": "Multi-Product Formulas for improved Hamiltonian simulation",
            "AQC-Tensor": "Approximate Quantum Compilation with tensor networks",
            "PNA": "Propagated Noise Absorption for error mitigation",
            "SLC": "Shaded Lightcones for reducing PEC sampling overhead",
        }
        desc = desc_map.get(display_name, "")
        addon_rows.append(f"| **{display_name}** | `{pip_pkg}` | {desc} |")

    index_content = f"""---
title: Qiskit Addons
sidebar_label: Overview
sidebar_position: 1
description: Tutorials for official Qiskit Addons — circuit cutting, sample-based quantum diagonalization, operator backpropagation, and more.
---

# Qiskit Addons

[Qiskit Addons](https://github.com/Qiskit?q=qiskit-addon) are official extension packages that provide specialized quantum computing algorithms and techniques. Each addon focuses on a specific area and includes tutorials with executable code.

## Available Addons

| Addon | Package | Description |
|-------|---------|-------------|
{chr(10).join(addon_rows)}

All tutorials can be executed directly in your browser using Binder, or on your own Jupyter server.

For API documentation, visit the individual addon repos on [GitHub](https://github.com/Qiskit?q=qiskit-addon).
"""
    index_path = addons_dst / "index.mdx"
    index_path.write_text(index_content)
    print("  ✓ index.mdx (generated)")

    total_stats = {"ipynb": 0, "images": 0, "skipped": 0}

    for display_name, config in ADDON_SOURCES.items():
        repo_dir = ADDONS_DIR / config["repo"]
        tutorials_src = repo_dir / config["path"]
        # Slug: e.g. "Circuit Cutting" → "circuit-cutting"
        slug_name = config["repo"].replace("qiskit-addon-", "")
        addon_dst = addons_dst / slug_name
        addon_nb_dst = notebooks_dst / slug_name

        if not tutorials_src.exists():
            print(f"  ⚠ {display_name}: tutorials not found at {tutorials_src}")
            continue

        addon_dst.mkdir(parents=True, exist_ok=True)
        addon_nb_dst.mkdir(parents=True, exist_ok=True)

        for src_path in sorted(tutorials_src.glob('*.ipynb')):
            rel_name = src_path.name
            dst_path = addon_dst / src_path.with_suffix('.mdx').name
            notebook_path = f"qiskit-addons/{slug_name}/{rel_name}"

            if convert_notebook(src_path, dst_path, notebook_path=notebook_path):
                total_stats["ipynb"] += 1
                print(f"  ✓ {display_name}: {rel_name} → .mdx")
            else:
                total_stats["skipped"] += 1

            # Copy original notebook for "Open in Lab"
            nb_dst = addon_nb_dst / rel_name
            nb_rel = Path('qiskit-addons') / slug_name / rel_name
            copy_notebook_with_rewrite(src_path, nb_dst, nb_rel)

        # Addon assets all land under static/img/qiskit-addons/<...>; addon
        # MDX references them via absolute /img/... URLs (rewritten by
        # rewrite_addon_relative_refs in convert_notebook). Same pattern as
        # the rest of docs/ — one canonical copy, no per-locale duplication.
        addon_static = STATIC_DIR / "img" / "qiskit-addons"

        # Loose images alongside the .ipynb files (ref'd as `./<file>`)
        for img_path in tutorials_src.glob('*'):
            if img_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
                dst = addon_static / slug_name / img_path.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(img_path, dst)
                total_stats["images"] += 1

        # Sibling images shared across an addon's tutorials (ref'd as
        # `../images/...` or `../_static/images/...`). Mirror the upstream
        # subdir layout under static/img/qiskit-addons/.
        docs_dir = repo_dir / config["path"].split("/")[0]  # e.g. "docs"
        for img_subdir in ("images", "_static/images", "_static"):
            img_src = docs_dir / img_subdir
            if not img_src.exists():
                continue
            img_dst = addon_static / img_subdir
            img_dst.mkdir(parents=True, exist_ok=True)
            for img_path in img_src.rglob('*'):
                if img_path.is_file() and img_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
                    rel = img_path.relative_to(img_src)
                    dst = img_dst / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        shutil.copy(img_path, dst)
                        total_stats["images"] += 1

        # Per-addon exp_data (e.g. SLC) — ref'd as `exp_data/...` (no leading
        # `./`), resolves under qiskit-addons/<slug>/exp_data/ in MDX terms.
        exp_data = tutorials_src / "exp_data"
        if exp_data.exists():
            exp_dst = addon_static / slug_name / "exp_data"
            exp_dst.mkdir(parents=True, exist_ok=True)
            for img_path in exp_data.rglob('*'):
                if img_path.is_file():
                    dst = exp_dst / img_path.relative_to(exp_data)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(img_path, dst)
                    total_stats["images"] += 1

    print(f"\n  Summary: {total_stats['ipynb']} notebooks, "
          f"{total_stats['images']} images, {total_stats['skipped']} skipped")


def generate_addons_sidebar():
    """Generate sidebar configuration for Qiskit Addons."""
    print("\n📋 Generating Qiskit Addons sidebar...")

    addons_dst = DOCS_OUTPUT / "qiskit-addons"
    sidebar_items = []

    for display_name, config in ADDON_SOURCES.items():
        slug_name = config["repo"].replace("qiskit-addon-", "")
        addon_dir = addons_dst / slug_name

        if not addon_dir.exists():
            continue

        # Collect all .mdx files in this addon directory
        mdx_files = sorted(addon_dir.glob('*.mdx'))
        if not mdx_files:
            continue

        items = []
        for mdx_file in mdx_files:
            # Docusaurus strips number prefixes (01_, 02_) from doc IDs
            stem = re.sub(r'^\d+_', '', mdx_file.stem)
            doc_id = f"qiskit-addons/{slug_name}/{stem}"
            items.append(sidebar_doc_item(doc_id))

        # Always wrap each addon in a category — even if it only has a
        # single tutorial — so the sidebar shows which addon every entry
        # belongs to. Without this, single-tutorial addons (OBP, MPF,
        # AQC-Tensor, PNA, SLC) render as bare notebook titles with no
        # indication of their parent addon.
        sidebar_items.append({
            'type': 'category',
            'label': display_name,
            'collapsed': True,
            'items': items,
        })

    sidebar_json = PROJECT_ROOT / "sidebar-addons.json"
    sidebar_json.write_text(json.dumps(sidebar_items, indent=2))

    # Count total docs
    total = sum(1 for item in sidebar_items
                if isinstance(item, str) or (isinstance(item, dict) and item.get('type') == 'doc'))
    total += sum(len(item.get('items', [])) for item in sidebar_items
                 if isinstance(item, dict) and item.get('type') == 'category')
    print(f"  Found {total} addon tutorials")
    print(f"  ✓ Generated {sidebar_json}")


def main():
    parser = argparse.ArgumentParser(description="Sync Qiskit tutorials for Docusaurus")
    parser.add_argument("--tutorials-only", action="store_true",
                        help="Only sync tutorials (skip courses, modules, guides)")
    parser.add_argument("--no-clone", action="store_true",
                        help="Skip cloning/updating upstream (use existing)")
    parser.add_argument("--sample-only", action="store_true",
                        help="Only create sample content (for testing)")
    parser.add_argument("--skip", action="append", default=[],
                        choices=["tutorials", "courses", "modules", "guides", "addons", "workshops"],
                        help="Skip specific content types (can be repeated)")
    parser.add_argument("--scan-deps", action="store_true",
                        help="Scan notebooks for missing deps (report only, no conversion)")
    parser.add_argument("--generate-locale-notebooks", action="store_true",
                        help="Generate translated notebooks for a locale")
    parser.add_argument("--locale", type=str, default=None,
                        help="Locale code for --generate-locale-notebooks (e.g. de, ja)")
    parser.add_argument("--meta-only", action="store_true",
                        help="Only refresh src/config/{contentMeta.ts,"
                             "upstreamFileMeta.json}; do not sync content. "
                             "Used by the daily refresh-page-dates workflow.")
    parser.add_argument("--freshness-report", type=str, metavar="PATH",
                        help="Write a markdown freshness report to PATH and "
                             "exit. Reads only src/config/upstreamFileMeta.json "
                             "and translation/status.json; does not touch "
                             "content or the upstream-docs submodule.")
    args = parser.parse_args()

    print("=" * 60)
    print("doQumentation - Content Sync")
    print("=" * 60)

    if args.scan_deps:
        scan_notebook_deps()
        return

    if args.freshness_report:
        write_freshness_report(Path(args.freshness_report))
        return

    if args.generate_locale_notebooks:
        if not args.locale:
            print("Error: --locale is required with --generate-locale-notebooks")
            sys.exit(1)
        generate_locale_notebooks(args.locale)
        return

    if args.sample_only:
        create_index_page()
        create_sample_tutorial()
        generate_sidebar_flat()
        print("\n✅ Sample content created!")
        return

    if args.meta_only:
        # Refresh per-file dates only. Ensures the upstream clone exists (so
        # ibm/main is fetchable for accurate per-file dates) but does NOT
        # touch docs/, notebooks/, sidebars, or any content. Intended for
        # daily CI to keep the source-date footer fresh without producing
        # noisy content diffs.
        if not args.no_clone:
            clone_or_update_upstream()
        if not UPSTREAM_DIR.exists():
            print("⚠️  upstream-docs not present, cannot refresh metadata")
            sys.exit(1)
        write_content_meta()
        write_page_dates_manifest()
        return

    if not args.no_clone:
        clone_or_update_upstream()

    if not UPSTREAM_DIR.exists():
        print("\n⚠️  Upstream not found. Creating sample content instead.")
        create_index_page()
        create_sample_tutorial()
        generate_sidebar_flat()
    else:
        skip: Set[str] = set(args.skip)
        if args.tutorials_only:
            skip.update(["courses", "modules", "guides"])

        create_index_page()

        if "tutorials" not in skip:
            process_tutorials()
        if "guides" not in skip:
            process_guides()
        if "courses" not in skip:
            process_courses()
        if "modules" not in skip:
            process_modules()
        if "addons" not in skip:
            process_addons()
        if "workshops" not in skip:
            process_workshops()

        create_learning_landing_pages()

        sync_upstream_images()
        publish_notebooks_to_static()

        if "tutorials" not in skip:
            generate_sidebar_from_toc()
        if "guides" not in skip:
            generate_guides_sidebar()
        if "courses" not in skip:
            generate_course_sidebar()
        if "modules" not in skip:
            generate_module_sidebar()
        if "addons" not in skip:
            generate_addons_sidebar()

    # Generate content metadata for the website (upstream commit + date)
    write_content_meta()
    write_page_dates_manifest()

    print("\n" + "=" * 60)
    print("✅ Content sync complete!")
    print("=" * 60)
    print(f"\nDocs output: {DOCS_OUTPUT}")
    print(f"Notebooks output: {NOTEBOOKS_OUTPUT}")
    print("\nNext steps:")
    print("  npm run start    # Preview locally")
    print("  npm run build    # Build for production")


def write_content_meta():
    """Write src/config/contentMeta.ts with upstream commit + date.

    The upstream commit date tells users how current the content actually is
    (not just when sync was last run). Used by the website to show content
    freshness on homepage and features page.
    """
    upstream_commit = ""
    upstream_date = ""
    if UPSTREAM_DIR.exists():
        try:
            sha = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=UPSTREAM_DIR)
            if sha.returncode == 0:
                upstream_commit = sha.stdout.strip()
            cdate = run_command(["git", "log", "-1", "--format=%cs", "HEAD"], cwd=UPSTREAM_DIR)
            if cdate.returncode == 0:
                upstream_date = cdate.stdout.strip()
        except Exception:
            pass

    out = PROJECT_ROOT / "src" / "config" / "contentMeta.ts"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"""// Auto-generated by scripts/sync-content.py — do not edit manually.
// Upstream commit + date represent the actual content version, not the sync run time.
export const UPSTREAM_COMMIT = {upstream_commit!r};
export const UPSTREAM_COMMIT_DATE = {upstream_date!r};
"""
    )
    print(f"\n📅 Content version: upstream {upstream_commit or '(unknown)'} from {upstream_date or '(unknown date)'}")


# Local-docs subtree → upstream subtree. Anything under docs/ not listed here
# (about, qiskit-addons, workshop, index.mdx) has no upstream counterpart.
PAGE_DATE_PATH_MAP = {
    "guides": "docs/guides",
    "tutorials": "docs/tutorials",
    "learning/courses": "learning/courses",
    "learning/modules": "learning/modules",
}


def _git_file_date(repo: Path, path: str, ref: str = "HEAD") -> str:
    res = run_command(
        ["git", "log", "-1", "--format=%cs", ref, "--", path], cwd=repo
    )
    if res.returncode == 0:
        return res.stdout.strip()
    return ""


def _git_file_sha(repo: Path, path: str, ref: str = "HEAD") -> str:
    res = run_command(
        ["git", "log", "-1", "--format=%h", ref, "--", path], cwd=repo
    )
    if res.returncode == 0:
        return res.stdout.strip()
    return ""


def _ibm_upstream_ref(upstream_repo: Path) -> Optional[str]:
    """Return the ref to query for true IBM-side per-file history.

    On the current upstream-Qiskit/documentation submodule, `HEAD` is
    already the right ref — this function returns None and callers fall
    back to HEAD. The legacy `ibm/main` ref is preserved for environments
    that still have an old JanLahmann/Qiskit-documentation fork clone on
    disk (whose HEAD is sync-flattened); _ensure_ibm_history sets that
    up. Returns None if no `ibm/main` exists; the caller defaults to HEAD.
    """
    res = run_command(
        ["git", "rev-parse", "--verify", "--quiet", "refs/remotes/ibm/main"],
        cwd=upstream_repo,
    )
    if res.returncode == 0 and res.stdout.strip():
        return "ibm/main"
    return None


def _content_authored_date(
    upstream_repo: Path, upstream_path: str, ref: str,
) -> str:
    """Return YYYY-MM-DD of the upstream commit whose blob matches the file
    *as it currently exists* on disk in `upstream_repo`. This is the IBM-side
    date of the content our EN page actually reflects, regardless of when
    our local sync moved it into docs/.

    Walks `ref`'s history newest → oldest and returns the date of the first
    commit whose blob is byte-identical to the on-disk file. Returns "" if
    the file is missing or no historical version matches (the latter
    indicates the local copy was edited independently of upstream sync).

    Uses raw `subprocess.run` with `text=False` so binary blobs (e.g. .ipynb
    files containing embedded image bytes) round-trip without UTF-8 mangling.
    """
    abs_path = upstream_repo / upstream_path
    if not abs_path.exists():
        return ""
    try:
        on_disk_hash = hashlib.sha256(abs_path.read_bytes()).digest()
    except Exception:
        return ""

    log = subprocess.run(
        ["git", "log", "--format=%H %cs", ref, "--", upstream_path],
        cwd=upstream_repo, capture_output=True, text=True, check=False,
    )
    if log.returncode != 0:
        return ""
    for line in log.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, cdate = line.partition(" ")
        blob = subprocess.run(
            ["git", "show", f"{sha}:{upstream_path}"],
            cwd=upstream_repo, capture_output=True, text=False, check=False,
        )
        if blob.returncode != 0:
            continue
        if hashlib.sha256(blob.stdout).digest() == on_disk_hash:
            return cdate
    return ""


def write_page_dates_manifest():
    """Write src/config/upstreamFileMeta.json with per-file upstream + EN dates.

    For each doc page that has an upstream counterpart, record:
      - upstream_path: path within the upstream-docs repo
      - upstream_date: last-commit date (YYYY-MM-DD) in upstream-docs
      - upstream_sha: last-commit short SHA in upstream-docs
      - en_date: last-commit date in this repo for the local docs/ file

    Pages without an upstream counterpart (docs/about, docs/qiskit-addons,
    docs/workshop, docs/index.mdx) are not included. The footer component
    treats a missing entry as "no upstream link / no upstream date".
    """
    if not UPSTREAM_DIR.exists():
        print("\n📅 Page dates manifest: upstream-docs not present, skipping")
        return

    # SHALLOW-CLONE GUARD (root-cause fix 2026-05-26): per-file dates require
    # full upstream history. `_content_authored_date`/`_git_file_date` walk
    # `git log -- <file>` to find the commit whose blob matches the on-disk
    # content; with a shallow clone (the content sync does `git clone
    # --depth 1`) only the TIP commit is visible, so EVERY file collapses to
    # the tip's date — typically a tree-wide dependency/CI commit, NOT the
    # real authoring date. That made the source-date footer show identical,
    # too-new dates for all pages (e.g. ansatz showing the sync date instead
    # of its real 2026-02-09). Regenerating from a shallow clone would
    # OVERWRITE the correct committed manifest (produced by the
    # refresh-page-dates.yml job, which checks out with fetch-depth: 0) with
    # garbage. So: if the clone is shallow, DO NOT rewrite — keep the
    # committed manifest. The full-history meta-refresh owns this file.
    shallow_marker = UPSTREAM_DIR / ".git" / "shallow"
    is_shallow = shallow_marker.exists()
    if not is_shallow:
        rc = run_command(["git", "rev-list", "--count", "HEAD"], cwd=UPSTREAM_DIR)
        if rc.returncode == 0 and rc.stdout.strip().isdigit() and int(rc.stdout.strip()) <= 1:
            is_shallow = True
    if is_shallow:
        out = PROJECT_ROOT / "src" / "config" / "upstreamFileMeta.json"
        print(
            "\n📅 Page dates manifest: upstream-docs is a SHALLOW clone — "
            "per-file dates would be inaccurate (all collapse to the tip "
            "commit date). PRESERVING the committed manifest"
            + (" (exists)." if out.exists() else " — but none exists yet!")
            + " The full-history refresh-page-dates.yml job owns this file."
        )
        return

    upstream_ref = _ibm_upstream_ref(UPSTREAM_DIR) or "HEAD"
    if upstream_ref == "HEAD":
        print(
            "📅 Page dates manifest: ibm/main not fetched in upstream-docs; "
            "per-file upstream dates will be coarse. Run: "
            "git -C upstream-docs fetch ibm main"
        )

    manifest: Dict[str, Dict[str, str]] = {}
    suffixes = (".mdx", ".md", ".ipynb")

    for local_sub, upstream_sub in PAGE_DATE_PATH_MAP.items():
        local_root = DOCS_OUTPUT / local_sub
        upstream_root = UPSTREAM_DIR / upstream_sub
        if not local_root.exists() or not upstream_root.exists():
            continue
        for local_file in local_root.rglob("*"):
            if not local_file.is_file() or local_file.suffix.lower() not in suffixes:
                continue
            rel = local_file.relative_to(DOCS_OUTPUT).as_posix()
            upstream_rel = (Path(upstream_sub) / local_file.relative_to(local_root)).as_posix()
            upstream_abs = UPSTREAM_DIR / upstream_rel
            if not upstream_abs.exists():
                # Locally generated (e.g., MDX rendered from upstream notebook
                # under a different name) — try the .ipynb sibling as the
                # upstream truth for date purposes.
                ipynb_candidate = upstream_abs.with_suffix(".ipynb")
                if ipynb_candidate.exists():
                    upstream_rel = ipynb_candidate.relative_to(UPSTREAM_DIR).as_posix()
                else:
                    continue

            # `en_date` semantics: the upstream commit date that matches the
            # content currently in our local upstream-docs/ — i.e. the IBM
            # content date our EN page reflects. NOT the local-MDX mtime
            # (which would move every time sync-content.py touches the file
            # for whitespace/transform reasons even when content is unchanged).
            #
            # For files committed via the locally-tracked docs/ subtree (the
            # rare case where someone edits a synced doc directly without
            # going through upstream), _content_authored_date returns "" and
            # we fall back to the upstream date — still better than the local
            # mtime, which can be misleadingly recent.
            content_date = _content_authored_date(
                UPSTREAM_DIR, upstream_rel, upstream_ref,
            )
            upstream_date = _git_file_date(
                UPSTREAM_DIR, upstream_rel, upstream_ref,
            )
            entry = {
                "upstream_path": upstream_rel,
                "upstream_date": upstream_date,
                "upstream_sha": _git_file_sha(UPSTREAM_DIR, upstream_rel, upstream_ref),
                "en_date": content_date or upstream_date,
            }
            manifest[rel] = entry

    out = PROJECT_ROOT / "src" / "config" / "upstreamFileMeta.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_generated_by": "scripts/sync-content.py",
        "_upstream_repo": "Qiskit/documentation",
        "files": dict(sorted(manifest.items())),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"📅 Page dates manifest: {len(manifest)} files → {out.relative_to(PROJECT_ROOT)}")


def write_freshness_report(out_path: Path) -> None:
    """Write a markdown freshness report. Reads only
    src/config/upstreamFileMeta.json and translation/status.json; does not
    touch the upstream-docs submodule or generate any content. Intended for
    auto-PR bodies and ad-hoc CLI inspection.
    """
    from datetime import datetime, timezone

    meta_path = PROJECT_ROOT / "src" / "config" / "upstreamFileMeta.json"
    status_path = PROJECT_ROOT / "translation" / "status.json"

    if not meta_path.exists():
        out_path.write_text("_No `upstreamFileMeta.json` found — skipping freshness report._\n")
        return
    meta = json.loads(meta_path.read_text())
    files = meta.get("files", {})

    en_behind: list[tuple[str, str, str]] = []  # (path, en_date, upstream_date)
    for rel, entry in files.items():
        en = entry.get("en_date", "")
        up = entry.get("upstream_date", "")
        if en and up and up > en:
            en_behind.append((rel, en, up))
    en_behind.sort(key=lambda t: (t[2], t[1]), reverse=True)

    locale_stale: dict[str, int] = {}
    locale_total: dict[str, int] = {}
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text())
        except json.JSONDecodeError:
            status = {}
        for locale, entries in status.items():
            if not isinstance(entries, dict):
                continue
            stale = 0
            total = 0
            for rel, info in entries.items():
                if not isinstance(info, dict):
                    continue
                if info.get("status") != "promoted":
                    continue
                base = info.get("en_base_commit_date", "")
                en_date = files.get(rel, {}).get("en_date", "")
                if not base or not en_date:
                    continue
                total += 1
                if base < en_date:
                    stale += 1
            locale_total[locale] = total
            locale_stale[locale] = stale

    upstream_repo = meta.get("_upstream_repo", "Qiskit/documentation")
    submodule_sha = ""
    # `git -C upstream-docs rev-parse HEAD` falls back to the parent repo
    # when upstream-docs isn't initialized, returning doQumentation's HEAD —
    # which would be silently wrong in the report. Require a .git
    # entry (file or dir) inside upstream-docs to confirm initialization.
    if UPSTREAM_DIR.exists() and (UPSTREAM_DIR / ".git").exists():
        res = run_command(["git", "-C", str(UPSTREAM_DIR), "rev-parse", "HEAD"])
        if res.returncode == 0:
            submodule_sha = res.stdout.strip()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("## Freshness report")
    lines.append("")
    lines.append(f"### EN pages behind upstream — {len(en_behind)}")
    if en_behind:
        lines.append("")
        lines.append("| Page | EN date | Upstream date |")
        lines.append("|---|---|---|")
        for rel, en, up in en_behind[:10]:
            lines.append(f"| `{rel}` | {en} | {up} |")
        if len(en_behind) > 10:
            lines.append(f"| _…and {len(en_behind) - 10} more_ | | |")
    else:
        lines.append("")
        lines.append("_All EN pages are caught up with upstream._")
    lines.append("")

    lines.append("### Per-locale staleness (promoted entries with `en_base_commit_date < en_date`)")
    if locale_total:
        lines.append("")
        lines.append("| Locale | Stale | Promoted | % stale |")
        lines.append("|---|---:|---:|---:|")
        for locale in sorted(locale_total):
            tot = locale_total[locale]
            st = locale_stale[locale]
            pct = f"{(100 * st / tot):.0f}%" if tot else "—"
            lines.append(f"| `{locale}` | {st} | {tot} | {pct} |")
    else:
        lines.append("")
        lines.append("_No translation status found._")
    lines.append("")

    lines.append("### Snapshot")
    lines.append("")
    lines.append(f"- Upstream repo: [`{upstream_repo}`](https://github.com/{upstream_repo})")
    if submodule_sha:
        lines.append(f"- Submodule HEAD: [`{submodule_sha[:9]}`](https://github.com/{upstream_repo}/commit/{submodule_sha})")
    lines.append(f"- Generated at: {generated_at}")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"📊 Freshness report → {out_path}")


if __name__ == "__main__":
    main()
