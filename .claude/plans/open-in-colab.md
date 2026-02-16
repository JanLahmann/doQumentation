# Open in Colab — Implementation Plan

## Context

doQumentation renders Jupyter notebooks as interactive Docusaurus pages. Each page that originates from a `.ipynb` already carries a `notebookPath` prop (e.g. `docs/tutorials/hello-world.ipynb`) that maps to the file in the upstream repo `JanLahmann/Qiskit-documentation` on branch `main`.

Currently the project offers two ways to open the original notebook externally:

| Component | Where | Shows when |
|-----------|-------|------------|
| **OpenInLabBanner** | Banner below page title | Always (Lab or Binder) |
| **ExecutableCode toolbar** | Above first code cell | `labEnabled && notebookPath` (local/Docker only) |

Google Colab can open any public GitHub notebook via a deterministic URL:

```
https://colab.research.google.com/github/{owner}/{repo}/blob/{branch}/{path}
```

For this project:

```
https://colab.research.google.com/github/JanLahmann/Qiskit-documentation/blob/main/docs/tutorials/hello-world.ipynb
```

---

## Scope

Add an "Open in Colab" button that appears on every notebook-sourced page, in all deployment environments (GitHub Pages, Docker, RasQberry, custom). The button opens the original `.ipynb` directly in Google Colab.

**In scope:**
- URL generation function in `src/config/jupyter.ts`
- Colab button in the `OpenInLabBanner` component (alongside existing Lab/Binder button)
- Colab button in the `ExecutableCode` toolbar (alongside existing Run/Back/Lab buttons)
- Styling consistent with existing buttons

**Out of scope:**
- Colab-specific dependency setup (Colab users run `!pip install qiskit` themselves)
- Deep Colab API integration (no runtime embedding, just a link)
- Changes to sync-content.py (existing `notebookPath` prop is sufficient)

---

## Implementation

### Step 1: Add `getColabUrl()` to `src/config/jupyter.ts`

Add a new URL generator after the existing `getBinderLabUrl()` function:

```typescript
/**
 * Colab base URL for opening notebooks from the upstream GitHub repo.
 */
const COLAB_GITHUB_BASE = 'https://colab.research.google.com/github';
const UPSTREAM_OWNER = 'JanLahmann';
const UPSTREAM_REPO = 'Qiskit-documentation';
const UPSTREAM_BRANCH = 'main';

/**
 * Get the Google Colab URL for a notebook in the upstream repo.
 */
export function getColabUrl(notebookPath: string): string {
  return `${COLAB_GITHUB_BASE}/${UPSTREAM_OWNER}/${UPSTREAM_REPO}/blob/${UPSTREAM_BRANCH}/${notebookPath}`;
}
```

Notes:
- No `config` parameter needed — Colab URLs are environment-independent.
- The upstream owner/repo/branch constants can later be reused by `getBinderLabUrl()` to DRY up the Binder URL, but that refactor is out of scope here.
- `notebookPath` values like `docs/tutorials/hello-world.ipynb` are already URL-safe (no spaces, no special chars in the upstream repo).

### Step 2: Add Colab button to `OpenInLabBanner`

Modify `src/components/OpenInLabBanner/index.tsx`:

1. Import `getColabUrl` from `../../config/jupyter`.
2. Generate the Colab URL from `notebookPath`.
3. Render a second button next to the existing Lab/Binder button.

The banner currently shows one action button on the right. Add the Colab button as a secondary link next to it. Keep the existing Lab/Binder button as the primary action (solid background), style Colab as an outlined/secondary button so the two are visually distinct but co-located.

```tsx
import { detectJupyterConfig, getLabUrl, getBinderLabUrl, getColabUrl } from '../../config/jupyter';

// Inside the render:
const colabUrl = getColabUrl(notebookPath);

// Render both buttons in a flex container:
<div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
  <a href={colabUrl} target="_blank" rel="noopener noreferrer"
     title="Open notebook in Google Colab"
     style={{ /* outlined style */ }}>
    Open in Colab ↗
  </a>
  {labUrl && (
    <a href={labUrl} target="_blank" rel="noopener noreferrer"
       title="Opens the full Jupyter notebook for editing and advanced use"
       style={{ /* existing primary style */ }}>
      {label} ↗
    </a>
  )}
</div>
```

**Key design decisions:**
- Colab button always shows (doesn't depend on environment — Colab is always available).
- If `labUrl` is `null` (unknown environment, no Binder, no local Lab), the banner still renders with Colab as the sole action. This is an improvement: currently those environments see nothing.
- Order: Colab first (secondary/outlined), then Lab/Binder (primary/filled) — keeps Lab as the primary recommendation for users who have it, but gives everyone a fallback.

### Step 3: Add Colab button to `ExecutableCode` toolbar

Modify `src/components/ExecutableCode/index.tsx`:

1. Import `getColabUrl`.
2. After the existing "Open in Lab" button (line ~879), add an "Open in Colab" button.
3. The Colab button shows whenever `notebookPath` is set (regardless of `labEnabled`).

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

Note: This uses an `<a>` tag (not `<button>` with `onClick` + `window.open`) for better accessibility and right-click support. The existing Lab button could be refactored to match, but that's out of scope.

### Step 4: Verify & test

1. `npm run build` — ensure no TypeScript or build errors.
2. `npm start` — manually verify on a tutorial page:
   - Banner shows both "Open in Colab" and "Open in Binder JupyterLab" (or "Open in JupyterLab" on local).
   - Clicking "Open in Colab" opens the correct notebook in a new Colab tab.
   - Toolbar above code cells shows the Colab button.
3. Spot-check URL correctness for each content type:
   - Tutorial: `docs/tutorials/{name}.ipynb`
   - Guide: `docs/guides/{name}.ipynb`
   - Course: `learning/courses/{dir}/{name}.ipynb`
   - Module: `learning/modules/{dir}/{name}.ipynb`

---

## Files Modified

| File | Change |
|------|--------|
| `src/config/jupyter.ts` | Add `getColabUrl()` function + upstream constants |
| `src/components/OpenInLabBanner/index.tsx` | Add Colab button alongside Lab/Binder button |
| `src/components/ExecutableCode/index.tsx` | Add Colab button to toolbar |

No changes to `sync-content.py`, `docusaurus.config.ts`, or any MDX files.

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Upstream repo path mismatch (notebook doesn't exist at that path) | Same paths already work for Binder — if Binder works, Colab works |
| Colab can't install Qiskit (heavy deps) | Out of scope — Colab supports `pip install qiskit` but users manage this themselves; no worse than any external Colab link |
| Upstream repo goes private | Same risk applies to existing Binder integration; repo is public and intended to stay so |
| Button clutter on mobile | Two compact buttons in a flex row; test on narrow viewports |
