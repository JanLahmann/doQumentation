# Plan: Add Guides, Modules, and API Reference to doQumentation

## Context

doQumentation currently syncs **Tutorials** (42 notebooks) and **Courses** (13 courses, ~154 pages) from the upstream `JanLahmann/Qiskit-documentation` fork. The upstream repo also contains **Guides** (172 pages of how-to content), **Modules** (12 classroom notebooks), and **API References** (680+ auto-generated pages). This plan adds all three content types.

## Summary of content to add

| Content | Files | Format | Effort | Approach |
|---------|-------|--------|--------|----------|
| **Modules** | 12 notebooks + 2 index MDX | `.ipynb` | Easy | Full sync (same pattern as courses) |
| **Guides** | 86 notebooks + 86 MDX | `.ipynb` + `.mdx` | Medium | Full sync with new component stubs |
| **API Reference** | 680+ auto-generated MDX | `.mdx` | N/A | Link-only (not synced — see rationale) |

## API Reference: Link-only (no sync)

**Rationale:** API docs are auto-generated from Qiskit source via a Sphinx→MDX pipeline. They use custom JSX components (`<Class>`, `<Function>`, `<Attribute>`) that would each need non-trivial rendering implementations. The volume is massive (680+ files for current versions alone, plus historical versions). And API docs are always available offline via `help()` in any Jupyter session. The effort-to-value ratio is poor.

