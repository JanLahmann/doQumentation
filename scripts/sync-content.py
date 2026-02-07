#!/usr/bin/env python3
"""
sync-content.py - Sync and transform Qiskit tutorials for Docusaurus

This script:
1. Clones/updates the Qiskit/documentation repository
2. Transforms MDX files for Docusaurus compatibility
3. Converts Jupyter notebooks to MDX
4. Copies original notebooks for "Open in Lab" feature
5. Generates sidebar configuration

Usage:
    python scripts/sync-content.py [--tutorials-only] [--no-clone]
"""

import argparse
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

# What to sync
CONTENT_PATHS = [
    "docs/tutorials",
    # Add more paths as needed:
    # "docs/guides",
]

# MDX Transformations
# Pattern -> Replacement (or callable)
MDX_TRANSFORMS = [
    # Admonition: Convert JSX syntax to Docusaurus directive syntax
    # <Admonition type="note" title="Title">content</Admonition>
    # → :::note[Title]\ncontent\n:::
    (
        r'<Admonition\s+type="(\w+)"(?:\s+title="([^"]*)")?\s*>',
        lambda m: f':::{m.group(1)}' + (f'[{m.group(2)}]' if m.group(2) else '') + '\n'
    ),
    (r'</Admonition>', '\n:::\n'),
    
    # Map IBM's "attention" type to Docusaurus "warning"
    (r':::attention', ':::warning'),
    
    # Ensure Tabs/TabItem imports are present
    # (handled separately in transform_mdx)
    
    # Clean up any double newlines from transformations
    (r'\n{3,}', '\n\n'),
]


def run_command(cmd: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def clone_or_update_upstream():
    """Clone or update the Qiskit/documentation repository."""
    print("\n📥 Syncing upstream repository...")
    
    if UPSTREAM_DIR.exists():
        # Update existing clone
        print("  Updating existing clone...")
        result = run_command(["git", "pull", "--ff-only"], cwd=UPSTREAM_DIR)
        if result.returncode != 0:
            print(f"  Warning: git pull failed, continuing with existing content")
    else:
        # Fresh clone with sparse checkout
        print("  Cloning repository (this may take a moment)...")
        
        # Clone with filter for faster download
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
        
        # Configure sparse checkout
        sparse_paths = "\n".join(CONTENT_PATHS)
        run_command(
            ["git", "sparse-checkout", "set"] + CONTENT_PATHS,
            cwd=UPSTREAM_DIR
        )
    
    print("  ✓ Upstream sync complete")


def transform_mdx(content: str, source_path: Path) -> str:
    """
    Transform Qiskit MDX to Docusaurus-compatible format.
    
    Args:
        content: The MDX file content
        source_path: Path to the source file (for context)
    
    Returns:
        Transformed content
    """
    # Apply regex transformations
    for pattern, replacement in MDX_TRANSFORMS:
        if callable(replacement):
            content = re.sub(pattern, replacement, content)
        else:
            content = re.sub(pattern, replacement, content)
    
    # Add Tabs/TabItem imports if used but not imported
    if '<Tabs>' in content or '<TabItem' in content:
        if "import Tabs from" not in content and "import TabItem from" not in content:
            import_statement = (
                "import Tabs from '@theme/Tabs';\n"
                "import TabItem from '@theme/TabItem';\n\n"
            )
            
            # Insert after frontmatter
            if content.startswith('---'):
                # Find end of frontmatter
                end_fm_match = re.search(r'^---\s*$', content[3:], re.MULTILINE)
                if end_fm_match:
                    insert_pos = 3 + end_fm_match.end()
                    content = content[:insert_pos] + '\n\n' + import_statement + content[insert_pos:]
            else:
                content = import_statement + content
    
    return content


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from content."""
    if not content.startswith('---'):
        return {}, content
    
    end_match = re.search(r'^---\s*$', content[3:], re.MULTILINE)
    if not end_match:
        return {}, content
    
    fm_end = 3 + end_match.end()
    fm_content = content[3:fm_end-3].strip()
    body = content[fm_end:].strip()
    
    # Simple YAML parsing (just key: value pairs)
    frontmatter = {}
    for line in fm_content.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            frontmatter[key.strip()] = value.strip().strip('"\'')
    
    return frontmatter, body


def convert_notebook(ipynb_path: Path, output_path: Path) -> bool:
    """
    Convert a Jupyter notebook to MDX format.
    
    Args:
        ipynb_path: Path to the .ipynb file
        output_path: Path for the output .mdx file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert to markdown using nbconvert
        result = subprocess.run([
            "jupyter", "nbconvert",
            "--to", "markdown",
            "--stdout",
            str(ipynb_path)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"    Warning: nbconvert failed for {ipynb_path.name}: {result.stderr[:200]}")
            return False
        
        content = result.stdout
        
        # Extract title from first heading or filename
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else ipynb_path.stem.replace('-', ' ').replace('_', ' ').title()
        
        # Calculate notebook path relative to notebooks dir
        # This will be used for "Open in Lab" feature
        try:
            notebook_rel = ipynb_path.relative_to(UPSTREAM_DIR / "docs")
            notebook_path = f"tutorials/{notebook_rel.name}"
        except ValueError:
            notebook_path = ipynb_path.name
        
        # Build frontmatter
        frontmatter = f"""---
title: "{title}"
sidebar_label: "{title}"
---

import ExecutableCode from '@site/src/components/ExecutableCode';

{{/* Original notebook: {notebook_path} */}}

"""
        
        # Transform Python code blocks to use ExecutableCode
        # Match ```python ... ``` blocks
        def replace_code_block(match):
            code = match.group(1)
            return f'<ExecutableCode language="python" notebookPath="{notebook_path}">\n{code}</ExecutableCode>'
        
        content = re.sub(
            r'```python\n(.*?)```',
            replace_code_block,
            content,
            flags=re.DOTALL
        )
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(frontmatter + content)
        
        return True
        
    except Exception as e:
        print(f"    Error converting {ipynb_path.name}: {e}")
        return False


def process_tutorials():
    """Process all tutorial files."""
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
    
    # Track statistics
    stats = {"mdx": 0, "ipynb": 0, "images": 0, "skipped": 0}
    
    # Process all files
    for src_path in tutorials_src.rglob('*'):
        if src_path.is_dir():
            continue
        
        rel_path = src_path.relative_to(tutorials_src)
        
        if src_path.suffix == '.mdx':
            # Transform MDX files
            dst_path = tutorials_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            content = src_path.read_text()
            transformed = transform_mdx(content, src_path)
            dst_path.write_text(transformed)
            
            stats["mdx"] += 1
            print(f"  ✓ {rel_path}")
            
        elif src_path.suffix == '.ipynb':
            # Convert notebook to MDX
            dst_path = tutorials_dst / rel_path.with_suffix('.mdx')
            if convert_notebook(src_path, dst_path):
                stats["ipynb"] += 1
                print(f"  ✓ {rel_path} → .mdx")
            else:
                stats["skipped"] += 1
            
            # Also copy original notebook for "Open in Lab"
            nb_dst = notebooks_dst / rel_path
            nb_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, nb_dst)
            
        elif src_path.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']:
            # Copy images
            dst_path = tutorials_dst / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, dst_path)
            stats["images"] += 1
            
        else:
            stats["skipped"] += 1
    
    print(f"\n  Summary: {stats['mdx']} MDX, {stats['ipynb']} notebooks, {stats['images']} images, {stats['skipped']} skipped")


