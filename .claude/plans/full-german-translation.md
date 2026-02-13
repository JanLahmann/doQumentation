# Full German Translation — 372 Remaining Pages

## Context

The 15-page German POC is working (verified on dev server). Now scaling to all ~387 MDX content pages. 15 are already translated, leaving **372 pages** to do.

Infrastructure is already in place: `docusaurus.config.ts` has `de` locale, `sidebars.ts` has deduplication, `scripts/translate-content.py` exists, navbar has locale dropdown.

---

## Scope

| Area | Files | Lines | Already done |
|------|-------|-------|--------------|
| Homepage | 1 | 150 | 1 |
| Tutorials | 44 | 28,294 | 4 |
| Guides | 172 | 39,438 | 5 |
| Courses | 154 | 50,656 | 3 |
| Modules | 15 | 10,559 | 2 |
| Learning index | 1 | 26 | 0 |
| **Total** | **387** | **129,123** | **15** |

**Remaining: 372 files** (~50% of lines are code/math/JSX that stay English)

React pages (`features.tsx`, `jupyter-settings.tsx`) are **out of scope** — they need i18n library integration, separate effort.

---

## Implementation

### Step 1: Generate full page list

Create `translation-batches/pages-full.txt` listing all 372 remaining MDX files (relative to `docs/`). Exclude the 15 already in `i18n/de/`.

```bash
# List all MDX files, exclude already-translated ones
find docs/ -name "*.mdx" | sed 's|^docs/||' | sort > /tmp/all-pages.txt
# Remove the 15 POC pages already done
comm -23 /tmp/all-pages.txt <(sort translation-batches/pages-poc.txt) > translation-batches/pages-full.txt
```

### Step 2: Extract batches

```bash
python scripts/translate-content.py extract --pages translation-batches/pages-full.txt --locale de
```

Produces **~19 batch JSON files** (372 files / 20 per batch).

### Step 3: Translate all batches

For each batch, launch **3 parallel Claude Code Task agents** (Sonnet), each handling ~7 files from the batch. This matches the POC approach (3 parallel agents worked well).

**Per batch (~20 files):**
- Agent 1: files 1-7
- Agent 2: files 8-14
- Agent 3: files 15-20

Each agent reads the source MDX from `docs/`, translates prose to German (preserving code/math/JSX), writes translated MDX directly to `i18n/de/docusaurus-plugin-content-docs/current/`.

**19 batches x 3 agents = ~57 agent invocations**, done sequentially in groups of 3.

### Step 4: Incremental verification

After every ~5 batches (~100 pages), run a quick build check:
```bash
NODE_OPTIONS="--max-old-space-size=8192" npm run build -- --locale de
```

This catches any MDX parsing errors early rather than at the end.

### Step 5: Final build & spot-check

Full German build + spot-check of:
- Largest files (1,900+ lines) rendered correctly
- Math-heavy course pages (KaTeX)
- Code-heavy tutorial pages (code blocks untouched)
- Sidebar navigation across all sections
- Internal links between translated pages

---

## Effort Estimate

| Phase | Time |
|-------|------|
| Page list + extract | ~5 min |
| Translation (19 batches x 3 agents) | ~2-3 hours (agent runtime) |
| Incremental builds (4 checks) | ~20 min |
| Final build + spot-check | ~10 min |
| **Total** | **~3-4 hours** |

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Agent translation errors | Spot-check sample from each content area |
| MDX build failures | Incremental builds every ~100 pages |
| Large files exceed agent context | Largest file is 1,934 lines — fits easily in Sonnet context |
| Inconsistent terminology | Same agent prompt template ensures consistent quantum computing terms |

---

## Files Modified

- `translation-batches/pages-full.txt` (NEW, gitignored) — full page list
- `i18n/de/docusaurus-plugin-content-docs/current/**/*.mdx` (NEW, 372 files) — translated content

No config changes needed — all infrastructure from the POC is reusable.
