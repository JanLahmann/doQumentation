# Video Subtitle Extraction — Claude Cowork + Chrome

Use this prompt with Claude Cowork (Chrome plugin) to extract English subtitles from IBM Video pages that block automated downloads.

## Background

IBM Video hosts 27 course videos that have English subtitles embedded in their HLS streams, but the Akamai CDN blocks all automated access (yt-dlp, ffmpeg, urllib — all get 503). A browser session can access them because the CDN allows browser traffic.

Direct URLs (`video.ibm.com/recorded/{ID}`) show "removed" — use embed URLs (`video.ibm.com/embed/recorded/{ID}`) or our site pages.

## Prompt

```
Extract English subtitles from IBM Video and save as VTT files.

POC: Extract subtitles from this one video only:
  132414879 (VQE Ansatz, ~8 min, Quantum Chemistry with VQE course)
  Embed URL: https://video.ibm.com/embed/recorded/132414879
  Our page: https://doqumentation.org/learning/courses/quantum-chem-with-vqe/ansatz

Steps:
1. Open the embed URL in the browser
2. Open Chrome DevTools → Network tab
3. Enable CC/subtitles on the video player
4. Play the video — observe network requests for VTT subtitle chunks

Key insight: Subtitle chunks live at path /rfc/8/ and video chunks at /rfc/1/.
The chunk hashes are shared between subtitle and video chunks at the same chunk
number. So once you discover a few chunk hashes from network requests, you can
construct all subtitle chunk URLs by using the /rfc/8/ path with those hashes.

Extraction approach:
1. From network requests, identify the subtitle chunk URL pattern:
   https://uhs-akamai.ustream.tv/.../rfc/8/chunk_{N}_{HASH}.vtt
2. Note that video chunks use the same hash at /rfc/1/:
   https://uhs-akamai.ustream.tv/.../rfc/1/chunk_{N}_{HASH}.ts
3. Fetch all VTT chunks in the browser JS context (they share the same CDN session):

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

4. Concatenate chunks, deduplicate overlapping cues, and format as clean VTT:

WEBVTT

{timestamp1} --> {timestamp2}
{subtitle text}

{timestamp3} --> {timestamp4}
{subtitle text}

...

5. Save to: static/transcripts/132414879/en.vtt

Verify:
- File starts with WEBVTT
- Timestamps are sequential (no gaps, no overlaps)
- No empty cue text
- No duplicate cues (chunks may overlap at boundaries — deduplicate by timestamp)
```

## Scaling to all 27 videos

For the remaining 26 videos, the same workflow applies: load the embed URL, enable CC, discover chunk hashes from network requests, fetch all VTT chunks in the browser JS context, deduplicate, and write the file.

Video IDs (by course):

| Course | Video IDs |
|--------|-----------|
| Quantum Chemistry with VQE | 132414879, 132414895, 132414916, 132414924, 132414925 |
| Quantum Business Foundations | 132596522, 132984196, 133010485, 133185610, 133345140, 133345141, 133345142, 134056407, 134056414, 134056416, 134056420 |
| Quantum Machine Learning | 133981147, 133981150, 134355930 |
| Guides (demos) | 134371939, 134371940, 134371941 |
| Utility-Scale QC | 134399598 |
| Integrating Quantum + HPC | 134680643, 134680646, 134680652, 134680662 |

## Notes

- CDN tokens expire quickly (~60 seconds). Work one video at a time.
- Some videos may not have subtitles — if no .vtt requests appear after enabling CC and playing for 30 seconds, skip and note which ones.
- VTT chunks use 6-second segments. A typical 8-minute video has ~80 chunks.
- After extraction, VTT files are translated using the same Claude Code workflow as YouTube transcripts.
