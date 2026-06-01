#!/usr/bin/env python3
"""Deterministic pre-filter / triage for Tier-3 linguistic review.

Most Tier-3 FAILs found by LLM reviewers are mechanically detectable WITHOUT an
LLM: dropped trailing sections, added/dropped table rows, fabricated or dropped
links, formal-register slips, and inconsistent glossary leakage. This script
runs those cheap checks first so the (paid) LLM pass only adjudicates the
genuinely linguistic calls — word salad, accuracy drift, hallucinated prose —
on a much smaller, flagged subset.

It reuses the freshness checker (so STALE/UNKNOWN files are never queued) and
emits a triage JSON that `review-build-batches.py` consumes.

IMPORTANT — what this is and is NOT (validated on the fully-reviewed ms locale,
422 files, against recorded LLM verdicts):
  * It is NOT a classifier. Per-flag precision for "is this a FAIL?" ranged
    17%-67%; INCONSISTENT_GLOSSARY fired on ~46% of files at only 29% precision.
    So the script NEVER auto-records a verdict and NEVER skips a fresh file.
  * It IS a freshness gate, a prioritizer, and a hint provider. The flags it
    emits are carried into the LLM prompt as "look here" hints (which both
    speeds the LLM pass and makes the borderline glossary/register call
    consistent — applied from one scripted definition instead of per-agent
    judgement). Structural-completeness flags mark files to review first.

Triage labels per file:
  SKIP_STALE / SKIP_UNKNOWN — not in sync with EN; reconcile + re-stamp first
                             (this is the only hard gate, and it is reliable).
  REVIEW                   — fresh; send to the LLM. `priority: true` if a
                             structural-completeness flag fired (dropped/added
                             headings, table rows, code blocks, or links) —
                             review these first; they often indicate real
                             content drift even when subtle.
  SAMPLE                   — short/stub/index page, structure matches EN, no
                             flags. Lower-stakes; review a sample, not all.
                             (~78% PASS in validation — NOT zero-risk, so
                             sample rather than skip.)

Usage:
  python translation/scripts/review-prefilter.py --locale ms
  python translation/scripts/review-prefilter.py --locale cs --section guides/ --json /tmp/cs_triage.json
  python translation/scripts/review-prefilter.py --locale pl --file guides/hello-world.mdx -v
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"
CURRENT = "docusaurus-plugin-content-docs/current"


def _import_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_freshness = _import_module("freshness", "check-translation-freshness.py")

# Short/stub pages below this prose-line count, when structure matches EN, are
# treated as LIKELY_CLEAN (sample, don't review exhaustively).
STUB_LINE_LIMIT = 40

# Per-locale formal-register markers (whole-word). Mirrors review-prompt.md.
# ms is handled specially (kamu vs anda ratio).
REGISTER_MARKERS = {
    "es": [r"usted", r"consulte", r"utilice", r"ejecute", r"seleccione", r"verifique", r"ingrese"],
    "de": [r"Sie", r"Ihnen", r"Verwenden Sie", r"Bitte beachten Sie"],
    "fr": [r"vous", r"votre", r"vos", r"veuillez"],
    "it": [r"Lei", r"consulti", r"utilizzi", r"verifichi"],
    "pt": [r"o senhor", r"a senhora", r"vossa"],
    "uk": [r"\bВи\b", r"\bВам\b", r"\bВаш"],
    "pl": [r"\bPan\b", r"\bPani\b", r"\bPaństw", r"proszę uprzejmie"],
    "cs": [r"\bVy\b", r"\bVám\b", r"\bVás\b", r"Chcete-li", r"naleznete", r"račte"],
    "ja": [r"ございます", r"いただく", r"ご覧ください"],
}

# Inconsistent-glossary map: a capitalized English term that, when it appears
# AS A WHOLE WORD alongside its target-language equivalent in the SAME file,
# signals inconsistent leakage (the precise, scriptable definition that the
# LLM reviewers kept splitting on). english_term -> [target equivalents].
GLOSSARY = {
    "ms": {"Circuit": ["litar"], "Gate": ["get"], "Qubit": ["qubit"]},
    "cs": {"Circuit": ["obvod"], "Gate": ["hradlo", "brána"], "Qubit": ["qubit"]},
    "pl": {"Circuit": ["obwód", "obwod"], "Gate": ["bramka"], "Qubit": ["kubit"]},
}
INCONSISTENT_GLOSSARY_MIN = 3  # >= this many capitalized-EN hits + target present

# Cross-language contamination seen in practice (other-language words that leak
# into a locale). Conservative, whole-word, low-false-positive.
FOREIGN_LEAKS = {
    "cs": [r"\bczęsto\b"],                       # Polish "often"
    "ms": [r"dirahasiakan", r"ngomong-ngomong"],  # Indonesian
}

LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+|/[^)\s]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^```", re.MULTILINE)


def load_status() -> dict:
    return json.loads(STATUS_FILE.read_text(encoding="utf-8")) if STATUS_FILE.exists() else {}


def strip_code_and_math(text: str) -> str:
    """Remove fenced code, inline code, and $math$ so lexical checks see prose only."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"\$[^$\n]*\$", " ", text)
    return text


