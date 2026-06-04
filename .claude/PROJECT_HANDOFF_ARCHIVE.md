# doQumentation — Project Handoff Archive

Historical detail moved out of `PROJECT_HANDOFF.md` to keep the active doc small. Items here are all completed; cross-link from the live doc where the detail still matters.

---

## Resolved — June 2026

### Repo file review + cleanup (Jun 4)
Full review of all project-authored files (excluding upstream content + translations). The code (`src/`, 19 workflows, 2 plugins, translation pipeline) was clean — **zero dead code**. Cleanup applied:
- **Removed orphaned `Dockerfile.web`** — built by no workflow; the `docker-compose.yml` `web` profile (`build: .`) was broken (no root `Dockerfile`). Dropped the `web` service; `jupyter-local` already serves the static site. README/handoff refs fixed.
- **Deleted one-shot migration scripts** (`scripts/migrate_output_imgs.py`, `translation/scripts/backfill-en-base-date.py`) — jobs done, results permanent; in git history.
- **Removed deprecated `translation/drafts/` scaffolding** — 22 empty `.gitkeep` dirs + stale per-locale `_feedback.md`/`_batches.json`/`_remaining.json` validation snapshots + an orphan `pl` draft mdx. The drafts→promote flow is retired (current pipeline edits `i18n/` directly).
- **Deleted point-in-time review reports** (de/fr/it linguistic reviews, `.claude/PHASE_4_LINGUISTIC_TRIAGE_2026-05-07.md`, `.claude/NOTEBOOK_SWEEP_PLAN.md`) — verdicts live in `status.json`; sweep findings in `notebook-sweep-report.md`.
- **Slimmed `PROJECT_HANDOFF.md` 87 KB → 67 KB** — moved the Recently-Resolved narrative into this archive (June + May sections above/below).
- **Deleted `.claude/PROJECT_REVIEW.md`** — the March code-review snapshot; its security items are in `SECURITY_REVIEW_2026-05.md` (S1/S3/S4/S6/S8), SET-2 in `AI_FEATURES_BRAINSTORMING.md` UX-3. The CI-1/CI-2 "FIXED" discrepancy was already reconciled in the tracker (→ S6, still OPEN).
- **Skipped** a proposed translation-prompt "Language Table" merge — the 4 prompts are purpose-built variants (terse table / verb-conjugation find-replace / review flags / tier-3 subset hard-coded in `review-build-batches.py`), not duplication; merging would lose content. `translation-prompt-web.md` kept (web `Write` limit still bites).
- Plan + full findings: `.claude/CLEANUP_PLAN.md` (kept as the record).

