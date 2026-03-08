# AI Integration Ideas for doQumentation

> Captured 2026-03-08 | Quantum computing education site with executable notebooks

---

## Quick Wins (Low Effort, High Value)

### 1. Code Cell Error Explanation
When a cell execution fails, send the error + cell code to Claude API and show a contextual explanation/fix suggestion inline. The existing `showErrorHint` infrastructure in `ExecutableCode/index.tsx` can be extended to support this.

### 2. "Explain This Code" Button
Add a button to each executable cell that sends the code to Claude and returns a plain-language explanation geared toward quantum computing learners. Plugs directly into the existing ExecutableCode component.

### 3. AI-Powered Semantic Search
Replace the current `@easyops-cn/docusaurus-search-local` plugin with semantic/vector search (e.g., Algolia with AI answers, or a custom RAG over the docs). Users could ask "how do I create a Bell state?" instead of keyword searching.

---

## Medium Effort

### 4. AI Tutor / Chat Sidebar
Embed a Claude-powered chat scoped to the current page's content. Students can ask follow-up questions about the material they're reading. Use RAG with docs as context.

### 5. Exercise Generation
Auto-generate practice problems from lesson content. "Based on this section on quantum entanglement, here are 3 exercises..." Could be pre-generated at build time or on-demand.

### 6. Translation Acceleration
19 locales are configured but most are <20% translated. Use Claude to draft translations, then have native speakers review. Could dramatically increase translation velocity.

---

## Higher Effort, High Impact

### 7. Adaptive Learning Paths
Track which pages/cells a user has visited/executed (already stored in preferences via `visited-pages` and `executed-pages`) and use AI to recommend what to study next.

### 8. Circuit Visualization from Natural Language
"Show me a 3-qubit GHZ state circuit" → generate Qiskit code → execute in the notebook cell. Combines Claude code generation with the existing kernel execution infrastructure.

---

## Broader Project Improvements

### 9. Test Coverage (Currently Zero)
No unit, integration, or E2E tests exist. No Jest, Vitest, Cypress, or Playwright. Add Jest + React Testing Library for components; pytest for Python scripts.

### 10. Linting & Formatting
No ESLint or Prettier configured. Code style is unenforced. Add both with pre-commit hooks.

### 11. Remaining Hardcoded English
- `src/clientModules/onboarding.ts` — onboarding tip messages (~2 strings)
- `src/components/OpenInLabBanner/index.tsx` — `PHASE_LABELS`, `BINDER_PHASE_HINTS`, `CE_PHASE_HINTS` (~15 strings)

These should be wrapped in `translate()` for i18n support.

### 12. Developer Documentation
No `ARCHITECTURE.md` or `DEVELOPMENT.md`. The thebelab integration, kernel lifecycle, and Binder/Code Engine fallback logic are undocumented. New contributors have a steep onboarding curve.

### 13. Error Monitoring
No Sentry or equivalent. Production kernel crashes and build failures are invisible to maintainers.

### 14. Performance Optimization
- No code splitting (`React.lazy`) — ExecutableCode and Settings page are good candidates for dynamic imports
- No image optimization (WebP, srcset, lazy loading)
- No bundle analysis (webpack-bundle-analyzer)

### 15. Accessibility Gaps
- Cell status icons (added in Sprint 13) lack `aria-label` text alternatives
- Onboarding tip injects raw HTML via `innerHTML` without `aria-live`
- No axe-core audit has been run

---

## User Experience Improvements

### Critical UX Issues

#### UX-1. Onboarding Is Too Minimal
- Only 2 static contextual tips shown on first 3 page visits (`src/clientModules/onboarding.ts`)
- Tips appear on content pages, not on the homepage where users first land
- No guided workflow, no "Get Started" path, no feature walkthrough
- **Suggestion**: Add a guided tour (Shepherd.js / Intro.js) covering: navigate content → open Settings → configure credentials → run first cell

#### UX-2. Binder Launch Wait Is Opaque
- First code execution triggers a 1–2 minute Binder launch with vague phase text ("In queue...", "Building...")
- No ETA, no progress bar, no percentage — just elapsed time
- Cache-miss warning ("10–25 min") appears late and may cause abandonment
- **Suggestion**: Show estimated time per phase, add a progress bar, and surface the Colab alternative more prominently upfront

