# Completed Features — Detailed Notes

Reference for completed work. See MEMORY.md for the concise index.

## Image handling (730fd5c, e472391)
- `_text_to_output()` in `extract_cell_outputs()`: detects `<Image>` JSX in notebook text/plain outputs, converts to markdown `![alt](src)`
- MDX transforms rewrite `https://docs.quantum.ibm.com/learning/images/` and `/docs/images/` to local paths
- `Image` component registered in MDXComponents as fallback (renders as `<img>`)
- Fixed 264 broken image refs + 20+ external IBM image URLs
- Fixed `/learning/images/` paths being rewritten to external IBM URLs (added `images/` to negative lookahead)

## LaTeX output handling (e472391)
- `extract_cell_outputs()` handles `text/latex` MIME type (priority: image/png > text/latex > text/plain)
- LaTeX content already has `$$` delimiters — passes through directly to KaTeX rendering
- 24 instances across 4 files (3 course pages + 1 guide)

## Cell execution feedback (7d97e5d, e5c63c5)
- Persistent left border on `.thebelab-cell`: amber (running), green (done), red (error)
- Error detection: `detectCellError()` inspects output for ModuleNotFoundError, NameError, tracebacks
- Contextual error hints: `showErrorHint()` injects `!pip install` or "run cells above" hint below cell
- CSS classes: `thebelab-cell--running`, `thebelab-cell--done`, `thebelab-cell--error`
- Toolbar legend: amber=running, green=done, red=error
- Back button shows `window.confirm()` if any cells have been executed

## IBMVideo embeds (221cf0b)
- `IBMVideo.tsx`: YouTube-first with IBM Video Streaming fallback
- `YOUTUBE_MAP`: 32 IBM Video IDs → YouTube video IDs (static mapping)
- Remaining ~16 videos use `video.ibm.com/embed/recorded/{id}` (unlisted but working)

## IBM Quantum credential store + simulator mode (96f25f6, bbbc0a1)
- Settings page (`/jupyter-settings`): IBM Quantum Account (token/CRN, 7-day auto-expiry) + Simulator Mode (AerSimulator/FakeBackend toggle, device picker with `<optgroup>` by qubit count)
- Kernel injection via `requestExecute()` after thebelab bootstrap: silent `save_account()` or `_DQ_MockService` monkey-patch
- Dynamic fake backend discovery: introspects `fake_provider` at kernel connect, caches in localStorage
- Active mode selector: radio buttons when both credentials + simulator configured
- Toolbar: "Simulator" badge + "Settings" link
- Settings page setup steps: 5 steps with direct links to IBM Quantum Cloud pages

## Mobile navigation fix (fda945c → 2fb59d0)
- Settings link added to `sidebars.ts` (after API Reference)
- Hamburger menu: minimal 1.5px border at 50% white, no background, 24px SVG

## Homepage redesign (91547ca → d6d933d, 4c5661b)
- Hero banner: centered H1 + subtitle + 3 outline CTA buttons
- Storyline: "IBM Quantum's open-source content" (factual) → "What this project adds" → featured italic blue h3 subtitle
- Content stats bar: 42 Tutorials | 171 Guides | 154 Course pages | 14 Modules — clickable links
- Tutorial cards: featured "Basics of QI" + Hello World + CHSH, Grover's, Kernel Training
- "Code execution" section with 3 `<details>` blocks
- CSS: `.hero-banner`, `.featured-subtitle`, `.content-stats`, `.tutorial-cards` in `custom.css`

## Website review fixes round 1 (262b699)
- Run/Back rename, dark mode circuit images, execution legend, warning suppression
- Code horizontal scroll, dismissible binder hint, JupyterLab tooltip, simulator mode note

## Website review fixes round 2 (e5c63c5)
- Search: `@easyops-cn/docusaurus-search-local` v0.52.3
- Landing pages: `create_learning_landing_pages()` generates `/learning/` and `/learning/modules/`
- Error detection + hints, Back confirmation, a11y verification

## JSX href path rewriting (cfc5c51)
- Card components use `href="/docs/..."` not markdown links — MDX_TRANSFORMS only caught `(/docs/...)`
- Added 3 JSX href transforms: `/docs/tutorials` → `/tutorials`, `/docs/guides/` → `/guides/`, catch-all → IBM upstream URL
- Fixed guides index page: Quickstart, Tutorials, all capability cards, Error registry → IBM, Support

## Docker (7a8142b)
- Multi-stage Dockerfile + Dockerfile.jupyter with content sync step
- Build stage: `node:20-alpine` + `python3 + git`, runs `sync-content.py` before `npm run build`
- GH Actions workflow (`docker.yml`) pushes to ghcr.io: `:latest` and `:jupyter`

