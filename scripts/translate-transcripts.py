#!/usr/bin/env python3
"""Translate VTT transcripts to other languages using an LLM.

Reads English VTT files from static/transcripts/{id}/en.vtt, translates
the cue text (preserving timestamps), and writes to {id}/{locale}.vtt.

Usage:
    # Translate one video to German
    python scripts/translate-transcripts.py --video-id 134413658 --locale de

    # Translate all transcripts to Japanese
    python scripts/translate-transcripts.py --locale ja

    # Dry run — show what would be translated
    python scripts/translate-transcripts.py --locale de --dry-run

Requirements:
    pip install anthropic
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = REPO_ROOT / "static" / "transcripts"

LOCALE_NAMES: dict[str, str] = {
    "de": "German",
    "ja": "Japanese",
    "uk": "Ukrainian",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "tl": "Tagalog/Filipino",
    "th": "Thai",
    "ar": "Arabic",
    "he": "Hebrew",
}

SYSTEM_PROMPT = """\
You are a professional translator specializing in quantum computing education.
Translate the following VTT subtitle file from English to {language}.

Rules:
- Preserve ALL VTT formatting exactly: the "WEBVTT" header, blank lines between cues, \
and all timestamp lines (HH:MM:SS.mmm --> HH:MM:SS.mmm)
- Translate ONLY the cue text lines (the lines after each timestamp)
- Keep standard quantum computing terms in English: qubit, gate, circuit, backend, \
transpiler, Hadamard, Qiskit, BB84
- Keep proper names unchanged (Alice, Bob, Eve, Bennett, Brassard)
- Use natural, fluent {language} — not word-for-word translation
- Use {register}
- Output ONLY the translated VTT file, nothing else
"""

REGISTER_MAP: dict[str, str] = {
    "de": 'informal register ("du" not "Sie")',
    "ja": "polite (です/ます) but not overly formal",
    "uk": 'informal ("ти" not "Ви")',
    "es": 'informal ("tú" not "usted")',
    "fr": 'informal ("tu" not "vous")',
    "it": 'informal ("tu" not "Lei")',
    "pt": 'informal ("você" casual)',
    "tl": "casual (no po/opo)",
    "th": "casual (no ครับ/ค่ะ)",
    "ar": "informal register",
    "he": "informal register",
}


def parse_vtt(text: str) -> list[dict]:
    """Parse VTT into a list of cues with timestamps and text."""
    cues = []
    # Split by blank lines
    blocks = re.split(r"\n\n+", text.strip())
    for block in blocks:
        if block.strip() == "WEBVTT":
            continue
        lines = block.strip().split("\n")
        # Find timestamp line
        ts_idx = None
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_idx = i
                break
        if ts_idx is not None:
            cues.append({
                "timestamp": lines[ts_idx],
                "text": "\n".join(lines[ts_idx + 1:]),
            })
    return cues


def validate_vtt(original: str, translated: str) -> list[str]:
    """Validate that translated VTT preserves structure of original."""
    errors = []
    orig_cues = parse_vtt(original)
    trans_cues = parse_vtt(translated)

    if len(orig_cues) != len(trans_cues):
        errors.append(
            f"Cue count mismatch: original has {len(orig_cues)}, "
            f"translated has {len(trans_cues)}"
        )
        return errors

    for i, (orig, trans) in enumerate(zip(orig_cues, trans_cues)):
        if orig["timestamp"] != trans["timestamp"]:
            errors.append(
                f"Cue {i + 1}: timestamp mismatch — "
                f"expected '{orig['timestamp']}', got '{trans['timestamp']}'"
            )

    if not translated.strip().startswith("WEBVTT"):
        errors.append("Missing WEBVTT header")

    return errors


def translate_vtt(
    english_vtt: str,
    locale: str,
    client: "anthropic.Anthropic",
    model: str,
) -> str:
    """Translate a VTT file using Claude."""
    language = LOCALE_NAMES[locale]
    register = REGISTER_MAP.get(locale, "informal register")

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT.format(language=language, register=register),
        messages=[{"role": "user", "content": english_vtt}],
    )
    return response.content[0].text


def process_video(
    ibm_id: str,
    locale: str,
    client: "anthropic.Anthropic",
    model: str,
    force: bool,
) -> bool:
    """Translate one video's transcript."""
    en_file = TRANSCRIPTS_DIR / ibm_id / "en.vtt"
    dest_file = TRANSCRIPTS_DIR / ibm_id / f"{locale}.vtt"

    if not en_file.exists():
        print(f"  Skipping {ibm_id} — no English transcript")
        return False

    if dest_file.exists() and not force:
        print(f"  Skipping {ibm_id} — {locale}.vtt already exists")
        return False

    english_vtt = en_file.read_text()
    print(f"  Translating to {LOCALE_NAMES[locale]}...")

    translated = translate_vtt(english_vtt, locale, client, model)

    # Validate
    errors = validate_vtt(english_vtt, translated)
    if errors:
        print(f"  Validation warnings for {ibm_id}:")
        for err in errors:
            print(f"    - {err}")
        # Still save — warnings are informational for now

    dest_file.write_text(translated)
    print(f"  Saved {dest_file}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Translate VTT transcripts using Claude"
    )
    parser.add_argument(
        "--video-id", help="IBM Video ID to translate (default: all with en.vtt)"
    )
    parser.add_argument(
        "--locale", required=True, help="Target locale (e.g., de, ja, es)"
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing translations"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be translated"
    )
    args = parser.parse_args()

    if args.locale not in LOCALE_NAMES:
        print(
            f"Error: Unknown locale '{args.locale}'. "
            f"Supported: {', '.join(sorted(LOCALE_NAMES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Find all videos with English transcripts
    all_ids = sorted(
        d.name
        for d in TRANSCRIPTS_DIR.iterdir()
        if d.is_dir() and (d / "en.vtt").exists()
    )

    if args.video_id:
        if args.video_id not in all_ids:
            print(
                f"Error: No English transcript for {args.video_id}. "
                f"Run generate-transcripts.py first.",
                file=sys.stderr,
            )
            sys.exit(1)
        target_ids = [args.video_id]
    else:
        target_ids = all_ids

    if args.dry_run:
        for ibm_id in target_ids:
            dest = TRANSCRIPTS_DIR / ibm_id / f"{args.locale}.vtt"
            status = "exists (skip)" if dest.exists() and not args.force else "will translate"
            print(f"  {ibm_id}: {status}")
        return

    if anthropic is None:
        print(
            "Error: anthropic package not found. Install with: pip install anthropic",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic()
    translated = 0
    for ibm_id in target_ids:
        print(f"\n[{ibm_id}]")
        if process_video(ibm_id, args.locale, client, args.model, args.force):
            translated += 1

    print(f"\nDone. Translated {translated} transcript(s) to {LOCALE_NAMES[args.locale]}.")


if __name__ == "__main__":
    main()