#### UX-3. Settings Page Information Overload
- 7 major sections (IBM Quantum, Code Engine, Advanced, Simulator, Display, Progress, Bookmarks) on a single scrolling page (~1333 lines in `jupyter-settings.tsx`)
- No tabs, accordion, or jump links beyond `#ibm-quantum` and `#code-engine`
- Mobile users must scroll extensively
- **Suggestion**: Refactor into a tabbed interface or collapsible accordion with section anchors

#### UX-4. Icon-Only Navbar Controls
- Settings gear, Language globe, and Dark Mode toggle are icon-only on desktop
- First-time users may not recognize them; no tooltips (only `aria-label`)
- **Suggestion**: Add `title` attributes and optional text labels (at least on first visit)

### High-Priority UX Improvements

#### UX-5. Credential Expiry Goes Unnoticed
- IBM token TTL countdown only visible on Settings page
- No banner or notification when credentials are about to expire or have expired
- Users discover expiry only when code execution fails
- **Suggestion**: Show a dismissible warning banner on content pages when credentials expire within 24 hours

#### UX-6. No Confirmation Before Destructive Actions
- "Clear All Progress", "Delete Credentials", "Reset All" execute immediately on click
- One accidental click loses all tracked progress or saved credentials
- **Suggestion**: Add a confirmation dialog ("Are you sure? This will remove X items")

#### UX-7. Kernel Death Recovery Is Unclear
- When the kernel crashes mid-session, cells show red borders but no actionable prompt
- The error hint "Click Back then Run to reconnect" only appears for specific error patterns
- **Suggestion**: Show a persistent banner with a "Reconnect" button when kernel status changes to `dead`

#### UX-8. Error Hints Have Low Contrast in Dark Mode
- Red error text on dark background (~3:1 contrast ratio) fails WCAG AA
- Error hints below cells can be missed
- **Suggestion**: Use a high-contrast error card (red background, white text) instead of inline colored text

#### UX-9. No Success Feedback After Cell Execution
- When a cell completes successfully, only feedback is a subtle green left border
- No toast, no checkmark animation, no "Done" indicator
- **Suggestion**: Brief "Executed successfully" fade-out indicator or checkmark icon in the cell toolbar

### Medium-Priority UX Enhancements

#### UX-10. Simulator Device Picker Is Overwhelming
- Dropdown lists 50+ fake backends in a flat `<select>` with `<optgroup>` by qubit count
- Hard to search or filter on mobile
- **Suggestion**: Replace with a searchable combobox or grouped card picker showing device specs

#### UX-11. No Pip Install Progress Indicator
- "Installing..." text with no spinner, no progress bar, no elapsed time
- For large packages this can take 30+ seconds with no visual feedback
- **Suggestion**: Add an animated spinner and elapsed time counter

#### UX-12. Code Block Toolbar Overlaps on Mobile
- Run/Back buttons positioned relative to code block may overlap content on narrow screens
- Touch targets are ~36px (below the recommended 48×48px minimum)
- **Suggestion**: Stack toolbar buttons vertically on mobile; increase touch target size

#### UX-13. No Keyboard Shortcut Documentation
- Shift+Enter for cell execution is a thebelab/CodeMirror convention, undocumented
- No keyboard shortcut overlay or help modal
- **Suggestion**: Add a "Keyboard Shortcuts" help button (?) or footer link showing available shortcuts

#### UX-14. Learning Progress Lacks Completion Percentage
- Sidebar badges show "3/10 visited" per category but no overall course completion indicator
- No summary dashboard beyond the Settings page stats cards
- **Suggestion**: Add a progress bar or percentage to the sidebar header and/or homepage

#### UX-15. No User Data Export/Import
- Bookmarks, progress, and preferences stored only in browser localStorage/cookies
- Switching browsers or clearing data loses everything
- **Suggestion**: Add Export/Import buttons on Settings page (JSON download/upload)

