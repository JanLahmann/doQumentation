# doQumentation — Feature Test Checklist

Manual testing checklist for verifying all implemented features.
Test on the live site (doqumentation.org) or local dev server (`npm start`).

> **Tip**: Clear localStorage before a full test run to start fresh:
> DevTools → Application → Local Storage → Clear All
> Or: Settings page → "Clear All Preferences"

---

## 1. Homepage

| # | Test | Expected |
|---|------|----------|
| 1.1 | Load `/` | Hero banner with "doQumentation" title, subtitle, and stats bar (42 / 171 / 154 / 14) |
| 1.2 | Click each stat in the stats bar | Navigates to correct section (Tutorials / Guides / Courses / Modules) |
| 1.3 | "See all features" link | Navigates to `/features` |
| 1.4 | Simulator callout card visible | "No IBM Quantum account? Enable Simulator Mode..." with link to Settings |
| 1.5 | Tutorial cards present | At least 3 tutorial cards + "Basics of QI" course card + Hello World guide |
| 1.6 | `<details>` blocks expand/collapse | "Available execution backends", "Deployment options", "Run locally..." |
| 1.7 | "Browse all Guides" / module links work | Navigate to correct sidebar sections |
| 1.8 | Mobile: hero stacks vertically | Resize to ~375px width — no horizontal overflow |
| 1.9 | ResumeCard appears after visiting a doc page | Visit any tutorial, return to `/` — "Continue where you left off" card with page title + time ago |
| 1.10 | RecentPages widget appears | After visiting 2+ pages, homepage shows "Recently viewed" with up to 5 links |
| 1.11 | RecentPages excludes homepage & settings | Visit `/` and `/jupyter-settings` — they should NOT appear in recent pages |

## 2. Navigation & Sidebar

| # | Test | Expected |
|---|------|----------|
| 2.1 | Navbar items | Tutorials · Guides · Courses · Modules · API Reference · Settings · GitHub icon · dark mode toggle |
| 2.2 | Navbar always dark | Switch between light/dark mode — navbar background stays `#161616` |
| 2.3 | GitHub icon | Octocat SVG, links to repo, light-colored in dark navbar |
| 2.4 | Dark mode toggle | Sun/moon icon, light-colored, toggles site theme |
| 2.5 | Settings link | Navigates to `/jupyter-settings`, text says "Settings" |
| 2.6 | API Reference | External link to `https://docs.quantum.ibm.com/api` |
| 2.7 | Navbar links don't wrap | At ~900px width, links stay on one line (nowrap) |
| 2.8 | Mobile hamburger menu | At <768px: hamburger icon visible with border/background; opens sidebar |
| 2.9 | Sidebar categories collapsible | Click category header → collapses/expands child items |
| 2.10 | Sidebar collapse memory | Collapse "Tutorials" → navigate away → come back → still collapsed |
| 2.11 | Sidebar top-level categories styled | 1.1rem font size, semibold weight |
| 2.12 | Tutorials & Courses collapsed by default | Fresh visit (clear localStorage) → these categories start collapsed |

## 3. Content Pages

| # | Test | Expected |
|---|------|----------|
| 3.1 | Tutorial page loads | e.g. `/tutorials/grover-examples` — title, markdown content, code blocks |
| 3.2 | Guide page loads | e.g. `/guides/transpile-with-pass-managers` — title, content |
| 3.3 | Course page loads | e.g. `/learning/courses/basics-quantum-information/single-systems` |
| 3.4 | Module page loads | e.g. `/learning/modules/...` |
| 3.5 | Landing pages | `/learning/` and `/learning/modules/` list all courses/modules with links |
| 3.6 | Images display | Circuit diagrams, plots visible; no broken image icons |
| 3.7 | Dark mode images | Toggle dark mode — circuit diagrams should have CSS filter (inverted) |
| 3.8 | LaTeX/math renders | Equations (inline `$...$` and block `$$...$$`) rendered via KaTeX |
| 3.9 | Admonitions render | Note/Warning/Tip boxes styled correctly |
| 3.10 | Tabs component | Pages with `<Tabs>` / `<TabItem>` — tabs switch content |
| 3.11 | Code blocks have syntax highlighting | Python code highlighted (keywords, strings, comments colored) |
| 3.12 | Code copy button | Hover over code block → copy button appears → copies to clipboard |
| 3.13 | Heading hierarchy | H1 (page title) → H2 → H3 — no H4 used as section headers |
| 3.14 | Alt text on images | Inspect images — should have contextual alt text, not generic |
| 3.15 | IBMVideo embeds | Course pages with videos — YouTube player or IBM Video iframe |
| 3.16 | Breadcrumbs | Present on all doc pages |
| 3.17 | "Open in JupyterLab" button | Notebook-derived pages show banner with JupyterLab link |

