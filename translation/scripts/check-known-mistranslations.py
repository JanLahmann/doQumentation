#!/usr/bin/env python3
"""Corpus-wide detector for KNOWN, deterministic mistranslations.

Complements the probabilistic Tier-4 Opus deep-review: when a review run finds a
false-friend or wrong term that is UNAMBIGUOUS in Qiskit docs (i.e. the flagged
word is never correct in this domain regardless of context), add it here once and
this script catches *every* occurrence across all ~7k locale files for ~zero cost
— instead of waiting for Opus to randomly sample each affected file.

Only put HIGH-CONFIDENCE terms here: the bad form must never be a legitimate word
in a Qiskit translation (e.g. biological "transpiration"/"traspirazione" when the
compiler term "transpilation"/"traspilazione" is meant). Matching is whole-word,
case-insensitive; replacement preserves the leading capital. Code fences are
skipped (we only touch prose) — but the bad word is reported there too.

Usage:
  check-known-mistranslations.py            # report all hits (exit 1 if any)
  check-known-mistranslations.py --locale it
  check-known-mistranslations.py --fix      # apply replacements in prose, lint-safe
"""
import argparse, re, sys, subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
I18N = REPO / "i18n"
DOC_SUB = "docusaurus-plugin-content-docs/current"

# locale -> list of (bad, good, note). "*" applies to every locale.
# bad/good are a plain word OR a fixed phrase; matched whole-word (\b at each
# end), case-insensitive, capital-preserving.
# Add a term here ONLY if the bad form is NEVER correct in this locale's Qiskit
# docs (a false friend, a fixed-term misspelling, or a boilerplate passage whose
# correct rendering is settled), so a blanket replace is safe.
# Phrase rules exist because some defects cannot be fixed a word at a time: the
# repair changes a neighbouring particle ("nagsasatisfy ng X" needs "tumutugon
# sa X"), or reorders a clause. Rules apply in list order, so a longer phrase
# MUST precede any shorter rule it contains.
KNOWN: dict[str, list[tuple[str, str, str]]] = {
    "*": [
        ("Credely", "Credly", "brand misspelling (Credly)"),
    ],
    "it": [
        ("traspirazione", "traspilazione", "transpile — not biological 'traspirazione'"),
    ],
    "fr": [
        ("transpiration", "transpilation", "transpile"),
        ("transpirer", "transpiler", "transpile (verb)"),
        ("transpirons", "transpilons", "transpile (1pl)"),
        ("transpirez", "transpilez", "transpile (2pl)"),
        ("transpire", "transpile", "transpile (3sg)"),
    ],
    "es": [
        ("transpiración", "transpilación", "transpile"),
        ("transpirar", "transpilar", "transpile (verb)"),
    ],
    "pt": [
        ("transpiração", "transpilação", "transpile"),
        ("transpirar", "transpilar", "transpile (verb)"),
    ],
    # tl entries come from the Opus deep-review rounds 2026081471-73 (121 files).
    # Two classes, both verified against every corpus occurrence before adding:
    #   1. malformed/non-words — never a Tagalog word, so always a defect
    #   2. fixed boilerplate — IBM/Credly notices and course furniture that
    #      repeat verbatim across dozens of files, where the review settled the
    #      correct rendering once and it applies to every copy
    "tl": [
        # --- 1. malformed / non-words (regression guards; the rounds fixed the
        # occurrences that existed, these keep them from coming back) ---
        ("teorama", "teorema", "theorem — misspelling of 'teorema'"),
        ("kumikillos", "kumikilos", "typo for 'kumikilos'"),
        ("mapinalaki", "mapalaki", "malformed causative of 'palaki'"),
        ("nagpapanatatangi", "nagpapatangi", "malformed; 'makes distinctive'"),
        ("sinisimoni", "minomonitor", "invented verb for 'monitor' (object focus)"),
        ("sumusimoni", "nagmomonitor", "invented verb for 'monitor' (actor focus)"),
        ("magsulsi", "maglutas", "'solve' — 'magsulsi' is to darn/mend cloth"),
        # --- 2. 'satisfies' — the repair moves ng -> sa, so it cannot be a
        # word-level rule. Longest first. ---
        ("nagsasatisfy lamang ng", "tumutugon lamang sa", "satisfies (only)"),
        ("nagsasatisfy ng", "tumutugon sa", "satisfies — English stem + wrong particle"),
        ("nagsasatisfy sa", "tumutugon sa", "satisfies — English stem"),
        # --- 3. fixed boilerplate: the IBM/Credly badge + privacy notice, which
        # repeats across the exam and course-index pages. Each rule recasts an
        # English-order "ay"-passive into the verb-initial Tagalog a native
        # writer uses, or fixes a literal-sense verb. ---
        ("Ito ay hahawakan", "Pangangasiwaan ito",
         "data 'handled' — 'hahawakan' is the physical grip sense"),
        ("Ito ay pangangasiwaan", "Pangangasiwaan ito", "verb-initial, not ay-passive"),
        ("Ang iyong feedback ay gagamitin", "Gagamitin ang iyong feedback",
         "ay-passive mirroring English word order"),
        ("Ang iyong personal na impormasyon ay ginagamit",
         "Ginagamit ang iyong personal na impormasyon", "ay-passive"),
        ("ang iyong badge ay awtomatikong ipapadala",
         "awtomatikong ipapadala ang iyong badge", "ay-passive"),
        ("Ang mga empleyado ng IBM ay maaaring tingnan ang",
         "Matitingnan ng mga empleyado ng IBM ang",
         "ang-marked actor with an object-focus verb; recast to ng-actor"),
        ("para tulungan sa pamamahala", "para tumulong sa pamamahala",
         "transitive 'tulungan' with no object; needs actor-focus 'tumulong'"),
        ("upang tulungan sa pamamahala", "upang tumulong sa pamamahala",
         "same defect as above, with 'upang' instead of 'para'"),
        # The badge/privacy boilerplate is not byte-identical across courses —
        # the same sentence appears with a different verb or a formal pronoun.
        # Each variant needs its own rule; the ay-passive is fixed but the
        # existing register ('inyong') is left alone, so one sentence is never
        # recast against the register of the paragraph around it.
        ("Ang inyong personal na impormasyon ay ginagamit",
         "Ginagamit ang inyong personal na impormasyon", "ay-passive ('inyong' variant)"),
        ("ang iyong badge ay awtomatikong maipapadala",
         "awtomatikong maipapadala ang iyong badge", "ay-passive ('maipapadala' variant)"),
        ("ang iyong badge ay awtomatikong ie-email",
         "awtomatikong ie-email ang iyong badge", "ay-passive ('ie-email' variant)"),
        ("Ang mga empleyado ng IBM ay maaaring makita ang",
         "Makikita ng mga empleyado ng IBM ang",
         "ang-marked actor with an object-focus verb ('makita' variant)"),
        # --- 4. course furniture ---
        ("Ginagabayan kayo", "Ginagabayan ka",
         "register: plural/formal 'kayo' where the locale convention is casual 'ka'"),
        ("20-tanong na pagsusulit", "pagsusulit na may 20 tanong",
         "English hyphenated pre-nominal compound; Tagalog marks it postnominally"),
    ],
}

