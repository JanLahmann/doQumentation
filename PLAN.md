# Plan: Synced Translated Transcripts — POC Implementation

## Scope

Two-part approach:
1. **YouTube auto-translated captions** — configure embeds with locale-aware caption parameters for instant translated subtitles
2. **Whisper transcription pipeline** — GitHub Actions workflow to generate high-quality English VTT transcripts from course videos

---

## Part 1: Locale-Aware YouTube Captions (Done)

**File:** `src/components/CourseComponents/IBMVideo.tsx`

- Uses `useDocusaurusContext()` to get `i18n.currentLocale`
- YouTube embed URL includes `hl={locale}` (player UI language)
- For non-English locales, also sets `cc_load_policy=1` and `cc_lang_pref={locale}` to auto-show translated captions
- Works for all 30+ videos with YouTube mappings, all languages YouTube supports

## Part 2: Whisper Transcript Generation Pipeline

### Script: `scripts/generate-transcripts.py`

- Downloads audio from YouTube via `yt-dlp`
- Runs OpenAI Whisper to generate timestamped English VTT transcripts
- Saves to `static/transcripts/{ibm_video_id}/en.vtt`
- Skips videos that already have transcripts (use `--force` to overwrite)
- Supports `--video-id` to transcribe a single video, or all videos by default
- Reads video ID mapping from `scripts/video-map.json`

### Workflow: `.github/workflows/generate-transcripts.yml`

- **Trigger:** `workflow_dispatch` (manual) with optional inputs:
  - `video_id` — specific IBM Video ID (empty = all)
  - `model` — Whisper model (`tiny`, `base`, `small`, `medium`, `large-v3`)
- **Runner:** `ubuntu-latest` (CPU), 6-hour timeout for long videos
- **Steps:** checkout → install whisper + yt-dlp → run script → commit VTT files
- Default model: `medium` (good accuracy/speed balance on CPU)

### Video Map: `scripts/video-map.json`

- JSON mapping of all 32 IBM Video IDs to YouTube IDs
- Single source of truth used by the generation script

---

## Files Summary

| Action | File |
|--------|------|
| Modify | `src/components/CourseComponents/IBMVideo.tsx` |
| Create | `scripts/generate-transcripts.py` |
| Create | `scripts/video-map.json` |
| Create | `.github/workflows/generate-transcripts.yml` |

## Future Enhancements

- LLM-based translation of VTT files (preserving timestamps, quantum computing terminology)
- Synced transcript panel below the video (interactive, click-to-seek)
- IBM Video Streaming adapter for videos without YouTube mappings
- GPU runners for faster Whisper transcription with `large-v3`
