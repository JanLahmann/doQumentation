# Plan: Synced Translated Transcripts — POC Implementation

## Scope

Build a working proof-of-concept that adds a synced transcript panel below video players on doqumentation.org. The POC targets **one video** (Basics of Quantum Information — Lesson 1, IBM Video ID `134056207` / YouTube ID `3-c4xJa7Flk`) with **two languages** (English + German).

---

## Step 1: Create VTT Parser Utility

**File:** `src/utils/vttParser.ts`

- `parseVTT(vttText: string): TranscriptCue[]` — parses WebVTT into `{ start, end, text }[]`
- `parseTimestamp(ts: string): number` — handles `HH:MM:SS.mmm` and `MM:SS.mmm`
- `findActiveCue(cues, currentTime): number` — binary search for active cue index
- Export `TranscriptCue` interface

No external dependencies needed.

## Step 2: Create YouTube Player Adapter

**File:** `src/utils/playerAdapters.ts`

Since most videos resolve to YouTube (via `YOUTUBE_MAP`), the POC focuses on the YouTube adapter only.

- `YouTubeAdapter` class implementing:
  - `getCurrentTime(cb)` — wraps `player.getCurrentTime()`
  - `seek(seconds)` — wraps `player.seekTo(seconds, true)`
  - `onPlayStateChange(cb)` — hooks into `onStateChange`
  - `destroy()` — cleanup
- Export `PlayerAdapter` interface for future IBM Video adapter

## Step 3: Create SyncedTranscript Component

**File:** `src/components/CourseComponents/SyncedTranscript.tsx`
**File:** `src/components/CourseComponents/SyncedTranscript.module.css`

Core React component:

- **Props:** `videoId: string` (IBM Video ID, used to look up transcript paths and YouTube ID)
- **State:** `cues`, `activeCueIndex`, `selectedLanguage`, `isPlaying`
- **Behavior:**
  - On mount, loads the YouTube IFrame API and creates a `YT.Player` in a div (replacing the current plain iframe approach)
  - Fetches the VTT file for the selected language from `/transcripts/{videoId}/{lang}.vtt`
  - Polls `getCurrentTime()` every 250ms while playing
  - Uses `findActiveCue()` to highlight the current line
  - Auto-scrolls to active cue (smooth scroll, centered), but pauses auto-scroll for 3s after user manual scroll
  - Click on any cue calls `adapter.seek(cue.start)`
  - Language dropdown switches VTT file (preserves playback position)
- **Layout:** Video on top, transcript panel below (scrollable, max-height ~300px)
- **Styling:**
  - Active cue: bold, left border accent, light background
  - Past cues: slightly dimmed
  - Future cues: normal
  - Each cue shows timestamp on the left, text on the right
  - Responsive: works on mobile (stacked layout is natural since video is already full-width)
- **Accessibility:**
  - Each cue is a `<button>` with `aria-label` including timestamp
  - Active cue has `aria-current="true"`
  - Language selector is a `<select>` with `<label>`

## Step 4: Create Sample VTT Transcript Files

**Files:**
- `static/transcripts/134056207/en.vtt` — English transcript (sample, ~10-15 cues covering first few minutes)
- `static/transcripts/134056207/de.vtt` — German translation (same timestamps, translated text)

These are hand-crafted sample cues for the POC. In production, Whisper would generate the full English transcript and Claude API would translate it.

## Step 5: Update IBMVideo Component

**File:** `src/components/CourseComponents/IBMVideo.tsx`

Modify the existing component:

- Import `SyncedTranscript`
- Instead of rendering a plain `<iframe>`, render:
  1. A `<div>` placeholder for the YouTube player (when YouTube ID exists)
  2. Fallback to current iframe for IBM Video (no transcript sync in POC)
  3. `<SyncedTranscript>` below the video, passing the video ID
- The `SyncedTranscript` component manages the YouTube player lifecycle via the IFrame API
- Keep backward compatibility: if no transcript exists for a video ID, render just the video as before

## Step 6: Add Transcript Configuration Map

**File:** `src/utils/transcriptConfig.ts`

```typescript
export const TRANSCRIPT_MAP: Record<string, {
  title: string;
  languages: { code: string; label: string }[];
}> = {
  '134056207': {
    title: 'Basics of Quantum Information — Lesson 1',
    languages: [
      { code: 'en', label: 'English' },
      { code: 'de', label: 'Deutsch' },
    ],
  },
};
```

This keeps transcript availability separate from video embedding logic.

## Step 7: Test & Verify

- Run `npm start` and navigate to a page using `<IBMVideo id="134056207" />`
- Verify: video plays, transcript highlights in sync, click-to-seek works, language switch works
- Verify: videos without transcripts still render normally (no regression)

---

## Files Created/Modified Summary

| Action   | File                                                    |
|----------|---------------------------------------------------------|
| Create   | `src/utils/vttParser.ts`                                |
| Create   | `src/utils/playerAdapters.ts`                           |
| Create   | `src/utils/transcriptConfig.ts`                         |
| Create   | `src/components/CourseComponents/SyncedTranscript.tsx`   |
| Create   | `src/components/CourseComponents/SyncedTranscript.module.css` |
| Create   | `static/transcripts/134056207/en.vtt`                   |
| Create   | `static/transcripts/134056207/de.vtt`                   |
| Modify   | `src/components/CourseComponents/IBMVideo.tsx`           |

## What's NOT in the POC

- IBM Video Streaming adapter (only YouTube for now, since all course videos have YouTube mappings)
- Whisper transcription pipeline / CI automation
- Full transcripts (only sample cues for demo)
- All 16 course videos (only 1 video)
- All languages (only English + German)
- Download transcript feature
- UstreamEmbed API integration