**Implementation:** Add a prominent "API Reference" link in the sidebar pointing to `https://docs.quantum.ibm.com/api`. Also mention it on the home page in the "We recommend IBM's official platform" section (it's already listed as "Documentation" — no change needed).

---

## Step 1: Modules sync

Modules are 12 classroom notebooks in 2 categories (Computer Science, Quantum Mechanics). Identical pattern to courses.

### 1a. `sync-content.py` — sparse checkout

Add to `CONTENT_PATHS`:
- `learning/modules`
- `public/learning/images` (already included for courses)

### 1b. `sync-content.py` — `process_modules()`

New function modeled on `process_courses()`:
- Input: `upstream-docs/learning/modules/`
- Output MDX: `docs/learning/modules/{module-name}/`
- Output notebooks: `notebooks/learning/modules/{module-name}/`
- Same transforms as courses: `convert_notebook()`, `transform_mdx()`, OpenInLabBanner injection
- Handle `foo/foo.ipynb` slug collision (same fix as courses)

### 1c. `sync-content.py` — `generate_module_sidebar()`

New function modeled on `generate_course_sidebar()`:
- Read per-module `_toc.json` files
- Skip "Modules" wrapper (same as "Lessons" skip in courses)
- Output: `sidebar-modules.json`

### 1d. `sidebars.ts`

- Import `sidebar-modules.json` (with empty-array fallback)
- Add "Modules" category under the existing "Courses" category in the sidebar
- Collapsed by default

### 1e. Image sync

Add `public/learning/images/modules` → `static/learning/images/modules` mapping (if module images exist in a separate path — likely already covered by existing `public/learning/images` mapping).

### 1f. Navbar

Add "Modules" to the top navbar alongside Tutorials and Courses (or nest under a "Learning" dropdown — see question below).

---

## Step 2: Guides sync

Guides are 172 pages of how-to content (86 notebooks + 86 MDX), organized in a flat directory with a rich hierarchical `_toc.json`.

### 2a. `sync-content.py` — sparse checkout

Add to `CONTENT_PATHS`:
- `docs/guides`
- `public/docs/images/guides` (if exists — guide images)

### 2b. `sync-content.py` — `process_guides()`

New function modeled on `process_tutorials()`:
- Input: `upstream-docs/docs/guides/`
- Output MDX: `docs/guides/`
- Output notebooks: `notebooks/guides/`
- Same transforms: `convert_notebook()`, `transform_mdx()`, OpenInLabBanner for notebook-derived pages
- Transform guides index page (`transform_guides_index()`) with site-specific frontmatter

### 2c. New component stubs

Guides use 3 components not yet stubbed in `src/theme/MDXComponents.tsx`:

| Component | Stub behavior |
|-----------|--------------|
| `Card` + `CardGroup` | Render as styled link cards (simple div + anchor). Only used in `guides/index.mdx`. |
| `OperatingSystemTabs` | Render as standard Docusaurus `<Tabs>` (map `value`/`label` props). Used in `install-qiskit.mdx`. |
| `CodeAssistantAdmonition` | Render as a tip admonition or skip entirely (IBM-specific feature). |

`Admonition` is already handled by the MDX transform (converted to `:::note` syntax).
`IBMVideo` is already stubbed.

### 2d. `sync-content.py` — `generate_guides_sidebar()`

- Read `upstream-docs/docs/guides/_toc.json`
- Parse hierarchical structure into Docusaurus sidebar categories
- Output: `sidebar-guides.json`

### 2e. `sidebars.ts`

- Import `sidebar-guides.json` (with fallback)
- Add "Guides" category to the sidebar

### 2f. MDX transform additions

Add to `MDX_TRANSFORMS`:
- `(/docs/guides/` → `(/guides/` (local guide links)
- Existing rule `(/docs/(?!tutorials|images/)` needs updating to also exclude `guides/`

### 2g. Image sync

Add `public/docs/images/guides` → `static/docs/images/guides` mapping.

---

## Step 3: API Reference (link-only)

### 3a. `sidebars.ts`

Add an external link item to the sidebar:
```ts
{
  type: 'link',
  label: 'API Reference',
  href: 'https://docs.quantum.ibm.com/api',
}
```

### 3b. Navbar

Add "API Reference" as an external link in the navbar.

---

## Step 4: Navbar reorganization

Current navbar: `doQumentation | Tutorials | Courses`

New flat navbar:
- **doQumentation** (logo/home)
- **Tutorials** → `/tutorials`
- **Guides** → `/guides`
- **Courses** → `/learning/courses/basics-of-quantum-information`
- **Modules** → `/learning/modules/computer-science`
- **API Reference** → external link to `https://docs.quantum.ibm.com/api`

---

## Step 5: Build & gitignore updates

- Add `sidebar-modules.json` and `sidebar-guides.json` to `.gitignore`
- Add `--guides-only`, `--modules-only` flags to `sync-content.py` for selective sync
- Update `main()` to call new processing functions

---

## Files to modify

| File | Changes |
|------|---------|
| `scripts/sync-content.py` | Add sparse paths, `process_modules()`, `process_guides()`, sidebar generators, transform updates |
| `sidebars.ts` | Import new sidebar JSONs, add Guides/Modules/API categories |
| `src/theme/MDXComponents.tsx` | Add stubs: Card, CardGroup, OperatingSystemTabs, CodeAssistantAdmonition |
| `docusaurus.config.ts` | Update navbar items |
| `.gitignore` | Add `sidebar-modules.json`, `sidebar-guides.json` |
| `docs/index.mdx` | No changes needed (API Reference already covered under "Documentation" link) |

---

## Verification

1. Run `python scripts/sync-content.py` — should clone and process all content types
2. Run `npm run build` — should build without errors (check broken link warnings)
3. Check sidebar: Home → Tutorials → Guides → Courses → Modules → API Reference (external)
4. Check navbar: Tutorials | Guides | Learning (dropdown) | API Reference
5. Spot-check a few pages:
   - A guide with notebook: code blocks present, OpenInLabBanner visible
   - A guide with tabs: OperatingSystemTabs renders as Docusaurus Tabs
   - A module notebook: renders like a course lesson
   - API Reference sidebar link: opens IBM docs in new tab

## Implementation order

1. Modules first (easiest, validates the pattern)
2. Guides second (larger, needs component stubs)
3. API Reference link + navbar reorganization last
