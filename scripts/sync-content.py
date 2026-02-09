#!/usr/bin/env python3
"""
sync-content.py - Sync and transform Qiskit content for Docusaurus

This script:
1. Clones/updates the JanLahmann/Qiskit-documentation repository
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
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Set

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
UPSTREAM_DIR = PROJECT_ROOT / "upstream-docs"
DOCS_OUTPUT = PROJECT_ROOT / "docs"
NOTEBOOKS_OUTPUT = PROJECT_ROOT / "notebooks"
STATIC_DIR = PROJECT_ROOT / "static"

# What to sync from upstream (content + images)
CONTENT_PATHS = [
    "docs/tutorials",
    "docs/guides",
    "learning/courses",
    "learning/modules",
    "public/docs/images/tutorials",
    "public/docs/images/guides",
    "public/learning/images",
]

# MDX Transformations for upstream .mdx files
MDX_TRANSFORMS = [
    # Normalize Admonition types to Docusaurus-supported values
    (r'<Admonition(\s+)type="attention"', r'<Admonition\1type="warning"'),
    (r'<Admonition(\s+)type="Note"', r'<Admonition\1type="note"'),
    (r'<Admonition(\s+)type="information"', r'<Admonition\1type="info"'),
    # Bare <Admonition> without type → default to note
    (r'<Admonition\s*>', '<Admonition type="note">'),
    # Strip IBM-specific components that we don't implement
    (r'<CodeCellPlaceholder[^>]*/>', ''),
    # Convert IBM's custom Table components to standard HTML
    (r'<Table>', '<table>'), (r'</Table>', '</table>'),
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
    # Clean up triple+ newlines
    (r'\n{3,}', '\n\n'),
]


def run_command(cmd: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def clone_or_update_upstream():
    """Clone or update the upstream repository."""
    print("\n📥 Syncing upstream repository...")

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
            "https://github.com/JanLahmann/Qiskit-documentation.git",
            str(UPSTREAM_DIR)
        ])
        if result.returncode != 0:
            print(f"  Error: Clone failed: {result.stderr}")
            sys.exit(1)

        run_command(
            ["git", "sparse-checkout", "set"] + CONTENT_PATHS,
            cwd=UPSTREAM_DIR
        )

    print("  ✓ Upstream sync complete")


def transform_mdx(content: str, source_path: Path) -> str:
    """Transform upstream MDX to Docusaurus-compatible format."""
    for pattern, replacement in MDX_TRANSFORMS:
        if callable(replacement):
            content = re.sub(pattern, replacement, content)
        else:
            content = re.sub(pattern, replacement, content)

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

    return content


def escape_mdx_outside_code(content: str) -> str:
    """Escape { and } in markdown text that would break MDX parsing.

    Leaves code blocks (``` ... ```), inline code (` ... `),
    math blocks ($$ ... $$ and $ ... $), and JSX comments ({/* ... */}) untouched.
    """
    parts = re.split(r'(\$\$[\s\S]*?\$\$|```[\s\S]*?```|`[^`]+`|\$[^$\n]+\$|\{/\*[\s\S]*?\*/\})', content)
    for i in range(0, len(parts), 2):  # even indices are outside code
        # Escape lone { } that aren't JSX expressions
        # Skip patterns like {' '} which are valid JSX
        parts[i] = re.sub(r'(?<!\{)\{(?![\'"])', r'\\{', parts[i])
        parts[i] = re.sub(r'(?<![\'"])\}(?!\})', r'\\}', parts[i])
    return ''.join(parts)


def cell_source(cell: dict) -> str:
    """Extract source text from a notebook cell (handles list or string)."""
    src = cell.get('source', '')
    if isinstance(src, list):
        return ''.join(src)
    return src


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


def extract_cell_outputs(cell: dict, output_dir: Path, img_counter: list) -> str:
    """Convert notebook cell outputs to markdown text.

    Handles text/plain, image/png (saved as files), and stderr/stdout streams.
    """
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
                parts.append(f'\n![output](./{img_name})\n')
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


def convert_notebook(ipynb_path: Path, output_path: Path,
                     notebook_path: Optional[str] = None,
                     slug: Optional[str] = None) -> bool:
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

        # Directory for extracted output images (beside the .mdx file)
        img_dir = output_path.parent
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
                output_text = extract_cell_outputs(cell, img_dir, img_counter)
                if output_text:
                    body_parts.append(output_text)

            elif cell_type == 'raw':
                body_parts.append(f'\n```\n{source}\n```\n')

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

        # Inject OpenInLabBanner after frontmatter if notebook_path is set
        banner = ''
        if notebook_path:
            banner = f'\n<OpenInLabBanner notebookPath="{notebook_path}" />\n'

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(frontmatter + banner + '\n' + content)

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
            # Upstream path for Binder/Lab: docs/tutorials/{name}.ipynb
            upstream_nb_path = f"docs/tutorials/{rel_path}"
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
            # Upstream path for Binder/Lab: docs/guides/{name}.ipynb
            upstream_nb_path = f"docs/guides/{rel_path}"
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


def toc_children_to_sidebar(children: list) -> list:
    """Recursively convert _toc.json children to Docusaurus sidebar items."""
    items = []
    for child in children:
        if 'children' in child and child['children']:
            # "Lessons"/"Modules" are wrappers in upstream _toc.json — unwrap children directly
            if child.get('title') in ('Lessons', 'Modules'):
                items.extend(toc_children_to_sidebar(child['children']))
                continue
            # Category with sub-items
            sub_items = toc_children_to_sidebar(child['children'])
            if sub_items:
                cat = {
                    'type': 'category',
                    'label': child['title'],
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
            # Skip non-doc resources (PDFs, etc.)
            if '.' in doc_id.split('/')[-1] and not doc_id.endswith('.mdx'):
                items.append({
                    'type': 'link',
                    'label': child.get('title', doc_id),
                    'href': f'https://docs.quantum.ibm.com/{url.lstrip("/")}',
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
            items.append(doc_id)
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


def copy_notebook_with_rewrite(src_path: Path, dst_path: Path, nb_rel_path: Path):
    """Copy a notebook, rewriting absolute image paths to relative."""
    content = src_path.read_text()
    content = rewrite_notebook_image_paths(content, nb_rel_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(content)


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

    sidebar_json = PROJECT_ROOT / "sidebar-generated.json"
    sidebar_json.write_text(json.dumps(sidebar_items, indent=2))

    # Count tutorials
    def count_docs(items):
        n = 0
        for item in items:
            if isinstance(item, str):
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
        tutorials.append(f"tutorials/{mdx_file.stem}")

    print(f"  Found {len(tutorials)} tutorials (flat)")

    sidebar_json = PROJECT_ROOT / "sidebar-generated.json"
    sidebar_json.write_text(json.dumps(tutorials, indent=2))
    print(f"  ✓ Generated {sidebar_json}")


def process_courses():
    """Process all course files from upstream."""
    print("\n📚 Processing courses...")

    courses_src = UPSTREAM_DIR / "learning" / "courses"
    courses_dst = DOCS_OUTPUT / "learning" / "courses"
    notebooks_dst = NOTEBOOKS_OUTPUT / "learning" / "courses"

    if not courses_src.exists():
        print(f"  Warning: Courses directory not found at {courses_src}")
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

    for course_dir in sorted(courses_src.iterdir()):
        if not course_dir.is_dir():
            continue

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

    courses_src = UPSTREAM_DIR / "learning" / "courses"
    if not courses_src.exists():
        print("  Warning: No courses directory found")
        return

    course_items = []
    for course_dir in sorted(courses_src.iterdir()):
        if not course_dir.is_dir():
            continue

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


def main():
    parser = argparse.ArgumentParser(description="Sync Qiskit tutorials for Docusaurus")
    parser.add_argument("--tutorials-only", action="store_true",
                        help="Only sync tutorials (skip courses, modules, guides)")
    parser.add_argument("--no-clone", action="store_true",
                        help="Skip cloning/updating upstream (use existing)")
    parser.add_argument("--sample-only", action="store_true",
                        help="Only create sample content (for testing)")
    parser.add_argument("--skip", action="append", default=[],
                        choices=["tutorials", "courses", "modules", "guides"],
                        help="Skip specific content types (can be repeated)")
    args = parser.parse_args()

    print("=" * 60)
    print("doQumentation - Content Sync")
    print("=" * 60)

    if args.sample_only:
        create_index_page()
        create_sample_tutorial()
        generate_sidebar_flat()
        print("\n✅ Sample content created!")
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

        sync_upstream_images()

        if "tutorials" not in skip:
            generate_sidebar_from_toc()
        if "guides" not in skip:
            generate_guides_sidebar()
        if "courses" not in skip:
            generate_course_sidebar()
        if "modules" not in skip:
            generate_module_sidebar()

    print("\n" + "=" * 60)
    print("✅ Content sync complete!")
    print("=" * 60)
    print(f"\nDocs output: {DOCS_OUTPUT}")
    print(f"Notebooks output: {NOTEBOOKS_OUTPUT}")
    print("\nNext steps:")
    print("  npm run start    # Preview locally")
    print("  npm run build    # Build for production")


if __name__ == "__main__":
    main()
