#!/usr/bin/env python3
"""
Detect cross-script contamination: a token in a foreign WRITING SYSTEM embedded
in a translation whose language uses a different script — a corruption artifact
(translation-memory bleed, mojibake, fused tokens) the Opus deep-review flagged
(e.g. a CJK char fused into an Indonesian word: "men挟pit").

This is the ONLY deterministically-detectable slice of the "broken-token"
pattern. Latin-on-Latin fusion (e.g. Indonesian "dibanding" + Polish
"wykorzystanie") and malformed-conjugation cases need an LLM — they're out of
scope here. But cross-SCRIPT contamination is unambiguous and high-precision:
a Cyrillic/CJK/Arabic/Hebrew/Thai char inside a Latin-script locale (or vice
versa) is essentially always a defect.

Prose only (reuses check-glossary-consistency.to_prose) so code identifiers,
math, and legitimately-foreign proper nouns in URLs/anchors are not flagged.

Usage:
    python3 translation/scripts/check-cross-script.py --locale id
    python3 translation/scripts/check-cross-script.py --all-latin
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _imp(name, fn):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / fn)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_chk = _imp("glossary_check", "check-glossary-consistency.py")

# Script ranges. A locale's "home" script(s) are allowed; foreign ones flag.
SCRIPTS = {
    "cyrillic": r"Ѐ-ӿԀ-ԯ",
    "arabic": r"؀-ۿݐ-ݿࢠ-ࣿ",
    "hebrew": r"֐-׿",
    "cjk": r"一-鿿぀-ヿ",   # Han + Hiragana/Katakana
    "hangul": r"가-힯ᄀ-ᇿ",
    "thai": r"฀-๿",
}

# Each locale's home script(s) — tokens in any OTHER script are contamination.
LOCALE_HOME = {
    # Latin-script locales: any non-Latin script token is foreign
    "de": [], "es": [], "fr": [], "it": [], "pt": [], "tl": [],
    "ms": [], "id": [], "ro": [], "pl": [], "cs": [],
    "uk": ["cyrillic"],
    "ar": ["arabic"], "he": ["hebrew"], "th": ["thai"],
    "ja": ["cjk"], "ko": ["hangul"],
}

LATIN_LOCALES = [l for l, home in LOCALE_HOME.items() if not home]


def _foreign_re(locale: str):
    """Regex matching any script char NOT in the locale's home set."""
    home = set(LOCALE_HOME.get(locale, []))
    foreign = [rng for name, rng in SCRIPTS.items() if name not in home]
    return re.compile(f"[{''.join(foreign)}]")


def scan_file(text: str, locale: str):
    """Return list of {line, token, context} contamination hits."""
    rx = _foreign_re(locale)
    hits = []
    prose = _chk.to_prose(text)
    for i, line in enumerate(prose.splitlines(), 1):
        for m in rx.finditer(line):
            # grab the surrounding token for context
            ctx = line[max(0, m.start() - 25):m.start() + 15]
            hits.append({"line": i, "char": m.group(0),
                         "context": ctx.strip()})
    return hits


def iter_files(locale):
    base = _chk.locale_current_dir(locale)
    if base.exists():
        for p in sorted(base.rglob("*.mdx")):
            yield p.relative_to(base).as_posix(), p


def report_locale(locale: str, as_json: bool):
    rows = []
    for rel, p in iter_files(locale):
        hits = scan_file(p.read_text(encoding="utf-8"), locale)
        if hits:
            rows.append((rel, hits))
    if as_json:
        import json
        print(json.dumps([{"locale": locale, "file": r, "hits": h}
                          for r, h in rows], ensure_ascii=False, indent=2))
        return len(rows)
    if rows:
        print(f"\n{locale}: {len(rows)} file(s) with cross-script contamination")
        for rel, hits in rows:
            for h in hits[:4]:
                print(f"  {rel}  L{h['line']}: '{h['char']}' in …{h['context']}…")
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Detect cross-script contamination")
    ap.add_argument("--locale")
    ap.add_argument("--all-latin", action="store_true",
                    help="scan all Latin-script locales (where any non-Latin "
                         "token is foreign)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.all_latin:
        total = 0
        for loc in LATIN_LOCALES:
            total += report_locale(loc, args.json)
        if not args.json:
            print(f"\nTotal: {total} file(s) across {len(LATIN_LOCALES)} Latin locales")
    elif args.locale:
        report_locale(args.locale, args.json)
    else:
        ap.error("--locale or --all-latin required")


if __name__ == "__main__":
    main()
