# Plan: Generate Translated Jupyter Notebooks from Translated MDX

## Context

"Open in Colab" and "Open in Lab" buttons currently always open English notebooks, even on translated locale sites (de.doqumentation.org, etc.). The translated MDX files contain translated markdown with identical Python code blocks — we can merge the translated text back into the original English `.ipynb` skeleton to produce translated notebooks.

## Approach: Merge (not full reverse conversion)

Use the English `.ipynb` as a template. Replace only the markdown cells with translated text extracted from the locale `.mdx`. Code cells, outputs, and metadata stay untouched.

**Why this works:** Code blocks in the MDX are byte-for-byte identical to code cells in the notebook. They serve as alignment anchors — the translated text between them maps directly to the markdown cells between code cells.

## Scope

- **Colab**: gets translated notebooks (served from `static/notebooks/` on each locale site)
- **Binder "Open in Lab"**: stays English (Binder opens from `JanLahmann/Qiskit-documentation` repo — no practical way to add translated notebooks without bloating the repo and breaking Binder caching)
- **Embedded "Run"**: stays English (thebelab executes code, language-agnostic)

## Implementation

### 1. Core merge function in `scripts/sync-content.py` (~4h)

New function `generate_translated_notebook(english_ipynb, translated_mdx, output_path)`:

1. Parse translated MDX into segments: `[TEXT, CODE, TEXT, CODE, ...]`
   - Strip frontmatter, `<OpenInLabBanner>`, `{/* comments */}`
   - Use code fence boundaries (` ```python `) as delimiters
2. Parse English `.ipynb` cells in order
3. Walk both in parallel using code blocks as alignment anchors:
   - **Code cell** → keep unchanged, advance MDX past matching code block
   - **Markdown cell** → replace `source` with translated text from MDX
4. Clean up translated text before injecting:
   - Strip heading anchors: `{#english-anchor}` (Docusaurus-specific, renders as visible text in Jupyter)
   - Unescape MDX characters: `\{` → `{`, `\}` → `}`
   - Convert `<Admonition type="note">` → `> **Note:** ...` (blockquote)
   - Strip `<OpenInLabBanner>`, `{/* ... */}` comments
   - Keep `<details>/<summary>` as-is (valid HTML in Jupyter markdown)
5. Apply existing `copy_notebook_with_rewrite()` logic (pip install cells + Colab metadata)
6. Write to `static/notebooks/{path}` (no locale prefix — each locale is its own site)

**Consecutive markdown cells:** Multiple markdown cells between two code cells produce a single text block in MDX. Split back using heading lines (`## ...`) as boundaries. If heading count mismatches, fall back to joining all text into one markdown cell (safe, slightly different structure).

**Skip untranslated pages:** MDX files with `{/* doqumentation-untranslated-fallback */}` marker → skip (just English with a banner, no point generating a "translated" notebook).

### 2. Orchestrator function (~1h)

New `generate_locale_notebooks(locale)`:
- Glob `i18n/{locale}/docusaurus-plugin-content-docs/current/**/*.mdx`
- For each file with `notebook_path` in frontmatter (and no fallback marker):
  - Find the upstream `.ipynb` at `upstream-docs/{notebook_path}`
  - Call `generate_translated_notebook()`
  - Output to `static/notebooks/{category}/{name}.ipynb`
- New CLI flag: `--generate-locale-notebooks --locale XX`

### 3. Frontend changes (~30min)

**`src/config/jupyter.ts`:**
- `getColabUrl(notebookPath, locale?)` — when locale is non-English, point to `{locale}.doqumentation.org/notebooks/...` instead of `doqumentation.org/notebooks/...`

**`src/components/OpenInLabBanner/index.tsx`:**
- Import `useDocusaurusContext`, extract `currentLocale`, pass to `getColabUrl()`

**`src/components/ExecutableCode/index.tsx`:**
- Same: pass `currentLocale` to `getColabUrl()` in toolbar

### 4. CI changes (~15min)

**`.github/workflows/deploy-locales.yml`:**
- Add step after `sync-content.py` and before `docusaurus build`:
  ```yaml
  - name: Generate translated notebooks
    run: python3 scripts/sync-content.py --generate-locale-notebooks --locale ${{ matrix.locale }}
  ```

### 5. Testing (~1h)

- Run merge on 3-5 notebooks across 2 locales (DE, JA — different scripts/structures)
- Open generated notebooks in Jupyter to verify markdown renders correctly
- Verify Colab URL opens the translated notebook
- Check edge cases: courses (nested paths), guides (MDX+notebook mix), hello-world (special path)

## Effort Summary

| Component | Effort |
|-----------|--------|
| Core merge algorithm + text cleanup | ~5h |
| Orchestrator + CLI flag | ~1h |
| Frontend (3 files, small changes) | ~30min |
| CI workflow | ~15min |
| Testing + edge cases | ~2h |
| **Total** | **~9h** |

## Build size impact

No increase — translated notebooks **replace** the English notebooks already shipped in every locale build (95 MB in `static/notebooks/`). For genuinely translated pages, the merged notebook replaces the English copy. For untranslated (fallback) pages, the English notebook is kept as-is.

## Files to modify

- `scripts/sync-content.py` — new functions: `generate_translated_notebook()`, `generate_locale_notebooks()`, CLI handling
- `src/config/jupyter.ts` — `getColabUrl()` locale parameter
- `src/components/OpenInLabBanner/index.tsx` — pass `currentLocale`
- `src/components/ExecutableCode/index.tsx` — pass `currentLocale`
- `.github/workflows/deploy-locales.yml` — add notebook generation step

## Existing code to reuse

- `copy_notebook_with_rewrite()` in sync-content.py — pip install injection + Colab metadata (line 912)
- `rewrite_notebook_image_paths()` — image path fixing for Jupyter (line 871)
- `analyze_notebook_imports()` — dependency detection (line 344)
- `COLAB_BASE_PKGS` — base Qiskit packages for Colab init cell (line 909)