# Stem rules: match a word-initial prefix and rewrite only that prefix, so ALL
# inflections are covered by one entry. Use ONLY where the prefix itself is the
# error (e.g. Polish 'variacyjn*' must be 'wariacyjn*' — Polish never spells it
# with a leading v). locale -> list of (bad_stem, good_stem, note).
STEMS: dict[str, list[tuple[str, str, str]]] = {
    "pl": [
        ("variacyjn", "wariacyjn", "variational — Polish 'wariacyjny' (w, not v)"),
    ],
}


def preserve_case(match: str, repl: str) -> str:
    if match[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def rules_for(locale: str):
    """Return compiled (pattern, good, note). Whole-word for KNOWN, prefix for STEMS."""
    out = []
    for bad, good, note in KNOWN.get("*", []) + KNOWN.get(locale, []):
        out.append((re.compile(rf"\b{re.escape(bad)}\b", re.IGNORECASE), good, note))
    for stem, good, note in STEMS.get(locale, []):
        out.append((re.compile(rf"\b{re.escape(stem)}", re.IGNORECASE), good, note))
    return out


# Spans we must never touch: inline `code` and heading anchors {#...}.
_PROTECT = re.compile(r"`[^`]*`|\{#[^}]*\}")


def _protected(line: str):
    return [m.span() for m in _PROTECT.finditer(line)]


def _in(spans, i: int) -> bool:
    return any(a <= i < b for a, b in spans)


def locale_dirs(only: str | None):
    for d in sorted(I18N.glob("*")):
        loc = d.name
        if only and loc != only:
            continue
        base = d / DOC_SUB
        if base.is_dir():
            yield loc, base


def scan_file(path: Path, rules) -> list[tuple[int, str, str, str]]:
    """Return (lineno, match, good, note) hits. Skips fenced code, inline code, anchors."""
    hits = []
    in_fence = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        spans = _protected(line)
        for pat, good, note in rules:
            for m in pat.finditer(line):
                if not _in(spans, m.start()):
                    hits.append((i, m.group(0), good, note))
    return hits


def fix_file(path: Path, rules) -> int:
    out_lines, n, in_fence = [], 0, False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        body = line.rstrip("\n")
        if body.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line); continue
        if in_fence:
            out_lines.append(line); continue
        spans = _protected(body)
        for pat, good, _ in rules:
            def _r(m):
                nonlocal n
                if _in(spans, m.start()):
                    return m.group(0)
                n += 1
                return preserve_case(m.group(0), good)
            body = pat.sub(_r, body)
            spans = _protected(body)  # spans may shift after a replace
        out_lines.append(body + ("\n" if line.endswith("\n") else ""))
    if n:
        path.write_text("".join(out_lines), encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale")
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()

    total_hits = 0
    fixed_files = 0
    for loc, base in locale_dirs(a.locale):
        rules = rules_for(loc)
        if not rules:
            continue
        for path in sorted(base.rglob("*.mdx")):
            hits = scan_file(path, rules)
            if not hits:
                continue
            rel = path.relative_to(I18N)
            if a.fix:
                n = fix_file(path, rules)
                fixed_files += 1
                print(f"FIXED {n:3d}  {rel}")
            else:
                total_hits += len(hits)
                for lineno, bad, good, note in hits:
                    print(f"  {loc}  {rel.as_posix().split(DOC_SUB+'/')[-1]}:{lineno}  {bad}→{good}  ({note})")

    if a.fix:
        print(f"\nFixed {fixed_files} file(s).")
    else:
        print(f"\n{total_hits} hit(s).")
        sys.exit(1 if total_hits else 0)


if __name__ == "__main__":
    main()
