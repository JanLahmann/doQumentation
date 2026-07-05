#!/usr/bin/env python3
"""Detect translation files written in the WRONG language for their locale.

Round-24 grep-discipline found 3 files at the French locale path written
entirely in Spanish — and all 3 had passed the Tier-3 Haiku review (wrong-
language is a Tier-3 blind spot). Random Tier-4 Opus sampling only catches such
a file if it happens to draw it. This deterministic detector scans EVERY
Latin-script locale file for ~zero cost and flags any whose prose matches a
DIFFERENT language's function-word fingerprint far better than its own.

Method (high-precision, conservative):
  - Strip code fences, inline code, math, JSX/HTML tags, links, anchors — keep
    only natural-language prose.
  - Count occurrences of short, highly-distinctive FUNCTION words for the file's
    own language and for a set of confusable languages.
  - Flag the file only when (a) it has enough prose to judge (>= MIN_HITS total
    own+other marker hits), (b) some OTHER language outscores the locale's own
    language, and (c) that other language wins by >= RATIO x. This tolerates the
    many English kept-terms in a normal translation while catching a whole-file
    language swap.

Only Latin-script locales are checked (where one natural language can masquerade
as another). Non-Latin locales (ar/he/ja/ko/th/uk) can't be silently populated
with a Latin-script sibling without it being obvious as leakage, and their
wrong-language risk is out of scope here.

Usage:
  check-wrong-language.py                 # scan all; exit 1 if any flagged
  check-wrong-language.py --locale fr
  check-wrong-language.py --verbose       # show per-language scores for flags
"""
import argparse, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
I18N = REPO / "i18n"
DOC_SUB = "docusaurus-plugin-content-docs/current"

# Distinctive function words per language. Chosen to be common in prose yet
# discriminating between the confusable Romance/Germanic neighbours. Whole-word,
# case-insensitive, accents required where they disambiguate (está vs esta).
MARKERS = {
    "es": ["el", "los", "las", "una", "con", "para", "por", "está", "también",
           "pero", "este", "esta", "cómo", "qué", "así", "según", "además",
           "mediante", "puede", "cada", "nosotros", "cuántico", "cuántica",
           "siguiente", "aunque", "entonces", "hacia"],
    "fr": ["le", "les", "des", "une", "avec", "pour", "être", "aussi", "nous",
           "cette", "ainsi", "selon", "où", "très", "plus", "peut", "chaque",
           "quantique", "suivant", "alors", "vers", "dont", "ces", "leur",
           "nous", "sont", "après"],
    "pt": ["os", "as", "uma", "com", "para", "por", "está", "também", "mas",
           "este", "esta", "como", "são", "não", "além", "através", "pode",
           "cada", "quântico", "quântica", "seguinte", "embora", "então",
           "para", "pelo", "pela"],
    "it": ["il", "gli", "una", "con", "per", "essere", "anche", "questo",
           "questa", "come", "così", "secondo", "più", "dove", "può", "ogni",
           "quantistico", "quantistica", "seguente", "sebbene", "allora",
           "verso", "sono", "loro", "nella", "degli"],
    "de": ["der", "die", "das", "und", "mit", "für", "ist", "auch", "dieser",
           "wird", "nicht", "oder", "wie", "kann", "jede", "quanten", "wenn",
           "sind", "einer", "eine", "durch", "werden", "einen"],
    "ro": ["și", "cu", "pentru", "este", "care", "din", "această", "acest",
           "sau", "cum", "poate", "fiecare", "cuantic", "cuantică", "următor",
           "deci", "către", "sunt", "lor", "prin", "unei", "unui", "dar"],
    "en": ["the", "of", "and", "with", "for", "this", "that", "are", "which",
           "from", "also", "can", "each", "quantum", "following", "then",
           "toward", "these", "their", "will", "into", "when"],
    # Malay / Indonesian are near-identical; a swap is plausible. Distinctive
    # divergent function words only.
    "ms": ["yang", "dengan", "untuk", "ialah", "ini", "itu", "boleh", "setiap",
           "kuantum", "berikut", "maka", "adalah", "akan", "pada", "litar",
           "daripada", "kita"],
    "id": ["yang", "dengan", "untuk", "adalah", "ini", "itu", "bisa", "setiap",
           "kuantum", "berikut", "maka", "akan", "pada", "sirkuit", "dari",
           "kita", "dapat"],
    "tl": ["ang", "ng", "sa", "mga", "na", "ay", "para", "ito", "kung", "bawat",
           "maaari", "kuwantum", "sumusunod", "kaya", "bilang", "din", "rin",
           "natin"],
}

