# Multi-Language Translation Scaling Strategy

## Context
The translation POC (15 pages each in DE, JA, UK) is complete and verified. The goal is now to scale to full site (~380 pages) across 7 planned languages (DE, ES, JA, FR, UK, IT, PT). Key constraints:

- **GitHub Pages limit**: 1 GB total site size
- **Per-locale build output**: ~320 MB → max 3 locales per GH Pages site
- **GitHub Actions runners**: ~7 GB RAM (need 8+ GB for single-locale build, 12+ for multi)
- **Binder**: 100 concurrent users/repo, language-agnostic (shared kernel)
- **Translation tool**: Claude Code (free, interactive), not Claude API

## Approaches Compared

### A. Single Source Repo + Per-Locale Builds + Satellite Hosting Repos ★ Recommended

**Architecture:**
- Main repo (`JanLahmann/doQumentation`): ALL source code + ALL translations (`i18n/`)
- Satellite repos (`doqumentation-de`, `-ja`, etc.): Empty repos with only a `gh-pages` branch
- CI/CD: Main repo builds each locale separately → pushes build output to satellite repos
- DNS: `de.doqumentation.org` → satellite repo's GitHub Pages

**Key enabler**: `docusaurus build --locale de` builds ONLY German, outputs to `build/` with NO `/de/` prefix (assumes separate domain deployment). Each build uses ~8 GB RAM and outputs ~320 MB.

**How it works:**
```
Main repo (all code + all i18n/)
  ├─ build --locale en  → push → doqumentation (main GH Pages)
  ├─ build --locale de  → push → doqumentation-de gh-pages
  ├─ build --locale ja  → push → doqumentation-ja gh-pages
  ├─ build --locale fr  → push → doqumentation-fr gh-pages
  └─ ... (7 satellite repos)
```

**Config**: Environment variable in `docusaurus.config.ts` for per-locale URL:
```ts
url: process.env.DQ_LOCALE_URL || 'https://doqumentation.org',
```

**Build command**: `DQ_LOCALE_URL=https://de.doqumentation.org docusaurus build --locale de`

**Pros**: Single source of truth, independent builds/deploys, scales to unlimited languages, fits GH Pages limits, Binder shared
**Cons**: 7+ satellite repos to create, DNS subdomains, custom locale switcher needed, CI matrix (7× build time)

### B. Full Fork Per Language
Each language gets its own full repo (code + translations). Each runs its own `sync-content.py`.

**Pros**: Complete independence, simple CI per repo
**Cons**: Code drift (theme/component changes across 7 repos), duplicated everything, maintenance nightmare. **Not recommended.**

### C. Alternative Hosting (Vercel / Cloudflare Pages)
Single repo, all locales, deploy to a platform without the 1 GB limit.

**Pros**: Single deployment, no satellite repos
**Cons**: Still needs 16+ GB RAM for 8-locale build (exceeds CI runners), DNS change from GH Pages, vendor dependency. Doesn't solve the build memory problem. Would still need per-locale builds.

## Recommended Architecture (Approach A) — Details

### Satellite Repo Structure

| Repo | Domain | Content |
|------|--------|---------|
| doQumentation (main) | doqumentation.org | English (source of truth) |
| doqumentation-de | de.doqumentation.org | German |
| doqumentation-ja | ja.doqumentation.org | Japanese |
| doqumentation-es | es.doqumentation.org | Spanish |
| doqumentation-fr | fr.doqumentation.org | French |
| doqumentation-uk | uk.doqumentation.org | Ukrainian |
| doqumentation-it | it.doqumentation.org | Italian |
| doqumentation-pt | pt.doqumentation.org | Portuguese |

Each satellite repo: empty except `gh-pages` branch (populated by CI from main repo). Custom domain via `CNAME` file + DNS.

### CI/CD Workflow (main repo)

New workflow: `.github/workflows/deploy-locales.yml`

```yaml
strategy:
  matrix:
    locale: [de, ja, es, fr, uk, it, pt]
    include:
      - locale: de
        url: https://de.doqumentation.org
        repo: JanLahmann/doqumentation-de
      # ... etc
steps:
  - Checkout main repo
  - sync-content.py (shared, cached across matrix jobs)
  - populate-locale --locale ${{ matrix.locale }}
  - DQ_LOCALE_URL=${{ matrix.url }} docusaurus build --locale ${{ matrix.locale }}
  - Push build/ to satellite repo gh-pages branch
```

