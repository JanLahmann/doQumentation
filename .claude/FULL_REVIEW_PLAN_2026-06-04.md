# doQumentation — Full Review Plan + Execution Log (2026-06-04)

Two parts: **(A)** a structural map of how the project fits together, and **(B)** a
prioritized, domain-by-domain review plan. **All 8 domains were executed** — findings +
fixes are in the EXECUTION LOG section below each plan item. Dialects (9 German) are
out of scope throughout.

## ✅ FINAL SUMMARY — all 8 domains reviewed (2026-06-04)

**Verdict: the project is healthy.** Content/translation corpus is clean; the real
bugs were in the execution layer and CI. Every fix verified by `tsc` (now 0 errors) +
EN build (green).

**Fixes applied this session (all build-verified):**
- D1: (empty-link + build-OOM noted; dialect-driven warnings reclassified out-of-scope)
- D2: 5 Arabic mistranslations; shared `inlineMarkup` helper hardening 2 stub leak risks; search-lang doc
- D3: H1+H2 frontend async-teardown (EventSource + retry-timer leak on nav); F1 connect-storm (SSE
  stagger + nginx /build rate-limit); cancelBinderBuild hardening
- D5: InfoIcon a11y (focusable+aria); form labels; reduced-motion guard; live hide-outputs toggle;
  cookie byte-length chunking; category-badge over-clear (+ new unmarkPageExecuted)
- D6: S5 dependabot.yml; S6 SHA-pin trivy@master + claude@beta; N2 permissions blocks; 3 workflow bugs
  (check-translations empty-push, deploy notebooks-race rebase-retry, codeengine scan-before-push +
  concurrency)
- D7: fixed all 4 pre-existing tsc errors; added `ci.yml` (PR-time typecheck + build gate)

**Top items NOT fixed (logged for follow-up), by leverage:**
1. 🔴 connections_dict underflow (workshop memory creep) — needs Jupyter patch or restart automation
2. 🔴 Security S1/S3 (IBM token plaintext + cross-subdomain cookie; full token over SSE) — deferred per
   local-tracker policy; substantive
3. 🟡 Translation pure-function pytest harness (~60-80 tests) + extract drifted `check_jsx_tag_balance`
   to shared `_common.py` (7-script status duplication)
4. 🟡 D3 M-series (session host-mismatch reuse, unbounded pool failover); image-size `-lite` variant
5. 🟡 D6 residual workflow nits (workshop-monitor restart-count, ce-monitor fractional-vCPU,
   sync-upstream cron-offset before enabling its schedule); setup-pi.sh untested
6. 🟢 a11y nits (cell-status aria-live, badge nested-interactive); cross-subdomain cookie live-sync;
   LICENSES/ dir nice-to-have

**Companion docs:** `.claude/D3_LIVE_VERIFICATION_CHECKLIST.md` (17 runtime checks for the live site),
`.claude/SECURITY_REVIEW_2026-05.md` (updated tracker — S5/N2 fixed, S6 partial, S1/S3 escalated).

---

---

## PART A — Structural map: how the project fits together

doQumentation is a **Docusaurus 3.x static site** that re-hosts IBM's open-source Qiskit
documentation (tutorials, guides, courses, modules) with three things bolted on:
**live in-browser code execution**, a **20-locale translation pipeline**, and a
**workshop-scale execution backend** on IBM Code Engine. ~12,500 tracked files,
~380 EN content pages, 27 locales.

It decomposes into **five subsystems** plus the Docusaurus shell that ties them together.

### 0. The Docusaurus shell (the spine)
- `docusaurus.config.ts` — single source of truth for the 27-locale list, per-locale
  subdomain URLs, navbar/footer, SEO head tags (JSON-LD, robots, Umami analytics),
  thebelab + KaTeX CDN injection, search theme, and two custom plugins.
- `sidebars.ts` — loads 5 generated sidebar JSONs from `.generated/` and runs
  `deduplicateLabels()` to prevent i18n key collisions across tutorials/guides.
- `src/` — React/TS: theme swizzles, components, the execution layer, the preferences
  system, custom pages. `plugins/` — `page-dates` (per-page source dates via globalData)
  and `hreflang` (international SEO alternate links).
- **Build**: needs `NODE_OPTIONS=--max-old-space-size=8192`; `onBrokenLinks: 'warn'`,
  broken markdown images `warn` (deliberate — locale image refs go stale between passes).

### 1. Content-sync pipeline (`scripts/sync-content.py`, 3194 lines)
The ingestion engine. Pulls upstream and emits all the content the site builds from.
- **Sources**: `upstream-docs/` submodule (Qiskit/documentation) is primary;
  `local-content/` overlay (e.g. custom hello-world); `upstream-addons/` (7 addon
  submodules); `workshop-notebooks/`. **Upstream wins** on same-named conflicts.
- **Outputs**: `docs/` (MDX the site builds — tracked in git since 2026-05-07 so
  per-file `git log` dates work), `notebooks/` (copies for "Open in Lab"),
  `static/img/` + `static/docs/` (assets, gitignored), `.generated/*.json` (sidebars).
- **Transforms**: regex MDX rewrites (Admonition normalization, IBM component
  stripping, `<Table>`→`<table>`, image/link URL rewriting EN-local vs IBM-remote),
  brace-escaping for MDX safety, notebook→MDX conversion (parses ipynb JSON directly,
  extracts outputs incl. base64 PNGs → `static/img/.../output_N.png`, injects a
  `!pip install` prerequisites cell via import scanning), and `OpenInLabBanner` injection.
- **Sidebars**: each content type parses its `_toc.json` → sidebar JSON via
  `toc_children_to_sidebar()` (strips Lessons/Modules wrappers, skips overviews,
  drops missing files, flags notebook pages). `index.mdx` is preserved, never regenerated.
- **Dates**: `write_page_dates_manifest()` → `src/config/upstreamFileMeta.json`
  (upstream date/SHA + EN authored date per page); a shallow-clone guard prevents
  overwriting good dates with garbage.

### 2. Translation / i18n pipeline (`translation/scripts/`, ~19 scripts)
The largest and most intricate subsystem. Weekly git-diff-driven stale-refresh.
- **Flow**: `check-translation-freshness.py` (compares embedded
  `doqumentation-source-hash` vs SHA of current EN) → `update-translations.py --analyze`
  (recovers old EN from per-locale manifest's `old_en_commit` or `PRE_SYNC_REF`,
  diffs hunks, auto-fixes structural drift, emits a per-passage workfile) → **Sonnet
  agents** translate only changed passages (`retranslation-prompt.md`) → deterministic
  repair chain (heading anchors, code-block restoration, survey/notice/URL fixes,
  iterated to fixed point) → **validate** → **lint** → **hash-bump + promote** to
  `i18n/<locale>/docusaurus-plugin-content-docs/current/`.
- **Hash layers**: `en-passage-hashes.json` (single-writer snapshot of current EN
  prose units) and `baseline-hashes.json` / per-locale manifests (per-translation
  snapshot at promote time). Dual-consumer conflict was resolved by moving old-EN
  tracking into per-locale manifests.