# For each locale, the confusable languages to test against (its own is added
# automatically). Only locales prone to a silent same-script swap are listed.
CONFUSABLE = {
    "es": ["fr", "pt", "it", "en"],
    "fr": ["es", "pt", "it", "en"],
    "pt": ["es", "fr", "it", "en"],
    "it": ["es", "fr", "pt", "en"],
    "de": ["en", "fr"],
    "ro": ["es", "it", "fr", "en"],
    "ms": ["id", "en"],
    "id": ["ms", "en"],
    "tl": ["es", "en"],  # Tagalog has heavy Spanish borrowing; en for kept-terms
}

MIN_HITS = 25     # need this many total marker hits to judge (skip tiny files)
RATIO = 1.6       # other language must beat own by this factor to flag

# Bibliography / citation-list pages are legitimately English-dominant (author
# names, paper titles, BibTeX @misc blocks) — they are not "wrong language".
# Skip them by basename so they don't false-positive as looking like English.
SKIP_BASENAMES = {"works-cited.mdx", "references.mdx", "bibliography.mdx"}

# Spans to strip so we score prose, not code/markup.
FENCE_RE = re.compile(r"^\s*```")
STRIP_INLINE = re.compile(
    r"`[^`]*`"                      # inline code
    r"|\$\$?[^$]*\$\$?"             # math
    r"|<[^>]+>"                     # JSX/HTML tags
    r"|\{[#/][^}]*\}"              # anchors / MDX expressions
    r"|\[[^\]]*\]\([^)]*\)"        # markdown links (keep link text? drop to be safe)
    r"|https?://\S+"               # bare URLs
)


def to_prose(text: str) -> str:
    out = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append(STRIP_INLINE.sub(" ", line))
    return "\n".join(out)


def score(prose: str, lang: str) -> int:
    low = prose.lower()
    n = 0
    for w in MARKERS[lang]:
        n += len(re.findall(rf"(?<!\w){re.escape(w)}(?!\w)", low))
    return n


def analyse(path: Path, locale: str):
    """Return (flagged, own, best_other_lang, best_other_score, all_scores)."""
    prose = to_prose(path.read_text(encoding="utf-8"))
    langs = [locale] + [l for l in CONFUSABLE.get(locale, []) if l != locale]
    scores = {l: score(prose, l) for l in langs}
    own = scores[locale]
    others = {l: s for l, s in scores.items() if l != locale}
    if not others:
        return False, own, None, 0, scores
    best_other, best_score = max(others.items(), key=lambda kv: kv[1])
    total = own + best_score
    flagged = (total >= MIN_HITS and best_score > own and best_score >= RATIO * max(own, 1))
    return flagged, own, best_other, best_score, scores


def locale_dirs(only):
    for d in sorted(I18N.glob("*")):
        loc = d.name
        if loc not in CONFUSABLE:
            continue
        if only and loc != only:
            continue
        base = d / DOC_SUB
        if base.is_dir():
            yield loc, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    flagged = []
    for loc, base in locale_dirs(a.locale):
        for path in sorted(base.rglob("*.mdx")):
            if path.name in SKIP_BASENAMES:
                continue
            is_bad, own, other, oscore, scores = analyse(path, loc)
            if is_bad:
                rel = path.as_posix().split(DOC_SUB + "/", 1)[-1]
                flagged.append((loc, rel, other, own, oscore))
                line = f"WRONG-LANG  {loc}  {rel}  → looks like '{other}' ({oscore} vs own {own})"
                if a.verbose:
                    line += "  " + " ".join(f"{l}={s}" for l, s in sorted(scores.items(), key=lambda kv: -kv[1]))
                print(line)

    print(f"\n{len(flagged)} file(s) flagged as wrong-language.")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
