# doQumentation — File Review & Cleanup Plan

**Date:** 2026-06-04
**Scope reviewed:** All project-authored files — `scripts/`, `translation/` tooling, `src/`, `.github/`, `ci/`, `binder/`, `plugins/`, root config & docs, `.claude/` corpus (tracked + local-only), and gitignored build artifacts.
**Out of scope (not reviewed):** `i18n/` translations, upstream content (`docs/guides|learning|tutorials|qiskit-addons`, `upstream-docs/`, `upstream-addons/`).

**Status:** APPROVED — executing in batches. Decisions locked 2026-06-04 (see below).

**Your decisions (2026-06-04):**
- Historical standalone docs → **delete** (git retains them).
- `PROJECT_HANDOFF.md` → **slim**, move history into `PROJECT_HANDOFF_ARCHIVE.md`.
- **§A1 → option (a):** delete `Dockerfile.web`, repoint compose `web` service to `Dockerfile.jupyter` target `jupyter-local`.
- **§A3:** Qiskit Addons hidden from menu is **intentional** — keep/clarify the claim, don't "un-hide". (Config already documents this at `docusaurus.config.ts:299-300`.)
- **§B:** delete one-shot migrations whose result is now permanent.
- **§C/§D/§E:** approved as written (with the read-first/reconcile guards).
- **§F:** approved. **F3 → KEEP `translation-prompt-web.md`** — the large-`Write` limitation in the web UI still bites.

---

## Headline findings

1. The **code** (`src/`, workflows, plugins) is *clean* — every component, client module, config, plugin, and workflow is wired in. **Zero dead code found.** No action needed there beyond two small config fixes below.
2. The **cruft is concentrated** in: (a) one orphaned/broken Docker path, (b) finished one-off scripts, (c) stale translation-draft scaffolding, and (d) the historical-doc backlog in `.claude/`.
3. The **translation tooling** is a live, coherent pipeline — but the **prompt/instruction markdown duplicates a big "Language Table"** across 4 files, and a few **point-in-time review artifacts** sit in the working tree.
4. A handful of **doc references are stale** (dangling `completed-features.md`, `Dockerfile.web` described as if built, addons-navbar claim).

Estimated net effect: ~**40–60 files removed/relocated** (mostly empty dirs + obsolete metadata), **2 config fixes**, **1 doc-dedup refactor**, **1 handoff slim**. No behavior change to the site or pipeline.

---

## A. Broken / incorrect — fix regardless of cleanup appetite

These are genuine defects, not just tidiness.

