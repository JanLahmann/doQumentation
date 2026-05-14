# doQumentation — Project Handoff Archive

Historical detail moved out of `PROJECT_HANDOFF.md` to keep the active doc small. Items here are all completed; cross-link from the live doc where the detail still matters.

---

## Resolved — April 2026

### Branch integration (Apr 9)
Merged 4 `claude/*` branches into main:
- `claude/video-transcript-translations-P5nk1`: 374 VTT files completing all 17-locale translations for 22 IBM Video transcripts (55/55 videos fully translated).
- `claude/plan-ai-features-I1bzx`: cherry-picked — adds `.claude/AI_FEATURES_BRAINSTORMING.md` (~30 AI feature ideas tiered by cost).
- `claude/document-todos-ideas-UQz3F`: 8/9 commits — Qiskit Addons Phase 1 (7 submodules, sync-content.py extension, `sidebar-addons.json`), breadcrumbs enabled, CE status messages, `TutorialFeedback` widget, `TranslationFeedback` banner, "View in English" link, code-injection transparency (`/about/code-modifications` page). Conflict on 22 tutorial MDX bottom-chunks resolved with `--theirs` (regenerable via sync-content.py).
- `claude/add-qamposer-doqumentation-4IIR4`: merged then later removed (Apr 24).

### User Test Session Feedback — April 14, 2026
Live test, very positive overall. Resolved:
- Dark mode black text in thebelab — added CodeMirror 5 dark mode CSS in `custom.css`.
- "Reset Everything" button on Settings (clears all progress, bookmarks, prefs, onboarding, Binder, credentials).
- Settings findability — responsive navbar (text + gear ≥1200px, icon only narrow).
- Japanese nakaguro (・) rule documented in `translation-prompt.md`.
- `annotateInjectedCells()` — compact per-cell badges showing what doQ intercepts (QiskitRuntimeService → AerSimulator, etc.).
- IBM Quantum setup instructions rewritten: 4-step list matching current Platform UI (Register → Create instance → Copy CRN → Create API key).

Open from that session:
- API key error after copy-paste (`InvalidAccountError: Unable to retrieve instances`). Possible whitespace/newline. (Still open — tracked in main TODO.)
- Kernel session interrupted on navigation — inherent to thebelab; documented as known.

### User Test Session Feedback — April 17–18, 2026
12 items, all resolved:
1. Default API key TTL → 1 day (`DEFAULT_TTL_DAYS`).
2. Custom Jupyter Server merged into backend selector as a radio.
3. CE Quick Config always visible (with Clear button).
4. Renamed "Clear All Preferences" → "Clear Learning Data"; "Reset Everything" unchanged.
5. Removed duplicate "Compute Backend" section. Backend status banner always at top.
6. Backend selector always shows all options (CE/Custom included even when not configured).
7. Admin PodMonitor reads CE creds from Settings; visible note added.
8. "Binder Federation Status" section in admin (2i2c, BIDS, GESIS links).
9. CE setup instructions expanded (IBM Cloud console link, sizing, CORS_ORIGIN, admin sizing table link).
10. Run-button-not-appearing fix: `setupCellFeedback()` retries 3× at 2s for thebelab render lag.
11. "View original on IBM Quantum Platform" link in `EditThisPage` via `getOriginalPageUrl()` (guides → docs.quantum.ibm.com, tutorials → learning, courses → /course, addons → qiskit.github.io).
12. Hidden workshop notebooks dir (`docs/workshop/`) with `workshopSidebar`, `noindex` meta.

### Additional Changes — April 18, 2026
- CE sizing corrected to 1 vCPU / 2 GB for single user.
- "IBM Cloud Code Engine" official name used consistently.
- Backend selector order pinned: Binder → CE → Custom Server.
- "View original" → "View original on IBM Quantum Platform".
- Execution mode reordered (none → AerSimulator default → FakeBackend → IBM Quantum).
- Admin page kept undiscoverable (no link from Settings).
- CE + Custom Server consolidated to single URL/Token section with radio.
- Cell execution labels: ► Running… / ✓ Done / ✗ Error as visible `::before` text.
- "Manage Your Data" restructured: Progress / Bookmarks / Display & UI / Sessions & Credentials. Privacy note added.
- `annotatePlaceholderCells()` detects `YOUR_API_KEY`/`deleteThisAndPaste` and offers credential injection.
- SPA navigation: bootstrap polls up to 10 frames waiting for `<pre data-executable>`.
- Multi-line inline math fix in `escape_mdx_outside_code()` regex.
- UI translations 100%: 210 new keys × 17 non-dialect locales (308 → 518+ keys).
- Workshop notebooks: 6 notebooks (01–06 prefix), 2 solution notebooks, `unlisted: true` + hidden sidebar class. Source `.ipynb` tracked, generated MDX gitignored.

