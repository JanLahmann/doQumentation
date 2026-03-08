# doQumentation — Full Project Review

> Generated 2026-03-07 | Covers entire codebase, not just branch changes
>
> Findings are grouped by area, then sorted by severity.
> Each item has a checkbox for tracking fixes.

---

## Scoreboard

| Severity | Count | Fixed in this branch | Remaining |
|----------|------:|---------------------:|----------:|
| Critical |     2 |                    2 |         0 |
| High     |     4 |                    2 |         2 |
| Medium   |    30 |                   21 |         9 |
| Low      |    37 |                   33 |         4 |
| **Total**| **71**|               **56** |    **15** |

---

## 1  Binder / Code Engine Infrastructure

### 1.1  SSE Build Server (`binder/sse-build-server.py`)

- [ ] **HIGH** SSE-1: Token sent in plaintext over SSE `ready` event (line 82). If the CORS origin site is XSS'd, the token is exfiltrated immediately. *Consider short-lived scoped tokens instead of the main Jupyter token.*
- [x] **MEDIUM** SSE-2: `HTTPServer` is single-threaded (line 105). One slow/malicious client blocks all other SSE requests for up to 30s (the health-poll timeout). *Switch to `ThreadingHTTPServer`.* **FIXED**
- [x] **LOW** SSE-3: `BrokenPipeError` not caught in `_send_event` / `do_GET`. Client disconnect mid-stream produces unhandled traceback. *Wrap writes in try/except for `BrokenPipeError`, `ConnectionResetError`.* **FIXED**
- [x] **LOW** SSE-4: `do_OPTIONS` responds with CORS headers for any path (line 90), unlike `do_GET` which checks `/build`. *Add the same path check.* **FIXED**
- [x] **LOW** SSE-5: No graceful shutdown handler. SIGTERM from supervisord abruptly kills in-flight SSE connections. *Add `signal.signal(SIGTERM, lambda: server.shutdown())`.* **FIXED**
- [x] **LOW** SSE-6: `log_message` overridden to no-op (line 98). All HTTP logging silently dropped — makes debugging and auditing impossible. *At minimum log errors; suppress only health-check GETs.* **FIXED**

### 1.2  Entrypoint (`binder/codeengine-entrypoint.sh`)

- [ ] **HIGH** ENT-1: XSRF protection globally disabled (generated config line 59: `disable_check_xsrf = True`). Comment says thebelab 0.4.0 requires it. *Investigate thebe >=0.5 XSRF support, or scope exemption to specific API paths.*
- [x] **MEDIUM** ENT-2: `allow_remote_access = True` + empty password (lines 49-51). Security relies entirely on the token. Minimum token length is only 8 chars. *Consider raising minimum to 32 chars for user-supplied tokens.* **FIXED**

### 1.3  nginx (`binder/nginx-codeengine.conf`)

- [x] **MEDIUM** NGX-1: No rate limiting on `/lab`, `/terminals/`, `/user/`, `/static/`, or default `/` locations. Only `/build/` and `/api/` are protected. *Add rate limits to at least `/lab` and `/terminals/`.* **FIXED**
- [x] **MEDIUM** NGX-2: Missing `Content-Security-Policy` and `Strict-Transport-Security` headers (lines 10-12 only have X-Content-Type-Options, X-Frame-Options, Referrer-Policy). *Add CSP and HSTS (if HTTPS guaranteed by Code Engine).* **FIXED**
- [x] **LOW** NGX-3: `client_max_body_size` not set. Default is 1MB — may silently reject large notebook uploads. *Set explicitly (e.g. `10m`) to make the limit intentional.* **FIXED**

### 1.4  Dockerfile (`binder/Dockerfile.codeengine`)

