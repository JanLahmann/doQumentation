# Plan: Add Arabic and Hebrew as RTL Languages

## Overview

Add Arabic (ar) and Hebrew (he) as the first right-to-left languages in doQumentation. This requires RTL infrastructure changes **before** any content translation begins, since all existing locales (en, de, es, uk) are LTR.

---

## Step 1: Docusaurus i18n Configuration

**File:** `docusaurus.config.ts`

- Add `ar` and `he` to the `locales` array
- Add locale configs with `direction: 'rtl'`, labels (`العربية`, `עברית`), and subdomain URLs (`ar.doqumentation.org`, `he.doqumentation.org`)
- Docusaurus natively supports `direction: 'rtl'` in locale configs — it automatically sets `dir="rtl"` on the `<html>` element and `lang` attribute when building for that locale

```ts
i18n: {
  defaultLocale: 'en',
  locales: ['en', 'de', 'es', 'uk', 'ar', 'he'],
  localeConfigs: {
    // ...existing...
    ar: { label: 'العربية', direction: 'rtl', url: 'https://ar.doqumentation.org' },
    he: { label: 'עברית', direction: 'rtl', url: 'https://he.doqumentation.org' },
  },
},
```

---

## Step 2: Convert Directional CSS to Logical Properties

**File:** `src/css/custom.css`

Replace all physical directional CSS properties with CSS logical properties. This is the core work — logical properties automatically flip for RTL. **All changes are backward-compatible with LTR.**

| Physical Property | Logical Replacement | Occurrences |
|---|---|---|
| `border-left` | `border-inline-start` | ~8 (sidebar active, alerts, execution states, legend, onboarding, resume card, simulator callout) |
| `border-left-width` | `border-inline-start-width` | 1 (`.alert`) |
| `border-left-color` | `border-inline-start-color` | 3 (cell running/done/error) |
| `margin-left` | `margin-inline-start` | 4 (install btn, settings link, binder dismiss, onboarding dismiss) |
| `margin-right` | `margin-inline-end` | 1 (navbar toggle) |
| `padding-left` | `padding-inline-start` | 1 (legend item) |
| `right: Npx` (absolute) | `inset-inline-end` | 2 (sidebar indicator, category badge) |
| `left: 2px` (toggle thumb) | `inset-inline-start` | 1 (toggle switch thumb) |

**Key conversions:**

```css
/* BEFORE */
.menu__link--active { border-left: 3px solid var(--ifm-color-primary); }
.alert { border-left-width: 4px; }
.dq-sidebar-indicator { right: 0.25rem; }
.dq-category-badge { right: 2rem; }
.executable-code__settings-link { margin-left: auto; }
.executable-code__legend-item { border-left: 3px solid transparent; padding-left: 4px; }
.thebelab-cell__install-btn { margin-left: 0.5rem; }
.executable-code__binder-hint-dismiss { margin-left: auto; }
.dq-onboarding-tip { border-left: 3px solid var(--ifm-color-primary); }
.dq-onboarding-tip__dismiss { margin-left: auto; }
.dq-resume-card { border-left: 4px solid var(--ifm-color-primary); }
.simulator-callout { border-left: 4px solid var(--ifm-color-primary); }
.navbar__toggle { margin-right: 0.25rem; }
.jupyter-settings__toggle-thumb { left: 2px; }

/* AFTER */
.menu__link--active { border-inline-start: 3px solid var(--ifm-color-primary); }
.alert { border-inline-start-width: 4px; }
.dq-sidebar-indicator { inset-inline-end: 0.25rem; }
.dq-category-badge { inset-inline-end: 2rem; }
.executable-code__settings-link { margin-inline-start: auto; }
.executable-code__legend-item { border-inline-start: 3px solid transparent; padding-inline-start: 4px; }
.thebelab-cell__install-btn { margin-inline-start: 0.5rem; }
.executable-code__binder-hint-dismiss { margin-inline-start: auto; }
.dq-onboarding-tip { border-inline-start: 3px solid var(--ifm-color-primary); }
.dq-onboarding-tip__dismiss { margin-inline-start: auto; }
.dq-resume-card { border-inline-start: 4px solid var(--ifm-color-primary); }
.simulator-callout { border-inline-start: 4px solid var(--ifm-color-primary); }
.navbar__toggle { margin-inline-end: 0.25rem; }
.jupyter-settings__toggle-thumb { inset-inline-start: 2px; }
```

**Safe / no change needed:**
- `text-align: center` — symmetric, works in both directions
- `flex-direction: column` — vertical, direction-independent
- `margin: 0 auto` — symmetric centering
- `gap`, `padding` (symmetric values) — direction-independent

---

## Step 3: Add RTL Fonts

**File:** `src/css/custom.css`

Add Arabic and Hebrew fonts to the Google Fonts import and font-family stacks. IBM Plex Sans does not support Arabic or Hebrew glyphs.

```css
/* Add to existing @import — Noto Sans Arabic + Noto Sans Hebrew */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&family=Noto+Sans+Hebrew:wght@400;500;600;700&display=swap');
```

Add RTL-specific font override rule:

```css
/* RTL font override — Arabic and Hebrew glyphs need Noto Sans */
[dir="rtl"] {
  --ifm-font-family-base: 'Noto Sans Arabic', 'Noto Sans Hebrew', 'IBM Plex Sans', sans-serif;
  --ifm-heading-font-family: 'Noto Sans Arabic', 'Noto Sans Hebrew', 'IBM Plex Sans', sans-serif;
}
```

