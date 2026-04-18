#!/usr/bin/env python3
"""
Translation helper for doQumentation MDX content.

Populates i18n locale directories with English fallback pages
(with "not yet translated" banners) for pages that haven't been
genuinely translated yet.

Usage:
    python translation/scripts/translate-content.py populate-locale --locale de
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"


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
    "swg": (
        "\n:::note[No net ibersetzt]\n"
        "Die Seid isch no net ibersetzt worda. "
        "Se gucket die englische Originalversion.\n"
        ":::\n"
    ),
    "bad": (
        "\n:::note[Nonig ibersetzt]\n"
        "Die Siite isch nonig ibersetzt worre. "
        "Ihr luege d englischi Originalversion aa.\n"
        ":::\n"
    ),
    "bar": (
        "\n:::note[No ned ibersetzt]\n"
        "De Seitn is no ned ibersetzt worn. "
        "Sie schaung de englische Originalversion o.\n"
        ":::\n"
    ),
    "ksh": (
        "\n:::note[Noch nit övversatz]\n"
        "Die Sigg es noch nit övversatz. "
        "Ehr luurt üch de änglesche Originalversion aan.\n"
        ":::\n"
    ),
    "nds": (
        "\n:::note[Noch nich översett]\n"
        "Disse Sied is noch nich översett. "
        "Se kiekt de engelsche Originalversion an.\n"
        ":::\n"
    ),
    "gsw": (
        "\n:::note[Nonig übersetzt]\n"
        "Di Siite isch nonig übersetzt worde. "
        "Dir luege d englischi Originalversion aa.\n"
        ":::\n"
    ),
    "sax": (
        "\n:::note[Noch nich ibersetzt]\n"
        "Die Seide is noch nich ibersetzt worn. "
        "Se guggen de englsche Originalversion.\n"
        ":::\n"
    ),
    "bln": (
        "\n:::note[Noch nich übersetzt]\n"
        "Die Seite is noch nich übersetzt. "
        "Se kieken die englische Originalversion.\n"
        ":::\n"
    ),
    "aut": (
        "\n:::note[Noch nicht übersetzt]\n"
        "Diese Seite wurde noch nicht übersetzt. "
        "Sie sehen die englische Originalversion.\n"
        ":::\n"
    ),
    "ms": (
        "\n:::note[Belum diterjemahkan]\n"
        "Halaman ini belum diterjemahkan. "
        "Anda sedang melihat versi asal dalam bahasa Inggeris.\n"
        ":::\n"
    ),
    "id": (
        "\n:::note[Belum diterjemahkan]\n"
        "Halaman ini belum diterjemahkan. "
        "Anda sedang melihat versi asli dalam bahasa Inggris.\n"
        ":::\n"
    ),
    "ko": (
        "\n:::note[번역 미완료]\n"
        "이 페이지는 아직 한국어로 번역되지 않았습니다. "
        "영어 원본을 보고 있습니다.\n"
        ":::\n"
    ),
    "pl": (
        "\n:::note[Nieprzetłumaczone]\n"
        "Ta strona nie została jeszcze przetłumaczona na język polski. "
        "Oglądasz oryginalną wersję angielską.\n"
        ":::\n"
    ),
    "ro": (
        "\n:::note[Netradus]\n"
        "Această pagină nu a fost încă tradusă în limba română. "
        "Vizualizați versiunea originală în limba engleză.\n"
        ":::\n"
    ),
    "cs": (
        "\n:::note[Nepřeloženo]\n"
        "Tato stránka zatím nebyla přeložena do češtiny. "
        "Zobrazujete původní anglickou verzi.\n"
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

        # Skip workshop notebooks — they're language-agnostic code
        if rel.startswith("workshop/") or rel.startswith("workshop\\"):
            continue

        if rel in existing_translations:
            skipped += 1
            continue

        content = src.read_text(encoding="utf-8")
        fallback_content = insert_banner_after_frontmatter(content, banner)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(fallback_content, encoding="utf-8")
        copied += 1

    # Copy sibling image/data files under docs/qiskit-addons/ so relative
    # image URLs in addon MDX (e.g. ./output_1.png, ../images/foo.png) resolve
    # in locale builds. Docusaurus requires referenced local images to exist
    # in the same filesystem subtree as the MDX; all other docs use absolute
    # /docs/... paths served from static/ and don't need copying.
    addons_src = DOCS_DIR / "qiskit-addons"
    images_copied = 0
    if addons_src.exists():
        asset_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        for asset in addons_src.rglob("*"):
            if not asset.is_file() or asset.suffix.lower() not in asset_exts:
                continue
            rel = asset.relative_to(DOCS_DIR)
            dest = locale_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(asset.read_bytes())
            images_copied += 1

    print(f"Locale '{locale}': {copied} fallback files written, "
          f"{skipped} existing translations preserved, "
          f"{images_copied} addon assets copied.")


def main():
    parser = argparse.ArgumentParser(
        description="Translation helper for doQumentation MDX content"
    )
    sub = parser.add_subparsers(dest="command")

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
    if args.command == "populate-locale":
        cmd_populate_locale(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
