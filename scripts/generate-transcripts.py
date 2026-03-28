#!/usr/bin/env python3
"""Generate English VTT transcripts from course videos using Whisper.

Downloads audio via yt-dlp (supports both IBM Video and YouTube sources),
transcribes with OpenAI Whisper, and saves VTT files to
static/transcripts/{ibm_video_id}/en.vtt.

Usage:
    # Transcribe all videos (uses YouTube when available, IBM Video otherwise)
    python scripts/generate-transcripts.py

    # Transcribe a specific video by IBM Video ID
    python scripts/generate-transcripts.py --video-id 134413658

    # Force IBM Video as the source (skip YouTube even if mapped)
    python scripts/generate-transcripts.py --video-id 134413658 --source ibm

    # Use a specific Whisper model (default: medium)
    python scripts/generate-transcripts.py --model large-v3

Requirements:
    pip install openai-whisper yt-dlp
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IBMVIDEO_TSX = REPO_ROOT / "src" / "components" / "CourseComponents" / "IBMVideo.tsx"
TRANSCRIPTS_DIR = REPO_ROOT / "static" / "transcripts"


def load_youtube_map() -> dict[str, str]:
    """Parse IBM Video ID → YouTube ID mapping from IBMVideo.tsx."""
    text = IBMVIDEO_TSX.read_text()
    return dict(re.findall(r"'(\d+)':\s*'([A-Za-z0-9_-]+)'", text))


def collect_all_ibm_ids() -> set[str]:
    """Collect all IBM Video IDs referenced in content files."""
    ids: set[str] = set()
    i18n_dir = REPO_ROOT / "i18n"
    docs_dir = REPO_ROOT / "docs"
    for search_dir in [docs_dir, i18n_dir]:
        if not search_dir.exists():
            continue
        for mdx_file in search_dir.rglob("*.mdx"):
            text = mdx_file.read_text(errors="ignore")
            ids.update(re.findall(r'IBMVideo\s+id="(\d+)"', text))
    return ids


def video_url(ibm_id: str, youtube_id: str | None, source: str) -> str:
    """Build the download URL based on source preference."""
    if source == "youtube" and youtube_id:
        return f"https://www.youtube.com/watch?v={youtube_id}"
    # IBM Video: yt-dlp supports video.ibm.com URLs
    return f"https://video.ibm.com/recorded/{ibm_id}"


def download_audio(url: str, output_path: Path, label: str) -> Path:
    """Download audio from a video URL using yt-dlp."""
    audio_file = output_path / f"{label}.%(ext)s"
    cmd = [
        "yt-dlp",
        "-x",                          # extract audio only
        "--audio-format", "wav",        # wav for whisper compatibility
        "--audio-quality", "0",         # best quality
        "-o", str(audio_file),
        url,
    ]
    print(f"  Downloading audio from {url}...")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_path / f"{label}.wav"


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


def process_video(
    ibm_id: str,
    youtube_id: str | None,
    model_name: str,
    source: str,
) -> bool:
    """Download, transcribe, and save VTT for one video."""
    dest_dir = TRANSCRIPTS_DIR / ibm_id
    dest_file = dest_dir / "en.vtt"

    if dest_file.exists():
        print(f"  Skipping {ibm_id} — transcript already exists at {dest_file}")
        return False

    url = video_url(ibm_id, youtube_id, source)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        audio_path = download_audio(url, tmppath, ibm_id)
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
    parser.add_argument(
        "--source",
        choices=["auto", "ibm", "youtube"],
        default="auto",
        help="Video source: 'auto' prefers YouTube when mapped, 'ibm' forces IBM Video, "
             "'youtube' forces YouTube (only works for mapped videos)",
    )
    args = parser.parse_args()

    if not shutil.which("yt-dlp"):
        print("Error: yt-dlp not found. Install with: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)

    youtube_map = load_youtube_map()
    all_ibm_ids = collect_all_ibm_ids() | set(youtube_map.keys())

    if args.video_id:
        if args.video_id not in all_ibm_ids:
            print(f"Error: Video ID {args.video_id} not found in content or {IBMVIDEO_TSX}", file=sys.stderr)
            sys.exit(1)
        target_ids = [args.video_id]
    else:
        target_ids = sorted(all_ibm_ids)

    # Determine effective source per video
    source_pref = args.source

    generated = 0
    errors = 0
    for ibm_id in target_ids:
        yt_id = youtube_map.get(ibm_id)
        effective_source = source_pref
        if effective_source == "auto":
            effective_source = "youtube" if yt_id else "ibm"
        if effective_source == "youtube" and not yt_id:
            print(f"\n[{ibm_id}] No YouTube mapping — skipping (use --source auto or ibm)")
            continue

        src_label = f"YouTube: {yt_id}" if effective_source == "youtube" else "IBM Video"
        print(f"\n[{ibm_id}] {src_label}")

        if args.force:
            dest = TRANSCRIPTS_DIR / ibm_id / "en.vtt"
            if dest.exists():
                dest.unlink()
        try:
            if process_video(ibm_id, yt_id, args.model, effective_source):
                generated += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1

    print(f"\nDone. Generated {generated} transcript(s), {errors} error(s).")


if __name__ == "__main__":
    main()