## Deps sync (sync-deps.yml)
- `scripts/sync-deps.py`: Fetches upstream requirements, applies arch exception rules
- `.github/workflows/sync-deps.yml`: Weekly Monday 8am UTC + manual dispatch, opens PR

## Binder usage analytics (Feb 2026)
- First 3 days: Feb 7 (25), Feb 8 (36), Feb 9 (6) = 67 total launches
- Well within Binder's 100-concurrent limit; no self-hosting needed yet

## Website review round 3 fixes (Feb 2026)
Based on 6-session comprehensive review (41 issues). Triaged: 10 already fixed, 7 by design, 1 reviewer error, 23 genuinely open.

### Kernel reliability (#38 CRITICAL, #39)
- `kernelDead` flag in ExecutableCode: set on thebelab `dead`/`failed` status
- `handleKernelStatusForFeedback()` detects kernel death → marks executing cell error, broadcasts error status
- `markCellExecuting()` checks `kernelDead` → shows red border + "Kernel disconnected" hint immediately
- `handleReset()` now resets all module-level state (`thebelabBootstrapped`, `kernelDead`, listeners) for fresh re-bootstrap
- Error status text: "Disconnected — click Back, then Run to retry"

### Event listener leak fix (code review)
- `setupCellFeedback()` stores cleanup fns in `feedbackCleanupFns[]`, cleans up before re-setup
- `handleReset()` calls all cleanup functions

### Toolbar polish (#10, #27)
- Removed redundant "Ready" badge — legend (running/done/error) already indicates active kernel
- Status indicator only shows for `connecting` and `error` states
- Thebelab restart buttons hidden via JS (`style.display = 'none'` for buttons with "restart" text)
- `aria-live="polite"` added to status indicator for screen readers

### URL encoding (code review XSS fix)
- `getLabUrl()` and `getNotebookUrl()` in `jupyter.ts`: path segments encoded via `encodeURIComponent`, token encoded

### robots.txt (#40)
- `static/robots.txt` created with standard directives + sitemap reference

## Execution mode indicator + cell injection feedback (abec1dd)
- Dynamic toolbar badge replaces static "Simulator" badge:
  - Simulator mode: shows "AerSimulator" or fake device name (e.g. "FakeSherbrooke") — blue badge
  - Credentials mode: shows "IBM Quantum" — teal badge
  - Neither: no badge
- Badge only appears after kernel ready + injection confirmed (not just localStorage check)
- `INJECTION_EVENT` custom event + `InjectionInfo` type coordinate injection result from `injectKernelSetup()` to component
- `broadcastInjection()` dispatches event with mode, label, and message
- Component state: `injectionInfo` (persists for badge) + `injectionToast` (auto-clears after 4s)
- Green toast below toolbar: "Simulator active — using AerSimulator" or "IBM Quantum credentials applied"
- CSS animation `dq-toast-fade`: fade-in 5%, hold 80%, fade-out 100% over 4s
- Dark mode support for both badge variants and toast
- Reset clears both states on Back click

## Learning Progress Tracking (cdd07a3, 8207d18 — Feb 11, 2026)
localStorage-based learning progress system for ~380 page learning platform.

### Architecture
- `src/config/preferences.ts` (NEW) — Central preferences module (separate from `jupyter.ts`). All localStorage getter/setters for visited pages, executed pages, last page, binder hint, progress stats, clearing functions. SSR-safe (`typeof window === 'undefined'` guards). Keys: `dq-visited-pages`, `dq-executed-pages`, `dq-last-page`, `dq-binder-hint-dismissed`.
- `src/clientModules/pageTracker.ts` (NEW) — Docusaurus client module registered in `docusaurus.config.ts`. Calls `markPageVisited()` + `setLastPage()` on every route change via `onRouteDidUpdate`. Dispatches custom `dq:page-visited` event for sidebar reactivity.

### Sidebar indicators
- `src/theme/DocSidebarItem/Link/index.tsx` (NEW swizzle) — Wraps original Link component. Shows clickable `<button>` with ✓ (visited) or ▶ (executed). Click calls `unmarkPageVisited()` to clear single page. Listens to `PAGE_VISITED_EVENT` for live updates.
- `src/theme/DocSidebarItem/Category/index.tsx` (NEW swizzle) — Wraps original Category. Shows aggregate "3/10" pill badge (visited/total leaf pages). `collectHrefs()` recursively walks sidebar item tree. `commonPrefix()` finds shared path prefix for batch clearing. Click calls `clearVisitedByPrefix()` + `clearExecutedByPrefix()`.

### Homepage resume card
- `src/components/ResumeCard/index.tsx` (NEW) — Reads `getLastPage()` from preferences. Shows "Continue where you left off" card with page title + relative time (e.g. "2 hours ago"). Renders nothing on first visit. Registered in `MDXComponents.tsx`, placed in `docs/index.mdx` below "Getting started".