### Accessibility Gaps

#### UX-16. No Skip Links
- No "Skip to main content" link at the top of the page for keyboard/screen reader users
- Standard WCAG 2.1 Level A requirement

#### UX-17. Settings Form Lacks Fieldset Grouping
- Related inputs (e.g., IBM Token + CRN + TTL) are not wrapped in `<fieldset>` with `<legend>`
- Screen readers can't announce section context when navigating form fields

#### UX-18. Thebelab CodeMirror Accessibility Unknown
- Third-party CodeMirror editor accessibility with screen readers is untested
- Mobile keyboard/touch editing likely poor
- **Suggestion**: Test with VoiceOver/NVDA; consider adding a plain `<textarea>` fallback

#### UX-19. Onboarding Tip Injected via innerHTML
- `innerHTML` insertion in `onboarding.ts` bypasses `aria-live` announcements
- Screen reader users won't hear the onboarding message appear
- **Suggestion**: Use React portal or `aria-live="polite"` region

### Content & Navigation UX

#### UX-20. No "Related Pages" or "Next Steps" Suggestions
- Pages end abruptly after content; no "You might also like..." or "Continue to..." links
- Docusaurus pagination (prev/next) exists but is limited to sidebar order
- **Suggestion**: Add a "Related Topics" section at the bottom of each page, curated or AI-generated

#### UX-21. Search Is Keyword-Only
- `@easyops-cn/docusaurus-search-local` does full-text search but no semantic/fuzzy matching
- Searching "how to entangle qubits" won't find "Bell state" or "CNOT gate" pages
- **Suggestion**: See AI idea #3 (semantic search) — this is also a core UX gap

#### UX-22. No Offline Support
- No service worker or PWA configuration
- Users on flaky connections (workshops, conferences) lose access entirely
- **Suggestion**: Add Docusaurus PWA plugin for offline reading of static content

#### UX-23. No Reading Time Estimates
- Pages don't show estimated reading time (common in education platforms)
- Users can't plan their learning sessions
- **Suggestion**: Add `plugin-content-docs` `showLastUpdateTime` + a reading time plugin

#### UX-24. Recent Pages Widget Limited
- Homepage shows 5 most recent pages but no way to pin, filter, or search history
- No "Resume where you left off" prominent CTA
- **Suggestion**: Add a "Continue Reading" hero card on the homepage showing last visited page with a prominent button

### End-to-End Learning Journey Gaps

#### UX-25. First-Run "Build Time Shock"
- Clicking "Run" on GitHub Pages triggers a 10–25 minute Binder build with no upfront warning
- Cache-miss warning only appears *after* the build phase starts (`OpenInLabBanner` line ~110)
- Phase hints give per-phase estimates ("Fetching 2–5 min", "Building 5–10 min") but never the cumulative total
- **Suggestion**: Show a one-time interstitial *before* first Run: "First launch takes 10–25 min. Want to use Colab instead?" with two clear buttons

#### UX-26. Credential Setup Timing Is Backwards
- TTL/expiry dropdown only appears *after* credentials are saved (line ~547 in `jupyter-settings.tsx`)
- Users can't set their preferred expiry before committing credentials
- **Suggestion**: Show TTL selector inline with the credential form, before the Save button

#### UX-27. Mixed Messaging on Credential Security
- Security warning says "plain text, readable by extensions, delete when done"
- But the UX then encourages saving credentials with a prominent Save button and auto-injection feature
- Creates cognitive dissonance: is this safe or not?
- **Suggestion**: Reframe as risk levels: "Recommended for personal devices" vs "Use manual `save_account()` on shared/public computers" — make the decision tree explicit

#### UX-28. Simulator vs Credentials Conflict Handled Too Late
- User can enable both IBM credentials *and* simulator mode without warning
- Conflict banner ("Both configured — using {mode}") only appears when code runs, with a 5-second auto-dismiss
- Active Mode radio buttons on Settings page only shown *after* both are enabled
- **Suggestion**: When enabling the second option, immediately prompt "Which mode should take priority?" inline