- [ ] **A1. `Dockerfile.web` is orphaned + `docker-compose.yml` `web` service is broken.**
  `docker-compose.yml`'s `web` service uses `build: .`, but there is **no root `Dockerfile`** — only `Dockerfile.web` and `Dockerfile.jupyter`. `docker compose --profile web up` fails. Nothing (no workflow, no compose file) ever builds `Dockerfile.web`; `docker.yml`'s `build-lite` actually uses `Dockerfile.jupyter --target jupyter-local` ([.github/workflows/docker.yml:94-95](.github/workflows/docker.yml#L94-L95)). `Dockerfile.web` is referenced **only in prose** (README:147, PROJECT_HANDOFF:174/231).
  **Options — pick one:**
  - **(a) Delete `Dockerfile.web`** and repoint the compose `web` service to `dockerfile: Dockerfile.jupyter, target: jupyter-local` (the jupyter target already serves the static site via nginx). Simplest; one image to maintain.
  - **(b) Keep `Dockerfile.web`** but fix the compose service to `build: {context: ., dockerfile: Dockerfile.web}` so the "static-only, 60 MB" path actually works.
  - Then update the README/handoff lines to match whichever you choose.
  *Recommendation: (a)* — the lite image isn't built by any workflow, so maintaining a second Dockerfile earns nothing.

- [ ] **A2. Dangling memory/doc reference: `.claude/completed-features.md` does not exist.**
  Referenced by auto-memory (`MEMORY.md`) and implied by PROJECT_HANDOFF. The content actually lives inline in `PROJECT_HANDOFF.md`. **Fix:** correct the memory line (point to the handoff section) — I'll update `MEMORY.md` and the relevant memory file. No file to create.

- [ ] **A3. Verify + correct the "Qiskit Addons hidden from navbar" claim** (PROJECT_HANDOFF.md:22). `docs/qiskit-addons/` is built (12 tracked pages). I'll check current `docusaurus.config.ts`/`sidebars.ts` and correct the line to match reality.

---

## B. Obsolete one-off / completed scripts (delete — git retains)

All confirmed **not invoked by any workflow, compose file, or other script** (only self-references or historical mentions in handoff). These were migrations/one-shots whose job is done.

- [ ] **B1. `translation/scripts/backfill-en-base-date.py`** — one-shot backfill of `en_base_commit_date` into `status.json`; field is now auto-populated at promotion. Only self + a historical PROJECT_HANDOFF mention. **Delete.**
- [ ] **B2. `scripts/migrate_output_imgs.py`** — one-shot addon-image migration (done; handoff lists it as migration-only). **Delete.**
- [ ] **B3. `__pycache__/` dirs** (4: `scripts/`, `binder/`, `translation/scripts/`, `scripts/notebook-sweep/`) — untracked local bytecode, already gitignored. **`rm -rf`** (cosmetic; never committed).

**Keep (do NOT delete) — verified still referenced, correcting an earlier mis-call:**
- ✅ `translation/scripts/get-register-fails.py` — **live helper**, referenced by the active `register-fix-prompt.md:286`. Keep.
- ✅ `translation/scripts/fix-tutorialfeedback-import.py`, `fix-heading-anchors.py`, `bootstrap-passage-hashes.py` — repair/re-baseline tools that may be needed again. Keep.
- ✅ `scripts/setup-pi.sh`, `scripts/ibmcloud-spending-limit.sh`, `scripts/generate-transcripts.py`, `scripts/translate-transcripts.py`, `scripts/encrypt-for-admin.mjs`, `scripts/notebook-sweep/*` — manual utilities still useful (Pi deploy, spending check, transcript regen, admin-URL encrypt used by `deploy.yml`, the notebook sweep). Keep. *(Optional: relocate the truly-manual ones to a `scripts/tools/` subfolder for clarity — low value, listed in §F.)*

---

## C. Stale translation-draft scaffolding (delete)

The current pipeline edits `i18n/` directly via git-diff hunk-splice; the old `drafts/` → `promote` flow is deprecated (per `CONTRIBUTING-TRANSLATIONS.md`). What remains under `translation/drafts/` is leftover scaffolding.

- [ ] **C1. 22 empty `.gitkeep`-only directories** under `translation/drafts/pl/learning/...` — placeholders from the abandoned draft layout, no content. **Delete the dirs.**
- [ ] **C2. Orphaned single draft file** `translation/drafts/pl/learning/courses/utility-scale-quantum-computing/bits-gates-and-circuits.mdx` — a lone leftover draft (pl is otherwise direct-to-i18n). Confirm it's superseded by the promoted `i18n/pl/...` version, then **delete**.
- [ ] **C3. Per-locale draft metadata** — `translation/drafts/{ar,cs,de,es,fr,pl,ro,th}/_feedback.md`, plus `cs/{_batches.json,_remaining.json}` — obsolete bookkeeping from the old batch pipeline. **Delete** (recoverable from git).
  - ⚠️ *Judgment point:* the `_feedback.md` files may contain per-locale linguistic notes you'd want to retain as reference. I'll **show you each `_feedback.md`'s first lines before deleting** so you can rescue any that still carry useful guidance into memory.

---

## D. Point-in-time review reports (delete per your call — but read first)

You chose "delete historical docs." These are accurate but describe finished review passes. I'll **delete**, with a pre-delete summary so nothing valuable is lost silently.

- [ ] **D1. `translation/drafts/de/linguistic-review-2026-03-28.md`**, **`translation/drafts/fr/linguistic-review.md`**, **`translation/reviews/it-linguistic-review.md`** — dated linguistic-review write-ups; verdicts now tracked in `status.json`. **Delete.**
- [ ] **D2. `.claude/PHASE_4_LINGUISTIC_TRIAGE_2026-05-07.md`** — May-7 triage; residual work is captured in memory + handoff TODOs. **Delete** *(but see caveat: it lists specific residual per-locale items — TL workshop/03, AR diagonalization. I'll confirm those are in memory before deleting so the open items aren't dropped.)*
- [ ] **D3. `.claude/NOTEBOOK_SWEEP_PLAN.md`** (the *plan*, marked COMPLETE) — the *findings* live in root `notebook-sweep-report.md` (keep that) and the methodology lives in `scripts/notebook-sweep/README.md` (keep that). The plan doc is redundant. **Delete.**

**Keep:**
- ✅ `notebook-sweep-report.md` (root) — live findings list; still drives open notebook fixes.
- ✅ `scripts/notebook-sweep/README.md` — how to re-run the sweep.

---

## E. `.claude/` doc consolidation

- [ ] **E1. Slim `PROJECT_HANDOFF.md`** (593 lines → ~400). Move the "Recently Resolved (Apr–May 2026)" narrative (~35%) into `PROJECT_HANDOFF_ARCHIVE.md`; keep What-it-is / Architecture / Features / Structure / Development / **Open Items** / Future Ideas live. This is the one place you asked to *archive* rather than delete.
- [ ] **E2. `.claude/PROJECT_REVIEW.md`** (code-review snapshot, Mar 7; 65/71 items fixed). Its still-open items are security findings already migrated to `SECURITY_REVIEW_2026-05.md` and the settings refactor (`plans/simplify-settings.md`). Per "delete historical": **delete**, after I confirm no *unmigrated* open finding is lost. ⚠️ *I found a discrepancy:* PROJECT_REVIEW marks CI pinning FIXED, but `SECURITY_REVIEW_2026-05.md` lists S6 (CI unshipped-pins) as **open** — I'll reconcile that into the security tracker before deleting the review.
- [ ] **E3. Leave as-is (KEEP-LIVE):** `README.md`, `NOTICE`, `LICENSE`, `LICENSE-DOCS`, `AI_FEATURES_BRAINSTORMING.md`, `transcript-status.md`, `plans/simplify-settings.md`, `plans/workshop-mode-codeengine.md`, `ORG_MIGRATION_PLAN.md` (local), `SECURITY_REVIEW_2026-05.md` + the two `BOB_*` evidence appendices (local). These are current or actionable.
  - *Minor:* once the GH-org migration (PRIO-1) actually executes, `ORG_MIGRATION_PLAN.md` + the `BOB_*`/`SECURITY_*` appendices become archive candidates — not now.

---

## F. Translation prompt/doc de-duplication — SKIPPED (premise was wrong)

**Resolution (2026-06-04): do not refactor.** Investigation showed the "Language
Table duplication" is actually **four purpose-built variants**, not copy-paste:
- `translation-prompt.md` — terse 18-locale reference table + the unique Japanese nakaguro rule.
- `register-fix-prompt.md` — detailed German **verb-conjugation find-replace rules** (Sie→du, `Verwenden Sie`→`Verwende`) + 4 German dialects, found nowhere else.
- `review-prompt.md` — 16 locales with **review-specific flag lists** (what to catch).
- `review-tier3-rubric.md` — intentional 11-locale subset, **hard-coded by path in `review-build-batches.py:25`**.

Merging would *lose* content and break a live script. Additionally,
`review-tier4-opus-prompt.md` + `translation/reviews/opus-20260604*.json` are
**another developer's active work in this exact area (dated 2026-06-04)** — not
to be disturbed. `review-instructions.md` is also NOT a redundant pointer: it
carries a genuine simple-path "how a full review works" tier walkthrough +
`review-translations.py` commands not duplicated in `review-tier3-workflow.md`.

**F3 (`translation-prompt-web.md`): KEEP** — the large-`Write` web-UI limitation
still bites (user-confirmed). It stays as the web variant.

→ No changes made in §F.

---

## G. Explicitly KEEP (verified load-bearing — no action)

Captured so we don't re-litigate these:

- **All of `src/`** — 45 files, every component/clientModule/theme override/page/config is imported or registered. (`TutorialFeedback` is an intentional `return null` stub kept for 56 EN docs that still import it inline — removing the inline calls is an *optional* future content pass, not cleanup.)
- **All 19 workflows** in `.github/workflows/` — each triggered and references existing scripts. Coherent set (deploy / sync / notebook-CI / workshop-ops / monitoring).
- **Both `plugins/`** (`hreflang`, `page-dates`) — registered in `docusaurus.config.ts`.
- **`local-content/` and `workshop-notebooks/`** — actively consumed by `scripts/sync-content.py` and `notebook-ci.yml`/`ci/`. **Not cruft.**
- **`binder/` runtime files** (`Dockerfile`, `codeengine-entrypoint.sh`, `nginx-codeengine.conf`, `sse-build-server.py`, the 3 `jupyter-requirements*.txt`) — all copied into `Dockerfile.jupyter` / used by deploy.
  - [ ] *one tiny candidate:* `binder/requirements.txt` is a stub comment pointing at `jupyter-requirements.txt`. Harmless; delete only if you want zero stubs. (Low priority.)
- **Translation core pipeline** (~15 scripts: sync/update/validate/lint/promote/status/freshness/passage_units + review-prefilter/build-batches/translations) and the 4 status/hash files (`status.json`, `STATUS.md`, `baseline-hashes.json`, `en-passage-hashes.json`) — distinct roles, no duplication.
- **`ci/`** (list-notebooks, skip-list, runtime patch, rubric) — used by notebook CI.

---

## Suggested execution order (once you approve items)

1. **§A** fixes (broken compose/Dockerfile, dangling refs) — correctness.
2. **§B + §C + §D** deletions — safe, after the per-file "read-first" confirmations noted inline.
3. **§E** doc slim/consolidate.
4. **§F** prompt de-dup (last, most careful).

I'll do nothing until you say which items (or sections) to run. I can execute them in batches and report per batch.