### Execution tracking
- `src/components/ExecutableCode/index.tsx` (MODIFIED) — Added `markPageExecuted(window.location.pathname)` in `handleRun`. Migrated Binder hint from direct localStorage to `isBinderHintDismissed()`/`dismissBinderHint()` from preferences module.

### Settings page
- `src/pages/jupyter-settings.tsx` (MODIFIED) — Added "Learning Progress" section with `getProgressStats()` (total visited, notebooks executed, breakdown by tutorials/guides/courses/modules). Clear buttons: per category, clear all progress, clear all preferences.

### CSS
- `src/css/custom.css` (MODIFIED) — Styles for `.dq-sidebar-link`, `.dq-sidebar-indicator` (green visited, blue executed, positioned absolute right), `.dq-category-badge` (pill-shaped), `.dq-resume-card` (flexbox with icon/text/time), `.dq-progress-stats`, `.dq-clear-buttons`. Mobile responsive.

### Bugs fixed during implementation
1. **CSS selector bug**: Used `>` (direct child) for `.menu__link` but it's a grandchild. Fixed to descendant selector.
2. **Stale sidebar state**: Sidebar items persist across client-side navigation — only checked localStorage on mount. Fixed with `PAGE_VISITED_EVENT` custom event dispatched by pageTracker, listened to in both sidebar components.
3. **Unclickable pseudo-element**: Initial `::after` CSS approach couldn't have click handlers. Replaced with real `<button>` elements.
4. **Cascade clearing**: Clearing a category or single page didn't notify parent/child sidebar components. Fixed by dispatching `PAGE_VISITED_EVENT` after clearing in both `handleClear` (Category) and `handleUnmark` (Link).

## Pip install injection (ea0a6d6 — Feb 11, 2026)
On `ModuleNotFoundError`, error hint now includes a clickable "Install {pkg}" button instead of static text.
- `activeKernel` module-level variable stores kernel ref from bootstrap callback, cleared on reset
- `showErrorHint()` enhanced: module errors build DOM manually with `<button class="thebelab-cell__install-btn">`
- When kernel unavailable or dead, falls back to static text hint (same as before)
- `handlePipInstall(cell, pkg, btn)`: disables button → "Installing..." (amber) → `!pip install -q {pkg}` via `executeOnKernel()` → "Installed ✓" (green) → auto-re-runs cell after 500ms by clicking thebelab's run button → "Install failed" (red) on error
- CSS: `.thebelab-cell__install-btn` with `--installing`, `--done`, `--failed` state variants using `--ifm-color-*` variables

## Navbar polish (cdd07a3 — Feb 11, 2026)
- Settings label: navbar link renamed from "⚙️ Jupyter" to "⚙ Settings" (matches sidebar + page purpose)
- GitHub icon: text "GitHub" replaced with octocat SVG via `header-github-link` CSS class + `::before` pseudo-element
  - `#c6c6c6` default, `#ffffff` on hover — always visible on dark navbar
  - `aria-label="GitHub repository"` for accessibility
- Dark mode toggle fix: was black-on-black (navbar always `#161616`). Fixed with `.navbar [class*='colorModeToggle'] button { color: #c6c6c6 }`
- Navbar link nowrap: `white-space: nowrap` on `.navbar__link` prevents "API Reference" wrapping to two lines at medium widths

## Features page + Simulator discoverability (Feb 11, 2026)

### Features page (`/features`)
- `src/pages/features.tsx` — standalone React page (same pattern as `jupyter-settings.tsx`)
- 22 feature cards across 5 sections: Content Library (3), Live Code Execution (6), IBM Quantum Integration (4), Learning & Progress (3), Search/UI/Deployment (6)
- Each card: title + description + optional link. `FeatureCard` component local to the file.
- Responsive CSS grid: `auto-fill, minmax(260px, 1fr)` — 3 cols desktop, 2 tablet, 1 mobile
- Linked from homepage ("See all features" in "What this project adds") and footer (first item in RasQberry column)
- Not in navbar (already crowded with 8 items)

### Simulator discoverability (website review #16)
- Homepage "Code execution" section restructured: Simulator Mode now listed first (was second/buried)
  - "Simulator Mode (no account needed)" with concrete detail: AerSimulator + 8 FakeBackends, "Zero setup required"
  - IBM Quantum Hardware listed second
- Simulator callout card added in "Getting started" section between intro text and tutorial cards
  - "No IBM Quantum account? Enable Simulator Mode in Settings to run all code without signing up."
  - CSS: `.simulator-callout` — left-border accent, subtle background, dark mode variant

### Dead code cleanup
- Removed `getNotebookUrl()` from `src/config/jupyter.ts` — exported but never imported anywhere (confirmed via grep)
- Updated PROJECT_HANDOFF.md to remove the reference