- **Three gates**: `validate-translation.py` (structural parity — code byte-identical,
  frontmatter, LaTeX ±35, links, images, word/line inflation thresholds tuned per
  locale), `lint-translation.py` (MDX-fatal: dup anchors, unescaped quotes,
  foreign-script intrusion, untranslated-EN drift), `review-translations.py`
  (manual linguistic verdict; invalidated to STALE_REFRESH on re-stamp).
- **State**: `status.json` (central per-file status/validation/review/source_hash),
  `STATUS.md` (generated dashboard), `manifests/<locale>.json` (durable resumable state).
- **Coverage**: 17 main locales ~complete; 9 German dialects partial (low-prio).

### 3. Code execution layer (`src/config/jupyter.ts` 1173 L + `ExecutableCode` 2080 L)
How a ```python block becomes a live cell.
- **Two backends**, chosen by `detectJupyterConfig()` priority: Custom server >
  Code Engine (workshop) > **Binder** (public default) > Local/RasQberry; user can
  override. Public site uses **thebelab 0.4.0** → Binder (`QuBins/qiskit-images`
  prebuilt image); workshops use the CE pod.
- **Run path**: `CodeBlock` swizzle marks python blocks executable → `ExecutableCode`
  → `doBootstrap()` waits for the thebelab CDN → `thebelab.bootstrap()` connects a
  kernel (session reused across cells on a page; reused across tabs via
  `sessionStorage dq-binder-session`, 8-min idle). Kernel-connect **race retries**
  in three places (frontend, harness, SSE server). Static MDX outputs stay visible
  alongside live ones (Run/Back toggle).
- **"Open in JupyterLab"**: `openBinderLab()` opens a blank tab immediately
  (popup-blocker-safe), streams the Binder build via EventSource, then navigates;
  nbgitpuller clones for Binder, pre-baked paths for CE. Colab uses `/github/` scheme.

### 4. Workshop / scaling infra (`binder/` + 9 CE workflows)
The Code Engine execution backend for live workshops.
- **Image**: `Dockerfile.jupyter` / `binder/Dockerfile` → CE pod running supervisord:
  **nginx** (8080, rate-limits + reverse-proxy, keepalive=0 for Knative scale-to-zero)
  + **Jupyter** (8888, token auth, XSRF off for thebelab, 300s kernel cull) +
  **SSE build server** (9091, `binder/sse-build-server.py`, mimics mybinder `/build/`
  so the frontend needs no special-casing; async tornado; `_fetch_jupyter_with_retry`
  absorbs Jupyter races).
- **Lifecycle workflows**: `codeengine-image` (build/push), `workshop-start`
  (resize + warm + post instructions), `workshop-monitor` (poll `/stats`),
  `workshop-close` (final snapshot + optional downsize), `resize-pod`, `ce-monitor`
  (cost watchdog), `stress-test`. Sizing rule of thumb: 8 vCPU/16 GB ≈ 80 users.

### 5. Frontend / UX / preferences (`src/` React)
- **Preferences system** (`src/config/preferences.ts` + client modules): 15 localStorage
  keys driving learning progress (sidebar ✓/▶, badges, resume card), bookmarks, display
  prefs (code font size, hide static outputs), onboarding tips, recent pages, sidebar
  collapse — coordinated via custom DOM events because sidebar items persist across SPA nav.
- **Theme swizzles**: CodeBlock, DocItem/Footer (source dates), EditThisPage (bookmark
  toggle), DocSidebarItem (progress), Navbar mobile, LocaleDropdown, MDXComponents
  (stubs for IBM components — must parse markdown in IBM string props), Root.
- **Pages**: features, jupyter-settings, legal/Impressum, admin (password-gated,
  AES-encrypted Umami URL), workshop-setup.
- **Analytics**: Umami (cookieless); `outboundTracker` + `FeedbackWidget` /
  `TranslationFeedback` / `TutorialFeedback`.

### 6. Deploy / infra
- **`deploy.yml`** builds + deploys EN to GitHub Pages (custom domain doqumentation.org,
  IONOS DNS, `static/CNAME`). **`deploy-locales.yml`** is a 27-row matrix pushing each
  locale to its own satellite repo's gh-pages (SSH `DEPLOY_KEY`, wildcard CNAME →
  `*.doqumentation.org`); skips locales without a key.
- **Other workflows**: `sync-upstream` (auto-PR, currently manual-dispatch),
  `check-translations` (daily freshness), `notebook-ci` / `notebook-review`,
  `docker`, `sync-deps`, `refresh-page-dates`, `lint-image-paths`, `binder-warmup`.
- **Other deploy targets**: Docker (full offline, `Dockerfile.web` + `docker-compose`),
  Raspberry Pi (`scripts/setup-pi.sh`, untested on hardware).

### How the pieces connect (data-flow seams — the high-risk joints)
1. `sync-content.py` → `docs/` + `.generated/` + `upstreamFileMeta.json` → consumed by
   the Docusaurus build, `sidebars.ts`, and the `page-dates` plugin.
2. `sync-content.py` EN output → `update-en-passage-hashes.py` → translation freshness
   detection → agents → `i18n/<locale>/`. **EN must be synced & hashed before any
   translation run**, or everything misclassifies.
3. Frontend `jupyter.ts` ↔ `sse-build-server.py` over the mimicked Binder `/build/`
   SSE contract — the seam that lets one frontend talk to both Binder and CE.
4. `sidebars.ts deduplicateLabels()` ↔ i18n sidebar translation keys — a rename in one
   must match the other or locale sidebars break.
5. localStorage is **domain-scoped** → preferences and credentials do **not** share
   across locale subdomains (deliberate, but a UX seam).

### ⚠️ Notable observation surfaced during mapping
**There is no automated test suite** — no unit/integration/E2E tests anywhere in the
tree (the only `*test*` file is `scripts/workshop-stress-test.py`, a load harness).
All ~3,200-line Python pipelines and the 2,080-line execution component are verified
only by the build gate and manual/agent sweeps. This is the single biggest structural
risk-multiplier and shapes several review priorities below.

---

## PART B — Review plan (prioritized, by domain)

Severity guide: 🔴 high-leverage / likely to find real problems · 🟡 worth doing ·
🟢 lower priority / confirmation. Each item lists *what to check* and *how* (tool/skill
where one applies).

### Domain 1 — Content correctness & freshness 🔴
1. **Re-run the notebook sweep** (`scripts/notebook-sweep/run_all.py`). Memory says
   ~28 still-broken EN notebooks (F2/F4/~10 P1) from 2026-05-17. Confirm current count;
   the sweep report on disk is stale. *How:* run sweep, diff vs `notebook-sweep-report.md`.
2. **Sync fidelity audit** — pick ~15 pages across tutorials/guides/courses and diff the
   synced MDX against `upstream-docs/` source: dropped sections, mangled Admonition
   nesting, `<Table>` conversions, broken image/link rewrites, brace-escape over-reach.
3. **Stale-but-fresh-hash detection** — the subtle class from memory: files whose
   source-hash == EN yet carry stale sections. *How:* heading-count divergence scan on
   FRESH files (the qunova #185 technique), corpus-wide.
4. **Broken-link / broken-image audit** — build emits warnings (not errors); collect and
   triage them. Internal cross-refs, anchors, `_toc.json` external URLs, locale image drift.
5. **Clean build integrity** — full `NODE_OPTIONS=...8192 npm run build`, capture and
   classify every warning; check for `foo/foo.mdx` slug collisions and MDX compile fails.

### Domain 2 — Translation & i18n quality 🔴 (largest surface)
6. **Coverage reconciliation** — for each main locale, assert
   `STATUS.md` count == `check-translation-freshness.py` count == manifest count. Memory
   flags this exact drift (de #191: 23 captured vs 31 actual). Reconcile before trusting "done".
7. **Run the validators corpus-wide** — `validate-translation.py` + `lint-translation.py`
   across all locales; confirm 0 structural FAIL and triage any new lint ERRORs
   (JSX balance, untranslated-EN leakage, foreign-script intrusion, MDX-fatal syntax).
8. **MDXComponents stub fidelity** — verify stubs parse markdown/HTML in IBM string props
   (`**bold**`, `` `code` ``, `<em>`) rather than leaking literally (known pitfall).
9. **Linguistic residue** — the AR Egyptian-dialect FAIL files not provably re-verified;
   spot-check. Decide whether the 9 German dialects are in scope (currently partial/low-prio).
10. **i18n plumbing** — locale build of 2-3 subdomains: sidebar key collisions, search
    `lunr-languages` gaps (no uk/tl), fallback-banner markers render, RTL (ar/he) layout,
    mobile locale selector, hreflang output correctness.

### Domain 3 — Code execution & Binder/Jupyter 🔴
11. **Live execution smoke test** — actually run cells on the live site (or local build):
    Binder connect, pip-install injection, simulator/fake-backend mode, circuit diagrams,
    histograms, the Run/Back toggle, dual static+live output. *How:* `/verify` or `/run`.
12. **Session-reuse & race paths** — exercise the 3 race-retry sites and the 8-min idle
    session reuse across tabs; confirm graceful failure when Binder cache misses.
13. **Workshop backend** — the open Jupyter `connections_dict` underflow bug (cull-skip →
    memory creep); confirm still open and that the restart-between-sessions workaround holds.
    Verify the SSE-stagger is *still not* implemented (memory says it isn't) and decide if it should be.
14. **Image-size reduction Phase 1** — `python:3.12-slim` base (~450 MB / cold-start win);
    scoped but not done.

### Domain 4 — Security 🔴
15. **Re-run `/security-review`** on the branch. Prior 6 findings fixed; re-verify CORS,
    credential injection, `innerHTML` JSON-LD, pip validation, sed injection, **SSRF
    allowlist** (Colab `/github/`), token length/handling, XSRF-disabled rationale.
16. **Secret / deploy-key hygiene** — 27 satellite repos with SSH `DEPLOY_KEY`s; admin
    page password hash + AES-GCM encrypted Umami URL (`encrypt-for-admin.mjs`); confirm no
    secrets in build output or client bundle; `ADMIN_PASSWORD` unset → page unprotected.
17. **Open-findings tracker** — reconcile against `.claude/SECURITY_REVIEW_2026-05.md`
    (local-only). nginx rate-limits and the token-auth boundary on the CE pod.

### Domain 5 — Frontend / UX / accessibility 🟡
18. **Preferences system** — exercise all 15 localStorage keys; the known gotchas
    (clearing progress must cascade events; static-output hiding via body class + sibling
    CSS; sidebar items persist across SPA nav). Bookmarks cap (50).
19. **Accessibility** — keyboard nav, focus order, contrast on the always-dark navbar,
    ARIA on the execution toolbar and swizzled sidebar, screen-reader labels, RTL.
20. **Responsive / mobile** — navbar wrap (`white-space: nowrap`), mobile nav, locale
    selector, code execution on small screens.
21. **SEO** — hreflang plugin output, sitemap (ignorePatterns), robots, JSON-LD validity,
    fallback-page noindex; **GSC DNS TXT still TODO** (memory).

### Domain 6 — Infrastructure & CI/CD 🟡
22. **Workflow audit** — read all 19 workflows for: failure modes when `DEPLOY_KEY` absent,
    permission scopes (least-privilege), pinned action versions, the manual-only
    `sync-upstream` auto-PR path (is it safe to enable the weekly schedule yet?).
23. **Docker / Pi** — full offline image builds and serves; `setup-pi.sh` is **untested on
    hardware** — at minimum a dry-run review.
24. **DNS / domain** — wildcard CNAME, `static/CNAME` correctly excluded from container
    builds, per-locale subdomain URLs match `localeConfigs`.

### Domain 7 — Code quality & maintainability 🟡
25. **`/code-review ultra`** on the branch (or targeted on the big files): `sync-content.py`
    (3.2k L), `update-translations.py` (1.9k L), `validate-translation.py` (1.4k L),
    `jupyter.ts` (1.2k L), `ExecutableCode` (2.1k L). Look for dead code, swizzle drift
    vs Docusaurus 3.7, duplicated regex transforms, error-swallowing.
26. **Test-coverage reality** 🔴 — there is **no test suite**. Scope at least: (a) a
    pytest harness around the validator/lint/passage-hash logic (pure functions, high ROI),
    (b) a smoke build in CI, (c) decide whether a fresh manual regression pass is warranted
    (old plans were deleted as stale). This is the highest-leverage *structural* improvement.

### Domain 8 — Licensing & compliance 🟢
27. **Attribution correctness** — Apache-2.0 (code) + CC BY-SA 4.0 (content) split;
    `LICENSE`/`LICENSE-DOCS`/`NOTICE`; IBM disclaimer + trademark lines in footer and synced
    pages; upstream attribution preserved through sync; non-affiliation statement present.

---

---

## EXECUTION LOG / FINDINGS

### Domain 1 — Content correctness & freshness ✅ DONE (2026-06-04)
Scope run: #2 sync fidelity, #3 stale-hash, #4 broken links, #5 build (notebook sweep #1 deferred).
- **#2 Sync fidelity — SOUND.** 15 pages diffed + corpus scans; 1,340/1,340 EN images resolve.
  2 LOW: brace-escape over-reach `data-encoding.mdx:1002` (mixed back-tick line confuses
  `escape_mdx_outside_code`, sync-content.py:340, 1 occurrence); bare `/docs/tutorials`·
  `/docs/guides` index links (no trailing slash) rewritten off-site to IBM (cosmetic).
- **#3 Stale-but-fresh-hash — CLEAN.** 7,225 FRESH files, 0 genuine divergences. Scan at
  /tmp/heading_divergence_scan.py.
- **#4 Broken links/images:** 840 broken markdown images = 100% dialect locales (0 in EN/main),
  expected. 13 broken-link + 13 broken-anchor blocks = API link-only (expected). **🟡 26
  empty-URL markdown links** trace to ONE real EN bug: `[text]()` at
  `docs/tutorials/solve-higher-order-binary-optimization-problems-with-q-ctrls-optimization-solver.mdx:517`
  (propagates to every locale). FIXABLE.
- **#5 Build integrity — 🔴 FULL 27-LOCALE BUILD OOMs at 8GB** (`FATAL ERROR: JS heap out of
  memory`, exit 134; died ~14/27 after dialect `bad`). No `[ERROR]`/slug collisions before crash.
  CI builds locales in separate matrix jobs so PROD is fine; only the local all-locales build is
  affected. Memory's "8192 is enough" note is stale for the full set. ACTION: raise heap or
  document per-locale local builds.

### Domain 2 — Translation & i18n quality ✅ DONE (2026-06-04, 17 main locales)
- **#6 Coverage reconciliation — CLEAN.** Live `check-translation-freshness --all-locales`: all 17
  main locales 100% FRESH (every STALE/CRITICAL is a dialect locale, out of scope). Matches
  status.json (428 promoted / 428 val=PASS / 0 FAIL each). de-#191-class drift NOT present.
- **#7 Validators corpus-wide — CLEAN.** `lint-translation.py` across all 17: **0 errors each**.
  status.json shows 0 structural FAIL corpus-wide.
- **#8 MDXComponents stub fidelity — MOSTLY SOUND, 2 latent risks.** AccordionItem correctly
  parses `**bold**`/`` `code` ``/`<em>` (and real content uses it). 🟡 **DefinitionTooltip**
  (renders `definition` into HTML `title=` attr, DefinitionTooltip.tsx:15) and **InfoIcon**
  (CSS `attr()`, InfoIcon styles.css:17) would leak literal markup IF given markdown — currently
  all call sites are plain text, so ZERO live exposure. AccordionItem regex is fragile on nested
  markup. ACTION: add plain-text-only JSDoc guards, or port AccordionItem's renderer.
- **#9 AR linguistic residue — dialect concern UNFOUNDED.** 6 files read in depth + corpus dialect
  grep: clean formal MSA, 0 Egyptian-dialect markers, consistent terminology. variational fix
  (التغايري) fully landed. 🟡 BUT diagonalization fix has **5 lingering تقطير (distillation)
  mistranslations** of SQD "diagonalization" → should be قطرنة: `computer-science/vqe.mdx:1012`,
  `designing-and-leading-quantum-projects/standing-up-team.mdx` ×3,
  `guides/error-mitigation-overview.mdx:109`. FIXABLE (term replacement).
- **#10 i18n plumbing — HEALTHY.** Sidebar deduplicateLabels renames label+key in lockstep (PASS);
  RTL ar/he configured with logical CSS props + KaTeX-LTR (PASS); mobile+desktop locale selectors
  wired, visibleLocales=[en,de,es] intentional (PASS); hreflang injects all-locale alternates +
  x-default + noindexes fallbacks, main locales 0 fallback / dialects 336 (PASS). 🟡 **Search
  language gap**: only 10 of 27 locales in the lunr `language` array; uk/tl documented-intentional,
  but ms/id/th/pl/ro/cs (+9 dialects) silently have degraded search — undocumented. ACTION: add
  supported langs or document.

### Domain 2 quick-fixes ✅ APPLIED (2026-06-04)
- **AR diagonalization stragglers FIXED** — 5 تقطير→القطرنة corrections across vqe.mdx (×2),
  standing-up-team.mdx (×3), error-mitigation-overview.mdx (×1). Matched canonical القطرنة الكمية /
  خوارزميات القطرنة الكمومية (204 canonical uses). All 3 files re-validated PASS; `التقطير`
  now 0 in corpus.
- **Stub leak risks FIXED** — new shared `src/lib/inlineMarkup.tsx` with `renderInlineMarkup`
  (JSX) + `stripInlineMarkup` (attribute-safe plain text). DefinitionTooltip.tsx and
  InfoIcon/index.tsx now strip markup before the native title=/data-tooltip attribute;
  MDXComponents AccordionItem reuses the shared renderer (de-dups + hardens the old inline regex).
- **Search-language gap DOCUMENTED** — explanatory comment in docusaurus.config.ts:219 spelling
  out the lunr-module gating (uk/tl no module; ms/id/th/pl/ro/cs + dialects degraded-by-choice).
- Verification: changed TS/TSX typecheck clean (4 tsc errors remain but are PRE-EXISTING in
  untouched files → logged as a Domain-7 item); EN build validates the new import resolves.

### Domain 3 — Code execution & Binder/Jupyter ✅ REVIEWED (2026-06-04, static + checklist)
Most findings to date. Two frontend bugs VERIFIED against source; workshop bugs CONFIRMED open.

**Frontend (jupyter.ts + ExecutableCode) — VERIFIED bugs:**
- 🔴 **H1 EventSource leak on SPA nav** — `resetModuleState()` (ExecutableCode:107) clears timers/state
  but does NOT call `cancelBinderBuild()`. Navigation effect (`:1465`) + unmount (`:1674`,`:1788`) reset
  without cancel; only the explicit Cancel button (`:1661-1662`) pairs them. An in-progress Binder/CE
  build EventSource (jupyter.ts `activeBinderES`, 20-min timeout) leaks across navigation → wasted
  Binder slots (100/repo cap) + live CE coroutine for an abandoned page. CONFIRMED.
- 🔴 **H2 cross-page kernel-race retry** — the race-retry `setTimeout` (ExecutableCode:1334, also 1248/1355)
  is fire-and-forget; handle not stored, so `resetModuleState()` can't cancel it. After nav, the pending
  retry fires `doBootstrap(oldPageOptions)` against the new page's DOM. CONFIRMED. (Shared root cause with H1:
  module-level async outlives the component but isn't torn down.)
- 🟡 **H3 false-ready during race window** — `thebelabBootstrapped=true` set before the retry; a concurrent
  `bootstrapOnce` short-circuits to 'ready' while no live kernel exists → cells execute against dead kernel.
- 🟡 **M1/M2 session-reuse host mismatch** — `dq-binder-session` foreign-guard only distinguishes
  binder-vs-not; CE↔CE and CE↔custom swaps pass; workshop pool reassignment clears `dq-workshop-assigned`
  but NOT the reusable binder session → already-connected tabs aren't moved on rebalance.
- 🟡 **M4 unbounded pool failover** — fresh-build onerror failover (jupyter.ts:988-1015) recurses via full
  `ensureBinderSession` with NO counter; "retry once" not enforced → walks the ring indefinitely when a
  whole pool is cold/down. Thundering-herd risk.
- 🟡 **M3 test-connection retries CORS/DNS for ~90s**; M5 20-min worst-case on silently-stalled SSE;
  M6 retry-budget not reset on the bootstrapOnce failure path.
- 🟢 L1-L6: unvalidated sessionStorage shape; unguarded setItem; backwards onIOPub guard (L3, latent
  fake-backend no-op); swallowed injectKernelSetup failure → silent unpatched cells; 60s-not-2s safety-net.
- ℹ️ Backend cascade footgun: a stale custom URL (no expiry) silently shadows freshly-saved CE creds.

**Workshop backend (sse-build-server.py + nginx + entrypoint):**
- 🔴 **connections_dict underflow — FULLY OPEN, zero repo mitigation.** No patch, no restart cron, no
  kernel-count guard in /stats, supervisord autorestart doesn't catch a logical leak. `cull_connected=False`
  (entrypoint:71-74) actively aggravates it. Only mitigation = manual between-session pod restart. CONFIRMED.
- 🔴 **F1 /build/ rate-limit self-DoS** — `rate=100r/m, burst=50 nodelay` keyed on remote IP; a workshop
  shares ONE NAT IP, so 80 simultaneous Runs → ~30 get instant 503; single-pod deploys go straight to
  reject (no failover). Defeats the 80-user sizing. Compounded by no stagger. Fix: raise burst / drop
  nodelay so excess queues / add the stagger.
- ✅ **SSE stagger — CONFIRMED NOT implemented.** Both Math.random() in jupyter.ts (527,534) are
  pool-selection only; EventSource opens immediately (jupyter.ts:948-949), no jitter. Matches memory.
- 🟡 F3 SSE clients hang full 30s on wedged pod (no backpressure); F4 nginx upstream keepalive defeated
  (conn churn to Jupyter); F5 single CORS origin may reject locale subdomains hitting CE — verify.
- 🟢 F2 _fetch_jupyter_with_retry body-pattern matching is dead-but-safe; tighten. Token/XSRF boundary OK;
  note `?token=` may land in nginx access logs (/api/ not access_log-off).

**Image size (#14): documented Phase-1 plan UNSOUND as written.** Switching to python:3.12-slim nets only
~100-200 MB (not 450 MB) after backfilling Jupyter Server (~200 MB) + build tools, AND loses the shared
base-layer pip cache that jupyter-local + jupyter-codeengine both use (commit bbe0056cc switched TO
base-notebook for exactly that reason). Heavy hitters: qiskit ~200 + aer ~100 + pyscf ~100 = 44% of 905 MB.
Better ROI: a `jupyter-codeengine-lite` variant dropping heavy addons (~150-200 MB), or pod-level image
caching / regional registry for cold-start (98s→~5s on warm pulls). Quick wins (layer merge) negligible.

**LIVE-VERIFICATION CHECKLIST (#11 + the static findings that need runtime confirmation):**
See `.claude/D3_LIVE_VERIFICATION_CHECKLIST.md`.

### Domain 3 quick-fixes ✅ APPLIED (2026-06-04) — H1, H2, F1, stagger
Root-cause fix for H1+H2 (module-level async outliving the component):
- **H1+H2 FIXED** — `resetModuleState()` (ExecutableCode) now (a) clears a newly-tracked
  `kernelRaceRetryTimer` so a pending race-retry can't fire against the next page, and (b) calls
  `cancelBinderBuild()` to abort an in-flight build SSE on navigation/unmount.
- **cancelBinderBuild() hardened** — added `activeBinderBuildCancel` teardown hook: cancel now clears
  the build's 20-min timeout AND marks it settled, so closing the ES does NOT trigger
  `onerror → workshop failover` (also closes the cancel-triggers-M4-failover edge). The build promise
  registers/nulls the hook via its existing `cleanup()`.
- **SSE stagger FIXED (F1 root cause)** — `ensureBinderSession` now delays opening the EventSource by a
  random 0–STAGGER_MAX_MS (3s) for workshop/CE configs only (solo public-Binder users get 0 delay).
  The stagger timer is cancellable via the same teardown hook. Refactored the ES wiring into
  `wireEventSource()` so the delayed open keeps the timeout/onmessage/onerror semantics intact.
- **F1 rate-limit FIXED** — nginx `/build/` zone raised `100r/m,burst=50,nodelay` → `300r/m,burst=120`
  and DROPPED `nodelay` so the over-burst tail of an 80-user single-IP class QUEUES (brief delay)
  instead of getting instant 503. Pairs with the client stagger.
- Verification: 0 new tsc errors (still exactly 4 pre-existing, incl. the ExecutableCode:1858
  `return null` → Domain-7); EN build green. Runtime behavior (storm absorption, leak-on-nav) still
  needs the live checklist (D3 items 7, 15).
- NOT fixed (logged, deferred): H3 false-ready, M1/M2 session host-mismatch, M4 unbounded failover
  (partially de-risked by stagger+rate-limit), M3/M5/M6, L1-L6, the connections_dict bug (needs a
  Jupiter-side patch or restart automation — bigger change), image-size variant.

### Domain 4 — Security ✅ REVIEWED (2026-06-04, skill-substitute diff + full-surface sweep)
`/security-review` skill couldn't run (it shells out to system git, blocked by Xcode license) — substituted
an equivalent diff-review agent + two full-surface sweeps. Findings folded into the local tracker
`.claude/SECURITY_REVIEW_2026-05.md` (the authoritative, git-untracked record).
- **Diff of the review's own fixes — NO security regression.** Markup helpers route through React
  auto-escaping (no dangerouslySetInnerHTML), regexes ReDoS-safe (linear negated classes), jupyter
  teardown preserves token handling + adds no new logging, nginx change raises a non-sensitive shim's
  ceiling while token-gated /api/ is unchanged. Net positive for leak hygiene.
- **All 13 tracked findings (S1-S13) CONFIRMED-OPEN** against current code; none closeable. Lines moved
  but findings stand.
- 🔴 **S1 ESCALATED (verified directly):** `storage.ts setItem()` cookies EVERY key unconditionally
  (storage.ts:178 → writeChunkedCookie, gated only by host ending doqumentation.org). The IBM API token
  (jupyter.ts:409) lands in a 1-year `Secure; SameSite=Lax` **non-HttpOnly** `.doqumentation.org` cookie
  → readable by every locale subdomain's JS + rides same-site requests. Wider than the localStorage-only
  tracker text. = new finding N1.
- 🔴 **S3:** SSE 'ready' carries the FULL long-lived JUPYTER_TOKEN (not scoped) — XSS-on-origin → exfil.
- 🟡 **S6 recount: 0/49 actions SHA-pinned** (trivy-action@master, claude-code-base-action@beta the worst).
  S5 (no Dependabot), S11 (no secret-scan), S12 (no SBOM/resource-limits/read-only-rootfs) all confirmed
  open — but Dockerfile DOES drop to USER jovyan + HEALTHCHECK, and Trivy vuln-scan IS present.
- **Secret hygiene CLEAN:** no committed secrets; 27 DEPLOY_KEYs + IBM_CLOUD_API_KEY + ADMIN_* all via
  `${{ secrets.* }}`, written to disk not logged; AES-GCM (encrypt-for-admin.mjs) sound (random salt+IV,
  PBKDF2-100k). N3: client-shipped admin hash is unsalted single-SHA-256 (brute-forceable; bounded impact).
- **New:** N2 (3 workflows missing `permissions:` block — priority lint-image-paths.yml, PR-triggered);
  N4 (document.write + IBMVideo postMessage '*' — currently safe). S7's 1 innerHTML confirmed non-exploitable.
- NOT fixed: S1-S13 are substantive/accepted-risk items (user keeps the tracker local & deferred); N2 is a
  cheap quick-fix candidate if desired. No fixes applied this domain — surfaced + tracker updated only.

### Domain 5 — Frontend / UX / accessibility ✅ REVIEWED (2026-06-04)
**Preferences system (#18) — robust core, a few real edge bugs.** Documented gotchas all hold (clearing
cascade wired, static-output sibling CSS + body class correct, caps enforced bookmarks≤50/recent≤10/
visited pruned@2000, every JSON.parse guarded, SSR guards present). Findings:
- 🟡 **hideStaticOutputs toggle isn't live** (jupyter-settings.tsx:1081 doesn't dispatch DISPLAY_PREFS_EVENT,
  and ExecutableCode has no listener for it) — needs reload to take effect, unlike font-size which is wired.
- 🟡 **Cookie chunking splits by UTF-16 length not bytes** (storage.ts:14,62) — a long CJK/Arabic bookmark
  title can exceed the 4KB cookie limit after encodeURIComponent → chunk silently lost → cross-subdomain
  value lost. Real given localized titles.
- 🟡 **Cross-subdomain cookie sync only works at page-load, not live** (storage.ts:147 — cookies don't emit
  `storage` events) — a bookmark added in tab A is invisible to tab B until reload. Contradicts the
  "shared across subdomains" intent.
- 🟡 **Category badge clears progress by common-prefix, not exact href set** (DocSidebarItem/Category:90) —
  a category with heterogeneous child paths could over-clear sibling categories' progress.
- 🟢 BookmarksList remove doesn't dispatch dq:bookmarks-changed (stale ★ across SPA); onboarding double
  source-of-truth for the "3 visits" threshold; minor perf in the per-render badge query.

**Accessibility (#19) — above average, concentrated gaps.** Strong baseline: global `:focus-visible` ring,
RTL via logical properties, navbar contrast 9-16:1, BookmarkButton exemplary, ExecutableCode toolbar uses
real buttons + aria-live. Findings ranked:
- 🔴 **InfoIcon tooltip keyboard/SR-inaccessible** (InfoIcon.tsx:12 + styles.css:11) — `:hover`-only CSS
  tooltip on a non-focusable `<span>` with no aria; content invisible to keyboard+AT. Used heavily
  (restart kernel, settings, lab banner). WCAG 2.1.1/1.4.13/4.1.2.
- 🔴 **Unlabeled form inputs** — CE URL+Token (jupyter-settings.tsx:658,670: label not associated, no
  id/htmlFor) and admin password (admin.tsx:175: placeholder only). WCAG 1.3.1/3.3.2/4.1.2.
- 🟡 **No prefers-reduced-motion guard anywhere** (custom.css: 0 occurrences, confirmed) — toast + ~25
  transitions unsuppressed. WCAG 2.3.3.
- 🟡 **Cell execution status not announced** (CSS ::before content + no per-cell aria-live) — blind user
  gets no done/error notification. WCAG 4.1.3.
- 🟡 Sidebar progress badge nests a focusable control inside the category link (nested-interactive) +
  async aria-label. 🟢 TranslationFeedback rating buttons title-only (no aria-label); settings `outline:none`
  replaced only by box-shadow (drops in forced-colors mode); OpenInLabBanner strings not translate()-wrapped.

**Responsive (#20) + SEO (#21) — PASS.** hreflang/fallback-noindex/mobile-locale already PASSed in D2.
Confirmed here: robots.txt (Disallow /admin), sitemap excludes admin/search/tags, 3/3 JSON-LD blocks valid
(Organization/WebPage/SoftwareApplication), navbar `.navbar__link` styling present. GSC DNS-TXT still TODO
(memory). Note: EN-only build shows 1 sitemap loc / 2 hreflang — full counts (430 pages, 27 alternates)
confirmed in D2's full build.

### Domain 5 quick-fixes ✅ APPLIED (2026-06-04) — a11y + preference bugs
**Accessibility:**
- **InfoIcon a11y FIXED** — now a focusable `<button type=button>` with `aria-label`=tooltip text
  (glyph aria-hidden); CSS resets button chrome + adds `:focus-visible` tooltip display. Keyboard + SR
  can now reach the content. (InfoIcon/index.tsx + styles.css)
- **Form labels FIXED** — CE URL/token inputs got id + `htmlFor` association (jupyter-settings.tsx:658,670);
  admin password got `aria-label` (admin.tsx:179).
- **Reduced-motion FIXED** — global `@media (prefers-reduced-motion: reduce)` block in custom.css kills
  animations/transitions/smooth-scroll (WCAG 2.3.3).

**Preference bugs:**
- **Live hide-static-outputs toggle FIXED** — root cause was ExecutableCode capturing the pref in mount
  state. Now the Run handler reads `getHideStaticOutputs()` LIVE; the Settings toggle dispatches
  DISPLAY_PREFS_EVENT; dead `hideStaticOutputs` state + stale useCallback dep removed. (Kept the class
  tied to run/static mode — it's NOT a page-global toggle, documented in displayPrefs.ts.)
- **Cookie byte-length chunking FIXED** — `chunkByEncodedSize()` now splits by URL-ENCODED length (was
  UTF-16 char length), iterating by code point so a long CJK/Arabic bookmark title can't silently blow
  past the 4KB cookie limit and be dropped. (storage.ts)
- **Category badge over-clear FIXED** — clears the EXACT href set via new `unmarkPageExecuted` +
  `unmarkPageVisited` per page instead of `commonPrefix` (which could wipe sibling categories'
  progress). Dead `commonPrefix` helper removed. (Category/index.tsx + preferences.ts)
- Verification: 0 new tsc errors (still 4 pre-existing); EN build green.
- NOT fixed (logged): cross-subdomain cookie sync is page-load-only (cookies don't emit storage events —
  bigger design change); cell-status aria-live; sidebar badge nested-interactive; minor a11y nits.

### Domain 6 — Infrastructure & CI/CD ✅ REVIEWED + fixes (2026-06-04)
**Workflow correctness (#22) — several real operational bugs found:**
- 🔴 **deploy ↔ deploy-locales `notebooks`-branch push race** — deploy.yml force-pushes `notebooks`
  (deploy.yml:83) while deploy-locales' update-notebooks does a NON-force push (deploy-locales.yml:246);
  on simultaneous main pushes the non-force push is rejected → red X, no retry/rebase. Different
  concurrency groups ("pages" vs "locales") so they run concurrently. NOT FIXED (needs rebase-retry or
  shared concurrency group — design choice).
- 🔴 **codeengine-image pushes `:latest` BEFORE Trivy scans it** (build+push :74 → scan :87) — CE deploy
  is correctly blocked on a CRITICAL/HIGH finding, but GHCR `:latest` already advanced to the unscanned
  image, which notebook-ci / a later workshop-start pull could pick up. Fix: scan before push (load,
  scan, then push), or scan-by-digest + re-tag latest after pass. NOT FIXED.
- 🟡 **check-translations daily empty-push bug** — `git diff --quiet || commit && push` precedence means
  `push` runs even with no changes → daily empty push to main (check-translations.yml:35). NOT FIXED.
- 🟡 **workshop-monitor restart-count `grep -c || echo 0` multiline bug** (monitor:313 → compare :352) →
  false restart reports. workshop-close reset_pod `--max-scale 1` may be a no-op (won't clear zombies).
- ✅ **deploy-locales IS graceful on missing DEPLOY_KEY** (explicit guard + ::warning:: + exit 0,
  fail-fast:false). ✅ **sync-upstream IS safe to schedule weekly** — build-gated, handles no-change,
  scoped add-paths, no recursive trigger — ONE change first: offset its Monday 06:00 cron off
  check-translations' daily 06:00 (both run sync-content.py with write perms).
- 🟢 ce-monitor fractional-vCPU misparse (false oversized alert); refresh-page-dates pushes to main with
  `[ci]` not `[ci skip]` (triggers full deploy); clock-equality daily-summary gates are fragile.

**Docker/Pi/DNS (#23/#24):**
- ✅ **static/CNAME handled** — Dockerfile.jupyter:31 `rm -f build/CNAME` + nginx roots at built output,
  so CNAME doesn't leak. 🟢 minor: not in .dockerignore (defense-in-depth gap, mitigated).
- 🟡 **setup-pi.sh would fail first at check_prerequisites** (assumes /home/pi/RQB2 venv pre-exists; not
  idempotent for a bare Pi) + doesn't install the static site (assumes pre-populated /opt) + systemd
  `User=$USER` not fixed. It's built for a pre-baked RasQberry SD image, not standalone. UNTESTED confirmed.
- ✅ **DNS/locale consistency PERFECT** — all 27 localeConfigs use https://XX.doqumentation.org; all 26
  non-EN satellite repos (JanLahmann/doqumentation-XX) match; EN has none (it's the main repo). CNAME
  per-satellite written at deploy. No orphans/mismatches.

**Fixes APPLIED (N2 + S5 + S6 per approval):**
- **S5** — added `.github/dependabot.yml` (npm/actions/docker/pip, weekly grouped).
- **S6** — SHA-pinned the 2 dangerous mutable tags: trivy-action @master → 1f0aa58 (v0.9.2);
  claude-code-base-action @beta → e8132bc (v0.0.63). (~47 @vN float-tags remain, de-risked + now
  Dependabot-tracked.)
- **N2** — top-level `permissions: contents: read` on lint-image-paths.yml (real gap, PR-triggered) +
  docker.yml + check-translations.yml (baseline). All 6 edited YAMLs parse clean.
- Tracker `.claude/SECURITY_REVIEW_2026-05.md` updated (S5 FIXED, S6 partial, N2 FIXED).

### Domain 6 workflow-bug fixes ✅ APPLIED (2026-06-04)
- **check-translations daily empty-push FIXED** — replaced `diff --quiet || commit && push` with an
  `if ! git diff --cached --quiet; then commit; push; fi` block, so push only runs on real changes.
- **deploy ↔ deploy-locales notebooks race FIXED** — added a 5-attempt push-with-rebase-retry loop to
  deploy-locales update-notebooks: on a non-fast-forward reject (EN job force-pushed concurrently) it
  re-fetches + rebases the locale-subdir commit and retries. Locale subdirs don't conflict with EN's
  push, so the rebase is clean.
- **codeengine-image :latest-before-scan FIXED** — split into Build(load:true, NOT pushed) → Trivy scan
  → Push(scan passed). A HIGH/CRITICAL now blocks BEFORE anything reaches GHCR. Also added a
  `concurrency: codeengine-image` group (cancel-in-progress) to stop revision thrash on rapid pushes.
- All 3 YAMLs parse clean. Remaining D6 items NOT fixed (logged): workshop-monitor restart-count
  multiline bug, ce-monitor fractional-vCPU misparse, refresh-page-dates `[ci]`-not-`[ci skip]`,
  setup-pi.sh prerequisites, sync-upstream cron-offset-before-enabling.

### Pre-existing tsc errors ✅ FIXED (2026-06-04) — Domain 7 prelude
The 4 long-standing `tsc --noEmit` errors (present before this review, surfaced repeatedly) are now fixed
— `tsc` is clean (0 errors):
- **sidebars.ts** — removed the unresolvable deep import `@docusaurus/.../lib/sidebars/types`; derived
  `SidebarItemConfig` from the PUBLIC `SidebarsConfig` via conditional/Extract inference.
- **ExecutableCode/index.tsx** — widened the component return type `JSX.Element` → `JSX.Element | null`
  (it legitimately returns null to hide injected pip-install cells on Binder/CE).
- **OperatingSystemTabs.tsx** — cast pass-through children to `Tabs`' expected children type.
- **admin.tsx** — Docusaurus 3.x `Layout` dropped the `noIndex` prop; replaced with a `<Head>` robots
  noindex meta (page is also robots.txt-Disallow-ed).
- **Implication (Domain 7):** these survived because `package.json` has a `typecheck` script but **no CI
  gate runs it** — a real maintainability finding. (build uses Babel, which doesn't type-check.)
- Verification: `tsc --noEmit` = 0 errors; EN build green.

### Domain 7 — Code quality & maintainability ✅ REVIEWED + CI gate added (2026-06-04)
Surface is remarkably clean (near-zero `any`, 0 `@ts-ignore`, 2 TODOs, 0 dead-code blocks). Debt is
structural, in 3 places:
- 🔴 **No PR-time typecheck/build gate** — only 1 PR-triggered workflow (lint-image-paths, image-paths
  only); nothing ran `tsc` or a build on PRs → the 4 tsc errors survived. **FIXED: added
  `.github/workflows/ci.yml`** (typecheck + sync + EN build on pull_request). Validated, references real
  npm scripts.
- 🟡 **Drifted duplicate of a load-bearing check** — `check_jsx_tag_balance` exists in BOTH
  validate-translation.py:804 (27 lines) and lint-translation.py:354 (48 lines) and they've DIVERGED →
  validator and linter disagree on the JSX-balance check that gates every translation PR. NOT FIXED
  (extract to shared `_common.py`).
- 🟡 **No shared util module** — `load_status`/`save_status` duplicated across 7 scripts;
  `find_genuine_translations` across 3; STATUS_FILE re-declared (twice in validate-translation.py). NOT FIXED.
- 🟢 6 inert `eslint-disable` comments (no eslint installed/configured); god-files (sync-content.py 3194,
  ExecutableCode 2093) have clear split seams. Test-harness proposal: a ~60-80 test pytest suite over the
  3 PURE modules (passage_units.py, validate/lint check_* functions) = most safety per effort. NOT DONE
  (proposal logged in agent output).

### Domain 8 — Licensing & compliance ✅ REVIEWED — SOUND, no risks
Exemplary. LICENSE (Apache 2.0) + LICENSE-DOCS (CC BY-SA 4.0) are real unmodified texts; NOTICE correctly
attributes IBM/Qiskit + states the dual-license boundary + translations-are-CC-BY-SA. CC BY-SA's
attribute/link/indicate-changes/sharealike all met (footer + README + legal page + homepage + the per-page
source-date footer from upstreamFileMeta.json). Trademark + non-affiliation prominent in 5 places. /legal is
a proper Impressum + GDPR privacy policy (Umami, fonts, CDNs disclosed). All deps permissive (MIT/BSD/Apache/
OFL); 7 addons Apache-2.0. NO compliance risk. Nice-to-have only: a LICENSES/ dir for dependency transparency.

### Follow-ups 1-4 ✅ DONE (2026-06-04, post-review round)
**FU1 — connections_dict workshop memory creep MITIGATED:**
- entrypoint: `cull_connected=False→True` + idle `300→600s` — culler now reclaims the zombie kernels the
  underflow bug makes it skip; 600s keeps a reading student's state. cull_busy=False still protects mid-exec.
- sse-build-server: `high_kernels` watchdog log + `kernel_leak_suspected`/`kernel_leak_threshold` in /stats
  (env KERNEL_LEAK_THRESHOLD, default 120) so monitoring can alert/restart. Pod-restart is now a fallback.

**FU2 — Security S1/S3:**
- **S1 = ACCEPTED TRADEOFF per user (2026-06-04):** ALL tokens (IBM API token/CRN + Jupyter/CE server
  tokens) intentionally shared across `*.doqumentation.org` so creds are entered once. A denylist was
  prototyped then REVERTED per user decision. storage.ts back to all-keys-cross-subdomain (kept the D5
  cookie byte-length fix, which makes non-ASCII sharing reliable). Encryption-at-rest remains the only
  open S1 hardening.
- **S3 token-in-logs FIXED:** nginx `token_safe` log format logs `$uri` (no `?token=` query) → tokens no
  longer hit access logs. Core S3 (full token over SSE) stays thebelab-0.4.0-bound (accepted, like S4).

**FU3 — test harness + de-drift:**
- **De-drifted `check_jsx_tag_balance`:** new `translation/scripts/_common.py` owns the canonical
  `jsx_tag_imbalances` primitive + PAIRED_JSX_TAGS + status helpers; validate + lint both call it (was
  copy-pasted + drifted). **The new tests immediately caught a real bug** in the consolidated primitive —
  a space-less `<Tabs/>` self-close yielded opens=-1 (false-flag); FIXED in the primitive. Lint on de still
  0 errors (behavior-preserving on the corpus).
- **pytest harness:** `translation/scripts/tests/` (conftest + 3 files, **38 tests, all pass**) over the
  PURE functions — `_common.jsx_tag_imbalances` (incl. validate/lint-agree test), validate's slugify/
  parse_frontmatter/count_jsx_tags/extract_link_urls/check_jsx_tag_balance, passage_units hash determinism
  + extraction. `pyproject.toml` pytest config; wired into `ci.yml` (runs on every PR).

**FU4 — D3 M-series:**
- **M1 session host-mismatch FIXED:** reuse guard now requires the cached session's host to match the
  config's target host (binderUrl/baseUrl) for non-Binder backends — catches CE↔CE / CE↔custom swaps the
  old binder-vs-not check missed.
- **M4 unbounded pool failover FIXED:** added a `failoverBudget` param (starts pool-size-1, decrements per
  hop) so a fully-down pool is tried at most once around the ring then gives up — no infinite thundering herd.
- Verification: tsc 0 errors, 38 tests pass, EN build green, all Python/shell parse.

### Open-items round ✅ DONE (2026-06-04, code-only items)
- **D3 H3 false-ready FIXED** — added a `kernelReady` flag distinct from `thebelabBootstrapped`; the
  bootstrapOnce short-circuit now broadcasts 'ready' only if a kernel actually connected, else 'connecting'.
  Reset on race-retry, kernel-death, and resetModuleState. (ExecutableCode/index.tsx)
- **D6 workflow nits FIXED (2 real bugs):** workshop-monitor + workshop-close `grep -c || echo 0` →
  `|| true` + `:-0` default (was producing "0\n0" → false restart reports / corrupt GITHUB_OUTPUT);
  ce-monitor CPU parse now normalizes decimals + millicpu via awk (was false-flagging 0.5/250m as
  oversized). refresh-page-dates `[ci]` LEFT AS-IS — its header documents it intentionally triggers
  deploy to ship new dates (not a bug).
- **status.json de-dup (partial, the high-value part):** bootstrap-passage-hashes migrated to
  `_common.load_status/save_status` — fixes its latent missing-file crash (it had no exists() guard).
  The other 6 scripts already handle missing-file correctly; `_common` now provides the canonical helpers
  for incremental migration (left to avoid churning 6 working pipeline scripts). +2 tests (40 total).
- **S1 encryption-at-rest → REJECTED as infeasible, S1 CLOSED.** Any cross-subdomain-working key must be
  readable by all subdomains' JS (zero protection vs the same-origin-XSS threat); a per-origin
  non-extractable key can't decrypt the IBM token on other language subdomains (breaks the cross-subdomain
  UX requirement). So encryption would be theater AND break the requirement. Documented in the tracker as
  an accepted product tradeoff. Revisit only if cross-subdomain sharing is ever dropped.
- Verification: tsc 0 errors, 40 tests pass, EN build green, all scripts/YAML parse.

### Remaining open items (need live site / your decision — NOT code-fixable here)
- **Live verification** (`.claude/D3_LIVE_VERIFICATION_CHECKLIST.md`): the frontend half (A1-A5, B7-B9, B12)
  is runnable via `/verify` or cowork against `docusaurus start`; the CE-pod-under-load half (F1 connect-
  storm @80 users, connections_dict creep reproduction, CORS-vs-subdomain) needs IBM Cloud creds + a
  deployed pod / the `stress-test.yml` workflow — your infra.
- **Decisions:** enable the weekly sync-upstream schedule (offset cron first); re-run the notebook sweep
  (~28 broken, needs Docker/execution); the 6 remaining status.json migrations (low-risk cleanup).

### Cross-domain dialect note (out-of-scope but logged)
The 9 German dialects carry real structural debt: freshness shows 13–28 CRITICAL files each
(missing `TutorialFeedback` import) + 5 STALE index files. Low-prio per project policy, but it's
the bulk of the 840 broken-image and the build-OOM tail. Worth a future dialect-refresh pass.

---

### Suggested execution order
1. **Build + sweep first** (Domain 1 #5, #1) — establishes a clean baseline and surfaces
   the most broken things cheaply.
2. **Validators + coverage reconciliation** (Domain 2 #6, #7) — your biggest surface,
   mostly automatable.
3. **Security + execution smoke** (Domains 3–4) — user-facing correctness + safety.
4. **Code review + the test-suite gap** (Domain 7) — the durable structural fix.
5. **UX/a11y/SEO, infra, licensing** (Domains 5, 6, 8) — polish and confirmation.

Domains 1, 2, 7-#26 are where a review is most likely to find *real, actionable* problems;
the rest is largely confirmation given how much has already been hardened.