def create_index_page():
    """Create the docs index page."""
    print("\n📄 Creating index page...")
    
    index_content = """---
title: RasQberry Tutorials
sidebar_position: 1
slug: /
---

# Welcome to RasQberry Tutorials

This site hosts IBM Quantum tutorials optimized for local execution on RasQberry.

## Features

- **📖 Read** - Browse tutorials with syntax-highlighted code
- **▶️ Run** - Execute Python code directly via Jupyter
- **🔬 Lab** - Open full notebooks in JupyterLab

## Getting Started

New to quantum computing? Start with [Hello World](/tutorials/hello-world).

## Jupyter Execution

Code blocks can be executed in three ways:

1. **On RasQberry** - Automatically connects to local Jupyter server
2. **On GitHub Pages** - Uses Binder for remote execution
3. **Custom Server** - Configure your own Jupyter server in [Settings](/jupyter-settings)

## Tutorials

Browse tutorials using the sidebar, or jump to a section:

- [Get Started](/tutorials/hello-world) - Your first quantum circuit
- [Quantum Algorithms](/tutorials/grovers-algorithm) - Classic algorithms
- [Advanced Topics](/tutorials/sample-based-quantum-diagonalization) - Cutting-edge techniques

---

*Tutorial content © IBM Corp, licensed under CC BY-SA 4.0.*
*Site built for the [RasQberry](https://github.com/JanLahmann/RasQberry-Two) project.*
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


def generate_sidebar_config():
    """Generate sidebar configuration from the docs structure."""
    print("\n📋 Generating sidebar configuration...")
    
    # This is a simplified version - the actual sidebars.ts can be more sophisticated
    tutorials_dir = DOCS_OUTPUT / "tutorials"
    
    if not tutorials_dir.exists():
        print("  Warning: No tutorials directory found")
        return
    
    tutorials = []
    for mdx_file in sorted(tutorials_dir.glob("*.mdx")):
        doc_id = f"tutorials/{mdx_file.stem}"
        tutorials.append(doc_id)
    
    print(f"  Found {len(tutorials)} tutorials")
    
    # Write a JSON file that can be imported by sidebars.ts
    sidebar_data = {
        "tutorials": tutorials
    }
    
    sidebar_json = PROJECT_ROOT / "sidebar-generated.json"
    sidebar_json.write_text(json.dumps(sidebar_data, indent=2))
    print(f"  ✓ Generated {sidebar_json}")


def main():
    parser = argparse.ArgumentParser(description="Sync Qiskit tutorials for Docusaurus")
    parser.add_argument("--tutorials-only", action="store_true",
                       help="Only sync tutorials (not guides)")
    parser.add_argument("--no-clone", action="store_true",
                       help="Skip cloning/updating upstream (use existing)")
    parser.add_argument("--sample-only", action="store_true",
                       help="Only create sample content (for testing)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("RasQberry Tutorials - Content Sync")
    print("=" * 60)
    
    if args.sample_only:
        create_index_page()
        create_sample_tutorial()
        generate_sidebar_config()
        print("\n✅ Sample content created!")
        return
    
    if not args.no_clone:
        clone_or_update_upstream()
    
    # Check if upstream exists
    if not UPSTREAM_DIR.exists():
        print("\n⚠️  Upstream not found. Creating sample content instead.")
        create_index_page()
        create_sample_tutorial()
    else:
        create_index_page()
        process_tutorials()
    
    generate_sidebar_config()
    
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
