# Video Subtitle Extraction — Claude Cowork + Chrome

Use this prompt with Claude Cowork (Chrome plugin) to extract English subtitles from IBM Video embeds.

## Background

IBM Video hosts 27 course videos with English subtitles in their HLS streams. The Akamai CDN blocks automated access (yt-dlp, ffmpeg — all get 503), but a browser session can access them. Direct URLs (`video.ibm.com/recorded/{ID}`) show "removed" — use embed URLs or our site pages.

## Prompt

```
Extract English subtitles from IBM Video embeds and save as VTT files.

For each video ID below:
1. Open the embed URL: https://video.ibm.com/embed/recorded/{VIDEO_ID}?html5ui
   Or open the course page on our site (listed below)
2. Open Chrome DevTools → Network tab
3. Enable CC/subtitles on the video player
4. Play the video — observe network requests for VTT subtitle chunks

Key insight: Subtitle chunks live at path /rfc/7/ or /rfc/8/ (varies per video)
and video chunks at /rfc/1/. The chunk hashes are shared between subtitle and
video at the same chunk number. Once you discover a few chunk hashes from network
requests, you can construct all subtitle chunk URLs by trying both /rfc/7/ and
/rfc/8/ paths with those hashes.

Extraction approach:
1. From network requests, identify the subtitle chunk URL pattern:
   https://uhs-akamai.ustream.tv/.../rfc/7/chunk_{N}_{HASH}.vtt  (or /rfc/8/)
2. Fetch all VTT chunks in the browser JS context:

   // In DevTools Console:
   async function fetchAllSubtitles(baseUrl, hash, count) {
     const cues = [];
     for (let i = 0; i < count; i++) {
       const url = baseUrl.replace('chunk_0', `chunk_${i}`);
       const resp = await fetch(url);
       const text = await resp.text();
       cues.push(text);
     }
     return cues;
   }

3. Concatenate chunks, deduplicate overlapping cues, and format as clean VTT:

WEBVTT

1
{timestamp1} --> {timestamp2}
{subtitle text}

2
{timestamp3} --> {timestamp4}
{subtitle text}

...

4. Save to: static/transcripts/{VIDEO_ID}/en.vtt

Verify each file:
- Starts with WEBVTT
- Timestamps are sequential
- No empty cue text
- No duplicate cues (chunks may overlap at boundaries)

Video IDs to process:

Quantum Chemistry with VQE:
  132414879 → /learning/courses/quantum-chem-with-vqe/ansatz (DONE — POC)
  132414895 → /learning/courses/quantum-chem-with-vqe/introduction
  132414916 → /learning/courses/quantum-chem-with-vqe/classical-optimizers
  132414924 → /learning/courses/quantum-chem-with-vqe/hamiltonian-construction
  132414925 → /learning/courses/quantum-chem-with-vqe/ground-state

Quantum Business Foundations:
  132596522 → /learning/courses/quantum-business-foundations/introduction-to-quantum-computing
  132984196 → /learning/courses/quantum-business-foundations/quantum-computing-fundamentals
  133010485 → /learning/courses/quantum-business-foundations/introduction-to-quantum-computing
  133185610 → /learning/courses/quantum-business-foundations/how-to-become-quantum-ready
  133345140 → /learning/courses/quantum-business-foundations/quantum-technology
  133345141 → /learning/courses/quantum-business-foundations/quantum-computing-fundamentals
  133345142 → /learning/courses/quantum-business-foundations/quantum-computing-fundamentals
  134056407 → /learning/courses/quantum-business-foundations/quantum-computing-fundamentals
  134056414 → /learning/courses/quantum-business-foundations/introduction-to-quantum-computing
  134056416 → /learning/courses/quantum-business-foundations/quantum-computing-fundamentals
  134056420 → /learning/courses/quantum-business-foundations/quantum-technology

Quantum Machine Learning:
  133981147 → /learning/courses/quantum-machine-learning/classical-ml-review
  133981150 → /learning/courses/quantum-machine-learning/classical-ml-review
  134355930 → /learning/courses/quantum-machine-learning/introduction (may be removed)

Guides (demo videos):
  134371939 → /guides/qiskit-code-assistant-vscode
  134371940 → /guides/execution-modes
  134371941 → /guides/qiskit-code-assistant-jupyterlab

Utility-Scale Quantum Computing:
  134399598 → /learning/courses/utility-scale-quantum-computing/quantum-phase-estimation

Integrating Quantum and HPC:
  134680643 → /learning/courses/integrating-quantum-and-high-performance-computing/programming-models
  134680646 → /learning/courses/integrating-quantum-and-high-performance-computing/sqd-skqd
  134680652 → /learning/courses/integrating-quantum-and-high-performance-computing/compute-resources
  134680662 → /learning/courses/integrating-quantum-and-high-performance-computing/introduction

Total: 27 videos (1 done, 26 remaining).
```

## Alternative (requires auth)

IBM Video has a REST API: `GET https://api.video.ibm.com/videos/{ID}/captions/en/vtt` — but it returns 401 (requires channel owner API token). If we ever get API access, this would be much simpler than the browser approach.

## Notes

- CDN tokens expire quickly (~60 seconds). Work one video at a time.
- Some videos may not have subtitles — if no .vtt requests appear after enabling CC and playing for 30 seconds, skip and note which ones.
- VTT chunks use 6-second segments. A typical 8-minute video has ~80 chunks.
- Some pages have multiple videos — each has its own IBM Video ID.
- 134355930 may have been removed — skip if unavailable.
- After extraction, VTT files are translated using Claude Code (same workflow as YouTube transcripts).
