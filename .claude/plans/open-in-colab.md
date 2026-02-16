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

**Solution:** Publish dependency-ready notebook copies via GitHub Pages with two install cells per notebook:

1. **Initialization cell** (auto-runs on Colab via `cell_execution_strategy: "setup"`) — installs the base Qiskit stack. On Binder this auto-runs too but resolves as a fast no-op since Qiskit is pre-installed.
2. **Normal extras cell** (only if needed, user-visible and user-controlled) — installs per-notebook extras like `scikit-learn`, `plotly`, etc. that are missing from both Colab and Binder.

---

## Scope

**In scope:**
- Extend `copy_notebook_with_rewrite()` in `sync-content.py` to inject up to two install cells + Colab notebook metadata
- Publish `notebooks/` via GitHub Pages (copy into `static/notebooks/`)
- URL generation functions in `src/config/jupyter.ts` (`getColabUrl`, updated `getBinderLabUrl`)
- Colab button in `OpenInLabBanner` and `ExecutableCode` toolbar
- Styling consistent with existing buttons

**Out of scope:**
- Platform-specific notebook variants (single set of copies serves both Colab and Binder)
- Deep Colab API integration (just a link)
- Changes to MDX files (existing `notebookPath` prop is sufficient)

---

## Implementation

### Step 1: Inject install cells + Colab metadata into notebook copies (`sync-content.py`)

Extend `copy_notebook_with_rewrite()` to:
1. Add Colab notebook metadata with `cell_execution_strategy: "setup"` so the first cell auto-runs on open.
2. Inject an **initialization cell** (cell 0) that installs the base Qiskit stack.
3. Optionally inject a **normal extras cell** (cell 1) for per-notebook dependencies detected by `analyze_notebook_imports()`.

```python
# Base packages always needed for Colab (pre-installed in Binder → no-op there)
COLAB_BASE_PKGS = ['qiskit', 'qiskit-aer', 'qiskit-ibm-runtime', 'pylatexenc']


def copy_notebook_with_rewrite(src_path: Path, dst_path: Path, nb_rel_path: Path):
    """Copy a notebook, rewriting image paths and injecting dependency cells."""
    content = src_path.read_text()
    content = rewrite_notebook_image_paths(content, nb_rel_path)

    nb = json.loads(content)
    cells = nb.get('cells', [])

    # ── Cell 0: Initialization cell (auto-runs on Colab) ──
    # Installs base Qiskit stack. On Binder this is a fast no-op.
    init_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Setup: install Qiskit (runs automatically in Colab, no-op in Binder)\n",
            f"!pip install -q {' '.join(COLAB_BASE_PKGS)}"
        ]
    }

    # ── Cell 1 (optional): Extras cell (user-visible, user-controlled) ──
    # Per-notebook dependencies missing from both Colab and Binder.
    extra_pkgs = analyze_notebook_imports(cells)
    # Filter out packages already covered by the init cell
    extra_pkgs = [p for p in extra_pkgs if p not in COLAB_BASE_PKGS]

    injected = [init_cell]
    if extra_pkgs:
        extras_cell = {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Additional dependencies for this notebook\n",
                f"!pip install -q {' '.join(extra_pkgs)}"
            ]
        }
        injected.append(extras_cell)

    nb['cells'] = injected + cells

    # ── Colab notebook metadata ──
    # "cell_execution_strategy": "setup" tells Colab to auto-run the
    # first cell (or first section) when the notebook is opened.
    colab_meta = nb.setdefault('metadata', {}).setdefault('colab', {})
    colab_meta['cell_execution_strategy'] = 'setup'

    content = json.dumps(nb, indent=1, ensure_ascii=False)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(content)
```

**Behavior by environment:**

| | Colab | Binder Lab |
|---|---|---|
| **Init cell** (Qiskit stack) | Auto-runs on open, installs Qiskit | Auto-runs, fast no-op (already installed) |
| **Extras cell** (scikit-learn, etc.) | User sees it, decides to run | User sees it, decides to run |
| **`cell_execution_strategy`** | Honored (drives auto-run) | Ignored (not a Colab feature) |

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
  // Point to gh-pages copy (has install cells) instead of raw upstream
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

1. `python scripts/sync-content.py` — verify notebooks in `notebooks/` have the install cells, and `static/notebooks/` is populated.
2. Spot-check a generated `.ipynb`:
   - Confirm notebook metadata contains `"cell_execution_strategy": "setup"`.
   - Confirm cell 0 is the Qiskit init cell.
   - Confirm cell 1 (if present) is the extras cell.
   - Confirm original notebook cells follow after.
3. `npm run build` — no TypeScript or build errors.
4. `npm start` — verify on a tutorial page:
   - Banner shows "Open in Colab" and "Open in Binder JupyterLab".
   - Toolbar shows "Open in Colab".
   - Colab link opens the gh-pages copy with init cell auto-running.
5. URL correctness for each content type:
   - Tutorial: `notebooks/tutorials/{name}.ipynb`
   - Guide: `notebooks/guides/{name}.ipynb`
   - Course: `notebooks/learning/courses/{dir}/{name}.ipynb`
   - Module: `notebooks/learning/modules/{dir}/{name}.ipynb`
6. Manual Colab test: open a notebook via the Colab URL, verify the init cell auto-runs and installs Qiskit.

---

## Files Modified

| File | Change |
|------|--------|
| `scripts/sync-content.py` | Extend `copy_notebook_with_rewrite()` with two-cell injection + Colab metadata; add `publish_notebooks_to_static()` |
| `src/config/jupyter.ts` | Add `getColabUrl()`; update `getBinderLabUrl()` to point to gh-pages copies |
| `src/components/OpenInLabBanner/index.tsx` | Add Colab button alongside Lab/Binder button |
| `src/components/ExecutableCode/index.tsx` | Add Colab button to toolbar |

No changes to `docusaurus.config.ts` or MDX files.

---

## Data Flow

```
Upstream .ipynb (no install cells, no Colab metadata)
    │
    ├── sync-content.py: convert_notebook()
    │       → MDX page with %pip install cell (for in-page execution)
    │
    └── sync-content.py: copy_notebook_with_rewrite()
            → notebooks/{path}.ipynb:
            │   - Colab metadata: cell_execution_strategy = "setup"
            │   - Cell 0: !pip install -q qiskit ... (init, auto-runs on Colab)
            │   - Cell 1: !pip install -q scikit-learn ... (extras, optional)
            │   - Cell 2+: original notebook cells
            │
            → static/notebooks/{path}.ipynb (deployed to gh-pages)
                    │
                    ├── Colab: colab.research.google.com/github/.../blob/gh-pages/notebooks/...
                    │          → init cell auto-runs, extras cell visible to user
                    │
                    └── Binder: mybinder.org/...?labpath=notebooks/...
                               → init cell auto-runs (no-op), extras cell visible to user
```

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Colab ignores `cell_execution_strategy` for GitHub-opened notebooks | Graceful degradation — init cell is still visible and runnable manually; test with actual Colab URL |
| Init cell no-op adds ~5-10s on Binder | Acceptable; `-q` suppresses output |
| gh-pages branch size increases | ~50 notebooks + images; negligible vs. existing site assets |
| Notebooks lag behind upstream until next sync+deploy | Same cadence as the rest of the site content; acceptable |
| `analyze_notebook_imports()` misses a dependency | Existing risk — already affects MDX pages; not new |
| Binder can't find notebook at new path | Verify Binder `?labpath=` resolves relative to repo root on gh-pages branch |
| Button clutter on mobile | Two compact buttons in a flex row; test on narrow viewports |
