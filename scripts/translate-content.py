#!/usr/bin/env python3
"""
Translation helper for doQumentation MDX content.

Extracts translatable text from MDX files into batch JSON files,
preserving code blocks, math, JSX, and frontmatter structure.
After translation (by Claude Code or API), reassembles complete MDX files
into the Docusaurus i18n directory structure.

Usage:
    # Extract translatable segments from listed pages:
    python scripts/translate-content.py extract --pages pages.txt --locale de

    # Reassemble translated MDX from batch JSON:
    python scripts/translate-content.py reassemble

    # One-shot: extract, (manual translation), reassemble
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
BATCH_DIR = REPO_ROOT / "translation-batches"
I18N_DIR = REPO_ROOT / "i18n"

# Max files per batch JSON (keeps file sizes manageable for Claude Code)
BATCH_SIZE = 20


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Split MDX into frontmatter dict and body.
    Returns (frontmatter_dict, body) or (None, full_content) if no frontmatter."""
    if not content.startswith("---"):
        return None, content
    end = content.find("\n---", 3)
    if end == -1:
        return None, content
    fm_raw = content[4:end]  # skip first "---\n"
    body = content[end + 4:]  # skip "\n---"

    # Simple YAML parser — handles key: "value" and key: value
    fm = {}
    for line in fm_raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            fm[key] = val
    return fm, body


def rebuild_frontmatter(fm: dict) -> str:
    """Reconstruct YAML frontmatter block."""
    lines = ["---"]
    for key, val in fm.items():
        # Quote values that contain special chars
        if any(c in str(val) for c in ':"{}[]#&*!|>%@'):
            lines.append(f'{key}: "{val}"')
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def segment_mdx(body: str) -> list[dict]:
    """Split MDX body into translatable and non-translatable segments.

    Returns list of {type: "translate"|"preserve", content: str} dicts.
    Segments are ordered and their concatenation equals the original body.
    """
    segments = []
    pos = 0
    text = body

    # Regex patterns for non-translatable blocks
    patterns = [
        # Code fences (```lang ... ```)
        (r"```[^\n]*\n[\s\S]*?```", "code"),
        # JSX comments {/* ... */}
        (r"\{/\*[\s\S]*?\*/\}", "jsx_comment"),
        # JSX self-closing tags on own line: <Component ... />
        (r"^[ \t]*<[A-Z]\w+[^>]*/>\s*$", "jsx_self_close"),
        # Import statements
        (r"^import\s+.*$", "import"),
        # Math display blocks ($$...$$)
        (r"\$\$[\s\S]*?\$\$", "math_block"),
    ]

    # Build a combined pattern that captures any non-translatable block
    combined = "|".join(f"(?P<t{i}>{p})" for i, (p, _) in enumerate(patterns))
    combined_re = re.compile(combined, re.MULTILINE)

    last_end = 0
    for m in combined_re.finditer(text):
        # Text before this match is translatable
        before = text[last_end : m.start()]
        if before:
            segments.append({"type": "translate", "content": before})
        segments.append({"type": "preserve", "content": m.group()})
        last_end = m.end()

    # Trailing text
    trailing = text[last_end:]
    if trailing:
        segments.append({"type": "translate", "content": trailing})

    return segments


# Frontmatter keys whose values should be translated
TRANSLATABLE_FM_KEYS = {"title", "description", "sidebar_label"}


def extract_file(mdx_path: Path, locale: str) -> dict:
    """Extract translatable content from a single MDX file."""
    content = mdx_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    # Relative path from docs/
    rel = mdx_path.relative_to(DOCS_DIR)
    dest = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel

    # Build frontmatter segments
    fm_segments = []
    if fm:
        for key, val in fm.items():
            if key in TRANSLATABLE_FM_KEYS and val:
                fm_segments.append(
                    {"key": key, "type": "translate", "content": val}
                )
            else:
                fm_segments.append(
                    {"key": key, "type": "preserve", "content": val}
                )

    # Build body segments
    body_segments = segment_mdx(body)

    return {
        "source": str(rel),
        "dest": str(dest.relative_to(REPO_ROOT)),
        "frontmatter": fm_segments,
        "body_segments": body_segments,
    }


