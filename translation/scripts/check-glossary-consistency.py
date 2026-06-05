#!/usr/bin/env python3
"""
Detect glossary/terminology defects in translations — the dominant Tier-4 FAIL
class (within-file inconsistency + capitalized-English leakage).

This is the DETERMINISTIC detector behind the corpus-wide quality cleanup. It
finds, per file, two mechanical defects the Opus deep-review kept flagging:

  1. LEAK  — a domain term that the locale conventionally TRANSLATES is left in
             capitalized English in prose (e.g. es "Gate"/"Circuit" instead of
             "puerta"/"circuito"), or a keep-in-English term is wrongly
             capitalized mid-sentence (e.g. "Qubit" — should be lowercase
             "qubit"). API/class identifiers (Sampler, Estimator, Backend, ...)
             are NEVER flagged — they correctly stay in English.
  2. MIX   — one concept rendered ≥2 ways within a single file (e.g. both
             "puerta" and "compuerta" for gate), i.e. the ≥3-inconsistency
             FAIL trigger.

Prose only: fenced code blocks, inline `code`, math ($...$, $$...$$), HTML/JSX
tags, URLs, and frontmatter are stripped before scanning, so legitimate code
identifiers and LaTeX are never false-flagged.

The glossary lives in translation/glossary/<locale>.json (see --init to scaffold
one from the corpus's own majority usage). Run --report for a dashboard, or
--file for one file's findings.

Usage:
    # scaffold a glossary for a locale from its current majority usage
    python3 translation/scripts/check-glossary-consistency.py --locale es --init

    # report all files for a locale
    python3 translation/scripts/check-glossary-consistency.py --locale es --report

    # one file (JSON, for an auto-fixer or agent to consume)
    python3 translation/scripts/check-glossary-consistency.py --locale es \
        --file learning/modules/quantum-mechanics/superposition-with-qiskit.mdx --json
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
I18N_DIR = REPO_ROOT / "i18n"
GLOSSARY_DIR = REPO_ROOT / "translation" / "glossary"

# Terms whose value is an English API/class identifier — NEVER flagged as a
# leak, in any locale. Lower-cased for matching.
API_IDENTIFIERS = {
    "sampler", "estimator", "backend", "session", "batch", "qiskit",
    "runtime", "primitive", "primitives", "transpiler", "passmanager",
    "isa", "qpu", "qasm", "openqasm", "ibm", "aer", "qubit", "qubits",
    # qubit stays English but lowercase — handled via keep_lowercase, not here
}


# ---------------------------------------------------------------------------
# MDX → prose
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`]*`")
_MATH_BLOCK = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_MATH_INLINE = re.compile(r"\$[^$\n]*\$")
_HTML_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_IMPORT = re.compile(r"^import\s.*$|^export\s.*$", re.MULTILINE)
# Heading-anchor slugs `{#get-started}` carry English source words — strip them.
_ANCHOR = re.compile(r"\{#[^}]*\}")
# Markdown link/image TARGETS: ](...) and the path inside — keep link TEXT, drop
# the URL/path. Also bare path-like tokens (/guides/foo, docs/images/...).
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_PATH_TOKEN = re.compile(r"/?(?:docs|guides|tutorials|learning|api|images)/\S*")


def to_prose(text: str) -> str:
    """Strip everything that isn't natural-language prose, preserving line
    numbers (replace stripped spans with same-length blanks where feasible)."""
    text = _FRONTMATTER.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _MATH_BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _IMPORT.sub("", text)
    text = _ANCHOR.sub(" ", text)
    text = _LINK_TARGET.sub("]", text)   # keep the ] so link text stays a word
    text = _PATH_TOKEN.sub(" ", text)
    text = _INLINE_CODE.sub(" ", text)
    text = _MATH_INLINE.sub(" ", text)
    text = _HTML_TAG.sub(" ", text)
    text = _URL.sub(" ", text)
    return text


def prose_lines(text: str):
    """Yield (lineno, prose_line) for the file."""
    prose = to_prose(text)
    for i, line in enumerate(prose.splitlines(), 1):
        yield i, line


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------
# glossary schema (per locale):
# {
#   "translate": { "gate": {"preferred": "puerta", "variants": ["compuerta"],
#                           "leaked_en": ["Gate", "Gates"]}, ... },
#   "keep_lowercase": ["qubit", "qubits"],   # English, but must be lowercase
# }


def load_glossary(locale: str) -> dict | None:
    p = GLOSSARY_DIR / f"{locale}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def locale_current_dir(locale: str) -> Path:
    return I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current"


def iter_files(locale: str):
    base = locale_current_dir(locale)
    if not base.exists():
        return
    for p in sorted(base.rglob("*.mdx")):
        yield p.relative_to(base).as_posix(), p


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def scan_file(text: str, glossary: dict) -> dict:
    """Return {'leaks': [...], 'mixes': [...]} for one file's prose."""
    translate = glossary.get("translate", {})
    keep_lower = set(w.lower() for w in glossary.get("keep_lowercase", []))

    leaks = []   # {term, form, line, kind}
    # per-concept rendering tally for MIX detection
    rendering = {concept: Counter() for concept in translate}

    lines = list(prose_lines(text))
    for lineno, line in lines:
        for concept, spec in translate.items():
            pref = spec["preferred"]
            variants = spec.get("variants", [])
            leaked = spec.get("leaked_en", [])
            # count preferred + variant renderings. Match the stem + optional
            # inflection (plural/agreement suffix) so "compuerta" also catches
            # "compuertas" — target-language words inflect. Case-insensitive.
            for rendering_form in [pref] + variants:
                n = len(re.findall(rf"\b{re.escape(rendering_form)}s?\b", line, re.IGNORECASE))
                if n:
                    rendering[concept][rendering_form.lower()] += n
            # leaked English (capitalized) — these are exact-case
            for en in leaked:
                if en.lower() in API_IDENTIFIERS:
                    continue
                for m in re.finditer(rf"\b{re.escape(en)}\b", line):
                    leaks.append({"term": concept, "form": en, "line": lineno,
                                  "kind": "leaked_en"})
        # keep-lowercase terms wrongly capitalized
        for kw in keep_lower:
            cap = kw[0].upper() + kw[1:]
            for m in re.finditer(rf"\b{re.escape(cap)}\b", line):
                # skip sentence-start capitalization (legit)
                start = m.start()
                prefix = line[:start].rstrip()
                if prefix == "" or prefix.endswith((".", ":", "!", "?", "•", "-", ">")):
                    continue
                leaks.append({"term": kw, "form": cap, "line": lineno,
                              "kind": "wrong_caps"})

    mixes = []
    for concept, counts in rendering.items():
        used = {k: v for k, v in counts.items() if v > 0}
        if len(used) >= 2:
            mixes.append({"term": concept, "renderings": used})

    return {"leaks": leaks, "mixes": mixes}


