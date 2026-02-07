#!/usr/bin/env python3
"""
sync-content.py - Sync and transform Qiskit tutorials for Docusaurus

This script:
1. Clones/updates the JanLahmann/Qiskit-documentation repository
2. Converts Jupyter notebooks to MDX (code blocks auto-wrapped by CodeBlock swizzle)
3. Transforms the upstream index.mdx for Docusaurus
4. Parses _toc.json to generate structured sidebar configuration
5. Copies original notebooks for "Open in Lab" feature

Usage:
    python scripts/sync-content.py [--tutorials-only] [--no-clone] [--sample-only]
"""

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

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
    "learning/courses",
    "public/docs/images/tutorials",
    "public/learning/images",
]

# MDX Transformations for upstream .mdx files
MDX_TRANSFORMS = [
    # Admonition: <Admonition type="note" title="Title"> → :::note[Title]
    (
        r'<Admonition\s+type="(\w+)"(?:\s+title="([^"]*)")?\s*>',
        lambda m: f':::{m.group(1)}' + (f'[{m.group(2)}]' if m.group(2) else '') + '\n'
    ),
    (r'</Admonition>', '\n:::\n'),
    # Map IBM's "attention" type to Docusaurus "warning"
    (r':::attention', ':::warning'),
    # Strip IBM-specific components that we don't implement
    (r'<CodeCellPlaceholder[^>]*/>', ''),
    # Fix link paths: /docs/tutorials/foo → /tutorials/foo (local)
    (r'\(/docs/tutorials/', '(/tutorials/'),
    # Rewrite other /docs/ and /learning/ links to upstream IBM Quantum docs
    # (negative lookahead to skip /docs/images/ which are served locally)
    (r'\(/docs/(?!tutorials/|images/)', '(https://docs.quantum.ibm.com/'),
    (r'\(/learning/', '(https://docs.quantum.ibm.com/learning/'),
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

    Leaves code blocks (``` ... ```) and inline code (` ... `) untouched.
    """
    parts = re.split(r'(```[\s\S]*?```|`[^`]+`)', content)
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
                    parts.append(f'\n```text\n{text.rstrip()}\n```\n')

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
            elif 'text/plain' in data and 'text' not in output:
                text = data['text/plain']
                if isinstance(text, list):
                    text = ''.join(text)
                if text.strip():
                    parts.append(f'\n```text\n{text.rstrip()}\n```\n')

        elif output_type == 'error':
            # Skip traceback noise — users will see errors when they run the code
            pass

    return ''.join(parts)


def convert_notebook(ipynb_path: Path, output_path: Path) -> bool:
    """
    Convert a Jupyter notebook to MDX by parsing the .ipynb JSON directly.

    No external dependencies needed (no nbconvert). Python code blocks are
    output as standard ```python fenced blocks — the CodeBlock swizzle
    auto-wraps them in ExecutableCode at render time.
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
        fm_lines.append('---\n')
        frontmatter = '\n'.join(fm_lines)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(frontmatter + '\n' + content)

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
            if convert_notebook(src_path, dst_path):
                stats["ipynb"] += 1
                print(f"  ✓ {rel_path} → .mdx")
            else:
                stats["skipped"] += 1

            # Copy original notebook for "Open in Lab"
            nb_dst = notebooks_dst / rel_path
            nb_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, nb_dst)

        elif src_path.suffix in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
            dst_path = tutorials_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, dst_path)
            stats["images"] += 1

        else:
            stats["skipped"] += 1

    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, "
          f"{stats['images']} images, {stats['skipped']} skipped")


def url_to_doc_id(url: str) -> str:
    """Convert upstream URL like /docs/tutorials/foo to Docusaurus doc ID tutorials/foo."""
    return url.replace('/docs/', '', 1).lstrip('/')


def toc_children_to_sidebar(children: list) -> list:
    """Recursively convert _toc.json children to Docusaurus sidebar items."""
    items = []
    for child in children:
        if 'children' in child and child['children']:
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
            doc_id = url_to_doc_id(child['url'])
            # Skip the overview entry (handled as category link)
            if doc_id == 'tutorials':
                continue
            items.append(doc_id)
    return items


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


def create_index_page():
    """Create the site home page (docs/index.mdx)."""
    print("\n📄 Creating home page...")

    index_content = """---
title: doQumentation
sidebar_position: 1
slug: /
---

# Qiskit Documentation — Interactive Notebooks

Built on [Qiskit/documentation](https://github.com/Qiskit/documentation) with interactive execution support.

For reading docs (tutorials, courses, etc), we recommend the official IBM websites — they are more current, better maintained, and have a much better layout and design: [Learning](https://quantum.cloud.ibm.com/learning) · [Tutorials](https://quantum.cloud.ibm.com/docs/en/tutorials) · [Source repo](https://github.com/Qiskit/documentation)

Use **doQumentation.org** when you want to **run notebook code directly in your browser** — browse any [Tutorial](/tutorials), click **Run** on a code block, and it executes right on the page. Available as:

- **[RasQberry](https://github.com/JanLahmann/RasQberry-Two)** — Self-hosted on Raspberry Pi with local Jupyter kernel (full features)
- **[Docker](https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation)** — Run the full stack locally with `docker compose up`
- **[GitHub Pages](https://janlahmann.github.io/doQumentation/)** — Static site using [Binder](https://mybinder.org) for remote code execution

## Getting started

- [CHSH inequality](/tutorials/chsh-inequality) — Run an experiment on a quantum computer
- [Grover's algorithm](/tutorials/grovers-algorithm) — Search with quantum speedup
- [Shor's algorithm](/tutorials/shors-algorithm) — Factor integers with quantum circuits

## How code execution works

Every tutorial has executable code blocks. Click **Run** to execute them using one of three backends:

1. **Binder** (default on GitHub Pages) — Free remote Jupyter kernel via [mybinder.org](https://mybinder.org) (first run may take 1–2 min to start)
2. **RasQberry** — Connects to the local Jupyter server on your [RasQberry](https://github.com/JanLahmann/RasQberry-Two)
3. **Custom server** — Point to any Jupyter endpoint in [Settings](/jupyter-settings)

---

*Tutorial content © IBM Corp, licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Site built with [Docusaurus](https://docusaurus.io/).*
"""

    index_path = DOCS_OUTPUT / "index.mdx"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(index_content)
    print(f"  ✓ Created {index_path}")


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
                        help="Only sync tutorials (not courses)")
    parser.add_argument("--no-clone", action="store_true",
                        help="Skip cloning/updating upstream (use existing)")
    parser.add_argument("--sample-only", action="store_true",
                        help="Only create sample content (for testing)")
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
        create_index_page()
        process_tutorials()
        sync_upstream_images()
        generate_sidebar_from_toc()

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