### Additional Changes — April 20, 2026
- Diff-based translation update tool: `translation/scripts/update-translations.py` (838 lines, 3-phase DETECT → AUTO-FIX → WORKFILE). Needs runtime testing.
- Workshop notebooks renumbered to `01_`–`06_`; two new IBM "Use a QC Today" notebooks at `01_`/`02_`.
- `process_workshops()` strips broken `/learning/images/courses/use-a-qc-today/...` refs (IBM proprietary build).
- `Accordion`/`AccordionItem` MDX stubs added; render as `<details>`/`<summary>`.
- Homepage "When you're ready for more" section pointing users to IBM Platform.
- `src/config/contentMeta.ts` generated by sync-content.py with `UPSTREAM_COMMIT` + date for Features page.
- Replaced concrete page/language counts with ballpark phrasing on Features page.
- `.dockerignore` notebook-branch experiment reverted (transient mybinder.org issue, not size).

---

## Resolved — Feb–Mar 2026

### Settings & UX
- **Backend selection UI** — radio buttons with `buildConfigFor()` helper + `doqumentation_backend_override` key. Auto-clears stale overrides; refreshes on save/delete.
- **Settings page reorg** — essentials top, advanced in `<details>`, hash deep-links auto-open. Simulator default ON. Onboarding simplified ("Click Run — no setup needed", 2 visits).
- **Run All** — page-level button. `waitForKernelIdle()` (debounced) + `waitForOutputStable()` (MutationObserver). Pause/Continue via promise gate. Aborts on Back/Restart/navigation.
- **Sidebar indicator redesign** — single unified indicator with 5 states (`✓` gray / `</>` gray non-clickable / `</>` blue / `</>` green). Category badges DOM-injected; `useLayoutEffect` survives re-renders from collapse-restore.
- **Info icons** — reusable `InfoIcon` component, CSS-only tooltips. Settings (5 fields), toolbar mode badge, 7 notebook-page locations.
- **Mobile side navigation** — fixed locked sidebar, invisible arrows, dark Back button.
- **Locale dropdown separator** — sibling combinator (`~`) instead of descendant; Docusaurus applies `className` to `<a>` not wrapper.
- **BetaNotice global** — moved to swizzled `Root.tsx`, removed per-locale `index.mdx` imports. Session-dismissible.

### Binder & CE
- **Binder enable** — full setup on `notebooks` branch. Shared session via `ensureBinderSession()`. Image ~3.5–4.5 GB (down from 7.6 GB conda).
- **Binder layer caching** — `binder/Dockerfile` with `FROM quay.io/jupyter/base-notebook:python-3.12` + pip install. Bypasses repo2docker conda solver.
- **Binder startup UX** — real-time phases in OpenInLabBanner / ExecutableCode / JupyterLab tab. Per-phase duration hints, cache-miss warnings.
- **Shared Binder session** — Lab + thebelab share one session; session in `sessionStorage`, 8 min idle. Fixed initial tab reuse via dropping `noopener`/`noreferrer` (was discarding named targets).
- **Skip redundant pip cells on Binder/CE** — `ExecutableCode` returns `null` for injected pip cells on Binder/CE; JupyterLab uses `importlib.util.find_spec` to skip when packages present.
- **Comprehensive prerequisites cell** — merged base+extras into single cell. Stdlib-only filter so all third-party imports appear (fixes 26 notebooks missing `qiskit-ibm-catalog`/`pyscf`/`ffsim`).
- **Open Plan Session compatibility** — `_DQ_JobModeSession` passthrough patches `qiskit_ibm_runtime.Session` for Open Plan users. Per-cell amber banner via `annotateSessionCells()`. Reactive fallback hint on "not authorized" error.
- **Trivy CVE fixes** — `urllib3>=2.6.3`, `apt-get upgrade gpgv`, `pip install --upgrade` for security pins, `.trivyignore` for unfixable bundled deps (mathjax/underscore/gpgv). `PyJWT>=2.12.0`, `pyasn1>=0.6.3` later. Pins moved to shared `jupyter-base` stage.
- **Audit "Open in" buttons** — removed redundant raw Binder button (Lab via Binder is better). Now consistently 2 buttons (JupyterLab + Colab) across all environments.
- **Test connection UX** — removed "Jupyter version: unknown"; retry 4→6 (~90s) for CE cold starts.
- **Thebelab bootstrap race fix** — first Run click didn't show per-cell run buttons. Deferred `bootstrapOnce()` to `requestAnimationFrame()`.
- **Error submission for contextual help** — "Report this error" link on all cell errors. Pre-filled GitHub issue with "Describe the issue" + auto-populated error/code/path/env. Generic hint for unmatched tracebacks.
- **Homepage Code execution section** — added IBM Code Engine to backends (3→4); deployment options table updated.