## 4. Search

| # | Test | Expected |
|---|------|----------|
| 4.1 | Search bar visible | Click search icon or press Ctrl+K / Cmd+K |
| 4.2 | Search returns results | Type "quantum circuit" → results from tutorials/guides/courses |
| 4.3 | Search result links work | Click a result → navigates to correct page |
| 4.4 | Search works offline | (Docker/local only) Disconnect network → search still works |

## 5. Code Execution (requires Binder or local Jupyter)

| # | Test | Expected |
|---|------|----------|
| 5.1 | Run button appears on Python blocks | Tutorial/guide pages with code → "Run" button in toolbar |
| 5.2 | Click Run — toolbar shows "Connecting" | Status indicator while Binder starts (may take 60-90s) |
| 5.3 | Kernel connects — cells become editable | Code blocks get CodeMirror editor, cells are editable |
| 5.4 | Execute a cell | Click a cell → amber left border (running) → green border (done) |
| 5.5 | Cell output appears | Execution results render below cell (text, images, etc.) |
| 5.6 | Multiple cells run sequentially | Variables persist across cells on the same page |
| 5.7 | Red border on error | Cell with intentional error → red left border + error output |
| 5.8 | Error hints | `ModuleNotFoundError` → contextual hint suggesting install |
| 5.9 | Pip install button | `ModuleNotFoundError` → "Install {pkg}" button → installs → auto-re-runs cell |
| 5.10 | `%pip install` injected cells | Notebooks with missing deps → first code cell is `%pip install -q ...` |
| 5.11 | Toolbar legend | After kernel connects: colored dots legend (running/done/error) |
| 5.12 | Back button | Click "Back" → confirmation dialog → reverts to static view |
| 5.13 | Back resets state | After Back → Run again → fresh kernel bootstrap (no stale state) |
| 5.14 | Warning suppression | No Python `FutureWarning`/`DeprecationWarning` in cell output |
| 5.15 | Binder hint | GitHub Pages: after kernel ready, dismissible "Binder packages" hint |
| 5.16 | Hint dismissal persists | Dismiss hint → navigate away → return → hint stays dismissed |
| 5.17 | Static outputs visible alongside live | After running, both pre-computed and live outputs visible |
| 5.18 | Green border accuracy | Fast cell (e.g. `1+1`) → green appears only after completion, not prematurely |

## 6. Simulator Mode

| # | Test | Expected |
|---|------|----------|
| 6.1 | Enable simulator | Settings → toggle on → "Simulator mode enabled" |
| 6.2 | AerSimulator selected by default | Backend radio: "AerSimulator" checked |
| 6.3 | FakeBackend option | Select "FakeBackend" → device picker appears with qubit groups |
| 6.4 | Execution mode badge | Run code with simulator on → toolbar shows "AerSimulator" (blue badge) |
| 6.5 | Injection toast | On kernel start: green toast "Simulator active — using AerSimulator" (auto-fades 4s) |
| 6.6 | Code runs without IBM credentials | Notebook using `QiskitRuntimeService` → runs successfully on simulator |
| 6.7 | Disable simulator | Settings → toggle off → badge disappears on next Run |

## 7. IBM Quantum Credentials

| # | Test | Expected |
|---|------|----------|
| 7.1 | Save credentials | Settings → enter API token + CRN → Save → success message |
| 7.2 | Expiry notice | After save: "Credentials expire in 7 days" |
| 7.3 | Delete credentials | Click "Delete Credentials" → fields cleared |
| 7.4 | Auto-injection | Save credentials → Run code → `save_account()` injected at kernel start |
| 7.5 | Execution mode badge | With credentials active → toolbar shows "IBM Quantum" (teal badge) |
| 7.6 | Conflict resolution | Both simulator + credentials → "Active Mode" radio buttons appear |
| 7.7 | No-selection warning | Both configured, no mode selected → warning banner shown |

## 8. Learning Progress

| # | Test | Expected |
|---|------|----------|
| 8.1 | Page visit tracked | Visit a tutorial → sidebar shows ✓ next to that page |
| 8.2 | ✓ indicator clickable | Click ✓ → clears visited status for that page |
| 8.3 | ▶ indicator after execution | Visit + click Run on a notebook page → sidebar shows ▶ instead of ✓ |
| 8.4 | Category badge | Visit 3 of 10 tutorials → category header shows "3/10" badge |
| 8.5 | Badge updates in real-time | Navigate between pages → badges update without refresh |
| 8.6 | Click badge to clear section | Click "3/10" badge → all progress for that section cleared, badge disappears |
| 8.7 | Resume card on homepage | Visit a page → go to `/` → "Continue where you left off" with correct title |
| 8.8 | Settings: progress stats | Settings page → Learning Progress section shows visited count + per-category breakdown |
| 8.9 | Settings: clear per category | Click "Clear Tutorials" → only tutorial progress cleared |
| 8.10 | Settings: clear all progress | Click "Clear All Progress" → all ✓/▶ indicators and badges gone |

