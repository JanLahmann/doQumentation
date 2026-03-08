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

## Remaining PROJECT_REVIEW Items (6)

| ID | Severity | Issue |
|----|----------|-------|
| SSE-1 | HIGH | Token sent in plaintext over SSE `ready` event |
| ENT-1 | HIGH | XSRF protection globally disabled |
| CFG-3 | MEDIUM | Hardcoded default token `'rasqberry'` |
| CFG-4 | MEDIUM | Tokens stored in localStorage plaintext |
| SET-2 | MEDIUM | Settings page needs refactor into sub-components |