This approach keeps IBM Plex Sans as fallback for any embedded Latin text (code, brand names) while using proper Arabic/Hebrew fonts for native script.

---

## Step 4: RTL-Specific CSS Overrides

**File:** `src/css/custom.css`

A small set of overrides for things logical properties alone can't handle:

```css
/* Toggle switch — translateX must flip direction */
[dir="rtl"] .jupyter-settings__toggle input:checked + .jupyter-settings__toggle-track .jupyter-settings__toggle-thumb {
  transform: translateX(-18px);
}

/* Sidebar collapse arrow (Docusaurus uses CSS rotation for the caret) */
[dir="rtl"] .menu__list-item-collapsible .menu__link--sublist-caret::after {
  transform: scaleX(-1);
}
```

---

## Step 5: UI String Translations

Create translation files for both locales:

- `i18n/ar/docusaurus-theme-classic/navbar.json`
- `i18n/ar/docusaurus-theme-classic/footer.json`
- `i18n/ar/code.json`
- `i18n/he/docusaurus-theme-classic/navbar.json`
- `i18n/he/docusaurus-theme-classic/footer.json`
- `i18n/he/code.json`

These contain the navbar labels (Tutorials, Guides, Courses, etc.), footer links, and custom component strings translated to Arabic and Hebrew. Copy structure from existing `i18n/de/` files as template.

---

## Step 6: Populate Fallback Content

Use the existing `populate-locale` system to fill untranslated pages with English content + an RTL-appropriate "this page is not yet translated" banner.

Add banner templates for Arabic and Hebrew to the fallback system:
- Arabic: `هذه الصفحة غير متوفرة بالعربية بعد. يتم عرض المحتوى باللغة الإنجليزية.`
- Hebrew: `דף זה אינו זמין עדיין בעברית. התוכן מוצג באנגלית.`

---

## Step 7: Infrastructure — Satellite Repos & DNS

Following the established pattern (documented in PROJECT_HANDOFF.md):

- Create satellite repos: `JanLahmann/doQumentation-ar`, `JanLahmann/doQumentation-he`
- Set up SSH deploy keys for CI push access
- Configure custom domains (`ar.doqumentation.org`, `he.doqumentation.org`) — DNS wildcard already in place
- Add `ar` and `he` to the `deploy-locales.yml` CI matrix

---

## Step 8: Update `deploy-locales.yml`

Add `ar` and `he` to the locale build matrix so CI builds and deploys them to their satellite repos.

---

## Frontend Considerations Checklist

These are the key things to observe/verify in the frontend:

| Concern | Status | Notes |
|---------|--------|-------|
| **`dir="rtl"` on `<html>`** | Handled by Docusaurus | Set automatically from `localeConfigs.direction` |
| **Sidebar flips to right side** | Handled by Docusaurus | Docusaurus layout is flexbox-based, respects `dir` |
| **Navbar mirrors** | Handled by Docusaurus | Logo moves to right, links flow RTL |
| **Active sidebar border** | Step 2 | `border-left` → `border-inline-start` (appears on right in RTL) |
| **Admonition accent border** | Step 2 | `border-left-width` → `border-inline-start-width` |
| **Code execution state borders** | Step 2 | All 3 states (running/done/error) use `border-left-color` |
| **Sidebar indicators (✓/▶)** | Step 2 | Positioned with `right` → `inset-inline-end` (moves to left in RTL) |
| **Category badges (3/10)** | Step 2 | Same absolute positioning fix |
| **Toggle switch animation** | Step 4 | `translateX(18px)` → `translateX(-18px)` for RTL |
| **Arabic/Hebrew font rendering** | Step 3 | IBM Plex Sans lacks these scripts — Noto Sans fills the gap |
| **Bidirectional text (bidi)** | Automatic | Browser handles mixed Arabic/Hebrew + English/code naturally with `dir="rtl"` |
| **Code blocks stay LTR** | Automatic | Code is always LTR — `<pre>`/`<code>` inherits from Docusaurus which isolates code blocks |
| **Math (KaTeX) rendering** | Automatic | Math is direction-independent |
| **Images/diagrams** | No change | Quantum circuit diagrams are direction-independent |
| **Hamburger menu (mobile)** | Automatic | Docusaurus mobile menu respects `dir` |
| **Search** | Automatic | `docusaurus-search-local` works per-locale |
| **`margin-left: auto` patterns** | Step 2 | Used for right-alignment (dismiss buttons, settings link) — must become `margin-inline-start: auto` |

## Implementation Order

1. **Steps 1-4** (config + CSS) — can be done immediately, no content needed
2. **Step 5** (UI translations) — can be done in parallel
3. **Step 6** (fallback content) — depends on Step 5 for banner text
4. **Steps 7-8** (infra + CI) — can be done in parallel with Steps 5-6

## Risk Assessment

- **Low risk:** All CSS logical property changes are backward-compatible — LTR locales behave identically
- **Low risk:** Docusaurus has mature RTL support (used by many Arabic/Hebrew documentation sites)
- **Medium attention:** Interactive code execution (thebelab) — code cells must remain LTR even in RTL pages. Docusaurus isolates `<pre>` blocks, but should be tested
- **Medium attention:** KaTeX math — should render correctly but needs visual verification with RTL surrounding text
- **Test:** Build locally with `npm start -- --locale ar` to verify layout before deploying