## 9. Bookmarks

> **Note**: The bookmark toggle (☆/★) on doc page footers may have been removed.
> Check current state — if the toggle is missing, bookmarks can only be managed via Settings.

| # | Test | Expected |
|---|------|----------|
| 9.1 | Bookmark toggle on doc pages | Below content: ☆ "Bookmark" button (click → ★ "Bookmarked") |
| 9.2 | BookmarksList on homepage | After bookmarking pages → homepage shows "Bookmarks" widget with links |
| 9.3 | Remove from homepage widget | Click remove button next to a bookmark → removed |
| 9.4 | Settings: bookmark count | Shows "N bookmarked pages" |
| 9.5 | Settings: clear all bookmarks | Click → all bookmarks cleared, widget disappears |
| 9.6 | Max 50 bookmarks | (Edge case) Bookmark 50+ pages → oldest auto-removed (FIFO) |

## 10. Display Preferences

| # | Test | Expected |
|---|------|----------|
| 10.1 | Code font size control | Settings → Display → +/– buttons change font size (10–22px) |
| 10.2 | Live preview | Preview code block on settings page updates as you change size |
| 10.3 | Font size applies to doc pages | Change to 18px → visit tutorial → code blocks use 18px font |
| 10.4 | Font size persists | Refresh page → font size still 18px |
| 10.5 | Hide static outputs toggle | Settings → toggle on → "Hide static outputs during live execution" |
| 10.6 | Static outputs hidden during Run | Enable hide → Run code → pre-computed outputs hidden, live outputs visible |
| 10.7 | Static outputs return on Back | Click Back → static outputs visible again |

## 11. Onboarding Tips

| # | Test | Expected |
|---|------|----------|
| 11.1 | First visit tip bar | Clear localStorage → visit a notebook page → tip bar: "Click Run to execute code blocks..." |
| 11.2 | Non-notebook tip | Visit a non-notebook guide → tip: "Track your progress — visited pages show ✓ in the sidebar" |
| 11.3 | Auto-dismiss after 3 visits | Visit 3 pages → tip bar stops appearing |
| 11.4 | Manual dismiss | Click × on tip bar → stops appearing |
| 11.5 | Reset onboarding | Settings → "Reset Onboarding Tips" → tips reappear on next visit |

## 12. Recently Viewed Pages

| # | Test | Expected |
|---|------|----------|
| 12.1 | Pages tracked | Visit 3 different docs → homepage shows them in "Recently viewed" |
| 12.2 | Most recent first | Last-visited page appears first |
| 12.3 | Deduplication | Visit same page twice → only appears once (moves to front) |
| 12.4 | Max 5 shown | Visit 8 pages → widget shows 5 most recent |
| 12.5 | Relative timestamps | Shows "2 minutes ago", "1 hour ago", etc. |
| 12.6 | Clear recent history | Settings → "Clear Recent History" → widget disappears |

## 13. Sidebar Collapse Memory

| # | Test | Expected |
|---|------|----------|
| 13.1 | Collapse persists | Collapse "Guides" category → navigate to a tutorial → return → Guides still collapsed |
| 13.2 | Expand persists | Expand a collapsed category → navigate away → return → still expanded |
| 13.3 | Reset sidebar layout | Settings → "Reset Sidebar Layout" → all categories return to defaults |
| 13.4 | Works across page loads | Collapse categories → hard refresh (F5) → collapse state preserved |

## 14. Settings Page

| # | Test | Expected |
|---|------|----------|
| 14.1 | Title | "doQumentation Settings" (page title and h1) |
| 14.2 | URL | `/jupyter-settings` |
| 14.3 | Environment status | Blue info bar showing current environment (GitHub Pages / Docker / etc.) |
| 14.4 | All sections present | IBM Quantum Account → Simulator → Learning Progress → Display → Bookmarks → Other → Binder Packages → Advanced |
| 14.5 | 5-step IBM setup guide | Numbered list with direct links to IBM Quantum pages |
| 14.6 | Custom server fields | URL + token inputs, Test/Save/Default/Clear buttons |
| 14.7 | Test connection | Enter valid Jupyter URL → "Test Connection" → success/failure message |
| 14.8 | Setup help sections | RasQberry, Local Jupyter, Docker, Remote Server — each with commands |

