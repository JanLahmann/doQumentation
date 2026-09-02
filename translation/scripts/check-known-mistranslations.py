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
        # --- from the Opus deep-review round 2026081475 (49 files). Every rule
        # below was checked against ALL of its corpus occurrences, and against
        # the aligned English line, before being added. Longest form first
        # wherever rules nest.
        # 1. misspelling
        ("tu acquérras", "tu acquerras", "future of 'acquérir' is 'acquerras'"),
        # 2. T1 relaxation. NOT a bare-verb rule: "se désintègre en/parfois" is
        # CORRECT elsewhere, where a meson really does decay into two particles.
        # Only the "vers |0>" direction is the mistranslated T1 decay.
        ("se désintègre vers", "se désexcite vers",
         "T1 decay of |1> to |0>; 'se désintégrer' is radioactive disintegration"),
        # 3. entanglement. 'enchevêtrement' (a tangle) is never the field term;
        # 'intrication' is. It is FEMININE where 'enchevêtrement' is masculine,
        # so the determiner form has to be fixed first.
        ("un enchevêtrement", "une intrication", "entanglement — gender changes with the term"),
        # Pre-existing defect the sweep surfaced rather than caused: the term
        # was already right here, the article was not. 'intrication' is always
        # feminine, so this is safe regardless of how it got there.
        ("un intrication", "une intrication", "'intrication' is feminine"),
        ("enchevêtrements", "intrications", "entanglement (plural)"),
        ("enchevêtrement", "intrication", "entanglement — 'enchevêtrement' is a tangle/jumble"),
        ("enchevêtrantes", "intriquantes", "entangling (fem. pl.)"),
        ("enchevêtrant", "intriquant", "entangling"),
        # 4. non-word calques and false friends
        ("valeurs d'expectation", "valeurs moyennes", "expectation values"),
        ("Retraites à venir", "Retraits à venir",
         "hardware retirements; 'retraite' is a person's retirement"),
        ("benchmarking aléatoire", "benchmarking randomisé",
         "randomized benchmarking is a named method"),
        ("journaliseur", "logger", "'journaliseur' is not used in French HPC writing"),
        # 5. French initialisms take no plural -s. Safe only because link
        # targets and URLs are now protected (see _PROTECT) — 'apis' occurs
        # inside /guides/access-instances-platform-apis#parameters.
        ("QPUs", "QPU", "French initialisms take no plural -s"),
        ("APIs", "API", "French initialisms take no plural -s"),
        ("GPUs", "GPU", "French initialisms take no plural -s"),
        # 6. twirling. 'torsion' is mechanical twisting. Only the forms whose
        # article/agreement can be carried along are listed; the bare plural
        # 'torsions' and the link-text form '[torsion]' are left for a
        # judgement pass rather than guessed at here.
        ("une torsion commune", "un twirling commun", "twirling — gender + agreement"),
        ("la torsion de gate", "le twirling de portes", "gate twirling"),
        ("la torsion de mesure", "le twirling de mesure", "measurement twirling"),
        ("la torsion de Pauli", "le twirling de Pauli", "Pauli twirling"),
        ("torsion de gate", "twirling de portes", "gate twirling"),
        ("torsion de mesure", "twirling de mesure", "measurement twirling"),
        ("torsion de Pauli", "twirling de Pauli", "Pauli twirling"),
        ("la torsion", "le twirling", "twirling — gender changes with the term"),
        # 7. feed-forward rendered as its opposite. NOT a bare-word rule:
        # "boucle de rétroaction" is CORRECT in three files where the English
        # really does say feedback. Only these fixed strings are unambiguous.
        ("Rétroaction classique et flux de contrôle",
         "Anticipation classique et flux de contrôle",
         "feed-forward, not feedback — page title / sidebar / link text"),
        ("contrôle de flux classique par rétroaction",
         "contrôle de flux classique par anticipation", "feed-forward, not feedback"),
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
    # ar: a find-and-replace artifact that doubled the definite article
    # (ال + المؤثرات). Not a word; the correct form is المؤثرات. NOTE the
    # near-miss: الالتفاف ("convolution") is a perfectly good Arabic word that
    # also begins الال — which is why this is a literal rule for the one
    # observed form and NOT a general "الال" pattern.
    "ar": [
        ("الالمؤثرات", "المؤثرات", "doubled definite article (find-and-replace artifact)"),
    ],
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


