# Video Transcript Status

Updated: 2026-04-07

59 `<IBMVideo>` components in content. Two underlying platforms:
- **YouTube** (32 videos): mapped via `YOUTUBE_MAP` in `IBMVideo.tsx`, transcripts via `youtube-transcript-api`
- **IBM Video** (27 videos): `video.ibm.com`, transcripts extracted manually via browser (Akamai CDN blocks automation)

Translations cover 17 languages: ar, cs, de, es, fr, he, id, it, ja, ko, ms, pl, pt, ro, th, tl, uk.

## Summary

| Status | YouTube | IBM Video | Total |
|--------|---------|-----------|-------|
| EN + 17 translations (complete) | 32 | 23 | 55 |
| No transcript at all | 0 | 4 | 4 |
| **Total** | **32** | **27** | **59** |

## Fully translated (55 videos)

All have `en.vtt` + 17 locale VTTs (ar, cs, de, es, fr, he, id, it, ja, ko, ms, pl, pt, ro, th, tl, uk).

### Batch 1 — Squash-merged 2026-04-04

- `archive/claude/check-translation-status-aXqD6` (ar, de, es, fr, he, it, ja, ko, pt, th, tl, uk)
- `archive/claude/translate-video-transcripts-c747O` (cs, id, ms, pl, ro)

**32 YouTube-mapped** (John Watrous, Katie McCormick, Chris Porter, Olivia Lanes, Darío Gil):
132414879, 134056207, 134056217, 134056222, 134056223, 134056224, 134056231, 134056235,
134056243, 134063416, 134063421, 134063422, 134063423, 134063424, 134063425, 134063426,
134082557, 134212334, 134313287, 134325501, 134325510, 134325519, 134352398, 134397390,
134413658, 134413660, 134413662, 134413665, 134413671, 134413680, 134413695, 134460549

**1 IBM Video**: 134627974

### Batch 2 — Branch `claude/video-transcript-translations-P5nk1` (2026-04-05 to 2026-04-07)

22 IBM Video transcripts translated via chunked Sonnet agent workflow.
- Session 1 (2026-04-05/06): ar, de, es, fr, id, ja, ms, th, tl, uk
- Session 2 (2026-04-07): it, pt, ko, he, pl, ro, cs

#### Quantum Business Foundations (11 videos)
132596522, 134056414, 133010485, 132984196, 133345142, 134056407, 133345141, 134056416, 133345140, 134056420, 133185610

#### Quantum Chemistry with VQE (4 videos)
132414895, 132414916, 132414924, 132414925

#### Quantum Machine Learning (3 videos)
134355930, 133981147, 133981150

#### Integrating Quantum and HPC (4 videos)
134680662, 134680643, 134680652, 134680646

## Missing transcripts entirely (4 videos)

Referenced in codebase but have **no transcript directory**. Likely demo/screencast videos without spoken subtitles.

| Video ID | Page | Notes |
|----------|------|-------|
| 134371939 | guides/qiskit-code-assistant-vscode | VS Code demo |
| 134371940 | guides/execution-modes | Session job demo |
| 134371941 | guides/qiskit-code-assistant-jupyterlab | JupyterLab demo |
| 134399598 | (unknown — needs investigation) | No transcript, no directory |

## Technical notes

- YouTube transcripts: auto-generated, fetched via `scripts/generate-transcripts.py` (instant)
- IBM Video transcripts: manual browser extraction, documented in `scripts/video-subtitle-cowork-prompt.md`
- Translation: `scripts/translate-transcripts.py` — Claude Sonnet chunked workflow (~248 lines/chunk)
- Locale fallback: `IBMVideo.tsx` tries `{locale}.vtt` → falls back to `en.vtt`
- IBM Video sync: postMessage API (handshake → progress polling at 500ms)
- YouTube sync: IFrame API with 250ms polling
- Akamai CDN tokens expire ~60s — extract one video at a time
- `YOUTUBE_MAP` in `IBMVideo.tsx` is source of truth for YouTube ↔ IBM Video ID mapping

## Next steps

1. **Investigate** the 4 missing videos — extract subtitles if they have spoken content, or mark as no-subtitle demos