## 15. Features Page

| # | Test | Expected |
|---|------|----------|
| 15.1 | Load `/features` | Page with 22 feature cards in 5 sections |
| 15.2 | Sections | Content Library (3) · Live Code Execution (6) · IBM Quantum Integration (4) · Learning & Progress (3) · Search/UI/Deployment (6) |
| 15.3 | Responsive grid | Desktop: 3 columns → tablet: 2 → mobile: 1 |
| 15.4 | Accessible from homepage | "See all features" link works |
| 15.5 | Accessible from footer | Footer has link to features page |

## 16. Dark Mode

| # | Test | Expected |
|---|------|----------|
| 16.1 | Toggle works | Click dark mode icon → site switches theme |
| 16.2 | Navbar stays dark in both modes | Navbar background `#161616` regardless of theme |
| 16.3 | Code blocks readable | Syntax highlighting colors work in both themes |
| 16.4 | Circuit diagrams | Dark mode: diagrams inverted or have appropriate backgrounds |
| 16.5 | Homepage cards | Cards readable in both themes |
| 16.6 | Settings page | All inputs and toggles readable in dark mode |
| 16.7 | Preference persists | Set dark mode → refresh → still dark |

## 17. Footer

| # | Test | Expected |
|---|------|----------|
| 17.1 | Two columns | RasQberry links · IBM Quantum & Qiskit links |
| 17.2 | IBM disclaimer | Disclaimer text present |
| 17.3 | Features link | Links to `/features` page |
| 17.4 | All links work | No 404s from footer links |

## 18. SEO & Accessibility

| # | Test | Expected |
|---|------|----------|
| 18.1 | `robots.txt` | Fetch `/robots.txt` → allows all + sitemap reference |
| 18.2 | `sitemap.xml` | Fetch `/sitemap.xml` → valid XML with page URLs |
| 18.3 | `CNAME` | `/CNAME` contains `doqumentation.org` (GitHub Pages only) |
| 18.4 | Page titles | Each page has unique `<title>` tag |
| 18.5 | Mobile tap targets | Sidebar links at least 44px tall on mobile |
| 18.6 | Keyboard navigation | Tab through navbar → sidebar → content — focus rings visible |
| 18.7 | aria-labels | Buttons (dark mode toggle, bookmark, progress indicators) have aria-labels |

## 19. Build & Infrastructure

| # | Test | Expected |
|---|------|----------|
| 19.1 | `npm run build` succeeds | With `NODE_OPTIONS="--max-old-space-size=8192"` — no errors |
| 19.2 | No broken links | Build warnings about broken links → zero |
| 19.3 | TypeScript clean | `npm run typecheck` → no errors |
| 19.4 | Content sync | `python scripts/sync-content.py --sample-only` → generates sample docs + sidebars |
| 19.5 | Dependency scan | `python scripts/sync-content.py --scan-deps` → report with 46 notebooks, 28 packages |
| 19.6 | Dev server starts | `npm start` → serves on localhost:3000 |

## 20. Docker (requires Docker/Podman)

| # | Test | Expected |
|---|------|----------|
| 20.1 | Web profile | `podman compose --profile web up` → site at `http://localhost:8080` |
| 20.2 | Jupyter profile | `podman compose --profile jupyter up` → site at `:8080` + JupyterLab at `:8888` |
| 20.3 | Token in logs | `docker compose --profile jupyter logs \| grep "Jupyter token"` → shows token |
| 20.4 | Website transparent auth | Code execution on `:8080` works without entering token |
| 20.5 | JupyterLab needs token | Direct access to `:8888` requires token from logs |
| 20.6 | Custom token | `JUPYTER_TOKEN=mytoken podman compose --profile jupyter up` → uses "mytoken" |
| 20.7 | Health check | `docker inspect --format='{{.State.Health.Status}}'` → "healthy" after startup |
| 20.8 | `%pip install` cells are no-ops | Run a notebook with injected install cell → "already satisfied" output |

---

## Quick Smoke Test (5 minutes)

For a fast sanity check, run through these critical items:

1. **Homepage loads** (1.1) — hero, stats bar, cards
2. **Navigate to a tutorial** (3.1) — content renders, code blocks highlighted
3. **Search works** (4.1, 4.2) — Ctrl+K, type query, results appear
4. **Dark mode** (16.1) — toggle works, navbar stays dark
5. **Settings page** (14.1) — loads, all sections visible
6. **Features page** (15.1) — loads, cards render
7. **Mobile** (1.8, 2.8) — resize to 375px, hamburger works, no overflow
8. **Learning progress** (8.1) — visit a page, ✓ appears in sidebar

---

*Created: February 11, 2026*
