#!/usr/bin/env python3
"""
Translation status from the PO files: what each locale has, what the current
English leaves untranslated, and how much of it has been reviewed.

    python3 translation/scripts/translation-status.py                 # overview
    python3 translation/scripts/translation-status.py --locale de     # per-section detail
    python3 translation/scripts/translation-status.py --json          # machine-readable
    python3 translation/scripts/translation-status.py --write-status  # write translation/STATUS.md

Everything here is read from i18n/<locale>/po/ (one PO per page: entries and
their fuzzy/empty state, the X-Doq-Review-Opus header) and docs/ (the pages
that exist in English). Nothing is cached: the v1 status.json this script
used to read was retired on 2026-09-10.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import polib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"
STATUS_MD = REPO_ROOT / "translation" / "STATUS.md"

MAIN_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "ms", "id", "th", "ko", "pl", "ro", "cs",
]
LOCALE_NAMES = {
    "de": "German", "es": "Spanish", "uk": "Ukrainian", "ja": "Japanese",
    "fr": "French", "it": "Italian", "pt": "Portuguese", "tl": "Tagalog",
    "ar": "Arabic", "he": "Hebrew", "ms": "Malay", "id": "Indonesian",
    "th": "Thai", "ko": "Korean", "pl": "Polish", "ro": "Romanian", "cs": "Czech",
}
SECTIONS = [("Tutorials", "tutorials/"), ("Guides", "guides/"),
            ("Courses", "learning/courses/"), ("Modules", "learning/modules/")]
REVIEW_HEADER = "X-Doq-Review-Opus"


def _po4a_io():
    spec = importlib.util.spec_from_file_location("po4a_io", REPO_ROOT / "translation" / "v2" / "po4a_io.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_io = _po4a_io()


def section_of(rel: str) -> str:
    for name, prefix in SECTIONS:
        if rel.startswith(prefix):
            return name
    return "Other"


def en_pages() -> list[str]:
    return sorted(str(p.relative_to(DOCS_DIR)) for p in DOCS_DIR.rglob("*.mdx"))


def locale_pages(locale: str) -> dict[str, dict]:
    """{rel: {entries, fuzzy, untranslated, reviewed}} for every PO of a locale."""
    base = I18N_DIR / locale / "po"
    out: dict[str, dict] = {}
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*.po")):
        rel = str(p.relative_to(base))[:-3] + ".mdx"
        po = polib.pofile(str(p), wrapwidth=0)
        entries = [e for e in po if _io.translatable(e)]
        out[rel] = {
            "entries": len(entries),
            "fuzzy": sum(1 for e in entries if e.fuzzy),
            "untranslated": sum(1 for e in entries if not e.fuzzy and not e.msgstr.strip()),
            "reviewed": bool(po.metadata.get(REVIEW_HEADER)),
        }
    return out


def summarize(locale: str, pages: dict[str, dict], en: list[str]) -> dict:
    en_set = set(en)
    by_section: dict[str, Counter] = {}
    for rel, info in pages.items():
        c = by_section.setdefault(section_of(rel), Counter())
        c["pages"] += 1
        c["entries"] += info["entries"]
        c["fuzzy"] += info["fuzzy"]
        c["untranslated"] += info["untranslated"]
        c["pending_pages"] += 1 if (info["fuzzy"] or info["untranslated"]) else 0
        c["reviewed"] += 1 if info["reviewed"] else 0
    for rel in en:
        by_section.setdefault(section_of(rel), Counter())["en_pages"] += 1
    total = Counter()
    for c in by_section.values():
        total.update(c)
    total["missing_pages"] = len([r for r in en if r not in pages])
    total["orphan_pages"] = len([r for r in pages if r not in en_set])
    return {"locale": locale, "name": LOCALE_NAMES.get(locale, locale),
            "sections": {k: dict(v) for k, v in by_section.items()}, "total": dict(total)}


def overview_table(rows: list[dict]) -> list[str]:
    L = ["| Locale | Code | Pages | Entries | Fuzzy | Untranslated | Pages mid-update | Reviewed pages |",
         "|--------|------|------:|--------:|------:|-------------:|-----------------:|---------------:|"]
    for r in rows:
        t = r["total"]
        L.append(f"| {r['name']} | `{r['locale']}` | {t.get('pages', 0)}/{t.get('en_pages', 0)} | "
                 f"{t.get('entries', 0)} | {t.get('fuzzy', 0)} | {t.get('untranslated', 0)} | "
                 f"{t.get('pending_pages', 0)} | {t.get('reviewed', 0)} |")
    return L


def detail_table(r: dict) -> list[str]:
    L = ["| Section | Pages | Entries | Fuzzy | Untranslated | Reviewed pages |",
         "|---------|------:|--------:|------:|-------------:|---------------:|"]
    for name, _ in SECTIONS + [("Other", "")]:
        c = r["sections"].get(name)
        if not c:
            continue
        L.append(f"| {name} | {c.get('pages', 0)}/{c.get('en_pages', 0)} | {c.get('entries', 0)} | "
                 f"{c.get('fuzzy', 0)} | {c.get('untranslated', 0)} | {c.get('reviewed', 0)} |")
    return L


def write_status_md(rows: list[dict]) -> None:
    L = ["# Translation Status", "",
         f"*Auto-generated on {date.today().isoformat()} by `translation-status.py --write-status`.*",
         "*Do not edit manually — regenerate with:*", "", "```bash",
         "python3 translation/scripts/translation-status.py --write-status", "```", "",
         "Read from the PO files under `i18n/<locale>/po/`: a page is translated when",
         "its PO exists; an entry is *fuzzy* when its English changed since it was",
         "translated and *untranslated* when it is new — both render in English until",
         "the locale's next sync (`translation/v2/README.md`). *Reviewed pages* carry a",
         "deep-review verdict in their PO header (`CONTRIBUTING-REVIEWS.md`).", "",
         "## Overview", ""]
    L += overview_table(rows)
    L += ["", "## Per-Locale Detail", ""]
    for r in rows:
        L += [f"### {r['name']} (`{r['locale']}`)", ""]
        L += detail_table(r)
        t = r["total"]
        notes = []
        if t.get("missing_pages"):
            notes.append(f"{t['missing_pages']} English page(s) without a PO (rendered in English)")
        if t.get("orphan_pages"):
            notes.append(f"{t['orphan_pages']} PO(s) for pages no longer in English")
        if notes:
            L += ["", "- " + "; ".join(notes)]
        L.append("")
    STATUS_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"Written {STATUS_MD.relative_to(REPO_ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", help="one locale: per-section detail")
    ap.add_argument("--json", action="store_true", help="print the summaries as JSON")
    ap.add_argument("--write-status", action="store_true", help="write translation/STATUS.md")
    args = ap.parse_args()

    en = en_pages()
    locales = [args.locale] if args.locale else MAIN_LOCALES
    rows = [summarize(loc, locale_pages(loc), en) for loc in locales]

    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0
    if args.write_status:
        write_status_md(rows)
        return 0
    if args.locale:
        r = rows[0]
        print(f"{r['name']} ({r['locale']})")
        print("\n".join(detail_table(r)))
    else:
        print("\n".join(overview_table(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