def file_summary(rel: str, result: dict) -> dict:
    nleak = len(result["leaks"])
    leak_terms = Counter(l["form"] for l in result["leaks"])
    return {
        "file": rel,
        "leak_count": nleak,
        "leak_terms": dict(leak_terms),
        "mixes": result["mixes"],
        # FAIL-like = the Tier-4 trigger: pervasive leak OR ≥1 mixed concept
        "flagged": nleak >= 3 or len(result["mixes"]) >= 1,
    }


# ---------------------------------------------------------------------------
# --init: scaffold a glossary from the corpus's own majority usage
# ---------------------------------------------------------------------------

# Seed concepts: (concept, [candidate TARGET-LANGUAGE renderings], [leaked EN]).
# IMPORTANT: candidates must be genuine target-language renderings — do NOT list
# the English word itself (e.g. "circuit"/"gate"): lowercase English in prose is
# code-identifier noise / leak, not a rendering, and "get" is the English verb.
# The scaffold picks 'preferred' = most frequent candidate; hand-review after.
SEED_CONCEPTS = {
    "gate":    (["puerta", "compuerta", "porta", "gatter", "вентиль", "гейт",
                 "ворота", "brama", "bramka", "hradlo", "brána", "poartă",
                 "게이트", "ゲート", "بوابة", "שער", "วงจรลอจิก"], ["Gate", "Gates"]),
    "circuit": (["circuito", "schaltkreis", "schemat", "obwód", "obvod",
                 "ланцюг", "коло", "litar", "sirkuit", "回路", "회로",
                 "วงจร", "دائرة", "מעגל"], ["Circuit", "Circuits"]),
}

# Tokens that are NEVER valid target renderings (English verbs / code noise that
# survive prose-stripping). Excluded from scaffold candidate selection.
_SCAFFOLD_NOISE = {"get", "circuit", "circuits", "gate", "gates", "porta"}
# (porta is ambiguous: real Italian "gate" but also Latin/PT "door"/code — keep
#  it as an it candidate only; the noise set is applied per non-it locale below.)


