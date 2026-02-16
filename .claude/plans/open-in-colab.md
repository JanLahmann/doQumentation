# Open in Colab — Implementation Plan

## Context

doQumentation renders Jupyter notebooks as interactive Docusaurus pages. Each page that originates from a `.ipynb` already carries a `notebookPath` prop (e.g. `docs/tutorials/hello-world.ipynb`) that maps to the file in the upstream repo `JanLahmann/Qiskit-documentation` on branch `main`.

Currently the project offers two ways to open the original notebook externally:

| Component | Where | Shows when |
|-----------|-------|------------|
| **OpenInLabBanner** | Banner below page title | Always (Lab or Binder) |
| **ExecutableCode toolbar** | Above first code cell | `labEnabled && notebookPath` (local/Docker only) |

The upstream `.ipynb` files assume a pre-configured environment (Binder or Docker) and contain **no `pip install` cells**. The sync script already detects missing imports via `analyze_notebook_imports()` and injects `%pip install` cells into the MDX pages, but the raw notebooks lack them.

**Problem:** When a user opens a notebook externally (Colab or Binder Lab), dependencies like `qiskit` (missing from Colab) or `scikit-learn` (missing from Binder) are not installed, causing `ModuleNotFoundError`.

**Solution:** Publish dependency-ready notebook copies via GitHub Pages with a single universal install cell per notebook. Both Colab and Binder Lab link to these copies instead of the raw upstream files.

---

## Scope

**In scope:**
- Extend `copy_notebook_with_rewrite()` in `sync-content.py` to inject a `!pip install -q` cell into each `.ipynb` copy
- Publish `notebooks/` via GitHub Pages (copy into `static/notebooks/`)
- URL generation functions in `src/config/jupyter.ts` (`getColabUrl`, updated `getBinderLabUrl`)
- Colab button in `OpenInLabBanner` and `ExecutableCode` toolbar
- Styling consistent with existing buttons

**Out of scope:**
- Platform-specific notebook variants (single universal install cell covers both Colab and Binder; already-installed packages resolve as no-ops)
- Deep Colab API integration (just a link)
- Changes to MDX files (existing `notebookPath` prop is sufficient)

---

## Implementation

### Step 1: Inject install cell into notebook copies (`sync-content.py`)

Extend `copy_notebook_with_rewrite()` to inject a pip install cell at the top of each `.ipynb` copy. The cell includes the full Qiskit stack (needed for Colab) plus any per-notebook extras detected by `analyze_notebook_imports()` (needed for both Colab and Binder).

```python
def copy_notebook_with_rewrite(src_path: Path, dst_path: Path, nb_rel_path: Path):
    """Copy a notebook, rewriting image paths and injecting dependency install cell."""
    content = src_path.read_text()
    content = rewrite_notebook_image_paths(content, nb_rel_path)

    # Parse notebook JSON to inject install cell
    nb = json.loads(content)
    cells = nb.get('cells', [])

    # Base packages needed for Colab (Binder has these, pip resolves as no-op)
    base_pkgs = ['qiskit', 'qiskit-aer', 'qiskit-ibm-runtime', 'pylatexenc']

    # Per-notebook extras (missing from both Colab and Binder baselines)
    extra_pkgs = analyze_notebook_imports(cells)

    all_pkgs = base_pkgs + [p for p in extra_pkgs if p not in base_pkgs]

    install_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Install dependencies (runs quickly if already installed)\n",
            f"!pip install -q {' '.join(all_pkgs)}"
        ]
    }

    nb['cells'] = [install_cell] + cells
    content = json.dumps(nb, indent=1, ensure_ascii=False)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(content)
```

**Key decisions:**
- Single universal install cell — redundant packages on either platform resolve in ~5-10s via `Requirement already satisfied` (suppressed by `-q`).
- `base_pkgs` covers the core Qiskit stack that Colab lacks. `extra_pkgs` covers per-notebook extras (scikit-learn, plotly, python-sat, etc.) missing from both platforms.
- The existing `analyze_notebook_imports()` already does the heavy lifting — it scans imports, filters stdlib and `BINDER_PROVIDED`, and maps import names to pip names.

### Step 2: Publish notebooks via GitHub Pages

During sync, copy the `notebooks/` directory into `static/notebooks/` so Docusaurus deploys it to gh-pages:

```python
# In sync-content.py, after all notebook copies are generated:
def publish_notebooks_to_static():
    """Copy notebooks/ into static/notebooks/ for GitHub Pages deployment."""
    static_nb = STATIC_DIR / "notebooks"
    if static_nb.exists():
        shutil.rmtree(static_nb)
    shutil.copytree(NOTEBOOKS_OUTPUT, static_nb)
```

This makes notebooks available at `https://doqumentation.org/notebooks/tutorials/hello-world.ipynb` and, critically, in the `gh-pages` branch at a known path for Colab's GitHub URL scheme.

### Step 3: Add `getColabUrl()` to `src/config/jupyter.ts`