#### UX-29. No "Continue Where You Left Off" Flow
- `dq-last-page` stores the last visited page with title and timestamp
- Recent Pages widget shows 5 items on homepage but with no visual hierarchy
- No prominent "Resume" call-to-action on the homepage or in the navbar
- **Suggestion**: Hero card at top of homepage: "Continue: {last page title} — {time ago}" with a single Resume button

#### UX-30. Progress Tracking Has No Goal-Setting
- Sidebar badges show "3/10 visited" but there's no concept of a "learning path" or "course completion"
- Users don't know which pages are prerequisites for others
- No milestones, achievements, or "you've completed section X" celebrations
- **Suggestion**: Define prerequisite chains in sidebar metadata; show a completion celebration toast when a section is 100% visited+executed

#### UX-31. Kernel State Invisible Between Pages
- Kernel is per-page (all cells share one kernel), but navigating away kills the session
- No warning that leaving the page will lose kernel state and all variable values
- Users who navigate to Settings mid-session lose their work
- **Suggestion**: Show a "You have a running kernel — leaving will end your session" prompt on navigation, or persist kernel across pages

#### UX-32. `save_account()` Cells Create Confusion
- When credentials are configured via Settings, `save_account()` cells show a skip hint
- But the skip hint says "Running it with placeholder values will overwrite them" — this scares users
- The hint appears *inside* the code block area (small font, 0.8rem) and is easy to miss
- **Suggestion**: Replace with a more prominent inline banner: "You've already configured credentials in Settings. This cell is optional."

#### UX-33. No Feedback Loop for Learning Effectiveness
- No quizzes, knowledge checks, or self-assessment after content sections
- No way for users to mark "I understood this" vs "I need to revisit"
- Visited/executed tracking measures exposure, not comprehension
- **Suggestion**: Add optional "Did you understand this?" thumbs up/down at page bottom; track for personal review later

### Operational & Environmental UX

#### UX-34. Environment Auto-Detection Is Silent
- Settings page shows detected environment (GitHub Pages / Code Engine / RasQberry) but doesn't explain implications
- Users don't understand *why* their code execution experience differs
- **Suggestion**: Show a one-line explanation on content pages: "Running on {env} — {what this means}" (e.g., "GitHub Pages — first run takes 2–5 min via Binder")

#### UX-35. Code Engine Setup Instructions Are Hidden
- Setup steps are inside a collapsed `<details>` element on Settings page
- Users who would benefit most from Code Engine (faster startup) may never discover it
- **Suggestion**: Surface Code Engine as the "recommended" option more prominently; consider a setup wizard

#### UX-36. No Error Recovery Guidance Beyond Hints
- Error hints cover 3 patterns (ModuleNotFoundError, NameError, kernel death)
- All other errors show raw Python tracebacks with no guidance
- Quantum-specific errors (transpilation failures, qubit count mismatches, service errors) get no special handling
- **Suggestion**: Add pattern matching for common Qiskit errors (TranspilerError, IBMNotAuthorizedError, etc.) with contextual guidance

#### UX-37. Cross-Tab State Not Synchronized
- localStorage changes broadcast via `storage` event, but cookie writes don't trigger cross-tab updates
- Opening Settings in one tab and running code in another can lead to stale credential state
- **Suggestion**: Use `BroadcastChannel` API to sync preference changes across tabs in real-time

#### UX-38. No Analytics or Usage Insights for Learners
- No personal dashboard showing: time spent per topic, execution success rate, most-revisited pages
- Progress stats are just raw counts (pages visited, notebooks executed)
- **Suggestion**: Add a "My Learning" dashboard with charts: topics explored over time, execution success/failure ratio, study streaks

---

## Remaining PROJECT_REVIEW Items (6)

| ID | Severity | Issue |
|----|----------|-------|
| SSE-1 | HIGH | Token sent in plaintext over SSE `ready` event |
| ENT-1 | HIGH | XSRF protection globally disabled |
| CFG-3 | MEDIUM | Hardcoded default token `'rasqberry'` |
| CFG-4 | MEDIUM | Tokens stored in localStorage plaintext |
| SET-2 | MEDIUM | Settings page needs refactor into sub-components |