- [x] **MEDIUM** DOC-1: No `autorestart=true` in supervisord config (lines 67-88). If nginx, Jupyter, or SSE crashes, the process stays dead while the container continues running. *Add `autorestart=true` and `startretries=3` to each `[program:*]`.* **FIXED**
- [ ] **LOW** DOC-2: Binder Dockerfile (`binder/Dockerfile`) uses rolling `python-3.12` tag while Code Engine Dockerfile uses pinned `2025-01-27`. Environments can silently diverge. *Pin both to the same date-based tag.*
- [x] **LOW** DOC-3: `COPY . /home/jovyan/` in `binder/Dockerfile` (line 13) copies entire build context. If `.dockerignore` is missing or incomplete, `.git`, secrets, etc. end up in the image. *Verify `.dockerignore` excludes `.git`, `.env`, `*.key`.* **FIXED**

### 1.5  Dependencies (`binder/jupyter-requirements.txt`)

- [x] **MEDIUM** DEP-1: `pylatexenc` and `pandas` have no version pins (lines 29-30). Non-reproducible builds. *Add version pins: `pylatexenc~=2.10`, `pandas~=2.2`.* **FIXED**

---

## 2  Frontend — Config Layer (`src/config/`)

### 2.1  Security

- [x] **HIGH** CFG-1: XSS in `makeTabHtml` (jupyter.ts:563). `title` and `initialPhase` are interpolated into raw HTML via template literals. Currently only called with hardcoded strings, but one future caller with user input = XSS. *HTML-escape inputs, or use `textContent` assignment.* **FIXED**
- [ ] **MEDIUM** CFG-2: Token exposed in URL query string (`?token=...`) in `getLabUrl` (line 421) and `openBinderLab` (line 635). Tokens in URLs leak via browser history, Referer headers, and proxy logs. *Document as accepted risk or pass token via header.*
- [ ] **MEDIUM** CFG-3: Hardcoded default token `'rasqberry'` (line 136). Anyone on the same LAN can access the Jupyter server. *Prompt user to set a custom token on first use.*
- [ ] **MEDIUM** CFG-4: Tokens stored in localStorage in plaintext (lines 243-246, 272-273). Any XSS or browser extension can exfiltrate. *Consider `SubtleCrypto` encryption at rest, or `HttpOnly` cookies.*
- [x] **MEDIUM** CFG-5: No URL validation on URLs loaded from storage for `customUrl`/`ceUrl` (lines 69, 83). A stored XSS could inject `javascript:` URLs. *Validate protocol is `http://` or `https://`.* **FIXED**

### 2.2  Logic Bugs

- [x] **MEDIUM** CFG-6: Private IP range `172.*` detection is too broad (line 124). RFC 1918 is `172.16.0.0/12` (172.16-172.31), but `hostname.startsWith('172.')` matches all of `172.0.0.0/8`. Public IPs in `172.0-172.15` would falsely trigger rasqberry mode. *Parse second octet and check `>= 16 && <= 31`.* **FIXED**
- [x] **MEDIUM** CFG-7: `getIBMQuantumCRN` does not call `checkCredentialExpiry()` (line 230), unlike `getIBMQuantumToken` which does (line 225). Callers reading CRN without first reading token can get expired CRN. *Add `checkCredentialExpiry()` call.* **FIXED**
- [x] **MEDIUM** CFG-8: `ensureBinderSession` EventSource has no timeout (lines 507-531). If the Binder build hangs indefinitely, the Promise never resolves/rejects. *Add a 20-minute timeout that closes EventSource and rejects.* **FIXED**
- [x] **LOW** CFG-9: `getCredentialTTLDays` doesn't validate stored value (line 200). `Number(stored)` can return NaN, Infinity, or negative. *Clamp: `isFinite(n) && n >= 1 && n <= 365 ? n : DEFAULT`.* **FIXED**
- [x] **LOW** CFG-10: `saveCodeEngineCredentials` silently drops empty token (line 273). `if (token)` means passing `''` leaves a stale old token in storage. *Always write or explicitly `removeItem` when falsy.* **FIXED**
- [x] **LOW** CFG-11: `testJupyterConnection` fetch has no `AbortController` timeout (line 386). Misconfigured URL hangs for browser default (5+ min). *Add 15s abort.* **FIXED**
- [x] **LOW** CFG-12: `getColabUrl` duplicates path-mapping logic from `mapBinderNotebookPath` (lines 680-681). If one is updated without the other, URLs diverge. *Refactor to share.* **FIXED**

