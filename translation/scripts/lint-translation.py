#!/usr/bin/env python3
"""
Lint translated MDX files for build-breaking syntax and content errors.

Two classes of checks:

  ERROR  Issues that break docusaurus build or are clearly wrong:
           - duplicate heading anchors, garbled XML tags, mid-line headings,
             unmatched code fences, missing imports, unescaped JSX quotes
           - foreign-script intrusion (German tokens in non-DE locales,
             Cyrillic in non-Cyrillic locales) — translator-tool contamination

  WARN   Issues worth a human glance:
           - invalid anchor characters
           - verbatim EN prose units in a translation, suggesting either
             untranslated content or stale translation after EN drift

Usage:
    # Lint all genuine translations for one locale
    python translation/scripts/lint-translation.py --locale ksh

    # Lint all locales
    python translation/scripts/lint-translation.py --all-locales

    # Lint a single file (with EN source for import / drift / fence checks)
    python translation/scripts/lint-translation.py --file <translated.mdx> --en-file <source.mdx>
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

ALL_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "ko", "th", "pl", "cs", "ro", "ms", "id",
    "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut",
]

STATUS_FILE = REPO_ROOT / "translation" / "status.json"
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

ERROR = "ERROR"
WARN = "WARN"


def load_status() -> dict:
    """Load translation/status.json."""
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {}


def save_status(status: dict) -> None:
    """Write translation/status.json with sorted keys."""
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_genuine_translations(locale: str) -> list[tuple[Path, Path]]:
    """Find all genuine (non-fallback) translations for a locale.
    Returns [(en_path, tr_path)] pairs.
    """
    locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"
    if not locale_dir.exists():
        return []

    pairs = []
    for tr_path in sorted(locale_dir.rglob("*.mdx")):
        content = tr_path.read_text(encoding="utf-8")
        if FALLBACK_MARKER in content:
            continue
        rel = tr_path.relative_to(locale_dir)
        en_path = DOCS_DIR / rel
        if en_path.exists():
            pairs.append((en_path, tr_path))
    return pairs


def is_inside_code_block(lines: list[str], line_idx: int) -> bool:
    """Check if a line is inside a fenced code block."""
    fence_count = 0
    for i in range(line_idx):
        if lines[i].strip().startswith("```"):
            fence_count += 1
    return fence_count % 2 == 1


# ---------------------------------------------------------------------------
# Lint checks
# ---------------------------------------------------------------------------


def check_duplicate_anchors(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for multiple {#anchor} on the same heading line."""
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        anchors = re.findall(r"\{#[^}]+\}", line)
        if len(anchors) > 1:
            findings.append((
                ERROR, i + 1,
                f"duplicate heading anchor: {' '.join(anchors)}"
            ))
    return findings