def cmd_extract(args):
    """Extract translatable segments from MDX files into batch JSON."""
    locale = args.locale
    pages_file = Path(args.pages)
    if not pages_file.exists():
        print(f"Error: pages file not found: {pages_file}", file=sys.stderr)
        sys.exit(1)

    # Read list of pages (relative to docs/ or absolute)
    pages = []
    for line in pages_file.read_text().strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = DOCS_DIR / line if not line.startswith("/") else Path(line)
        if not p.exists():
            print(f"Warning: skipping missing file: {p}", file=sys.stderr)
            continue
        pages.append(p)

    if not pages:
        print("No valid pages found.", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting {len(pages)} pages for locale '{locale}'...")

    # Create batch directory
    BATCH_DIR.mkdir(exist_ok=True)

    # Process files and create batches
    batch_num = 0
    for i in range(0, len(pages), BATCH_SIZE):
        batch_num += 1
        batch_pages = pages[i : i + BATCH_SIZE]
        batch_data = {
            "batch": batch_num,
            "target_locale": locale,
            "locale_label": {"de": "German", "es": "Spanish", "ja": "Japanese",
                             "fr": "French", "uk": "Ukrainian", "it": "Italian",
                             "pt": "Portuguese", "tl": "Tagalog/Filipino",
                             "th": "Thai", "ar": "Arabic",
                             "he": "Hebrew"}.get(locale, locale),
            "status": "pending",  # pending → translated → assembled
            "files": [],
        }

        for page in batch_pages:
            file_data = extract_file(page, locale)
            batch_data["files"].append(file_data)
            print(f"  Extracted: {file_data['source']}")

        batch_path = BATCH_DIR / f"batch-{batch_num:03d}.json"
        batch_path.write_text(
            json.dumps(batch_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  → Wrote {batch_path.name} ({len(batch_pages)} files)")

    print(f"\nDone. {batch_num} batch(es) in {BATCH_DIR}/")
    print("Next: translate the 'translate' segments, then run 'reassemble'.")


FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

BANNER_TEMPLATES = {
    "de": (
        "\n:::note[Noch nicht übersetzt]\n"
        "Diese Seite wurde noch nicht übersetzt. "
        "Sie sehen die englische Originalversion.\n"
        ":::\n"
    ),
    "ja": (
        "\n:::note[未翻訳]\n"
        "このページはまだ翻訳されていません。"
        "英語の原文を表示しています。\n"
        ":::\n"
    ),
    "uk": (
        "\n:::note[Ще не перекладено]\n"
        "Ця сторінка ще не перекладена. "
        "Ви бачите оригінальну англійську версію.\n"
        ":::\n"
    ),
    "es": (
        "\n:::note[Aún no traducido]\n"
        "Esta página aún no ha sido traducida. "
        "Está viendo la versión original en inglés.\n"
        ":::\n"
    ),
    "fr": (
        "\n:::note[Pas encore traduit]\n"
        "Cette page n'a pas encore été traduite. "
        "Vous voyez la version originale en anglais.\n"
        ":::\n"
    ),
    "it": (
        "\n:::note[Non ancora tradotto]\n"
        "Questa pagina non è stata ancora tradotta. "
        "Stai visualizzando la versione originale in inglese.\n"
        ":::\n"
    ),
    "pt": (
        "\n:::note[Ainda não traduzido]\n"
        "Esta página ainda não foi traduzida. "
        "Você está vendo a versão original em inglês.\n"
        ":::\n"
    ),
    "tl": (
        "\n:::note[Hindi pa naisalin]\n"
        "Ang pahinang ito ay hindi pa naisalin. "
        "Nakikita mo ang orihinal na bersyon sa Ingles.\n"
        ":::\n"
    ),
    "th": (
        "\n:::note[ยังไม่ได้แปล]\n"
        "หน้านี้ยังไม่ได้รับการแปล "
        "คุณกำลังดูเวอร์ชันต้นฉบับภาษาอังกฤษ\n"
        ":::\n"
    ),
    "ar": (
        "\n:::note[لم تُترجم بعد]\n"
        "هذه الصفحة لم تُترجم بعد. "
        "يتم عرض المحتوى باللغة الإنجليزية.\n"
        ":::\n"
    ),
    "he": (
        "\n:::note[טרם תורגם]\n"
        "דף זה טרם תורגם. "
        "התוכן מוצג באנגלית.\n"
        ":::\n"
    ),
}


def insert_banner_after_frontmatter(content: str, banner: str) -> str:
    """Insert fallback marker + banner after frontmatter, before body."""
    if not content.startswith("---"):
        return f"{FALLBACK_MARKER}\n{banner}\n{content}"
    end = content.find("\n---", 3)
    if end == -1:
        return f"{FALLBACK_MARKER}\n{banner}\n{content}"
    fm_end = end + 4  # position after "\n---"
    frontmatter = content[:fm_end]
    body = content[fm_end:]
    return f"{frontmatter}\n{FALLBACK_MARKER}\n{banner}\n{body}"


def cmd_populate_locale(args):
    """Populate i18n locale dir with English fallbacks + untranslated banner.

    Copies all MDX files from docs/ to the locale directory.
    Files that already have a genuine translation (no fallback marker) are preserved.
    Files that are old fallbacks (contain the marker) are overwritten with fresh content.
    """
    locale = args.locale
    banner = BANNER_TEMPLATES.get(locale)
    if not banner:
        print(f"Error: no banner template for locale '{locale}'. "
              f"Known locales: {', '.join(BANNER_TEMPLATES)}", file=sys.stderr)
        sys.exit(1)

    locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"

    # Identify existing genuine translations (files WITHOUT the fallback marker)
    existing_translations = set()
    if locale_dir.exists():
        for f in locale_dir.rglob("*.mdx"):
            content = f.read_text(encoding="utf-8")
            if FALLBACK_MARKER not in content:
                rel = str(f.relative_to(locale_dir))
                existing_translations.add(rel)

    # Copy all docs/ MDX files, inserting banner into fallbacks
    copied = 0
    skipped = 0
    for src in sorted(DOCS_DIR.rglob("*.mdx")):
        rel = str(src.relative_to(DOCS_DIR))
        dest = locale_dir / rel

        if rel in existing_translations:
            skipped += 1
            continue

        content = src.read_text(encoding="utf-8")
        fallback_content = insert_banner_after_frontmatter(content, banner)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(fallback_content, encoding="utf-8")
        copied += 1

    print(f"Locale '{locale}': {copied} fallback files written, "
          f"{skipped} existing translations preserved.")


def cmd_reassemble(args):
    """Reassemble translated batch JSON files into MDX in the i18n directory."""
    if not BATCH_DIR.exists():
        print(f"Error: no batch directory found at {BATCH_DIR}", file=sys.stderr)
        sys.exit(1)

    batch_files = sorted(BATCH_DIR.glob("batch-*.json"))
    if not batch_files:
        print("Error: no batch JSON files found.", file=sys.stderr)
        sys.exit(1)

    total_written = 0
    for bf in batch_files:
        batch = json.loads(bf.read_text(encoding="utf-8"))
        locale = batch["target_locale"]
        print(f"Reassembling {bf.name} ({len(batch['files'])} files, locale={locale})...")

        for file_data in batch["files"]:
            # Rebuild frontmatter
            fm = {}
            if file_data.get("frontmatter"):
                for seg in file_data["frontmatter"]:
                    fm[seg["key"]] = seg["content"]

            # Rebuild body
            body_parts = []
            for seg in file_data["body_segments"]:
                body_parts.append(seg["content"])

            # Combine
            parts = []
            if fm:
                parts.append(rebuild_frontmatter(fm))
            parts.append("".join(body_parts))
            mdx_content = "\n".join(parts) if fm else "".join(body_parts)

            # Write to i18n directory
            dest = REPO_ROOT / file_data["dest"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(mdx_content, encoding="utf-8")
            print(f"  Wrote: {file_data['dest']}")
            total_written += 1

    print(f"\nDone. {total_written} translated MDX file(s) written.")


def main():
    parser = argparse.ArgumentParser(
        description="Translation helper for doQumentation MDX content"
    )
    sub = parser.add_subparsers(dest="command")

    # extract
    p_extract = sub.add_parser("extract", help="Extract translatable segments")
    p_extract.add_argument(
        "--pages", required=True, help="Text file listing MDX paths (relative to docs/)"
    )
    p_extract.add_argument(
        "--locale", required=True, help="Target locale code (e.g., de, es, ja)"
    )

    # reassemble
    sub.add_parser("reassemble", help="Reassemble translated MDX files")

    # populate-locale
    p_populate = sub.add_parser(
        "populate-locale",
        help="Populate i18n locale dir with English fallbacks + untranslated banner",
    )
    p_populate.add_argument(
        "--locale", required=True,
        help="Target locale code (e.g., de, ja)",
    )

    args = parser.parse_args()
    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "reassemble":
        cmd_reassemble(args)
    elif args.command == "populate-locale":
        cmd_populate_locale(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
