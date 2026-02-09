# Plan: Split embedded code blocks into executable cells in Jupyter notebooks

## Context

Upstream IBM Quantum notebooks are designed for IBM's custom web renderer, not direct JupyterLab use. Many markdown cells contain fenced Python code blocks embedded inside numbered lists and nested bullets. In JupyterLab, these render as non-executable formatted text within the markdown. Users expect to run them as separate code cells.

**Scope**: 483 fenced code blocks in markdown cells across 94 upstream notebooks:
- `python`/`py`: 84 blocks → extract as executable code cells
- `shell`/`bash`/`sh`: 39 blocks → leave as markdown (not runnable in Python kernel)
- `text`/`toml`/`ini`/(none): 360 blocks → leave as markdown (display-only)

## Approach

Add a `split_markdown_code_cells()` function that processes notebook JSON before copying to `notebooks/`. It splits markdown cells at fenced `python` code blocks, creating alternating markdown/code cells.

### Example transformation

**Before** (1 markdown cell):
```
## Install and authenticate

1. Save your credentials:

    ```python
    from qiskit_ibm_runtime import QiskitRuntimeService
    QiskitRuntimeService.save_account(token="...")
    ```

2. Now authenticate:
    ```python
    service = QiskitRuntimeService()
    ```
```

**After** (5 cells):
1. Markdown: `## Install and authenticate\n\n1. Save your credentials:`
2. Code: `from qiskit_ibm_runtime import QiskitRuntimeService\nQiskitRuntimeService.save_account(token="...")`
3. Markdown: `2. Now authenticate:`
4. Code: `service = QiskitRuntimeService()`
5. *(empty markdown cells are dropped)*

### Algorithm

1. For each markdown cell, use regex to find fenced code blocks: `` ^(\s*)```python\n(.*?)^\s*``` `` (multiline, dotall)
2. Only match `python` and `py` language tags
3. For each match:
   - Emit preceding markdown text as a markdown cell (if non-empty)
   - Dedent the code content (strip common leading whitespace from list indentation)
   - Emit the code as a code cell
4. Emit remaining markdown text as a final markdown cell
5. Preserve cell metadata (slide type, etc.)

### Where to integrate

**`copy_notebook_with_rewrite()`** (line ~691 in `scripts/sync-content.py`) — this is the function that copies .ipynb files to the `notebooks/` directory. Currently it only rewrites image paths. Add cell splitting here.

The function already loads/saves notebook JSON, so adding cell manipulation is natural.

**NOT** in `convert_notebook()` — the MDX output for Docusaurus renders code blocks fine in the browser. Only the Jupyter-served notebooks need splitting.

## Files to modify

| File | Changes |
|------|---------|
| `scripts/sync-content.py` | Add `split_markdown_code_cells()` function; call it from `copy_notebook_with_rewrite()` |

## Verification

1. Run `python scripts/sync-content.py`
2. Check `notebooks/guides/hello-world.ipynb` — cell 3 should now be split into multiple cells with Python code in executable code cells
3. Run `npm run build` — confirm no regressions (MDX output unchanged)
4. Open a notebook in JupyterLab locally to verify the split cells render correctly
