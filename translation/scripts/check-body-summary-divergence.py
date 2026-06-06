#!/usr/bin/env python3
"""
Detect the "two-pass-merge fingerprint": a domain term rendered one way in the
BODY of a file but a different way in its CLOSING/SUMMARY sections.

Both Strategy-C FAILs (ar/vqe, ms/exploring-uncertainty) had exactly this shape:
the body and the "Konsep utama" / review-questions / conclusion sections were
translated in different passes and never reconciled, so a central term flips
rendering partway down — e.g. "variational" = التباديلي in the body but التبايني
in the conclusion; "observable" = "boleh cerap" in the body but "pemboleh ukur"
in the summary. The plain within-file MIX detector only catches this when both
renderings are pre-listed in a glossary; this catches it POSITIONALLY for any
repeated term, with no per-locale glossary required.

How it works (glossary-light, locale-agnostic):
  - Split the prose into a BODY zone (first `--body-frac`, default 0.65) and a
    TAIL zone (last `--tail-frac`, default 0.25).
  - For each candidate term (a token that recurs ≥`--min-occurrences` times),
    compare its dominant rendering. Since we don't know translations a priori,
    we anchor on the ENGLISH source term: take the core domain terms the field
    keeps recognizable (capitalized/transliterated forms + a seed list), and for
    each, see whether the surrounding target-language word that co-occurs with it
    differs body-vs-tail. Simpler and robust: flag when a CAPITALIZED-or-Latin
    domain token appears in one zone but its target-language synonym dominates
    the other — approximated by detecting that the SET of distinct renderings of
    a tracked concept is partitioned across zones.

To stay precise without a full glossary, this script tracks a compact set of
high-value concepts via candidate renderings supplied per locale OR discovered:
it reports, per concept, the rendering histogram in BODY vs TAIL and flags a
DIVERGENCE when the top rendering differs between zones AND each zone's top
rendering is absent (or rare) in the other.

Usage:
    python3 translation/scripts/check-body-summary-divergence.py --locale ar \
        --file learning/modules/computer-science/vqe.mdx
    python3 translation/scripts/check-body-summary-divergence.py --locale ms --report
"""

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
I18N_DIR = REPO_ROOT / "i18n"
GLOSSARY_DIR = REPO_ROOT / "translation" / "glossary"


def _imp(name, fn):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / fn)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_chk = _imp("glossary_check", "check-glossary-consistency.py")

# Concepts to track for divergence. Each is a list of candidate target-language
# renderings (lower-cased, stem-matched). We DON'T need the full set — we detect
# divergence among whatever renderings actually appear. The seed gives the
# script anchors; a per-locale glossary's `translate` concepts are merged in.
# Concept → candidate renderings (lower-cased, stem-matched). The detector flags
# a file when one rendering dominates the BODY and a DIFFERENT one dominates the
# TAIL. The list is grounded in the terms the Opus reviews actually flagged as
# body-vs-summary inconsistent (gate, backend, observable, operator, expectation
# value, entanglement, Hamiltonian, ground state, variational, ansatz). Add a
# rendering here when a review names a new divergent form.
SEED_RENDERINGS = {
    "variational": ["variational", "variazional", "variacion", "variacij",
                    "التباديلي", "التبايني", "التباينية", "التبايينية", "تغايري",
                    "変分", "변분", "וריאציוני", "wariacyjn", "variațional"],
    "observable": ["observable", "osservabil", "observ", "rascati", "rascáti",
                   "boleh cerap", "pemboleh ukur", "مرصود", "رصدي", "مشاهد",
                   "مؤثر قابل للرصد", "オブザーバブル", "観測量", "관측가능량",
                   "可観測量", "מצפה", "פעיל נצפה"],
    "operator": ["operator", "operador", "operatore", "operatör", "מפעיל",
                 "مؤثر", "مشغل", "معامل", "pengendali", "演算子", "연산자", "оператор"],
    "ground state": ["ground state", "estado fundamental", "stato fondamentale",
                     "grundzustand", "stan podstawowy", "keadaan tanah",
                     "الحالة الأساسية", "الحالة الأرضية", "기저", "바닥", "基底状態"],
    # added from this window's FAIL notes (the dominant flagged terms):
    "hamiltonian": ["hamiltonian", "hamiltoniano", "hamiltonien", "hamiltonijan",
                    "هاملتون", "هاميلتوني", "هاملتوني", "המילטוניאן", "ハミルトニアン",
                    "해밀토니안", "гамільтоніан"],
    "backend": ["backend", "الخلفية", "серверна частина", "zaplecze"],
    "expectation value": ["expectation value", "valor esperado", "valore atteso",
                          "wartość oczekiwana", "قيمة التوقع", "القيمة المتوقعة",
                          "ערך תוחלת", "기댓값"],
    "entanglement": ["entanglement", "entrelazamiento", "intreccio", "splątanie",
                     "provázání", "התпреплитання", "التشابك", "تشابك", "כיפול",
                     "もつれ", "얽힘", "заплутаність"],
    "ansatz": ["ansatz", "ansaz", "الأنساتز", "أنساتز", "안사츠", "앤사츠"],
    "optimizer": ["optimizer", "optimizador", "ottimizzatore", "optymalizator",
                  "최적화기", "최적화", "옵티마이저"],
}