### Translations
- **Translation review + register fix** — all 456 structurally-passing files reviewed across 19 locales. 194 formal-register files fixed via targeted LLM rewrite. Full linguistic review for 9 major locales (3,477 files; zero FAILs): DE 387, IT 387, AR 385, ES 387, FR 387, UK 387, JA 388, PT 387, TL 387. Fixes: ES 2, FR 10 (Spanish files in FR dir), DE 8 (Sie→du).
- **DE/ES/FR/IT full review (Mar 28)** — merged 4 dedicated review branches. DE ~150 fixes / 84 files. ES accent + tú/usted / 110 files. FR gate→porte / 146 files. IT ~1,160 fixes / 207 files.
- **Translation register fix (194 files)** — DE 64, FR 36, ES 36, UK 18, IT 17, SWG 10, BAD 8, SAX 3, AUT 1. Helper: `translation/scripts/get-register-fails.py`. `FIXED` verdict added to `review-translations.py`.
- **DE tutorial fixes (18/18 PASS)** — 8 failing DE tutorials: 3 missing IBM survey links, 5 EN-comment restorations, 1 truncated output, 1 missing internal link, 2 paragraph misalignments. Locale-specific paragraph inflation threshold (`de: 3.0x`).
- **FR/ES/DE 100% completion** — squashed 963-file `continue-translations` branch. Fixed all 73 validation failures. Tuned validator (paragraph inflation MIN_TR_WORDS=250, LaTeX display ±4, inline ±30, short-file absolute tolerance).
- **Translation status dashboard** — `translation-status.py` with overview / `--locale` / `--backlog` / `--validate` / `--markdown`/`--json` / `--update-contributing`. `validate-translation.py --record` to status.json.
- **Translation draft pipeline** — `translation/drafts/` staging. validate → fix → promote. Scripts gained `--dir`/`--section`/`--file`/`--force`/`--keep`. Backward compatible (defaults to `i18n/`).
- **Translation validation improvements** — fixed 3 false-positive categories (code-block trailing whitespace, frontmatter title allowlist, dialect locales). Pass rate 53% → 63%. Fixed 130 missing heading anchors / 13 locales.
- **Translation build fixes** — KSH garbled `<bcp47:`, HE missing newlines (×2), SAX `tutorial`→`tutorials` image path.
- **Locale build MDX fixes (Mar 2026)** — 13+6 errors across DE/ES/FR/IT. Five categories: leading space before `{#anchor}` headings (kipu-optimization × 4 locales + IT quantum-circuit-optimization), duplicate dot-anchors (`{#name-1.0}` invalid JS private field) in 5 files, missing `<details></details>` in 4 files, German `"`(U+0022) inside `definition="..."` → `&quot;` (2 DE), `$$` indent mismatch in FR. IT-specific: missing `##` in `vqe.mdx`, truncated `</Admonition>` in addons-sqd. FR `qiskit-1.0-installation.mdx` was Spanish (mislabeled) — re-translated.
- **Full validation audit (Mar 2026)** — all 19 locales, 100% PASS on 2,180 promoted files. Fixed 4: DE/FR/ES `quantum-circuit-optimization.mdx` leading space; IT `vqe.mdx` spurious `## 6. Conclusione` removed; ES heading translated.
- **Translation structural sync (Mar 2026)** — `sync-translations.py`. Three fix functions: pip blocks, code blocks, survey URLs. 727 fixes / 587 files in one run / 19 locales. Validator tolerances tuned. 643 → 108 failures (83% reduction).
- **MDX lint script** — `lint-translation.py` for build-breaking errors validate misses (duplicate anchors, garbled XML, mid-line headings, invalid anchor chars, unmatched fences, missing imports). `--record` for status.json.
- **Translation review orchestration** — `review-translations.py`. `--auto-check` populates all 885 entries. `--progress` dashboard. `--next-chunk` prioritized batch. Baseline: 456 PASS struct, 877 CLEAN lint, 440 ready for review.
- **Translation freshness system** — `check-translation-freshness.py` with embedded `{/* doqumentation-source-hash: XXXX */}`. Daily CI workflow detects CRITICAL (missing components) and STALE (content changed).
- **Translation prompt improvements** — three orchestrator-issue fixes: explicit Source File Paths section (courses at `docs/learning/courses/`, modules at `docs/learning/modules/`); prescriptive chunking algorithm for >400-line files; discovery via `translation-status.py --backlog` + globs.
- **Three new locales: MS, ID, TH** — full infra (config, CI matrix, banner templates for ms/id, validators). Satellite repos with main+gh-pages, deploy keys, custom domains. UI string templates × 4 JSON each. 387 fallbacks per locale. Hidden from dropdown by default. **Build fix**: `th` removed from search `language` (lunr.th.js needs `wordcut.init()` not loaded by `@easyops-cn/docusaurus-search-local`). 12 UI JSON files for ms/id/th had bln German content — regenerated. `grovers.mdx` German content from stale build — re-ran sync.

