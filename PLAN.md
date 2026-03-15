# Plan: Synced Translated Transcripts — POC Implementation

## Scope

Use YouTube's built-in auto-translated captions to provide translated subtitles on all course videos. YouTube handles transcription, translation, and sync — we just need to configure the embed URL with the correct caption language based on the current Docusaurus locale.

---

## Step 1: Update IBMVideo Component

**File:** `src/components/CourseComponents/IBMVideo.tsx`

Modify the YouTube embed URL to include caption parameters based on the current locale:

- Use `useDocusaurusContext()` to get `i18n.currentLocale`
- For YouTube embeds, append URL parameters:
  - `cc_load_policy=1` — show captions by default
  - `cc_lang_pref={locale}` — preferred caption language (YouTube auto-translates if the language isn't natively available)
  - `hl={locale}` — player interface language
- For non-English locales, captions are shown automatically in the user's language
- For English locale, captions are available but not forced on (users can enable them via the CC button)

### Locale Mapping

Docusaurus locale codes map directly to YouTube language codes in most cases (`de` → `de`, `es` → `es`, `ja` → `ja`). No special mapping needed for the active locales (en, de, es).

## Step 2: Verify

- Run `npm start` with different locales and confirm captions appear in the correct language
- Verify English locale still works as before (no forced captions)
- Verify IBM Video fallback (no YouTube mapping) still works unchanged

---

## Files Modified

| Action | File |
|--------|------|
| Modify | `src/components/CourseComponents/IBMVideo.tsx` |

## What This Gives Us

- Translated captions on all 50+ course videos with YouTube mappings
- All languages YouTube supports (far more than our 20 locales)
- No VTT files to maintain, no translation pipeline, no new components
- Captions are synced to the video by YouTube automatically

## Future Enhancements (Not in POC)

- Synced transcript panel below the video (interactive, click-to-seek) using YouTube IFrame API
- Custom VTT files for higher-quality translations of quantum computing terminology
- IBM Video Streaming adapter for videos without YouTube mappings
