# Plan: Synced Translated Transcripts — POC Implementation

## Scope

Three-part approach:
1. **YouTube auto-translated captions** — configure embeds with locale-aware caption parameters for instant translated subtitles
2. **Whisper transcription pipeline** — GitHub Actions workflow to generate high-quality English VTT transcripts from course videos (IBM Video + YouTube sources)
3. **LLM-based transcript translation** — Claude-powered translation of VTT files preserving timestamps and quantum computing terminology

**POC video:** `134413658` — Katie McCormick, Quantum Key Distribution (IBM Video source)

---

## Part 1: Locale-Aware YouTube Captions (Done)

**File:** `src/components/CourseComponents/IBMVideo.tsx`

- Uses `useDocusaurusContext()` to get `i18n.currentLocale`
- YouTube embed URL includes `hl={locale}` (player UI language)
- For non-English locales, also sets `cc_load_policy=1` and `cc_lang_pref={locale}` to auto-show translated captions
- Works for all 30+ videos with YouTube mappings, all languages YouTube supports

## Part 2: Whisper Transcript Generation Pipeline

### Script: `scripts/generate-transcripts.py`

- Downloads audio via `yt-dlp` from **IBM Video or YouTube** (configurable `--source`)
- `--source auto` (default): prefers YouTube when mapped, falls back to IBM Video
- `--source ibm`: forces IBM Video for all videos (works for all 59 videos in content)
- `--source youtube`: forces YouTube (only works for 32 mapped videos)
- Scans all MDX content files to discover IBM Video IDs (not just the 32 mapped ones)
- Runs OpenAI Whisper to generate timestamped English VTT transcripts
- Saves to `static/transcripts/{ibm_video_id}/en.vtt`
- Skips videos that already have transcripts (use `--force` to overwrite)
- Reads YouTube ID mapping by parsing `IBMVideo.tsx` (single source of truth)

### Workflow: `.github/workflows/generate-transcripts.yml`

- **Trigger:** `workflow_dispatch` (manual) with optional inputs:
  - `video_id` — specific IBM Video ID (empty = all)
  - `model` — Whisper model (`tiny`, `base`, `small`, `medium`, `large-v3`)
  - `source` — Video source (`auto`, `ibm`, `youtube`)
- **Push trigger:** smoke-tests POC video `134413658` from IBM Video with `tiny` model
- **Runner:** `ubuntu-latest` (CPU), 6-hour timeout for long videos
- **Steps:** checkout → install whisper + yt-dlp → run script → commit VTT files

## Part 3: LLM-Based Transcript Translation

### Script: `scripts/translate-transcripts.py`

- Translates English VTT files to target locales using Claude API
- Preserves all VTT structure (WEBVTT header, timestamps, blank-line cue separators)
- Keeps quantum computing terms in English (qubit, gate, Hadamard, BB84, etc.)
- Keeps proper names unchanged (Alice, Bob, Eve)
- Uses locale-appropriate register (informal "du" for DE, polite です/ます for JA, etc.)
- Validates translated output: cue count, timestamp preservation, WEBVTT header
- Saves to `static/transcripts/{ibm_video_id}/{locale}.vtt`

### Workflow: `.github/workflows/translate-transcripts.yml`

- **Trigger:** `workflow_dispatch` (manual) with inputs:
  - `locale` — target language (required): de, ja, uk, es, fr, it, pt, tl, th, ar, he
  - `video_id` — specific IBM Video ID (empty = all with en.vtt)
  - `model` — Claude model (default: claude-sonnet-4-20250514)
  - `force` — overwrite existing translations
- **Secret required:** `ANTHROPIC_API_KEY`
- **Steps:** checkout → install anthropic → run script → commit translations

---

## Files Summary

| Action | File |
|--------|------|
| Modify | `src/components/CourseComponents/IBMVideo.tsx` |
| Modify | `scripts/generate-transcripts.py` |
| Modify | `.github/workflows/generate-transcripts.yml` |
| Create | `scripts/translate-transcripts.py` |
| Create | `.github/workflows/translate-transcripts.yml` |
| Create | `static/transcripts/134413658/en.vtt` (POC sample) |

## Video Coverage

| Category | Count |
|----------|-------|
| Total IBM Video IDs in content | 59 |
| Mapped to YouTube | 32 |
| IBM Video only | 27 |
| POC transcript (sample) | 1 (`134413658`) |

## Future Enhancements

- Synced transcript panel below the video (interactive, click-to-seek)
- GPU runners for faster Whisper transcription with `large-v3`
- Batch translation of all 59 videos across all locales
- Quality review workflow for translated transcripts