def structural_metrics(text: str) -> dict:
    return {
        "headings": len(HEADING_RE.findall(text)),
        "table_rows": len(TABLE_ROW_RE.findall(text)),
        "fences": len(FENCE_RE.findall(text)),
        "links": LINK_RE.findall(text),
    }


def analyse(locale: str, rel: str, en_text: str, tr_text: str) -> dict:
    """Return metrics + flags for one EN/translation pair."""
    flags: list[str] = []
    en_m = structural_metrics(en_text)
    tr_m = structural_metrics(tr_text)

    # --- structural (robust to prose reflow) ---
    if en_m["headings"] - tr_m["headings"] >= 1:
        flags.append(f"MISSING_HEADINGS(en={en_m['headings']},tr={tr_m['headings']})")
    if abs(en_m["table_rows"] - tr_m["table_rows"]) >= 1:
        flags.append(f"TABLE_ROW_DELTA(en={en_m['table_rows']},tr={tr_m['table_rows']})")
    if en_m["fences"] != tr_m["fences"]:
        flags.append(f"CODE_BLOCK_DELTA(en={en_m['fences']},tr={tr_m['fences']})")

    # --- link-set diff (URLs should match; translated link *text* may differ) ---
    en_links, tr_links = set(en_m["links"]), set(tr_m["links"])
    fabricated = tr_links - en_links
    dropped = en_links - tr_links
    if fabricated:
        flags.append(f"FABRICATED_LINK({len(fabricated)})")
    if dropped:
        flags.append(f"DROPPED_LINK({len(dropped)})")

    # --- lexical checks on prose only ---
    prose = strip_code_and_math(tr_text)

    if locale == "ms":
        kamu = len(re.findall(r"\bkamu\b", prose, re.IGNORECASE))
        anda = len(re.findall(r"\banda\b", prose, re.IGNORECASE))
        if kamu >= 3 and kamu >= anda:
            flags.append(f"REGISTER_KAMU(kamu={kamu},anda={anda})")
        elif kamu:
            flags.append(f"register_kamu_minor({kamu})")
    else:
        hits = 0
        for pat in REGISTER_MARKERS.get(locale, []):
            hits += len(re.findall(pat, prose))
        if hits > 2:
            flags.append(f"REGISTER_FORMAL({hits})")
        elif hits:
            flags.append(f"register_formal_minor({hits})")

    # inconsistent glossary leak (precise definition)
    for eng, targets in GLOSSARY.get(locale, {}).items():
        eng_hits = len(re.findall(rf"\b{eng}\b", prose))
        tgt_hits = sum(len(re.findall(rf"\b{t}\b", prose, re.IGNORECASE)) for t in targets)
        if eng_hits >= INCONSISTENT_GLOSSARY_MIN and tgt_hits >= 1:
            flags.append(f"INCONSISTENT_GLOSSARY({eng}:{eng_hits}/tgt:{tgt_hits})")

    # foreign-language contamination
    for pat in FOREIGN_LEAKS.get(locale, []):
        if re.search(pat, prose, re.IGNORECASE):
            flags.append(f"FOREIGN_LEAK({pat})")

    return {"en": en_m, "tr": tr_m, "flags": flags,
            "tr_lines": tr_text.count("\n") + 1}