### Full upstream sync `47abf7714` + all-17-locale retranslation + pipeline hardening + repo cleanup (Jun 2–4, PRs #189–#213, all merged)
One continuous session, start to finish:
- **Repo declutter (#189, #190)** — moved generated `sidebar-*.json` from the repo root into gitignored `.generated/` (`sidebars.ts` requires from there with a try/catch fallback); ignored local-only `.claude` security/migration docs; deleted ~170 MB of stale gitignored root artifacts (25 old locale-build dirs + `.sweep-out`). The cleanup exposed and fixed a stale `sidebar-*.json` glob in `sync-upstream.yml`'s `add-paths` (#190) that would have failed the sync workflow's PR-creation step.
- **Upstream content sync (#191)** — first successful real `sync-upstream.yml` run (`833ab77dc → 47abf7714`), reviewed (the 3 `qiskit-code-assistant-*` deletions were verified as genuine upstream removals, not a sync bug) and merged. EN ended 0 pages behind.
- **Baseline-ref fix (#192)** — `update-translations.py` over-escalated ~10 files/locale to whole-file retranslation because `PRE_SYNC_REF` was hard-pinned to the *first-ever* sync (`9f2948310^`), so a 4-line change diffed against months-old EN. Added a `DQ_PRE_SYNC_REF` env override → point it at the current sync's parent → every file stays a tight splice. Verified safe via source-hash match. **This is the single biggest efficiency fix** — turned ~180 wasteful whole-file jobs into hunk-splices.
- **17-locale refresh (#193–#210)** — refreshed every main locale (~34 files each, ~595 total) to 0-stale via Workflow fan-outs of Sonnet Read/Edit splice agents, one PR per locale. `classical-feedforward-and-control-flow.mdx` needed a code-fence-parity rework in 12/17 locales (the new "Store" subsection). Three runs hit a structured-output throttle and silently no-op'd files (id, pl, uk) — **caught by a `git diff main` substantive-change guard, not the agents' own "done" report.** A small NOOP-hash-bump PR (#209) cleaned up the 6 early locales whose `hello-world` code-indent NOOP predated the per-locale auto-fix step.
- **Pipeline hardening (#211)** — folded every lesson back into the pipeline: a **RECONCILE guard** in `--finalize` (re-scans freshness, exits nonzero if any intended file is still stale — converts the silent-no-op failure into a hard stop); the added-fenced-code-block rule + `DQ_PRE_SYNC_REF` doc + macOS homebrew-git note in `retranslation-prompt.md`; a ~12-agent concurrency cap; and workfiles moved off `/tmp` (reaped mid-run) to `translation/workfiles/`.
- **Review-staleness fix (#213)** — a refreshed file's bumped source-hash was masking its now-stale linguistic-review verdict, so `review-translations.py` kept counting it reviewed. `--finalize` now downgrades a re-stamped file's verdict to `STALE_REFRESH` (re-queued by `--next-chunk`, no longer counted by `--progress`); retroactively applied to the 595 refreshed files → dashboard honestly reads `393/428 reviewed`. Future refreshes self-flag automatically.
- **GSC link (#212)** — added the Google Search Console property (`sc-domain:doqumentation.org`, DNS-verified) to the `/admin` Analytics section.
- Lessons in memory: `feedback_refresh_must_cover_full_stale_set`, `project_sync47abf_retranslation_run` (full resume recipe), plus the #192/#211/#213 behaviors.

---

## Resolved — May 2026

- **Cleared the entire main-locale structural-FAIL + build-fatal backlog (9 PRs #171–#180) + two validator/tooling upgrades** (May 30–31). Closed out the deferred #159 weak-5 rework *by locale* and swept the rest of the corpus. **Polish PRs #171–#177** took every main locale to **0 structural FAILs** (428 PASS each): #171 fr/ms/ar (16 files, incl. the 5 reverted re-translations + whole-file fr `runtime-options-overview` & ar `computer-science/vqe` — the latter via a 4-chunk splice, the file being too large for a single agent Write to land), #172 ko (8), #173 pl (12), #174 ja (13), #175 pt (14, incl. the same vqe `26→2 $$` chunked re-translation), #176 ro (1), #177 it (40 — 11 whole-file re-translations + 29 mechanical). Method: classify each FAIL as **drift** (whole-file re-translate) vs **mechanical** (surgical: links, anchors, `.avif↔.svg`, heading levels, Admonition counts, stray/missing fences); fan out ≤5 parallel Sonnet agents per wave; **one locale = one PR**. **Lint gate was load-bearing** — validator-PASS alone shipped a build-fatal duplicate `</Accordion>` in pt vqe (caught only by a separate `lint-translation.py` run) and ~17 untranslated-English TabItem bodies in pl `qpu-information`; every changed file was lint-checked for JSX imbalance + verbatim-EN. **Tooling PR #178**: (1) folded the build-fatal **JSX-tag-balance** check INTO `validate-translation.py` (`check_jsx_tag_balance` — `count_jsx_tags` only counted *opening* tags vs EN, so it was blind to an orphan/duplicate *closer*; 0 false positives across clean locales, catches the dup-closer that previously passed); (2) added `update-translations.py --audit-cross-locale` (read-only; validates every locale, groups FAILing EN files by how many locales fail them, shared-drift first) — its first run surfaced that the **9 German dialects** (aut/bad/bar/bln/gsw/ksh/nds/sax/swg) carry 16–28 structural FAILs + ~387 misplaced-import build-fatal files each, almost all the SAME shared-drift files. **Dialects intentionally NOT fixed** (user decision 2026-05-31). **Build-fatal sweep PR #179**: `lint-translation.py` ERROR sweep of all main locales found genuine build-breakers independent of the polish work — misplaced `TutorialFeedback` import *inside a code fence* in ar(1)/id(4)/pl(1) tutorials (relocated via the idempotent `fix-tutorialfeedback-import.py`) + ar `quantum-machine-learning/data-encoding.mdx` had a spurious duplicate `import qiskit/get_version_info()` block leaving the final fence unterminated (removed dup + closed → 26 blocks == EN). ar + id now 0 build-fatal. **Latent-bug PR #180**: pt `workshop/04_Hands-on…:253` had a stray `"/>` after a self-closing `<img/>` → odd double-quote count → build-fatal (pt-only; stripped to match EN); and `fix-heading-anchors.py` math-heading corruption root-caused & fixed — `extract_headings_with_positions()` didn't track `$$` display-math fences (a `#`-LaTeX line inside `$$` was miscounted as a heading), and on any EN/TR heading-count mismatch the function *fell through* to a misaligned `zip` that appended `{#anchor}` onto the wrong line (historically inside `$...$` math); now skips `$$` blocks AND aborts (writes nothing) on count mismatch. **Note on each-locale-builds-independently**: per-locale `deploy-locales.yml` matrix + satellite repos + deploy only with a `DEPLOY_KEY`, so a build-fatal error in locale X breaks only X's deploy, not the main site. Memory: `feedback_polish_backlog_workflow` (canonical workflow + the dialect-backlog note + the lint-gate lesson).
- **Landed the parallel dev branch + 5 build-fatal-JSX fixes + page-dates shallow-clone fix** (May 26, PRs #158–#164, all merged to main, deploy 27/27 green). The 247-commit parallel branch `claude/retranslation-status-instructions-VaqMP` (the ms/id/th + falsely-fresh work in the entry below) was assessed in an isolated worktree — **0 MDX-fatal across all 17 locales**, strong-12 ~90%+ structural pass, weak-5 (ko/pl/cs/ro/th) ~107 FAIL each — and split: **#158** (12 strong locales, ~3,123 files + the dev's pipeline improvements: ESM-fence-aware import auto-fix + the `--audit` *prompt text*), **#161** (the 872 validation-clean weak-5 files → 5 new locales partially live, 0 broken pages), **#159** held (the 275 genuinely-defective weak-5 files — real Link/JSX/heading defects — marked DO-NOT-MERGE, superseded by #171–#177). **#160** then *implemented* the `--audit` flag the prompt documented but never shipped (falsely-fresh detector). **Build-fatal JSX class found post-deploy** — passes `validate-translation.py` but aborts `docusaurus build`: orphan `</content>` (ar/pt/cs QAOA) + a `</details>` closing an `<Accordion>` left by a details→Accordion migration (pt qiskit-addons-sqd-get-started, id vqe). Fixed in **#162**/**#163** (5 files) + new `check_jsx_tag_balance` lint wired into the `--finalize` MDX-fatal gate. The `--finalize` MDX-fatal gate now covers all three build-fatal-but-validator-invisible classes: import-isolation (#108), acorn-invalid bare import (#151), JSX tag-balance (#163). Memory: `feedback_mdx_build_fatal_classes`. **Page-dates footer wrong dates** (user-reported: ansatz showed the sync date on both footer lines instead of its real 2026-02-09): root cause = `deploy.yml`'s full `sync-content.py` re-clones upstream `git clone --depth 1` (shallow), so `write_page_dates_manifest()` collapsed *every* file's `upstream_date`+`en_date` to the tip commit's date and OVERWROTE the correct committed manifest at build time. Fixed in **#164**: `write_page_dates_manifest()` now detects a shallow clone and PRESERVES the committed manifest — the full-history `refresh-page-dates.yml` job remains the sole accurate producer. Memory: `project_page_dates_shallow_clone`. **Also:** rewrote `CONTRIBUTING-TRANSLATIONS.md` for the current git-diff pipeline + added a maintainer onboarding section; recorded `feedback_staging_loop_nul_delimited`.
- **Full STALE retranslation of ms/id/th + cleared the falsely-fresh MAJOR backlog across all 13 main locales** (May 26, branch `claude/retranslation-status-instructions-VaqMP`) — continued the git-diff pipeline (auto-fix → workfile → Sonnet sub-agent hunk-splice in waves of ≤10, later throttled to 5 → CLI-PASS hash-bump → commit continuously). Refreshed every hunk-splice stale file for **ms** (~205), **id** (204), and **th** (205). **Key discovery (user-flagged): falsely-fresh MAJOR files.** `check-translation-freshness` is hash-based, so a deferred MAJOR file whose `{/* doqumentation-source-hash */}` had been bumped to the current EN hash *without* a real translation reported FRESH forever while its content was a stale, much-longer old version that FAILS `validate-translation`. A validation matrix (3 MAJOR files × 13 locales) found `estimator-rest-api.mdx` broken in de/ja/ar/he/ms/id/th and `tutorials/quantum-approximate-optimization-algorithm.mdx` broken in 12 locales — both invisible to the stale report. **`retranslation-prompt.md` updated** with three durable rules: (1) NEVER hash-bump a deferred/MAJOR file; (2) add a `--audit` mode that validates every file whose hash already matches EN; (3) codify the orchestrator-side mechanical auto-fixes into `--auto-fix`.
- **Retranslation auto-fix pass + two pipeline bugfixes** (May 23, branch `claude/retranslation-status-instructions-VaqMP`) — ran `update-translations.py --auto-fix` for the 10 main locales after root-causing why every stale file was misclassified `MAJOR`. **Two issues fixed:** (1) **Shallow-clone baseline gotcha** — the pipeline diffs each file against `PRE_SYNC_REF` (`9f2948310^`); a shallow clone doesn't contain that commit, so `old_en_content()` returned `None` → 100% `MAJOR`. Fix: `git fetch --depth=2 origin 9f29483105b21a91d0b3abf0ba9cfd735a084b9b`. (2) **Auto-fix import-sync corrupted code fences** (`update-translations.py:794`) — the old `^import\s+.+$` match conflated MDX imports with **Python** imports inside ` ```python ` fences. Fixed to be ESM-only and code-fence-aware. **Result:** 1,221 `.mdx` auto-fixed; ~1,090 NOOP files hash-bumped fresh.
- **Hello World refresh + AccordionItem stub bugfix** (May 21) — `local-content/hello-world.ipynb` rewritten: dropped all stale fork URLs, inlined the 5-step IBM Quantum account setup, modernized `save_account()`, and rewrote "What next?" to point at `doqumentation.org` entry routes. **AccordionItem bug**: the stub in `src/theme/MDXComponents.tsx` was passing the `title` prop straight to `<summary>`, so upstream inline markdown/HTML rendered literally — 99 broken accordion summaries across 15 pages. Fixed via `renderAccordionTitle()`. Memory note `feedback_jsx_stub_prop_parsing`.
- **Notebook execution sweep** (May 17) — executed all 261 EN notebooks cell-by-cell in the real production image `ghcr.io/qubins/images:2.3-xl`, simulator/fake only. **Result: ~166 clean, ~26 cloud-only-by-design, ~66 broken for real users.** Systemic causes: **F1** graphviz binaries missing (~14 nb); **F2** `qiskit-ibm-transpiler` missing (~5 nb, local mode also needs `qiskit-ibm-ai-local-transpiler`); **F4** ~13 nb import absent packages; plus ~10 genuine upstream bugs. Punch list + action order in **`notebook-sweep-report.md`** (repo root). Reusable harness in **`scripts/notebook-sweep/`**; re-run `python3 scripts/notebook-sweep/sweep.py`. Methodology in `notebook-sweep-report.md` + `scripts/notebook-sweep/README.md` (the dated `.claude/NOTEBOOK_SWEEP_PLAN.md` was deleted 2026-06-04 — durable findings live in the report). Memory `project_notebook_sweep`.
- **`.claude/` working-doc cleanup + consolidation** (May 17) — pruned 11 dead/redundant docs, consolidated AI ideation and security tracking. **`AI_FEATURES_BRAINSTORMING.md`** is now the single canonical AI-ideation doc. **`.claude/SECURITY_REVIEW_2026-05.md`** is the single code-verified security tracker (13 findings S1–S13, local-only/untracked) with `BOB_SECURITY_REVIEW_DEEP_DIVE.md` + `BOB_SECURITY_INFRASTRUCTURE_2026-05.md` as untracked appendices. PROJECT_REVIEW.md's 4 security items migrated into the tracker. **Verified discrepancy**: PROJECT_REVIEW marked CI-1/CI-2 FIXED but they are actually still OPEN (0/47 GH-Actions SHA-pinned, `trivy-action@master`) — now tracked as S6. Memory updated (`feedback_deletion_safety`, `project_security_findings_tracker`).
- **Upstream submodule: fork → Qiskit/documentation direct** (May 15) — `.gitmodules` now tracks `Qiskit/documentation` directly. Sparse-clone fallback in `sync-content.py` flipped too. Adds `.github/workflows/sync-upstream.yml` (workflow_dispatch only; weekly cron commented out) that fetches upstream, advances the submodule, runs `sync-content.py`, gates on `npm run build`, and opens an auto-PR.
- **QuBins org migration** (May 15) — QuBins moved to its own org: now [QuBins/qiskit-images](https://github.com/QuBins/qiskit-images), GHCR package `ghcr.io/qubins/images:{version}-{small,xl}` (NOT `.../qiskit`). Updated `src/config/jupyter.ts` `binderUrl`, `admin.tsx` links, and `binder-warmup.yml` cron URLs.
- **Binder cold-build broken + image split** (May 14) — resolved by switching Binder to QuBins. doQumentation points `binderUrl` at `mybinder.org/v2/gh/QuBins/qiskit-images/2.3-xl`; **nbgitpuller pulls notebooks** at session-launch from the `notebooks` branch. Eliminates doQumentation's image-publishing pipeline entirely. **Bump in lockstep when the Qiskit pin moves.**
- **"Use a quantum computer today" course** (May 7) — new IBM course added via `local-content/` overlay. Sidebar 13→14 courses; 102 i18n files.
- **Index "When you're ready for more" — all 26 locales** (May 5, PRs #12 + #14) — homepage section translated to 17 standard + 9 dialect locales.
- **Archive-branch merge `claude/translation-status-review-nal3k`** (May 5, PRs #5–#10) — 6-step staged merge of 662-commit archive, 699 files. KO + PL now 100%. Tags preserve full history.
- **Translation Phase 4 cheap fixes** (May 8) — 619 replacements / 289 files. Honorifics/formal-register cleanup across JA, UK, TL, DE, FR, PT, AR. (Detail was in `.claude/PHASE_4_LINGUISTIC_TRIAGE_2026-05-07.md`, deleted 2026-06-04 — in git history.)
- **HE Phase 2 review** (May 8) — 100% reviewed via Sonnet 5-file chunks. 1,448 register/terminology slips fixed + 26 surgical accuracy fixes. HE structural now 412/0.
- **KO Phase 3 — 100% reviewed** (May 8) — 414/414. Site-wide deferential-honorific cleanup. 383 PASS / 22 MINOR / 5 FAIL (intentional fallback).
- **TH/PL/CS Phase 3 stratified samples** (May 8) — ~45 files each, 4-wave parallel Sonnet. All three: zero polite/formal-register slips.

#### Items also resolved (one-liners)
- ✅ **Download notebook option** — "Download ↓" button on `OpenInLabBanner`. Links to `/notebooks/{path}.ipynb`. Analytics event `Notebook Download`.
- ✅ **Remove Qamposer** (Apr 24) — deleted `/qamposer` page, `QamposerEmbed/` dir, `@qamposer/react` dep, 11 `qamposer.*` i18n keys × 18 locales.
- ✅ **Workshop mode — single-pod stress testing** (Apr 11–12) — 1/4/8/12 vCPU validated. 8 vCPU/16 GB → 80 users, 0 failures at 5s burst. `scripts/workshop-stress-test.py`. Fixes: nginx rate limit 5→100/m, kernel cull 600→300s, cgroup-aware `/stats`, SSE shim async refactor, Jupyter race retries. **Known Jupyter Server 2.16.0 bugs**: `connections_dict` underflow → kernel cull broken → memory creep (workaround: restart pods between workshops). Full writeup: `memory/project_workshop_mode.md`.
- ✅ **GH Actions automations using `IBM_CLOUD_API_KEY`** — smarter Deploy to Code Engine, Stress Test, Resize Pod, Workshop lifecycle (start/monitor/close).
- ✅ **Admin page** — password-protected via build-time SHA-256. `ADMIN_PASSWORD` secret hashed into `customFields.adminPasswordHash`.

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
- **Branch integration Phase 1 (A–E)** — cherry-picked ~40 non-CE improvements from `claude/ibm-cloud-serverless-concept-UP0PJ` (52 commits). Touched 7 files: storage.ts (cross-tab sync, dev-gated logging), preferences.ts (Array.isArray guards, LRU 2000, schema guards), jupyter.ts (12 fixes: URL/ws/RFC1918 validation, TTL/backend/mode validation, 15s AbortController, 20-min EventSource timeout, encodeURIComponent, escapeHtml/makeTabHtml, getColabUrl dedup), jupyter-settings.tsx (CRN validation), ExecutableCode/index.tsx (resetModuleState, isValidPackageName, 15 i18n keys, SPA cleanup, MutationObserver, BOOTSTRAP_MAX_RETRIES), custom.css (6 vars for badge/toast/conflict, ▶✓✗ icons, settings max-width 900px, focus-visible toggle), .dockerignore (*.key, *.pem). CE Phase 2 deferred. Refs: `.claude/PROJECT_REVIEW.md`, `.claude/AI_INTEGRATION_IDEAS.md` (the latter merged into `.claude/AI_FEATURES_BRAINSTORMING.md` and deleted 2026-05-17; original in git history).

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
