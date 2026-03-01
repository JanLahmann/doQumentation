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
├── binder/requirements.txt    # Qiskit deps (downloaded from sister repo)
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

### 1. `.github/workflows/deploy.yml` — Binder config + preserve locale dirs

Replace the orphan-branch force-push (lines 43–51) with a selective update that preserves locale subdirectories and adds Binder config:

```yaml
      - name: Push notebooks to notebooks branch
        run: |
          # Clone existing notebooks branch (preserves locale dirs)
          git clone --depth 1 --branch notebooks \
            "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" \
            notebooks-repo 2>/dev/null || {
              mkdir notebooks-repo && cd notebooks-repo && git init && git checkout -b notebooks && cd ..
            }
          cd notebooks-repo

          # Remove EN content but keep locale subdirs (2-3 letter dirs)
          for d in tutorials guides learning; do rm -rf "$d" 2>/dev/null; done

          # Copy fresh EN notebooks
          cp -r ../build/notebooks/* .

          # Download Binder config from sister repo (stays in sync)
          mkdir -p binder
          curl -sL "https://raw.githubusercontent.com/JanLahmann/Qiskit-documentation/main/binder/requirements.txt" \
            -o binder/requirements.txt
          curl -sL "https://raw.githubusercontent.com/JanLahmann/Qiskit-documentation/main/runtime.txt" \
            -o runtime.txt

          git add -A
          git diff --cached --quiet && echo "No changes" && exit 0
          git -c user.name="github-actions[bot]" -c user.email="github-actions[bot]@users.noreply.github.com" \
            commit -m "Update EN notebooks + Binder config from ${{ github.sha }}"
          git push --force "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" notebooks
```

### 2. `.github/workflows/deploy-locales.yml` — Upload notebooks + consolidation job

Add `permissions: contents: write` at workflow level.

In each matrix job, add after the build step (before satellite deploy):
```yaml
      - name: Upload locale notebooks
        uses: actions/upload-artifact@v4
        with:
          name: notebooks-${{ matrix.locale }}
          path: build/notebooks/
          retention-days: 1
```

New post-matrix consolidation job:
```yaml
  update-notebooks-branch:
    needs: build-and-deploy
    runs-on: ubuntu-latest
    steps:
      - name: Download all locale notebook artifacts
        uses: actions/download-artifact@v4
        with:
          pattern: notebooks-*
          path: locale-notebooks/

      - name: Push locale notebooks to notebooks branch
        run: |
          git clone --depth 1 --branch notebooks \
            "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" \
            notebooks-repo 2>/dev/null || {
              mkdir notebooks-repo && cd notebooks-repo && git init && git checkout -b notebooks && cd ..
            }
          cd notebooks-repo
          for dir in ../locale-notebooks/notebooks-*; do
            locale=$(basename "$dir" | sed 's/^notebooks-//')
            rm -rf "$locale"
            cp -r "$dir" "$locale"
          done
          git add -A
          git diff --cached --quiet && echo "No changes" && exit 0
          git -c user.name="github-actions[bot]" -c user.email="github-actions[bot]@users.noreply.github.com" \
            commit -m "Update translated notebooks ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
          git push "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" notebooks
```

### 3. `.github/workflows/binder.yml` — New cache warming workflow

Modeled on the sister repo's `binder.yml`. Hits all 3 federation members daily + on notebooks branch changes:

```yaml
name: Binder Cache

on:
  schedule:
    - cron: "0 6 * * *"
  push:
    branches: [notebooks]
  workflow_dispatch:

jobs:
  warm:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        binder:
          - name: 2i2c
            url: https://2i2c.mybinder.org/build/gh/JanLahmann/doQumentation/notebooks
          - name: BIDS
            url: https://bids.mybinder.org/build/gh/JanLahmann/doQumentation/notebooks
          - name: GESIS
            url: https://notebooks.gesis.org/binder/build/gh/JanLahmann/doQumentation/notebooks
    name: Warm ${{ matrix.binder.name }}
    steps:
      - name: Trigger Binder build on ${{ matrix.binder.name }}
        run: |
          curl -s --max-time 1200 \
            "${{ matrix.binder.url }}" \
          | while IFS= read -r line; do
              echo "$line"
              if echo "$line" | grep -q '"phase": "ready"'; then
                echo "Binder image is ready on ${{ matrix.binder.name }}."
                exit 0
              fi
              if echo "$line" | grep -q '"phase": "failed"'; then
                echo "::error::Binder build failed on ${{ matrix.binder.name }}."
                exit 1
              fi
            done
```

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

### 6. `binder/requirements.txt` — Update stub note

Replace stub with:
```
# Binder config lives on the `notebooks` branch (auto-pushed by CI).
# The active requirements are downloaded from JanLahmann/Qiskit-documentation.
# See .github/workflows/deploy.yml for details.
```

## CI Timing

Both workflows trigger on `push: main`:
- `deploy.yml` (~8 min) → pushes EN + binder config, preserving locale dirs
- `deploy-locales.yml` (~15 min matrix + 2 min consolidation) → adds locale dirs on top

`deploy.yml` finishes first. The locale consolidation clones the updated branch, adds locales, pushes (non-force). If `deploy.yml` is still running (rare), the consolidation uses EN from the previous run. The `binder.yml` warm-up triggers on `notebooks` branch push, keeping the cache hot.

## Files Modified

1. `.github/workflows/deploy.yml` — Binder config in notebooks push, preserve locale dirs
2. `.github/workflows/deploy-locales.yml` — Artifact upload + consolidation job + permissions
3. `.github/workflows/binder.yml` — **New** cache warming workflow
4. `src/config/jupyter.ts` — `binderUrl`, `getBinderLabUrl()`, `getThebelabOptions()`
5. `src/components/OpenInLabBanner/index.tsx` — Pass locale to `getBinderLabUrl()`
6. `binder/requirements.txt` — Update stub note

## Verification

1. **Build test**: `npm run build` — no TypeScript errors
2. **CI**: Push to main, verify both deploy workflows + binder warm-up succeed
3. **Branch content**: Verify `notebooks` branch has `binder/requirements.txt`, `runtime.txt`, EN dirs, locale dirs
4. **EN Binder test**: `mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks?labpath=tutorials/hello-world.ipynb` → JupyterLab opens with pip install cell
5. **DE Binder test**: Same URL with `labpath=de/tutorials/hello-world.ipynb` → German notebook
6. **Thebelab test**: "Run" button on live site → kernel connects via new Binder image
7. **Colab unchanged**: Colab links still use `/github/` scheme (no changes to `getColabUrl()`)