def init_glossary(locale: str) -> None:
    """Scaffold translation/glossary/<locale>.json from majority usage. The
    output is a STARTING POINT — review/edit before relying on it."""
    counts = {c: Counter() for c in SEED_CONCEPTS}
    noise = _SCAFFOLD_NOISE - ({"porta"} if locale == "it" else set())
    for rel, p in iter_files(locale):
        prose = to_prose(p.read_text(encoding="utf-8"))
        low = prose.lower()
        for concept, (cands, _leaked) in SEED_CONCEPTS.items():
            for cand in cands:
                if cand.lower() in noise:
                    continue
                n = len(re.findall(rf"\b{re.escape(cand.lower())}\b", low))
                if n:
                    counts[concept][cand.lower()] += n

    translate = {}
    for concept, (cands, leaked) in SEED_CONCEPTS.items():
        ranked = counts[concept].most_common()
        if not ranked:
            continue
        preferred = ranked[0][0]
        variants = [w for w, _ in ranked[1:] if _ >= 3]  # only real variants
        translate[concept] = {
            "preferred": preferred,
            "variants": variants,
            "leaked_en": leaked,
            "_counts": dict(ranked),  # informational; strip after review
        }
    glossary = {
        "_note": "SCAFFOLD from majority usage — review before trusting. "
                 "Set 'preferred', prune 'variants', delete '_counts'.",
        "translate": translate,
        "keep_lowercase": ["qubit", "qubits"],
    }
    GLOSSARY_DIR.mkdir(parents=True, exist_ok=True)
    out = GLOSSARY_DIR / f"{locale}.json"
    out.write_text(json.dumps(glossary, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"Scaffolded {out}")
    for concept, spec in translate.items():
        print(f"  {concept}: preferred={spec['preferred']!r} "
              f"variants={spec['variants']} counts={spec['_counts']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="Detect glossary/terminology defects")
    ap.add_argument("--locale", required=True)
    ap.add_argument("--init", action="store_true",
                    help="scaffold a glossary from majority usage")
    ap.add_argument("--report", action="store_true",
                    help="report all files for the locale")
    ap.add_argument("--file", help="scan a single file (rel path under current/)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    if args.init:
        init_glossary(args.locale)
        return

    glossary = load_glossary(args.locale)
    if glossary is None:
        print(f"No glossary for {args.locale}. Run --init first "
              f"(then review translation/glossary/{args.locale}.json).",
              file=sys.stderr)
        sys.exit(2)

    if args.file:
        p = locale_current_dir(args.locale) / args.file
        if not p.exists():
            print(f"not found: {p}", file=sys.stderr)
            sys.exit(2)
        res = scan_file(p.read_text(encoding="utf-8"), glossary)
        summ = file_summary(args.file, res)
        if args.json:
            print(json.dumps({**summ, "leaks": res["leaks"]}, ensure_ascii=False, indent=2))
        else:
            print(f"{args.file}: {summ['leak_count']} leak(s), "
                  f"{len(summ['mixes'])} mixed concept(s)")
            for term, n in summ["leak_terms"].items():
                print(f"  leak {term!r} ×{n}")
            for m in summ["mixes"]:
                print(f"  MIX {m['term']}: {m['renderings']}")
        return

    if args.report:
        rows = []
        for rel, p in iter_files(args.locale):
            res = scan_file(p.read_text(encoding="utf-8"), glossary)
            summ = file_summary(rel, res)
            if summ["flagged"]:
                rows.append(summ)
        rows.sort(key=lambda r: -r["leak_count"])
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return
        total_leaks = sum(r["leak_count"] for r in rows)
        total_mix = sum(1 for r in rows if r["mixes"])
        print(f"{args.locale}: {len(rows)} flagged file(s), "
              f"{total_leaks} total leak(s), {total_mix} file(s) with mixed terms\n")
        for r in rows[:40]:
            mix = (" MIX:" + ",".join(m["term"] for m in r["mixes"])) if r["mixes"] else ""
            print(f"  {r['leak_count']:4} leak  {r['file']}{mix}")
        if len(rows) > 40:
            print(f"  ... {len(rows) - 40} more")
        return

    ap.error("one of --init / --report / --file is required")


if __name__ == "__main__":
    main()