### Build / infra
- **Consolidate Docker images** — single `Dockerfile.jupyter` with shared `jupyter-base` + two targets: `jupyter-local` + `jupyter-codeengine`.
- **Update Features page** — 22 → 31 cards / 6 sections. Added CE, Colab, Bookmarks, Recent Pages, Display Prefs, Multi-Language. Plus Run All & Restart, Onboarding, backend selection, Binder cancel.
- **Colab "Open in Colab" 403 fix** — Colab `/url/` blocks non-GitHub (SSRF allowlist). Switched to `/github/` scheme. EN: `doQumentation/blob/notebooks/` (force-pushed by `deploy.yml` `contents: write`). Translated: satellite `/blob/gh-pages/notebooks/`. Unified path map via `mapBinderNotebookPath()`. KSH build fix: removed duplicate apostrophe-anchor in transpilation tutorial.
- **Notebook MDX corruption in JupyterLab/Colab** — all 128 EN notebooks showed raw frontmatter + JSX comments as text. Fixed in `copy_notebook_with_rewrite()`: strip YAML frontmatter from first markdown cell + `clean_notebook_markdown()` on all markdown cells. Added `re.DOTALL` for multi-line JSX comments.
- **Hide "Open in:" banner on code-cell-free pages** — `sync-content.py` checks `has_code_cells`. 86 notebook-derived pages (conceptual lessons in Basics QI, Foundations QEC, etc.) + 7 guides no longer show banner. 1,634 i18n files cleaned up.
- **License detection + content submodule** — removed custom preamble from `LICENSE`/`LICENSE-DOCS` (Licensee needs clean templates). Dual-license explanation in `NOTICE`. Added `upstream-docs/` submodule for clear license boundary. CI workflows updated with `submodules: true`.
- **IBM Cloud spending limits** — no hard limits; set $5/month notification. Existing controls: max-scale=1, min-scale=0, rate limiting.
- **Branch integration Phase 1 (A–E)** — cherry-picked ~40 non-CE improvements from `claude/ibm-cloud-serverless-concept-UP0PJ` (52 commits). Touched 7 files: storage.ts (cross-tab sync, dev-gated logging), preferences.ts (Array.isArray guards, LRU 2000, schema guards), jupyter.ts (12 fixes: URL/ws/RFC1918 validation, TTL/backend/mode validation, 15s AbortController, 20-min EventSource timeout, encodeURIComponent, escapeHtml/makeTabHtml, getColabUrl dedup), jupyter-settings.tsx (CRN validation), ExecutableCode/index.tsx (resetModuleState, isValidPackageName, 15 i18n keys, SPA cleanup, MutationObserver, BOOTSTRAP_MAX_RETRIES), custom.css (6 vars for badge/toast/conflict, ▶✓✗ icons, settings max-width 900px, focus-visible toggle), .dockerignore (*.key, *.pem). CE Phase 2 deferred. Refs: `.claude/PROJECT_REVIEW.md`, `.claude/AI_INTEGRATION_IDEAS.md`.