def _load_concepts(locale):
    concepts = {k: list(v) for k, v in SEED_RENDERINGS.items()}
    gp = GLOSSARY_DIR / f"{locale}.json"
    if gp.exists():
        g = json.loads(gp.read_text(encoding="utf-8"))
        for concept, spec in g.get("translate", {}).items():
            rends = [spec["preferred"]] + spec.get("variants", [])
            concepts.setdefault(concept, [])
            for r in rends:
                if r.lower() not in [x.lower() for x in concepts[concept]]:
                    concepts[concept].append(r)
    return concepts


def _zone_counts(prose_lines, concepts, body_frac, tail_frac):
    """Return {concept: (Counter body, Counter tail)} rendering histograms."""
    n = len(prose_lines)
    body_end = int(n * body_frac)
    tail_start = int(n * (1 - tail_frac))
    out = {c: (Counter(), Counter()) for c in concepts}
    for i, line in enumerate(prose_lines):
        zone = None
        if i < body_end:
            zone = 0
        elif i >= tail_start:
            zone = 1
        if zone is None:
            continue
        low = line.lower()
        for concept, rends in concepts.items():
            for r in rends:
                if re.search(rf"\b{re.escape(r.lower())}\w*", low):
                    out[concept][zone][r.lower()] += 1
    return out


def scan_file(text, concepts, body_frac=0.65, tail_frac=0.25, min_occ=2):
    prose = _chk.to_prose(text)
    lines = prose.splitlines()
    zc = _zone_counts(lines, concepts, body_frac, tail_frac)
    divergences = []
    for concept, (body, tail) in zc.items():
        if sum(body.values()) < min_occ or sum(tail.values()) < min_occ:
            continue
        body_top = body.most_common(1)[0][0]
        tail_top = tail.most_common(1)[0][0]
        if body_top == tail_top:
            continue
        # divergence only if each zone's top is essentially absent in the other
        body_top_in_tail = tail.get(body_top, 0)
        tail_top_in_body = body.get(tail_top, 0)
        if body_top_in_tail == 0 or tail_top_in_body == 0:
            divergences.append({
                "concept": concept,
                "body_rendering": body_top, "body_count": body[body_top],
                "tail_rendering": tail_top, "tail_count": tail[tail_top],
            })
    return divergences


def iter_files(locale):
    base = _chk.locale_current_dir(locale)
    if base.exists():
        for p in sorted(base.rglob("*.mdx")):
            yield p.relative_to(base).as_posix(), p


def main():
    ap = argparse.ArgumentParser(description="Detect body-vs-summary term divergence")
    ap.add_argument("--locale", required=True)
    ap.add_argument("--file")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--body-frac", type=float, default=0.65)
    ap.add_argument("--tail-frac", type=float, default=0.25)
    ap.add_argument("--min-occurrences", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    concepts = _load_concepts(args.locale)

    if args.file:
        p = _chk.locale_current_dir(args.locale) / args.file
        if not p.exists():
            print(f"not found: {p}", file=sys.stderr); sys.exit(2)
        div = scan_file(p.read_text(encoding="utf-8"), concepts,
                        args.body_frac, args.tail_frac, args.min_occurrences)
        if args.json:
            print(json.dumps({"file": args.file, "divergences": div},
                             ensure_ascii=False, indent=2))
        elif div:
            print(f"{args.file}: {len(div)} body↔summary divergence(s)")
            for d in div:
                print(f"  {d['concept']}: body='{d['body_rendering']}'×{d['body_count']}"
                      f"  →  summary='{d['tail_rendering']}'×{d['tail_count']}")
        else:
            print(f"{args.file}: no divergence")
        return

    if args.report:
        rows = []
        for rel, p in iter_files(args.locale):
            div = scan_file(p.read_text(encoding="utf-8"), concepts,
                            args.body_frac, args.tail_frac, args.min_occurrences)
            if div:
                rows.append((rel, div))
        if args.json:
            print(json.dumps([{"file": r, "divergences": d} for r, d in rows],
                             ensure_ascii=False, indent=2))
            return
        print(f"{args.locale}: {len(rows)} file(s) with body↔summary divergence\n")
        for rel, div in rows:
            terms = ", ".join(d["concept"] for d in div)
            print(f"  {rel}  [{terms}]")
        return

    ap.error("--file or --report required")


if __name__ == "__main__":
    main()