### 2.3  Type Safety

- [x] **LOW** CFG-13: `getSimulatorBackend` casts any string from storage to `SimulatorBackend` without validation (line 321). *Validate against known values.* **FIXED**
- [x] **LOW** CFG-14: `getActiveMode` same issue (line 360). *Validate against known values.* **FIXED**

### 2.4  i18n

- [ ] **MEDIUM** CFG-15: `BINDER_TAB_PHASE_HINTS` and `CE_TAB_PHASE_HINTS` (lines 546-560) are hardcoded English. *Accept translated strings or locale parameter.*
- [ ] **MEDIUM** CFG-16: `makeTabHtml` warning text and tab title (lines 574-576) are hardcoded English. *Pass translated strings.*
- [ ] **MEDIUM** CFG-17: `openBinderLab` error messages written to popup tab DOM (lines 648-650) are hardcoded English. *Pass translated strings.*
- [x] **LOW** CFG-18: `testJupyterConnection` result messages (lines 395-407) are hardcoded English. *Return structured data, let UI translate.* **FIXED**

### 2.5  Storage Layer (`src/config/storage.ts`)

- [x] **LOW** STO-1: Module-level mutable `cache` (line 19) goes stale if another tab modifies localStorage. *Listen for `storage` events to invalidate.* **FIXED**
- [x] **LOW** STO-2: `migrateLocalStorageToCookies` logs untranslated English via `console.debug` (line 212). *Gate behind `__DEV__` check.* **FIXED**

### 2.6  Preferences (`src/config/preferences.ts`)

- [x] **MEDIUM** PRF-1: Unbounded growth of `visited-pages` and `executed-pages` sets (lines 62-64). On a large site with long-lived users, this can exceed cookie chunk limits or localStorage quotas. *Add max size with LRU eviction.* **FIXED**
- [x] **LOW** PRF-2: `normalizePath` docstring says "lowercase" but implementation doesn't (line 413). *Fix docstring.* **FIXED**
- [x] **LOW** PRF-3: `JSON.parse` of storage data at lines 46, 227, 297, 338, 350 lacks schema validation. Corrupted storage can cause runtime errors. *Add `Array.isArray()` checks after parsing.* **FIXED**
- [x] **LOW** PRF-4: `clearRecentPages` also clears `KEY_LAST_PAGE` data (line 360). Name doesn't reflect this. *Rename or split.* **FIXED**

---

## 3  Frontend — ExecutableCode Component

### 3.1  React / Lifecycle

- [x] **MEDIUM** EXE-1: `setTimeout` in conflict/injection event handlers (lines 964, 977) never cleaned up on unmount. Causes `setState` on unmounted component. *Store timer IDs in refs, clear in useEffect cleanup.* **FIXED**
- [ ] **MEDIUM** EXE-2: Module-level mutable state (`thebelabBootstrapped`, `activeKernel`, etc., lines 54-85) persists across SPA navigations. No reset on page change. *Add page-navigation cleanup hook or wrap in singleton class.*
- [x] **MEDIUM** EXE-3: Race condition in `bootstrapOnce` (line 773). `thebelabBootstrapped` is set inside deferred `doBootstrap` after `setTimeout`. Two rapid clicks can trigger duplicate Binder builds. *Set "in-progress" flag synchronously at start of `bootstrapOnce`.* **FIXED**
- [x] **LOW** EXE-4: `handleReset` not wrapped in `useCallback` (line 1005), unlike all other handlers. Causes unnecessary button re-renders. *Wrap in `useCallback([], ...)`.* **FIXED**
- [ ] **LOW** EXE-5: `isFirstCell` determined once on mount via DOM query (line 882), never updated. If components mount/unmount dynamically, it goes stale. *Use shared React context or MutationObserver.*
- [x] **LOW** EXE-6: `doBootstrap` retries via `setTimeout(tryBootstrap, 500)` with no max retry limit (line 675). If CDN never loads, polls indefinitely. *Add retry counter or 30s total timeout.* **FIXED**

### 3.2  Accessibility

