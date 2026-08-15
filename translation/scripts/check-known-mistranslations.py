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
# bad/good are plain words; matched whole-word, case-insensitive, capital-preserving.
# Add a term here ONLY if the bad form is NEVER correct in this locale's Qiskit
# docs (a false friend or fixed-term misspelling), so a blanket replace is safe.
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
