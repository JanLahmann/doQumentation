#!/usr/bin/env python3
"""Generate English VTT transcripts from course videos.

YouTube videos: uses youtube-transcript-api (instant, no download needed).
IBM Video: must be extracted via browser (see scripts/video-subtitle-cowork-prompt.md).

Usage:
    # Transcribe all YouTube-mapped videos
    python scripts/generate-transcripts.py

    # Transcribe a specific video by IBM Video ID
    python scripts/generate-transcripts.py --video-id 134413658

    # Force overwrite existing transcripts
    python scripts/generate-transcripts.py --force

    # List all video IDs and their status
    python scripts/generate-transcripts.py --list

Requirements:
    pip install youtube-transcript-api

Alternative (Whisper — higher quality but much slower):
    pip install openai-whisper yt-dlp
    # Download audio + run Whisper locally:
    yt-dlp -x --audio-format wav -o "/tmp/{id}.wav" "https://youtube.com/watch?v={yt_id}"
    whisper /tmp/{id}.wav --model medium --output_format vtt --language en
    # Produces cleaner sentence-level cues but takes ~5 min/video on Apple Silicon.
    # Use for videos where YouTube captions are unavailable or very low quality.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

REPO_ROOT = Path(__file__).resolve().parent.parent
IBMVIDEO_TSX = REPO_ROOT / "src" / "components" / "CourseComponents" / "IBMVideo.tsx"
TRANSCRIPTS_DIR = REPO_ROOT / "static" / "transcripts"

# Known Whisper/YouTube transcription errors → corrections
CORRECTIONS = {
    "Kisket": "Qiskit",
    "KisKit": "Qiskit",
    "Kiskuit": "Qiskit",
    "Kizkit": "Qiskit",
    "kiskit": "Qiskit",
    "Watchras": "Watrous",
    "Wautrous": "Watrous",
}


def load_youtube_map() -> dict[str, str]:
    """Parse IBM Video ID → YouTube ID mapping from IBMVideo.tsx."""
    text = IBMVIDEO_TSX.read_text()
    return dict(re.findall(r"'(\d+)':\s*'([A-Za-z0-9_-]+)'", text))


def collect_all_ibm_ids() -> set[str]:
    """Collect all IBM Video IDs referenced in content files."""
    ids: set[str] = set()
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.exists():
        for mdx_file in docs_dir.rglob("*.mdx"):
            text = mdx_file.read_text(errors="ignore")
            ids.update(re.findall(r'IBMVideo\s+id="(\d+)"', text))
    return ids


def apply_corrections(text: str) -> str:
    """Fix known transcription errors."""
    for wrong, right in CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def fetch_youtube_transcript(youtube_id: str) -> list[dict]:
    """Fetch transcript from YouTube and merge into clean cues."""
    api = YouTubeTranscriptApi()
    raw = list(api.fetch(youtube_id))

    # Merge short consecutive cues into ~6-8 second non-overlapping groups
    # Split at sentence boundaries when possible
    groups = []
    buf_start = raw[0].start
    buf_texts = []

    for i, entry in enumerate(raw):
        buf_texts.append(entry.text)
        next_start = raw[i + 1].start if i + 1 < len(raw) else entry.start + entry.duration

        elapsed = next_start - buf_start
        ends_sentence = entry.text.rstrip().endswith((".", "!", "?"))

        if elapsed >= 6 or (elapsed >= 3 and ends_sentence):
            groups.append({
                "start": buf_start,
                "end": next_start,
                "text": " ".join(buf_texts),
            })
            buf_start = next_start
            buf_texts = []

    if buf_texts:
        groups.append({
            "start": buf_start,
            "end": raw[-1].start + raw[-1].duration,
            "text": " ".join(buf_texts),
        })

    return groups


def format_vtt(cues: list[dict]) -> str:
    """Format cue list as VTT string."""
    lines = ["WEBVTT", ""]
    for i, cue in enumerate(cues, 1):
        start, end = cue["start"], cue["end"]
        sm, ss = int(start // 60), start % 60
        em, es = int(end // 60), end % 60
        text = apply_corrections(cue["text"])
        lines.append(str(i))
        lines.append(f"{sm:02d}:{ss:06.3f} --> {em:02d}:{es:06.3f}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def process_video(ibm_id: str, youtube_id: str) -> bool:
    """Fetch transcript and save VTT for one YouTube video."""
    dest_dir = TRANSCRIPTS_DIR / ibm_id
    dest_file = dest_dir / "en.vtt"

    if dest_file.exists():
        print(f"  Skipping — transcript already exists")
        return False

    cues = fetch_youtube_transcript(youtube_id)
    vtt = format_vtt(cues)

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file.write_text(vtt)
    print(f"  Saved {len(cues)} cues → {dest_file}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate VTT transcripts from YouTube captions"
    )
    parser.add_argument("--video-id", help="IBM Video ID to transcribe (default: all YouTube-mapped)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing transcripts")
    parser.add_argument("--list", action="store_true", help="List all video IDs and status")
    args = parser.parse_args()

    if YouTubeTranscriptApi is None:
        print("Error: youtube-transcript-api not found. Install with: pip install youtube-transcript-api",
              file=sys.stderr)
        sys.exit(1)

    youtube_map = load_youtube_map()
    all_ibm_ids = collect_all_ibm_ids() | set(youtube_map.keys())

    if args.list:
        for ibm_id in sorted(all_ibm_ids):
            yt_id = youtube_map.get(ibm_id)
            has_vtt = (TRANSCRIPTS_DIR / ibm_id / "en.vtt").exists()
            source = f"YouTube: {yt_id}" if yt_id else "IBM Video only"
            status = "✓" if has_vtt else " "
            print(f"  [{status}] {ibm_id}  {source}")
        yt_count = sum(1 for i in all_ibm_ids if i in youtube_map)
        ibm_count = len(all_ibm_ids) - yt_count
        has_count = sum(1 for i in all_ibm_ids if (TRANSCRIPTS_DIR / i / "en.vtt").exists())
        print(f"\n{len(all_ibm_ids)} total: {yt_count} YouTube, {ibm_count} IBM Video only. {has_count} transcribed.")
        return

    if args.video_id:
        if args.video_id not in youtube_map:
            print(f"Error: {args.video_id} has no YouTube mapping. Use Cowork for IBM Video.",
                  file=sys.stderr)
            sys.exit(1)
        target = [(args.video_id, youtube_map[args.video_id])]
    else:
        target = [(ibm_id, yt_id) for ibm_id, yt_id in sorted(youtube_map.items())]

    generated = 0
    errors = 0
    for ibm_id, yt_id in target:
        print(f"\n[{ibm_id}] YouTube: {yt_id}")

        if args.force:
            dest = TRANSCRIPTS_DIR / ibm_id / "en.vtt"
            if dest.exists():
                dest.unlink()

        try:
            if process_video(ibm_id, yt_id):
                generated += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1

    print(f"\nDone. Generated {generated}, skipped {len(target) - generated - errors}, errors {errors}.")


if __name__ == "__main__":
    main()