# Structural-completeness flags — dropped/added content. Low subjectivity:
# when they fire, the structure genuinely differs from EN. Used only to mark a
# file `priority` (review first), NOT to auto-classify it.
_STRUCTURAL_FLAGS = ("MISSING_HEADINGS", "TABLE_ROW_DELTA", "CODE_BLOCK_DELTA",
                     "DROPPED_LINK", "FABRICATED_LINK")


def is_priority(info: dict) -> bool:
    return any(f.split("(")[0] in _STRUCTURAL_FLAGS for f in info["flags"])


def triage(fresh: str, info: dict, entry: dict) -> str:
    # Gate on the same conditions as review-translations.py --next-chunk:
    # structurally-invalid or lint-failing files can't be linguistically
    # reviewed until fixed, and STALE/UNKNOWN files aren't in sync with EN.
    if entry.get("validation") != "PASS":
        return "SKIP_VALIDATION"
    if entry.get("lint") not in ("CLEAN", "WARNINGS"):
        return "SKIP_LINT"
    if fresh == "STALE":
        return "SKIP_STALE"
    if fresh == "UNKNOWN":
        return "SKIP_UNKNOWN"
    if info["tr_lines"] <= STUB_LINE_LIMIT and not info["flags"]:
        return "SAMPLE"
    return "REVIEW"


def freshness_of(en_path: Path, tr_path: Path) -> str:
    embedded = _freshness.extract_embedded_hash(tr_path.read_text(encoding="utf-8"))
    if embedded is None:
        return "UNKNOWN"
    cur = _freshness.compute_source_hash(en_path.read_text(encoding="utf-8"))
    return "FRESH" if embedded == cur else "STALE"


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic Tier-3 review pre-filter")
    ap.add_argument("--locale", required=True)
    ap.add_argument("--section", help="Only files under this prefix, e.g. guides/")
    ap.add_argument("--file", help="Single REL path (skips status filtering)")
    ap.add_argument("--unreviewed-only", action="store_true",
                    help="Only files with no review verdict yet")
    ap.add_argument("--json", help="Write triage array to this path")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    loc = args.locale
    base = I18N_DIR / loc / CURRENT
    status = load_status()
    entries = status.get(loc, {})

    if args.file:
        rels = [args.file]
    else:
        rels = sorted(entries.keys())

    out = []
    for rel in rels:
        if args.section and not rel.startswith(args.section):
            continue
        e = entries.get(rel, {})
        if args.unreviewed_only and e.get("review") is not None:
            continue
        en_path, tr_path = DOCS_DIR / rel, base / rel
        if not (en_path.exists() and tr_path.exists()):
            continue
        fresh = freshness_of(en_path, tr_path)
        info = analyse(loc, rel, en_path.read_text(encoding="utf-8"),
                       tr_path.read_text(encoding="utf-8"))
        label = triage(fresh, info, e)
        out.append({"locale": loc, "file": rel, "fresh": fresh,
                    "triage": label, "priority": is_priority(info),
                    "flags": info["flags"], "tr_lines": info["tr_lines"]})

    # summary
    from collections import Counter
    counts = Counter(r["triage"] for r in out)
    prio = sum(1 for r in out if r["priority"])
    print(f"[{loc}] {len(out)} files: " +
          ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) +
          f"  (of REVIEW, {prio} priority)")
    flag_counts = Counter(f.split("(")[0] for r in out for f in r["flags"])
    if flag_counts:
        print("  hint flags: " + ", ".join(f"{k}={v}" for k, v in flag_counts.most_common()))

    if args.verbose or args.file:
        for r in out:
            if r["flags"] or r["triage"].startswith("SKIP"):
                tag = r["triage"] + ("*" if r["priority"] else "")
                print(f"  {tag:14} {r['file']}  {r['flags']}")

    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  → wrote {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