English build stays in existing `deploy.yml` (unchanged).

### Custom Locale Switcher

Docusaurus's built-in `localeDropdown` expects all locales on the same domain. For cross-domain, replace with a custom navbar item:

```tsx
// src/theme/NavbarItem/LocaleDropdown.tsx
const LOCALE_URLS = {
  en: 'https://doqumentation.org',
  de: 'https://de.doqumentation.org',
  ja: 'https://ja.doqumentation.org',
  // ...
};
// Dropdown that redirects to equivalent page on other domain
```

### Binder Sharing

- All locale deployments point to the SAME Binder endpoint (`mybinder.org/v2/gh/JanLahmann/Qiskit-documentation/main`)
- Code execution is language-agnostic (Python kernel doesn't care about UI language)
- No changes needed to Binder setup
- **Future**: If 100-user concurrent limit becomes an issue, create per-language Binder forks (identical `requirements.txt`, separate user pools + caches). Not needed now.

### Docker Multi-Locale

Docker has no 1 GB limit. The `Dockerfile.jupyter` could build with multiple locales:
```dockerfile
RUN docusaurus build  # All enabled locales → /de/, /ja/ subpaths
```
This gives Docker/RasQberry users all languages in one deployment. Leave for later.

## Incremental Translation (Avoiding Full Re-Translation)

### Problem
When upstream content changes (IBM updates Qiskit docs), `sync-content.py` regenerates English `docs/`. Need to identify which pages changed and only re-translate those.

### Solution: Content Hash Manifest

**1. Generate manifest after sync** — Enhance `sync-content.py`:
```python
# At end of sync, hash each generated MDX file
content-manifest.json = {
  "upstream_commit": "abc123",
  "files": {
    "tutorials/hello-world.mdx": { "hash": "sha256:..." },
    "guides/install-qiskit.mdx": { "hash": "sha256:..." },
    ...
  }
}
```

**2. Track source hash per translation** — Enhance `translate-content.py`:
- Store `source_hash` in each translation's metadata (frontmatter comment or separate manifest)
- After translation: write `i18n/{locale}/translation-manifest.json`

**3. Detect changes** — New command `detect-stale`:
```bash
python scripts/translate-content.py detect-stale --locale de
# Compares content-manifest.json hashes vs translation-manifest.json
# Output: list of pages needing re-translation
```

**4. Re-translate only changed pages:**
```bash
python scripts/translate-content.py extract --pages stale-pages-de.txt --locale de
# Claude Code translates only the changed pages
python scripts/translate-content.py reassemble
```

### Simpler Alternative: Git Diff

For quick checks without the manifest system:
```bash
# After sync-content.py, see what changed in docs/
git diff HEAD -- docs/ --name-only | grep '\.mdx$' > changed-pages.txt
```
Less precise (detects file touches, not content changes) but zero infrastructure.

### Expected Update Volume

IBM updates Qiskit docs ~monthly. Typical update: 10-30 pages change. This means:
- **Without manifest**: Re-translate all 380 pages (wasteful)
- **With manifest**: Re-translate only 10-30 changed pages (~15 min of Claude Code per language)
- **Across 7 languages**: ~2 hours total for incremental updates vs ~25 hours for full re-translation

## Translation Workflow (Claude Code at Scale)

### Full Site Translation (One-Time Per Language)

~380 pages, batch size 20, 3 parallel Sonnet agents per batch:
```
380 pages ÷ 20 per batch = 19 batches
19 batches × ~10 min each = ~3-4 hours per language
7 languages × 3-4 hours = ~21-28 hours total
```

**Workflow per language:**
1. `extract --pages all-pages.txt --locale es` → 19 batch JSONs
2. For each batch: launch 3-4 parallel Claude Code Task agents (Sonnet)
3. Each agent reads English source, writes translated MDX to `i18n/{locale}/`
4. `populate-locale --locale es` fills remaining fallbacks
5. `docusaurus build --locale es` to verify
6. `git add -f` translated files, commit

**Optimization**: Process multiple languages in parallel (different Claude Code sessions). Practically limited by context window management.

### Incremental Updates

After upstream sync:
1. `detect-stale --locale de` → 15 changed pages
2. `extract --pages stale-de.txt --locale de` → 1 batch
3. 1 round of Claude Code agents → done in ~10 min
4. Repeat for each language

## Other Considerations

### UI String Translation

Currently only content pages are translated. Docusaurus UI strings (sidebar labels, buttons, "Next"/"Previous", search placeholder) should also be translated:
```bash
npm run write-translations -- --locale de
# Creates i18n/de/code.json with all UI strings
```
These are ~200 short strings per language — one Claude Code session per language.

### SEO / hreflang Tags

Cross-domain locale sites should have `<link rel="alternate" hreflang="de" href="...">` tags so search engines serve the right language. Docusaurus doesn't do this for cross-domain setups. Need a custom `<Head>` component:
```html
<link rel="alternate" hreflang="de" href="https://de.doqumentation.org/tutorials/hello-world" />
<link rel="alternate" hreflang="en" href="https://doqumentation.org/tutorials/hello-world" />
```

### Search Per Locale

Each satellite build configures search for its language:
- `lunr-languages` supports: de, ja, fr, es, it, pt
- Does NOT support: uk (Ukrainian uses English tokenization)
- Config via env variable or locale-specific search settings

### Costs

- **Translation**: Free (Claude Code)
- **Hosting**: Free (GitHub Pages per repo)
- **DNS**: 7 CNAME records (IONOS, already have account)
- **CI/CD**: GitHub Actions free tier (2,000 min/month). 7 locale builds × ~5 min = ~35 min per deploy. Well within limits.
- **Binder**: Shared, no additional cost

## Decisions

- **Subdomains**: `de.doqumentation.org`, `ja.doqumentation.org`, etc.
- **Language priority**: DE → JA → UK → then ES, FR, IT, PT
- **Binder upstream forking**: Deferred — single `JanLahmann/Qiskit-documentation` fork for now
- **Docker**: Two variants — EN-only (current) and multi-lang (all translated locales)
- **UI strings**: Translate per language in parallel with content (not as a separate phase)
- **Translation scope**: MDX only — JupyterLab stays English. "MDX + generated translated notebooks" kept as future option.
- **Storage**: All translations in main repo (git-tracked, force-added). ~50-60 MB for full 7-language coverage.

## Implementation Priority

### Phase 1: Full German (content + UI) — validates workflow at scale

**Content translation** (~372 remaining pages):
1. Generate `all-pages.txt` listing all MDX files in `docs/`
2. `extract --pages all-pages.txt --locale de` → ~19 batches of 20
3. Translate with parallel Claude Code Sonnet agents (3 per batch)
4. ~3-4 hours of Claude Code time
5. `populate-locale --locale de` (preserves genuine translations, fills fallbacks)

**UI string translation** (in parallel with content):
1. `npm run write-translations -- --locale de` → `i18n/de/code.json`
2. ~200 short strings (buttons, nav labels, search placeholder, "Next"/"Previous")
3. Single Claude Code session to translate the JSON file

**Verify**: `docusaurus build --locale de` (single-locale, ~8 GB, ~320 MB output)

### Phase 2: Content manifest + satellite repo for DE

1. **Content manifest**: Enhance `sync-content.py` to generate `content-manifest.json` (SHA256 per MDX file + upstream commit hash)
2. **Translation manifest**: Enhance `translate-content.py` to track source hashes per translation
3. **Detect-stale command**: Compare manifests → output list of pages needing re-translation
4. **Satellite repo**: Create `JanLahmann/doqumentation-de`, set up GitHub Pages + DNS (`de.doqumentation.org`)
5. **CI/CD**: New `deploy-locales.yml` workflow with matrix strategy — builds `--locale de` → pushes to satellite
6. **Custom locale switcher**: Navbar component mapping locales to subdomain URLs
7. **hreflang tags**: `<Head>` component injecting `<link rel="alternate">` for SEO

### Phase 3: Roll out JA, UK (content + UI each)

Same workflow as Phase 1, per language. CI/CD matrix expands. New satellite repos + DNS records.

### Phase 4: Remaining languages (ES, FR, IT, PT)

Add banner templates, locale configs, translate, deploy. Each language is now a well-understood process.

### Phase 5: Docker multi-lang

Build a `Dockerfile.multilang` that includes all translated locales in one image. No GH Pages size constraint — Docker images can be multi-GB.