## Settings page rename (185cd65)
- `src/pages/jupyter-settings.tsx`: page title/h1 changed from "Jupyter Settings" to "doQumentation Settings"
- Reflects broader scope: IBM credentials + simulator + display preferences + learning progress + bookmarks + onboarding + sidebar + recent pages
- Navbar link was already renamed to "⚙ Settings" in cdd07a3; this aligns the page content

## Website review round 4 — deferred fixes (Feb 11, 2026)
Six medium/low-severity issues from the 41-issue review. All verified with successful build.

### #15: thebelab button overflow (CSS)
- `@media (max-width: 640px)` shrinks `.thebelab-button` font/padding to prevent overflow on narrow screens

### #19: copy button visibility (CSS)
- `button[class*='copyButton']` always visible at `opacity: 0.7` (not just hover), with background for contrast
- Only affects non-Python blocks (Python blocks use ExecutableCode which has no copy button)

### #24: mobile sidebar tap targets (CSS)
- `.menu__link` gets `min-height: 44px` + flex alignment at `max-width: 996px` (WCAG minimum)
- Top-level collapsible categories get `font-weight: 600` for visual hierarchy

### #28: contextual alt text
- **sync-content.py**: `_infer_alt_text(source)` inspects cell code for `.draw(`/`circuit`/`plot(`/`hist(`/`imshow(` patterns → returns "Quantum circuit diagram", "Plot output", "Image output", or "Code output" instead of generic "output"
- **ExecutableCode/index.tsx**: `settleCellFeedback()` post-processes live thebelab `<img>` elements with empty/generic alt text → sets "Code execution output"

### #37: heading hierarchy (sync-content.py)
- `re.sub(r'^#{4,}\s+(Check your understanding)', r'### \1', ..., re.MULTILINE)` in `transform_mdx()` — converts H4+ "Check your understanding" sections to H3
- Safe targeted fix — this heading is always a section-level heading under H2

## Translation POC — German + Japanese + Ukrainian (Feb 12-13, 2026)
15-page content translation in 3 languages using Claude Code (Sonnet) as translator.

### Config changes
- `docusaurus.config.ts`: `localeConfigs` for en/de/ja/uk, `localeDropdown` navbar item, `language: ['en', 'de', 'ja']` in search plugin (no `uk` — `lunr-languages` lacks module). Currently disabled (`locales: ['en']`).
- `sidebars.ts`: `collectCategoryLabels()` + `deduplicateLabels()` for i18n sidebar key collision fix
- `.gitignore`: `translation-batches/` + `i18n/*/docusaurus-plugin-content-docs/` (generated fallbacks)

### Translation script (`scripts/translate-content.py`)
- **extract**: Reads MDX files from a page list, parses into segments (translate vs preserve), writes batch JSON
- **reassemble**: Reads translated batch JSON, writes MDX to `i18n/{locale}/...`
- **populate-locale**: Copies all `docs/*.mdx` to locale dir with "untranslated" banner + hidden fallback marker. Genuine translations (no marker) never overwritten. Idempotent.
- **Preservation rules**: Code fences, JSX comments, JSX self-closing tags, import statements, math display blocks marked "preserve"
- **Frontmatter**: title, description, sidebar_label translated; all other keys preserved

### Translation process
- 3 parallel Claude Code Task agents (Sonnet) per language, ~5 files each
- Agents read source MDX, write translated MDX directly to `i18n/{locale}/` directory
- All 45 files verified (15 DE + 15 JA + 15 UK): native prose, code blocks untouched, math/JSX preserved

### Fallback system
- `populate-locale --locale de` fills ~372 untranslated pages with English content + banner
- Marker: `{/* doqumentation-untranslated-fallback */}` distinguishes fallbacks from real translations
- Banners: `:::note[Noch nicht übersetzt]` (DE), `:::note[未翻訳]` (JA), `:::note[Ще не перекладено]` (UK)
- Build output: 961 MB (3 locales), 1.3 GB (4 locales). Needs `--max-old-space-size=12288`.

### Pages translated (same 15 for DE, JA, and UK)
Homepage, 4 tutorials (hello-world, chsh-inequality, grovers-algorithm, repetition-codes), 5 guides (install-qiskit, hello-world, bit-ordering, construct-circuits, visualize-circuits), 3 course pages (basics-of-quantum-information: index, single-systems/quantum-information, multiple-systems/quantum-information), 2 module pages (computer-science: index, grovers)

### #41: syntax highlighting
- **docusaurus.config.ts**: Added `shell-session`, `yaml`, `toml`, `diff`, `markup` to Prism `additionalLanguages`
- **sync-content.py**: `_tag_untagged_code_blocks()` heuristic — detects `$`/`%` → bash, `import`/`from`/`def`/`class`/`print(` → python, `{` → json, `pip`/`pip3` → bash. Called at end of `transform_mdx()`. Leaves unrecognized blocks unchanged.
