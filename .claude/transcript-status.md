# Video Transcript Status

Generated: 2026-04-04

59 `<IBMVideo>` components in content. Two underlying platforms:
- **YouTube** (32 videos): mapped via `YOUTUBE_MAP` in `IBMVideo.tsx`, transcripts via `youtube-transcript-api`
- **IBM Video** (27 videos): `video.ibm.com`, transcripts extracted manually via browser (Akamai CDN blocks automation)

Translations cover 17 languages: ar, cs, de, es, fr, he, id, it, ja, ko, ms, pl, pt, ro, th, tl, uk.

## Summary

| Status | YouTube | IBM Video | Total |
|--------|---------|-----------|-------|
| EN + 17 translations (complete) | 32 | 1 | 33 |
| EN only (needs translation) | 0 | 22 | 22 |
| No transcript at all | 0 | 4 | 4 |
| **Total** | **32** | **27** | **59** |

## Fully translated (33 videos)

All have `en.vtt` + 17 locale VTTs. Squash-merged from two branches on 2026-04-04:
- `archive/claude/check-translation-status-aXqD6` (ar, de, es, fr, he, it, ja, ko, pt, th, tl, uk)
- `archive/claude/translate-video-transcripts-c747O` (cs, id, ms, pl, ro)

**32 YouTube-mapped** (all by John Watrous, Katie McCormick, Chris Porter, Olivia Lanes, Darío Gil):
132414879, 134056207, 134056217, 134056222, 134056223, 134056224, 134056231, 134056235,
134056243, 134063416, 134063421, 134063422, 134063423, 134063424, 134063425, 134063426,
134082557, 134212334, 134313287, 134325501, 134325510, 134325519, 134352398, 134397390,
134413658, 134413660, 134413662, 134413665, 134413671, 134413680, 134413695, 134460549

**1 IBM Video only**: 134627974

## EN transcript only — needs translation (22 IBM Video)

All EN transcripts are committed (2026-04-04). Translations into 17 languages still needed.

### Quantum Business Foundations (11 videos)

| Video ID | Page | Speaker / Topic |
|----------|------|-----------------|
| 132596522 | introduction-to-quantum-computing | Victoria Lipinska — QC overview |
| 134056414 | introduction-to-quantum-computing | Katie Pizzolato — QC applications |
| 133010485 | introduction-to-quantum-computing | Victoria Lipinska — problem classes |
| 132984196 | quantum-computing-fundamentals | Katie Pizzolato — QC myths |
| 133345142 | quantum-computing-fundamentals | Darío Gil — bits vs qubits |
| 134056407 | quantum-computing-fundamentals | Antonio Corcoles — superposition |
| 133345141 | quantum-computing-fundamentals | Darío Gil — circuits and gates |
| 134056416 | quantum-computing-fundamentals | Qiskit pronunciation & features |
| 133345140 | quantum-technology | Darío Gil — quantum volume |
| 134056420 | quantum-technology | Error mitigation |
| 133185610 | how-to-become-quantum-ready | Olivia Lanes — responsible QC |

### Quantum Chemistry with VQE (4 videos)

| Video ID | Page | Speaker / Topic |
|----------|------|-----------------|
| 132414895 | introduction | Victoria Lipinska — VQE overview |
| 132414916 | classical-optimizers | Victoria Lipinska — classical optimizers |
| 132414924 | hamiltonian-construction | Victoria Lipinska — Hamiltonians |
| 132414925 | ground-state | Victoria Lipinska — combining components |

### Quantum Machine Learning (3 videos)

| Video ID | Page | Speaker / Topic |
|----------|------|-----------------|
| 134355930 | introduction | Chris Porter — subspace quantum diagonalization |
| 133981147 | classical-ml-review | Chris Porter — kernel methods |
| 133981150 | classical-ml-review | Chris Porter — neural networks |

### Integrating Quantum and HPC (4 videos)

| Video ID | Page | Speaker / Topic |
|----------|------|-----------------|
| 134680662 | introduction | Iskandar Sitdikov — HPC & QC intro |
| 134680643 | programming-models | Iskandar Sitdikov — programming models |
| 134680652 | compute-resources | Iskandar Sitdikov — computing resources |
| 134680646 | sqd-skqd | Iskandar Sitdikov — hybrid calculation |

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

1. **Translate** the 22 EN-only videos into 17 languages using `scripts/translate-transcripts.py`
2. **Investigate** the 4 missing videos — extract subtitles if they have spoken content, or mark as no-subtitle demos
