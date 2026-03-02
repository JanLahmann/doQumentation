# Plan: Binder-Enable doQumentation for Enhanced + Translated Notebooks

## Context

"Open in Binder JupyterLab" currently points to the sister repo (`Qiskit-documentation/main`), which has only raw English notebooks (no pip install cells, no translations). Thebelab (embedded "Run" button) also uses that repo for its kernel. We want to:
1. Binder-enable this repo's `notebooks` branch with enhanced + translated notebooks
2. Unify thebelab and JupyterLab to use the same Binder image
3. Add a daily cache warming workflow

**Size check**: EN notebooks = 95 MB (261 files), translated ≈ 207 MB (19 locales), total ≈ 302 MB. The sister repo is 380 MB and works fine with Binder. Well within limits.

## Strategy: Unified `notebooks` Branch

All notebooks (EN + 19 locales) + Binder config on one `notebooks` branch. One Binder image for everything (thebelab kernel + "Open in JupyterLab").

```
notebooks branch:
├── binder/requirements.txt    # Heavy Qiskit deps (Layer 1)
├── binder/postBuild           # Lighter packages (Layer 2)
├── runtime.txt                # python-3.12
├── tutorials/                 # EN enhanced notebooks
├── guides/
├── learning/
├── de/                        # Translated notebooks
│   ├── tutorials/
│   ├── guides/
│   └── learning/
├── es/
└── ...19 locales
```

Binder URLs:
- EN: `mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks?labpath=tutorials/hello-world.ipynb`
- DE: `mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks?labpath=de/tutorials/hello-world.ipynb`

## Changes

### 1. `.github/workflows/deploy.yml` — Binder config + preserve locale dirs [DONE]

Replaced the orphan-branch force-push with a selective update that preserves locale subdirectories and adds Binder config. Packages split across two Docker layers with cleanup to reduce size:

- **`binder/requirements.txt`** (Layer 1 — core, Docker-cached): `qiskit[visualization]~=2.3.0`, `qiskit-aer~=0.17`, `qiskit-ibm-runtime~=0.43.1`
- **`binder/postBuild`** (Layer 2 — lighter + cleanup): `qiskit-ibm-catalog`, `qiskit-ibm-transpiler`, `qiskit-addon-cutting`, `pylatexenc` + aggressive cleanup (remove test dirs, .pyc, strip .so, remove docs)

See `.github/workflows/deploy.yml` lines 43–83 for the implementation.

### 2. `.github/workflows/deploy-locales.yml` — Upload notebooks + consolidation job [DONE]

Added `permissions: contents: write`, artifact upload per matrix job, and `update-notebooks` consolidation job. See `.github/workflows/deploy-locales.yml` for the implementation.

### 3. `.github/workflows/binder.yml` — New cache warming workflow [DONE]

Hits all 3 federation members (2i2c, BIDS, GESIS) daily + on notebooks branch push. See `.github/workflows/binder.yml`.

### 4. `src/config/jupyter.ts` — Unified Binder URL + locale-aware functions

**Line 89** — Update `binderUrl` in `detectJupyterConfig()`:
```typescript
binderUrl: 'https://mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks',
```

**Lines 354–366** — Rewrite `getBinderLabUrl()` with locale + path mapping:
```typescript
export function getBinderLabUrl(config: JupyterConfig, notebookPath: string, locale?: string): string | null {
  if (!config.binderUrl) return null;

  // Same path mapping as getColabUrl()
  let nbPath = notebookPath.replace(/^docs\//, '');
  if (!nbPath.includes('/')) {
    nbPath = `tutorials/${nbPath}`;
  }

  const fullPath = locale && locale !== 'en'
    ? `${locale}/${nbPath}`
    : nbPath;

  return `${config.binderUrl}?labpath=${encodeURIComponent(fullPath)}`;
}
```

**Lines 614–625** (`getThebelabOptions` in ExecutableCode) — Switch thebelab to unified Binder:
```typescript
binderOptions: {
  repo: 'JanLahmann/doQumentation',
  ref: 'notebooks',
  binderUrl: 'https://mybinder.org',
},
```

### 5. `src/components/OpenInLabBanner/index.tsx` — Pass locale

**Line 31**: `labUrl = getBinderLabUrl(config, notebookPath, currentLocale);`

### 6. `binder/requirements.txt` — Update stub note [DONE]

Updated to point to `notebooks` branch and `deploy.yml`. See `binder/requirements.txt`.

## CI Timing

Both workflows trigger on `push: main`:
- `deploy.yml` (~8 min) → pushes EN + binder config, preserving locale dirs
- `deploy-locales.yml` (~15 min matrix + 2 min consolidation) → adds locale dirs on top

`deploy.yml` finishes first. The locale consolidation clones the updated branch, adds locales, pushes (non-force). If `deploy.yml` is still running (rare), the consolidation uses EN from the previous run. The `binder.yml` warm-up triggers on `notebooks` branch push, keeping the cache hot.

## Files Modified

1. `.github/workflows/deploy.yml` — Binder config (split layers) in notebooks push, preserve locale dirs **[DONE]**
2. `.github/workflows/deploy-locales.yml` — Artifact upload + consolidation job + permissions **[DONE]**
3. `.github/workflows/binder.yml` — **New** cache warming workflow **[DONE]**
4. `src/config/jupyter.ts` — `binderUrl`, `getBinderLabUrl()`, `getThebelabOptions()` **[Phase 4 — pending verification]**
5. `src/components/OpenInLabBanner/index.tsx` — Pass locale to `getBinderLabUrl()` **[Phase 4 — pending verification]**
6. `binder/requirements.txt` — Update stub note **[DONE]**

## Verification

1. **Build test**: `npm run build` — no TypeScript errors
2. **CI**: Push to main, verify both deploy workflows + binder warm-up succeed
3. **Branch content**: Verify `notebooks` branch has `binder/requirements.txt`, `runtime.txt`, EN dirs, locale dirs
4. **EN Binder test**: `mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks?labpath=tutorials/hello-world.ipynb` → JupyterLab opens with pip install cell
5. **DE Binder test**: Same URL with `labpath=de/tutorials/hello-world.ipynb` → German notebook
6. **Thebelab test**: "Run" button on live site → kernel connects via new Binder image
7. **Colab unchanged**: Colab links still use `/github/` scheme (no changes to `getColabUrl()`)