- [x] **MEDIUM** EXE-7: Conflict banner and injection toast (lines 1218, 1236) lack `role="alert"` or `aria-live`. Screen readers won't announce these dynamic notifications. *Add `role="alert"` or `aria-live="assertive"`.* **FIXED**
- [ ] **LOW** EXE-8: Cell execution status indicated only by border color (running=amber, done=green, error=red). No text/icon on the cell itself. Toolbar legend has text labels which is good. *Consider adding subtle icons to cells.*

### 3.3  i18n

- [x] **MEDIUM** EXE-9: `window.confirm` at line 1009 uses hardcoded English string. Other confirms at 1036 and 1044 correctly use `translate()`. *Wrap in `translate()`.* **FIXED**
- [x] **MEDIUM** EXE-10: `showErrorHint` (lines 149-164) builds DOM with hardcoded English: "Kernel disconnected", "Back", "Run", "to reconnect", "is not defined. Run the cells above first...". *Use `translate()` for each fragment.* **FIXED**
- [x] **MEDIUM** EXE-11: `handlePipInstall` button text (lines 176, 184, 202) — "Installing...", "Installed", "Install failed" — hardcoded English. *Use `translate()`.* **FIXED**

### 3.4  Code Quality

- [x] **LOW** EXE-12: `handleReset` and `handleClearSession` (lines 1005-1033 vs 1043-1058) duplicate cleanup of module-level state. *Extract `resetModuleState()` helper.* **FIXED**
- [x] **LOW** EXE-13: Safety-net timer uses magic number `60000` (line 324). *Extract to named constant.* **FIXED**
- [x] **LOW** EXE-14: `discoverFakeBackends` swallows all errors silently (line 606). *Add `console.debug` for dev troubleshooting.* **FIXED**
- [x] **LOW** EXE-15: `thebeContainerRef` created at line 873 but never read. *Remove if unused.* **FIXED**
- [x] **LOW** EXE-16: pip install validation duplicated in two places (lines 112, 174). *Extract single `isValidPackageName()` helper.* **FIXED**

---

## 4  Frontend — Settings Page (`src/pages/jupyter-settings.tsx`)

### 4.1  Security

- [x] **LOW** SET-1: `handleCeTest` (line 326) doesn't validate URL protocol before `fetch()`. The `handleCeSave` function validates HTTPS but the test button doesn't. *Share the URL validator.* **FIXED**

### 4.2  React / UX

- [ ] **MEDIUM** SET-2: Component has ~18 `useState` hooks (lines 138-177). Should be broken into sub-components (IBMQuantumSection, CodeEngineSection, SimulatorSection, etc.) for maintainability and render performance. *Refactor into sections.*
- [x] **LOW** SET-3: `backendsByQubits` Map recomputed on every render (lines 370-377). *Wrap in `useMemo(() => ..., [fakeBackends])`.* **FIXED**
- [x] **LOW** SET-4: Category capitalization at line 943 (`cat.charAt(0).toUpperCase()`) assumes English. *Use locale-aware methods or i18n.* **FIXED**

### 4.3  CSS / Accessibility

- [x] **MEDIUM** CSS-1: Toggle checkbox has no `:focus-visible` style on the track element (`custom.css` line 818). Hidden input with `opacity: 0` loses keyboard focus indicator. *Add focus-visible outline on `.jupyter-settings__toggle-track`.* **FIXED**
- [x] **LOW** CSS-2: Hardcoded hex colors for mode badges/toast/banner (custom.css lines 738-795) instead of CSS custom properties. *Define as `:root` variables.* **FIXED**
- [x] **LOW** CSS-3: `.jupyter-settings { max-width: none }` (custom.css line 660) — text lines too long on wide screens. *Add `max-width: 900px`.* **FIXED**
- [x] **LOW** CSS-4: No `@media` mobile breakpoints for settings form inputs. Button containers use inline `flexWrap` which provides basic wrapping. *Add explicit mobile styles.* **FIXED**

---

## 5  CI/CD & Build (`/.github/workflows/`, `docusaurus.config.ts`)

### 5.1  Supply Chain