```typescript
/**
 * Get the Google Colab URL for a notebook.
 * Points to the dependency-ready copy on gh-pages (not the raw upstream).
 */
export function getColabUrl(notebookPath: string): string {
  // notebookPath is upstream-relative, e.g. "docs/tutorials/hello-world.ipynb"
  // notebooks/ on gh-pages mirrors this structure under the content-type prefix:
  //   docs/tutorials/X.ipynb → notebooks/tutorials/X.ipynb
  //   docs/guides/X.ipynb   → notebooks/guides/X.ipynb
  //   learning/courses/...   → notebooks/learning/courses/...
  //   hello-world.ipynb      → notebooks/tutorials/hello-world.ipynb
  const nbPath = notebookPath
    .replace(/^docs\//, '');  // strip docs/ prefix → tutorials/X.ipynb

  return `https://colab.research.google.com/github/JanLahmann/doQumentation/blob/gh-pages/notebooks/${nbPath}`;
}
```

### Step 4: Update `getBinderLabUrl()` in `src/config/jupyter.ts`

Point Binder Lab at the same dependency-ready copies instead of the raw upstream:

```typescript
export function getBinderLabUrl(config: JupyterConfig, notebookPath: string): string | null {
  if (!config.binderUrl) {
    return null;
  }
  // Point to gh-pages copy (has install cell) instead of raw upstream
  const nbPath = notebookPath.replace(/^docs\//, '');
  const fullPath = `notebooks/${nbPath}`;
  return `${config.binderUrl}?labpath=${encodeURIComponent(fullPath)}`;
}
```

**Note:** `getLabUrl()` (local/Docker) is unchanged — it opens from the local `notebooks/` directory where all deps are already installed in the Docker environment.

### Step 5: Add Colab button to `OpenInLabBanner`

Modify `src/components/OpenInLabBanner/index.tsx`:

1. Import `getColabUrl`.
2. Render Colab button alongside the existing Lab/Binder button.
3. Colab button always shows when `notebookPath` is set (environment-independent).

```tsx
const colabUrl = getColabUrl(notebookPath);

<div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
  <a href={colabUrl} target="_blank" rel="noopener noreferrer"
     title="Open notebook in Google Colab"
     style={{ /* outlined style */ }}>
    Open in Colab ↗
  </a>
  {labUrl && (
    <a href={labUrl} target="_blank" rel="noopener noreferrer" ...>
      {label} ↗
    </a>
  )}
</div>
```

### Step 6: Add Colab button to `ExecutableCode` toolbar

Modify `src/components/ExecutableCode/index.tsx` (after the existing "Open in Lab" button at line ~879):

```tsx
{notebookPath && (
  <a
    className="executable-code__button"
    href={getColabUrl(notebookPath)}
    target="_blank"
    rel="noopener noreferrer"
    title="Open notebook in Google Colab"
  >
    Open in Colab
  </a>
)}
```

Uses `<a>` instead of `<button>` for better accessibility and right-click support.

### Step 7: Verify & test

1. `python scripts/sync-content.py` — verify notebooks in `notebooks/` have the install cell, and `static/notebooks/` is populated.
2. Spot-check a generated `.ipynb` — confirm the first cell is `!pip install -q qiskit ...`.
3. `npm run build` — no TypeScript or build errors.
4. `npm start` — verify on a tutorial page:
   - Banner shows "Open in Colab" and "Open in Binder JupyterLab".
   - Toolbar shows "Open in Colab".
   - Colab link opens the gh-pages copy with install cell.
5. URL correctness for each content type:
   - Tutorial: `notebooks/tutorials/{name}.ipynb`
   - Guide: `notebooks/guides/{name}.ipynb`
   - Course: `notebooks/learning/courses/{dir}/{name}.ipynb`
   - Module: `notebooks/learning/modules/{dir}/{name}.ipynb`

---

## Files Modified

| File | Change |
|------|--------|
| `scripts/sync-content.py` | Extend `copy_notebook_with_rewrite()` to inject install cell; add `publish_notebooks_to_static()` |
| `src/config/jupyter.ts` | Add `getColabUrl()`; update `getBinderLabUrl()` to point to gh-pages copies |
| `src/components/OpenInLabBanner/index.tsx` | Add Colab button alongside Lab/Binder button |
| `src/components/ExecutableCode/index.tsx` | Add Colab button to toolbar |

No changes to `docusaurus.config.ts` or MDX files.

---

## Data Flow

```
Upstream .ipynb (no install cell)
    │
    ├── sync-content.py: convert_notebook()
    │       → MDX page with %pip install cell (for in-page execution)
    │
    └── sync-content.py: copy_notebook_with_rewrite()
            → notebooks/{path}.ipynb (image paths rewritten + install cell injected)
            → static/notebooks/{path}.ipynb (deployed to gh-pages)
                    │
                    ├── Colab URL: colab.research.google.com/github/.../blob/gh-pages/notebooks/...
                    └── Binder URL: mybinder.org/...?labpath=notebooks/...
```

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Redundant pip installs add startup time | `-q` flag suppresses output; ~5-10s of no-op resolution is acceptable |
| gh-pages branch size increases | ~50 notebooks + images; negligible vs. existing site assets |
| Notebooks lag behind upstream until next sync+deploy | Same cadence as the rest of the site content; acceptable |
| `analyze_notebook_imports()` misses a dependency | Existing risk — already affects MDX pages; not new |
| Binder can't find notebook at new path | Verify Binder `?labpath=` resolves relative to repo root on gh-pages branch |
| Button clutter on mobile | Two compact buttons in a flex row; test on narrow viewports |