def check_garbled_xml_tags(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for garbled XML namespace tags like <bcp47:setzongen."""
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        # Match <word:word patterns that aren't valid JSX
        matches = re.findall(r"<([a-z][a-z0-9]*):([a-z])", line, re.IGNORECASE)
        for ns, _ in matches:
            # Skip known valid patterns (e.g. https: in URLs)
            if ns.lower() in ("https", "http", "mailto"):
                continue
            findings.append((
                ERROR, i + 1,
                f"garbled XML namespace tag: <{ns}:..."
            ))
    return findings


def check_heading_mid_line(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for heading markers glued to preceding text on the same line.

    Catches: `...some text.#### Heading` (heading mid-line, causes acorn parse error).
    Does NOT flag headings on their own line (even without preceding blank line).
    """
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        # Look for ## heading markers that don't start at position 0.
        # A real heading starts at col 0; mid-line ones have text before them.
        m = re.search(r"(?<=\S)#{2,6}\s", line)
        if m and m.start() > 0:
            # Skip heading anchors {#...} — the char before ## would be {
            if line[m.start() - 1] == "{":
                continue
            # Skip if ## is part of a normal heading at start of line
            if line.lstrip().startswith("#"):
                continue
            findings.append((
                ERROR, i + 1,
                "heading marker glued to preceding text (needs blank line + own line)"
            ))
    return findings


def check_invalid_anchor_chars(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for heading anchors with special characters that cause issues."""
    findings = []
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        for m in re.finditer(r"\{#([^}]+)\}", line):
            anchor = m.group(1)
            bad_chars = re.findall(r"[.:?()!,;]", anchor)
            if bad_chars:
                findings.append((
                    WARN, i + 1,
                    f"anchor contains special characters: {{#{anchor}}} — chars: {''.join(set(bad_chars))}"
                ))
    return findings


def check_unescaped_jsx_quotes(lines: list[str]) -> list[tuple[str, int, str]]:
    """Check for unescaped quotes inside JSX attribute values.

    Heuristic: on lines containing JSX attribute patterns like definition="...",
    title="...", label="...", an odd number of double-quotes suggests one is
    unescaped inside an attribute value.
    """
    findings = []
    # Attributes commonly translated that carry string values
    attr_pattern = re.compile(
        r'(?:definition|title|label|description|alt|placeholder|aria-label)\s*=\s*"'
    )
    for i, line in enumerate(lines):
        if is_inside_code_block(lines, i):
            continue
        if not attr_pattern.search(line):
            continue
        # Count double-quotes on the line
        quote_count = line.count('"')
        if quote_count % 2 != 0:
            findings.append((
                ERROR, i + 1,
                f"odd number of double-quotes ({quote_count}) on JSX attribute line "
                f"— likely unescaped quote (use &quot;)"
            ))
    return findings


def check_code_fence_balance(
    lines: list[str], en_lines: list[str] | None = None
) -> list[tuple[str, int, str]]:
    """Check that TR has the same number of code fences as EN.

    Compares TR fence count to EN fence count rather than checking odd/even,
    because some EN files legitimately have odd fence counts (e.g. JSX
    template literals).
    """
    findings = []
    tr_fence_count = 0
    last_fence_line = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            tr_fence_count += 1
            last_fence_line = i + 1

    if en_lines is not None:
        en_fence_count = sum(
            1 for line in en_lines if line.strip().startswith("```")
        )
        if tr_fence_count != en_fence_count:
            findings.append((
                ERROR, last_fence_line,
                f"code fence count mismatch: TR={tr_fence_count}, EN={en_fence_count}"
            ))
    else:
        # Fallback when no EN source available: flag odd count
        if tr_fence_count % 2 != 0:
            findings.append((
                ERROR, last_fence_line,
                f"unmatched code fence ({tr_fence_count} total, expected even)"
            ))
    return findings


def check_missing_imports(
    lines: list[str], en_lines: list[str] | None
) -> list[tuple[str, int, str]]:
    """Check that import statements from EN source exist in translation."""
    if en_lines is None:
        return []

    findings = []

    # Extract imports from EN (outside code blocks)
    en_imports = set()
    en_fence = 0
    for line in en_lines:
        if line.strip().startswith("```"):
            en_fence += 1
        if en_fence % 2 == 0 and line.strip().startswith("import "):
            en_imports.add(line.strip())

    # Extract imports from translation
    tr_imports = set()
    tr_fence = 0
    for line in lines:
        if line.strip().startswith("```"):
            tr_fence += 1
        if tr_fence % 2 == 0 and line.strip().startswith("import "):
            tr_imports.add(line.strip())

    missing = en_imports - tr_imports
    for imp in sorted(missing):
        findings.append((
            ERROR, 0,
            f"missing import: {imp}"
        ))

    return findings


# ---------------------------------------------------------------------------
# English-prose drift detection
# ---------------------------------------------------------------------------
#
# Catches multi-line prose paragraphs in a translation file that appear
# verbatim in the EN source. Two patterns this surfaces:
#
#   1. Untranslated EN content that was promoted as-is (e.g. a closing
#      paragraph the translator skipped).
#   2. EN content that was added after the translation was produced and
#      never retranslated (drift).
#
# Uses passage_units.extract_units(mode="strict") so the same definition
# of "prose unit" is shared with the drift-detection (--check-drift) and
# baseline-snapshot tooling.

import importlib.util as _il_util
_passage_units_spec = _il_util.spec_from_file_location(
    "passage_units", Path(__file__).resolve().parent / "passage_units.py")
_passage_units = _il_util.module_from_spec(_passage_units_spec)
_passage_units_spec.loader.exec_module(_passage_units)
_extract_units = _passage_units.extract_units


def check_english_prose_drift(
    lines: list[str], en_lines: list[str] | None
) -> list[tuple[str, int, str]]:
    """Flag prose units in the translation that appear verbatim in the EN source.

    Strong signal that the unit is either untranslated, or the EN was updated
    after the translation was made and the TR was never re-translated.
    Surfaced at WARN level — needs human review since some matches may be
    intentional (e.g. recommended-reading link lists with multi-word titles).
    """
    if en_lines is None:
        return []
    tr_units = _extract_units("\n".join(lines), mode="strict")
    en_units = set(_extract_units("\n".join(en_lines), mode="strict"))
    findings = []
    for unit in tr_units:
        if unit not in en_units:
            continue
        # Locate (best-effort) the line where the unit starts
        first_line = unit.splitlines()[0]
        line_no = 0
        for i, line in enumerate(lines, 1):
            if first_line in line:
                line_no = i
                break
        snippet = unit.replace("\n", " ⏎ ")
        if len(snippet) > 100:
            snippet = snippet[:100] + "..."
        findings.append((
            WARN, line_no,
            f"verbatim EN prose unit (possible untranslated content or EN drift): {snippet}"
        ))
    return findings


# ---------------------------------------------------------------------------
# Foreign-script contamination
# ---------------------------------------------------------------------------
#
# Detects tokens from a foreign-language script leaking into a translation
# (e.g. German "terverschränkt" in an Indonesian file, Russian "произвольный"
# in a Hebrew file, Polish "zobraził" in a Czech file). Each pattern signals
# translator-tool cross-contamination.

# Tokens to ignore even when they look like German contamination — these are
# legitimate physics loanwords, proper nouns, or cspell:ignore-comment entries
# that appear across many locales.
FOREIGN_TOKEN_ALLOWLIST = {
    "ansä",        # truncated "ansätze" in citations
    "ansätze",     # German plural used as loanword in physics
    "ansätzów",    # Polish-inflected form of the loanword
    "ansätzom",    # Polish dative form
    "-ansätze",    # appears in compound German loanwords (e.g. HEA-ansätze)
    "würfelt",     # part of Einstein quote ("Gott würfelt nicht")
    "pösch",       # appears in Pöschl-Teller potential references
    "angström",    # physics unit, used as loanword
    "angströms",
    "ångström",
    "ångströms",
}


# Each rule: (label, char-class regex, token-min-length, locales-where-foreign,
#             require-lowercase-token, require-discriminator-char).
#
# - "label" appears in the error message.
# - "char-class regex" picks out tokens; we then check whether any character
#   in the token is in the discriminator set. (For pure-script rules like
#   Cyrillic, the regex already restricts to that block so the discriminator
#   check is satisfied by every match.)
# - "locales-where-foreign" is the set of locales that should NEVER contain
#   tokens from this script. Built relative to ALL_LOCALES so adding a new
#   locale doesn't silently turn off checks.
# - "require-lowercase" filters out capitalized tokens (proper nouns like
#   "Schrödinger" or "Łukasiewicz").
#
# Tuples kept short; build via _build_foreign_script_rules() below.

def _build_foreign_script_rules():
    all_locales = set(ALL_LOCALES)

    # German ä/ö/ü/ß tokens — leaks into non-German Latin-script locales.
    # Excludes DE itself + dialects, CS (uses äöü in a few words), and ES
    # (uses ü in diaeresis: ambigüedad, antigüedad, multilingüe).
    german_native = {"de", "swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut", "cs", "es"}
    german_foreign = all_locales - german_native

    # Cyrillic — leaks into all non-Cyrillic locales.
    cyrillic_native = {"uk"}
    cyrillic_foreign = all_locales - cyrillic_native

    # Hebrew block — should never appear outside HE.
    hebrew_native = {"he"}
    hebrew_foreign = all_locales - hebrew_native

    # Arabic block — should never appear outside AR.
    arabic_native = {"ar"}
    arabic_foreign = all_locales - arabic_native

    # Greek block — should never appear in any of our locales. Math uses
    # LaTeX-rendered Greek (\alpha, \pi, etc.) inside $...$, which we already
    # exclude with the code-span strip + the "skip $...$" logic.
    greek_native: set[str] = set()
    greek_foreign = all_locales - greek_native

    # Polish-unique diacritics — leaking into Czech is a translator-tool drift.
    # Czech does not natively use any of: ł ą ę ć ś ź ż ń.
    polish_chars = "łĄąĆćŁŃńŚśŹźŻż"
    polish_native = {"pl"}
    polish_foreign = {"cs"}  # only flag in CS; other Latin locales don't claim PL alphabet

    # Czech-unique diacritics — leaking into Polish.
    # Polish does not natively use any of: ř ů ě ť ď ň.
    czech_chars = "ŘřŮůĚěŤťĎďŇň"
    czech_native = {"cs"}
    czech_foreign = {"pl"}

    return [
        # label,        token regex,                  discriminator chars,    foreign locales,   min len, allow_capitalized
        ("German",      r"[A-Za-zÀ-ɏ-]+",             set("äöüßÄÖÜ"),         german_foreign,    4,       False),
        ("Cyrillic",    r"[Ѐ-ӿ]+",                    None,                   cyrillic_foreign,  3,       True),
        ("Hebrew",      r"[֐-׿]+",                    None,                   hebrew_foreign,    2,       True),
        ("Arabic",      r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]+",        None,                   arabic_foreign,    2,       True),
        ("Greek",       r"[Ͱ-Ͽἀ-῿]+",                 None,                   greek_foreign,     3,       True),
        ("Polish",      rf"[A-Za-zÀ-ɏ{polish_chars}-]+", set(polish_chars),    polish_foreign,    4,       False),
        ("Czech",       rf"[A-Za-zÀ-ɏ{czech_chars}-]+",  set(czech_chars),     czech_foreign,     4,       False),
    ]


_FOREIGN_SCRIPT_RULES = _build_foreign_script_rules()


def check_foreign_script(
    tr_path: Path, lines: list[str], locale: str
) -> list[tuple[str, int, str]]:
    """Flag tokens from foreign scripts in non-matching locales.

    Surfaced at ERROR level — these intrusions are almost always translator-tool
    contamination (e.g. a German completion leaking into an Indonesian file,
    or Cyrillic morphemes leaking into a Swiss German translation).
    """
    findings: list[tuple[str, int, str]] = []
    # Only apply rules that target this locale
    active_rules = [
        (label, re.compile(pat), disc, min_len, allow_cap)
        for (label, pat, disc, foreign, min_len, allow_cap) in _FOREIGN_SCRIPT_RULES
        if locale in foreign
    ]
    if not active_rules:
        return findings

    in_code = False
    for i, raw in enumerate(lines, 1):
        s_left = raw.lstrip()
        if s_left.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        clean = re.sub(r"`[^`]*`", "", raw)
        clean = re.sub(r"<[^>]+>", "", clean)
        clean = re.sub(r"https?://\S+", "", clean)
        if "{/*" in clean and "cspell" in clean:
            continue

        for label, pat, disc, min_len, allow_cap in active_rules:
            for tok in pat.findall(clean):
                if len(tok) < min_len:
                    continue
                # If a discriminator set is given, the token must contain ≥1
                # such char (so plain ASCII Latin words don't trigger the
                # German/Polish/Czech rules).
                if disc is not None and not any(c in disc for c in tok):
                    continue
                if not allow_cap and tok[0].isupper():
                    continue
                if tok.lower() in FOREIGN_TOKEN_ALLOWLIST:
                    continue
                findings.append((
                    ERROR, i,
                    f"foreign-script intrusion ({label}): {tok!r}"
                ))

    return findings


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_duplicate_anchors,
    check_garbled_xml_tags,
    check_heading_mid_line,
    check_invalid_anchor_chars,
    check_unescaped_jsx_quotes,
]


def lint_file(
    tr_path: Path,
    en_path: Path | None = None,
    label: str = "",
    locale: str | None = None,
) -> list[tuple[str, int, str]]:
    """Run all lint checks on a single file."""
    content = tr_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    en_lines = None
    if en_path and en_path.exists():
        en_lines = en_path.read_text(encoding="utf-8").splitlines()

    findings = []
    for check in ALL_CHECKS:
        findings.extend(check(lines))
    findings.extend(check_code_fence_balance(lines, en_lines))
    findings.extend(check_missing_imports(lines, en_lines))
    findings.extend(check_english_prose_drift(lines, en_lines))
    if locale:
        findings.extend(check_foreign_script(tr_path, lines, locale))

    return findings


def record_lint_results(
    results: dict[str, dict[str, tuple[int, int]]],
) -> None:
    """Record lint results to status.json.

    results: {locale: {rel_path: (error_count, warning_count)}}
    """
    status = load_status()
    today = date.today().isoformat()

    for locale, files in results.items():
        if locale not in status:
            status[locale] = {}
        for rel, (errors, warnings) in files.items():
            entry = status[locale].get(rel, {})
            entry["linted"] = today
            if errors > 0:
                entry["lint"] = "ERRORS"
            elif warnings > 0:
                entry["lint"] = "WARNINGS"
            else:
                entry["lint"] = "CLEAN"
            entry["lint_errors"] = errors
            entry["lint_warnings"] = warnings
            if "status" not in entry:
                entry["status"] = "promoted"
            status[locale][rel] = entry

    save_status(status)


def run_lint(locales: list[str], verbose: bool = False,
             record: bool = False) -> int:
    """Lint translations for given locales. Returns exit code."""
    total_errors = 0
    total_warnings = 0
    total_files = 0
    error_files = []
    all_results: dict[str, dict[str, tuple[int, int]]] = {}

    for locale in locales:
        pairs = find_genuine_translations(locale)
        if not pairs:
            continue

        locale_dir = I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"
        locale_results: dict[str, tuple[int, int]] = {}

        for en_path, tr_path in pairs:
            rel = str(tr_path.relative_to(locale_dir))
            findings = lint_file(tr_path, en_path, f"{locale} {rel}", locale=locale)
            total_files += 1

            errors = [f for f in findings if f[0] == ERROR]
            warnings = [f for f in findings if f[0] == WARN]

            locale_results[rel] = (len(errors), len(warnings))

            if errors:
                total_errors += len(errors)
                error_files.append((locale, rel))
            total_warnings += len(warnings)

            for severity, line_no, message in findings:
                loc = f":{line_no}" if line_no else ""
                print(f"{severity:5s} {locale:4s} {rel}{loc} — {message}")

            if verbose and not findings:
                print(f"OK    {locale:4s} {rel}")

        if locale_results:
            all_results[locale] = locale_results

    # Summary
    print(f"\n--- Summary: {total_files} files linted ---")
    print(f"  Errors:   {total_errors}")
    print(f"  Warnings: {total_warnings}")

    if error_files:
        print(f"\n{len(error_files)} file(s) with errors:")
        for loc, rel in error_files:
            print(f"  {loc}/{rel}")

    if record and all_results:
        record_lint_results(all_results)
        print(f"\n  Recorded lint results for {total_files} files to status.json")

    return 1 if error_files else 0


def run_single_file(tr_path: Path, en_path: Path | None) -> int:
    """Lint a single file. Returns exit code."""
    # Infer locale from path if the file lives under i18n/<locale>/...
    locale = None
    try:
        parts = tr_path.resolve().relative_to(REPO_ROOT).parts
        if len(parts) >= 2 and parts[0] == "i18n":
            locale = parts[1]
    except (ValueError, OSError):
        pass
    findings = lint_file(tr_path, en_path, locale=locale)

    for severity, line_no, message in findings:
        loc = f":{line_no}" if line_no else ""
        print(f"{severity:5s} {tr_path.name}{loc} — {message}")

    errors = [f for f in findings if f[0] == ERROR]
    if not findings:
        print("OK — no issues found")
    elif not errors:
        print(f"\n{len(findings)} warning(s), 0 errors")

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Lint translated MDX files for build-breaking syntax errors"
    )
    parser.add_argument("--locale", help="Lint a single locale")
    parser.add_argument(
        "--all-locales", action="store_true", help="Lint all locales"
    )
    parser.add_argument("--file", type=Path, help="Lint a single file")
    parser.add_argument(
        "--en-file", type=Path, help="EN source file (for --file mode)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all files")
    parser.add_argument(
        "--record", action="store_true",
        help="Record lint results to translation/status.json"
    )

    args = parser.parse_args()

    if args.file:
        if not args.file.exists():
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(2)
        sys.exit(run_single_file(args.file, args.en_file))

    if not args.locale and not args.all_locales:
        parser.error("Specify --locale XX, --all-locales, or --file PATH")

    locales = ALL_LOCALES if args.all_locales else [args.locale]
    sys.exit(run_lint(locales, verbose=args.verbose, record=args.record))


if __name__ == "__main__":
    main()