- [x] **HIGH** CI-1: `aquasecurity/trivy-action@master` in `codeengine-image.yml:53` — pinned to mutable `master` branch. Most dangerous: any commit to that repo's main branch runs in your CI. *Pin to SHA.* **FIXED**
- [x] **MEDIUM** CI-2: All 7 workflows use tag-only action refs (`@v4`, `@v3`, etc.) — no SHA pinning. Third-party `peter-evans/create-pull-request@v7` in `sync-deps.yml:31` is highest risk. *Pin all to full commit SHAs.* **FIXED**
- [ ] **MEDIUM** CI-3: thebelab loaded from unpkg.com CDN at runtime without SRI hash (docusaurus.config.ts:133). KaTeX stylesheet has SRI — thebelab should too. *Add `integrity` attribute or self-host.*

### 5.2  Permissions & Config

- [x] **MEDIUM** CI-4: `binder.yml` and `codeengine-image.yml` have no `permissions` block. Default token gets broad permissions on push triggers. *Add explicit least-privilege `permissions: {}`.*  **FIXED**
- [x] **MEDIUM** CI-5: Trivy scan `exit-code: 0` (codeengine-image.yml:57) — vulnerabilities never fail the build. *Change to `exit-code: '1'`.*  **FIXED**
- [x] **LOW** CI-6: `onBrokenLinks: 'warn'` (docusaurus.config.ts:20) — broken links ship silently. *Change to `'throw'`.* **FIXED**
- [x] **LOW** CI-7: `onBrokenMarkdownLinks` not set — defaults to `'warning'`. *Add `onBrokenMarkdownLinks: 'throw'`.* **FIXED**
- [ ] **LOW** CI-8: `git push --force` to `notebooks` branch (deploy.yml:69). Overlapping runs can lose history. *Accepted if concurrency controls are sufficient.*

---

## 6  Previously Fixed (this branch)

For reference, these were already addressed:

| # | Severity | Fix |
|---|----------|-----|
| 1-2 | Critical | SSE CORS wildcard, CORS_ORIGIN injection into Python config |
| 3-6 | High | Health check static 200, SSE server readiness check, CORS_ORIGIN validation |
| 9 | Medium | Missing proxy headers on `/terminals/` |
| 10 | Medium | Token printed in full to container logs |
| 11-12 | Medium | Binder-specific labels for Code Engine |
| 13-14 | Medium | No URL validation on CE credential save |
| 15 | Medium | CRN not validated |
| 16 | Medium | No nginx rate limiting |
| 20-21 | Low | Inconsistent inline environment checks / duplicate translation IDs |
| 22 | Low | Dead `ibmExpiredNotice` state |
| 23 | Low | Container runs as root |
| 24 | Low | No image vulnerability scanning in CI |

---

## Recommended Fix Order

**Sprint 1 — Security quick wins (high impact, small changes):**
1. CI-1: Pin `trivy-action` to SHA (1 line)
2. CI-2: Pin all third-party actions to SHA (grep + replace)
3. CI-4: Add `permissions` blocks (3 lines each)
4. CI-5: Change Trivy `exit-code` to 1 (1 line)
5. CFG-7: Add `checkCredentialExpiry()` to `getIBMQuantumCRN` (1 line)
6. CFG-6: Fix 172.* range check (5 lines)

**Sprint 2 — Reliability & architecture:**
7. SSE-2: Switch to `ThreadingHTTPServer` (1 line)
8. DOC-1: Add `autorestart=true` to supervisord (3 lines)
9. EXE-3: Fix bootstrap race condition (add guard flag)
10. EXE-1: Fix setTimeout leak on unmount (refs + cleanup)
11. CFG-8: Add EventSource timeout (10 lines)

**Sprint 3 — i18n & accessibility:**
12. EXE-9 + EXE-10 + EXE-11: Translate hardcoded English strings
13. CFG-15 + CFG-16 + CFG-17: Translate tab/popup strings
14. EXE-7: Add `role="alert"` to dynamic banners
15. CSS-1: Add `:focus-visible` to toggle track

**Sprint 4 — Code quality & defense in depth:**
16. Everything else (LOW items)