### Upstream PRs
- **Upstream license detection PR** — same preamble issue exists in `Qiskit/documentation`. Filed [PR #4846](https://github.com/Qiskit/documentation/pull/4846).

### Testing
- 180+ comprehensive tests, ~200 Chrome browser tests — 99.5% pass, zero real bugs.
- Binder execution: 19/19 passed, 30–40s kernel connect, 45-min stable session.
- Test plans: `.claude/BINDER-EXECUTION-TEST-PLAN.md`, `.claude/test-checklist.md`.

---

## Qiskit Addons Phase 1 (shipped, hidden) — implementation detail

Phase 1 implemented and on `main`. Seven addon repos integrated as submodules in `upstream-addons/`; `sync-content.py` converts notebooks to MDX under `docs/qiskit-addons/`; `sidebar-addons.json` wired into `sidebars.ts`. Navbar entry intentionally hidden (`Hide Qiskit Addons from navbar and main sidebar`). Pages reachable via direct URL (`/qiskit-addons/...`) with `qiskitAddonsSidebar`.

**License**: All addon repos Apache 2.0. Notebook content under CC BY-SA 4.0 with attribution in NOTICE.

### Repos & Content Inventory (verified April 2026)

| Repo | Notebooks | Path | Content |
|------|-----------|------|---------|
| qiskit-addon-cutting | 4 | `docs/tutorials/` | Gate cutting, wire cutting, automatic cut finding |
| qiskit-addon-sqd | 2 | `docs/tutorials/` | Chemistry / fermionic lattice Hamiltonian |
| qiskit-addon-mthree | 5 | `tutorials/` | Measurement mitigation, QV, dynamic BV, VQE |
| qiskit-addon-obp | 1 | `docs/tutorials/` | Getting started with OBP |
| qiskit-addon-mpf | 1 | `docs/tutorials/` | Getting started with MPF |
| qiskit-addon-aqc-tensor | 1 | `docs/tutorials/` | Initial state AQC |
| qiskit-addon-opt-mapper | 5 | `docs/how_tos/` | Migration, problem definition, converters, validation, DOCPLEX |
| qiskit-addon-pna | 1 | `docs/tutorials/` | Noise-mitigating observable generation |
| qiskit-addon-slc | 1 | `docs/tutorials/` | Getting started with SLC |
| qiskit-addon-utils | 2 | `docs/how_tos/` | Circuit slices, device edge coloring |
| **Total** | **23** | | |

**Repos with no notebooks (skipped):** qiskit-addon-sqd-hpc (C++), qiskit-addon-dice-solver (API only), qiskit-fermions (RST only).

**Future Phase 3 — qiskit-community application modules:** ML (13), nature (11), optimization (12), finance (12), algorithms (11) ≈ 59 notebooks. Some no longer IBM-supported. Major future expansion.

### Implementation pattern (for Phase 2/3)
1. Add submodule under `upstream-addons/` (direct to Qiskit org repo).
2. `ADDON_SOURCES` map in `sync-content.py` — `{"submodule":..., "path":..., "pip":...}`. Output to `docs/qiskit-addons/<addon-name>/`. Existing `%pip install` injection handles deps.
3. Generate `sidebar-addons.json`, register in `sidebars.ts`.
4. Navbar entry in `docusaurus.config.ts` (currently hidden).
5. `NOTICE` attribution per repo.
6. Binder/Docker: keep heavy addons (e.g. `pyscf`) as `%pip install` cells, not pre-install.
7. CI: `submodules: recursive`.
8. `docs/qiskit-addons/index.mdx` with Card/CardGroup overview.

### Phases
- **Phase 1** ✅ — 7 addons, 11 notebooks (cutting, sqd, obp, mpf, aqc-tensor, pna, slc).
- **Phase 2** — mthree (5), opt-mapper (5), utils (2) = 12 more. Total 23 notebooks.
- **Phase 3** (future) — qiskit-community modules (~59 notebooks).
