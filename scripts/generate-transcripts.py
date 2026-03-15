#!/usr/bin/env python3
"""Generate English VTT transcripts from course videos using Whisper.

Downloads audio from YouTube via yt-dlp, transcribes with OpenAI Whisper,
and saves VTT files to static/transcripts/{ibm_video_id}/en.vtt.

Usage:
    # Transcribe all videos
    python scripts/generate-transcripts.py

    # Transcribe a specific video by IBM Video ID
    python scripts/generate-transcripts.py --video-id 134056207

    # Use a specific Whisper model (default: medium)
    python scripts/generate-transcripts.py --model large-v3

Requirements:
    pip install openai-whisper yt-dlp
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEO_MAP_PATH = REPO_ROOT / "scripts" / "video-map.json"
TRANSCRIPTS_DIR = REPO_ROOT / "static" / "transcripts"


def load_video_map() -> dict[str, str]:
    """Load IBM Video ID → YouTube ID mapping."""
    with open(VIDEO_MAP_PATH) as f:
        return json.load(f)


def download_audio(youtube_id: str, output_path: Path) -> Path:
    """Download audio from YouTube using yt-dlp."""
    audio_file = output_path / f"{youtube_id}.%(ext)s"
    cmd = [
        "yt-dlp",
        "-x",                          # extract audio only
        "--audio-format", "wav",        # wav for whisper compatibility
        "--audio-quality", "0",         # best quality
        "-o", str(audio_file),
        f"https://www.youtube.com/watch?v={youtube_id}",
    ]
    print(f"  Downloading audio for {youtube_id}...")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_path / f"{youtube_id}.wav"


def transcribe(audio_path: Path, model_name: str, output_dir: Path) -> Path:
    """Run Whisper to generate a VTT transcript."""
    cmd = [
        "whisper",
        str(audio_path),
        "--model", model_name,
        "--output_format", "vtt",
        "--language", "en",
        "--output_dir", str(output_dir),
    ]
    print(f"  Transcribing with model '{model_name}'...")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_dir / f"{audio_path.stem}.vtt"


def process_video(ibm_id: str, youtube_id: str, model_name: str) -> bool:
    """Download, transcribe, and save VTT for one video."""
    dest_dir = TRANSCRIPTS_DIR / ibm_id
    dest_file = dest_dir / "en.vtt"

    if dest_file.exists():
        print(f"  Skipping {ibm_id} — transcript already exists at {dest_file}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        audio_path = download_audio(youtube_id, tmppath)
        vtt_path = transcribe(audio_path, model_name, tmppath)

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vtt_path, dest_file)
        print(f"  Saved transcript to {dest_file}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate VTT transcripts using Whisper")
    parser.add_argument("--video-id", help="IBM Video ID to transcribe (default: all)")
    parser.add_argument("--model", default="medium", help="Whisper model (default: medium)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing transcripts")
    args = parser.parse_args()

    if not shutil.which("yt-dlp"):
        print("Error: yt-dlp not found. Install with: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)

    video_map = load_video_map()

    if args.video_id:
        if args.video_id not in video_map:
            print(f"Error: Video ID {args.video_id} not found in {VIDEO_MAP_PATH}", file=sys.stderr)
            sys.exit(1)
        videos = {args.video_id: video_map[args.video_id]}
    else:
        videos = video_map

    generated = 0
    for ibm_id, youtube_id in videos.items():
        print(f"\n[{ibm_id}] YouTube: {youtube_id}")
        if args.force:
            dest = TRANSCRIPTS_DIR / ibm_id / "en.vtt"
            if dest.exists():
                dest.unlink()
        if process_video(ibm_id, youtube_id, args.model):
            generated += 1

    print(f"\nDone. Generated {generated} transcript(s).")


if __name__ == "__main__":
    main()