# Regex rules: for defect CLASSES that no list of literals can close off. The
# replacement may use \1 backreferences. Same protected-span handling as the
# others. Use ONLY where the pattern itself is definitionally an error.
REGEX: dict[str, list[tuple[str, str, str]]] = {
    # A glossary-substitution artifact: the keep-English prefix form (الـ / للـ /
    # بـ …) is pasted in front of a word that was then translated to Arabic,
    # leaving the connector tatweel stranded before a space — "الـ دائرة" for
    # "الدائرة", "للـ دائرة" for "للدائرة", "بـ دوال" for "بدوال". A tatweel is a
    # justification kashida that joins to the NEXT letter, so tatweel-then-space
    # is never well-formed Arabic and the join is unconditional.
    # Found by the 20260828 deep-review (flagged independently in five ar files);
    # a corpus sweep then found 107 occurrences across 19 files. Written as a
    # class rather than literals because the first fix pass closed only the
    # bare-article form and three prefixed variants immediately survived it.
    "ar": [
        (r"([\u0600-\u063F\u0641-\u06FF]{1,3})\u0640[ \t]+(?=[\u0600-\u06FF])",
         r"\1", "glossary prefix left detached by a tatweel (الـ دائرة -> الدائرة)"),
    ],
}


def preserve_case(match: str, repl: str) -> str:
    if match[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def rules_for(locale: str):
    """Return compiled (pattern, good, note, expand) rules.

    Whole-word for KNOWN, word-initial prefix for STEMS, verbatim for REGEX.
    `expand` is True only for REGEX rules, whose replacement may use \\1
    backreferences and so must go through m.expand() instead of a literal.
    """
    out = []
    for bad, good, note in KNOWN.get("*", []) + KNOWN.get(locale, []):
        out.append((re.compile(rf"\b{re.escape(bad)}\b", re.IGNORECASE), good, note, False))
    for stem, good, note in STEMS.get(locale, []):
        out.append((re.compile(rf"\b{re.escape(stem)}", re.IGNORECASE), good, note, False))
    for pat, good, note in REGEX.get(locale, []):
        out.append((re.compile(pat), good, note, True))
    return out


# Spans we must never touch: inline `code` and heading anchors {#...}.
_PROTECT = re.compile(
    r"`[^`]*`"          # inline code
    r"|\{#[^}]*\}"      # heading anchors
    r"|\]\([^)]*\)"     # markdown link TARGETS — never rewrite a URL path
    r"|https?://\S+"    # bare URLs
)


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
    # YAML frontmatter is machine-readable, not prose: notebook_path, slug and
    # friends must match EN byte-for-byte or code execution breaks. A rule like
    # "French initialisms take no plural -s" firing on
    # notebook_path: "guides/retired-qpus.ipynb" is always a false positive,
    # and --fix acting on it would silently point the page at a notebook that
    # does not exist.
    in_front = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.rstrip() == "---" and (i == 1 or in_front):
            in_front = not in_front
            continue
        if in_front:
            continue
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        spans = _protected(line)
        for pat, good, note, expand in rules:
            for m in pat.finditer(line):
                if not _in(spans, m.start()):
                    shown = m.expand(good) if expand else good
                    hits.append((i, m.group(0), shown, note))
    return hits


def fix_file(path: Path, rules) -> int:
    out_lines, n, in_fence = [], 0, False
    in_front, lineno = False, 0
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        body = line.rstrip("\n")
        lineno += 1
        # Never rewrite frontmatter — see the note in scan_file.
        if body.rstrip() == "---" and (lineno == 1 or in_front):
            in_front = not in_front
            out_lines.append(line); continue
        if in_front:
            out_lines.append(line); continue
        if body.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line); continue
        if in_fence:
            out_lines.append(line); continue
        spans = _protected(body)
        for pat, good, _, expand in rules:
            def _r(m, good=good, expand=expand):
                nonlocal n
                if _in(spans, m.start()):
                    return m.group(0)
                n += 1
                # A REGEX rule's replacement is a template, not a word, so it
                # goes through expand() and case-preservation does not apply.
                return m.expand(good) if expand else preserve_case(m.group(0), good)
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
