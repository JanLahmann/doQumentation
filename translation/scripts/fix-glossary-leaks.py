#!/usr/bin/env python3
"""
Auto-fix the SAFE subset of glossary leaks found by check-glossary-consistency.py.

Scope (deliberately conservative — high precision over high recall):
  - keep_lowercase terms wrongly capitalized → decapitalize (Qubit→qubit). Pure
    case change, zero agreement risk. Skips sentence-start capitalization.
  - leaked_en → preferred translation (Gate→puerta, Circuit→circuito, +plural),
    ONLY where the leaked noun is preceded by an article/determiner that already
    agrees with the target gender (un/una/el/la/los/las/del/al/nuestro…). The
    human translator inflected the Spanish around the English noun, so the
    article already agrees — a bare noun swap is safe. Anything else (quoted
    "Gate", "Gate Hadamard" name patterns, no preceding article) is LEFT for an
    agent and reported as `manual`.

Prose-only: reuses check-glossary-consistency.to_prose scoping so code/math/
anchors/paths are never edited. After editing, the file must still pass
lint-translation.py and not increase freshness STALE (the source-hash marker is
never touched).

Usage:
    # dry-run one file (show what would change)
    python3 translation/scripts/fix-glossary-leaks.py --locale es \
        --file learning/modules/quantum-mechanics/superposition-with-qiskit.mdx --dry-run

    # apply to one file
    python3 translation/scripts/fix-glossary-leaks.py --locale es --file <REL>

    # apply to ALL flagged files for a locale
    python3 translation/scripts/fix-glossary-leaks.py --locale es --all
"""

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent


def _imp(name, fn):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / fn)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_chk = _imp("glossary_check", "check-glossary-consistency.py")

# Determiners that, when preceding a leaked noun, mean the surrounding Spanish
# already carries the gender — so a bare noun swap is safe. (gender-agnostic set
# kept simple: we only swap the noun, not the determiner.)
SAFE_DETERMINERS = {
    # Spanish
    "un", "una", "unos", "unas", "el", "la", "los", "las", "del", "al",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    "nuestro", "nuestra", "nuestros", "nuestras", "cada", "esta", "dicha",
    "su", "sus", "mismo", "misma", "otro", "otra", "otros", "otras",
    "varios", "varias", "algún", "alguna", "ningún", "ninguna",
    # French
    "le", "les", "des", "une", "du", "au", "aux",
    "ce", "cet", "cette", "ces", "mon", "ton", "son", "notre", "votre", "leur",
    "mes", "tes", "ses", "nos", "vos", "leurs",
    "chaque", "aucun", "aucune", "plusieurs", "certains", "certaines",
    "de",
    # Italian
    "il", "lo", "gli", "i", "uno", "della", "dello", "delle", "degli",
    "questa", "questo", "queste", "questi", "quella", "quello", "ogni",
    "nostra", "nostro", "vostra", "vostro", "sua", "suo",
    # Portuguese
    "o", "os", "as", "um", "uns", "umas", "uma", "do", "da", "dos", "das",
    "no", "na", "nas", "este", "esta", "estes", "estas", "esse", "essa",
    "nosso", "nossa", "seu", "qualquer",
    # Ukrainian (articleless; demonstratives/quantifiers precede)
    "цей", "ця", "це", "ці", "той", "та", "те", "ті", "кожен", "кожна",
    "наш", "наша", "ваш", "ваша", "його", "її", "один", "одна", "одне",
    # Polish
    "ten", "ta", "to", "te", "ci", "tej", "tego", "tych", "każdy", "każda",
    "nasz", "nasza", "wasz", "jego", "jej", "jeden", "jedna", "jedno", "danej",
    # Czech
    "této", "tohoto", "těchto", "každý", "každá",
    "náš", "naše", "váš", "jeho", "její", "jeden", "jedna", "jedno", "dané",
    # Romanian (enclitic articles, but determiners precede)
    "niște", "acest", "această", "aceste", "acești", "acel",
    "fiecare", "nostru", "noastră", "vostru", "său",
    # Indonesian / Malay (no articles; demonstratives/quantifiers)
    "sebuah", "suatu", "setiap", "ini", "itu", "satu", "beberapa",
    # Arabic (no articles; definite article الـ attaches; prepositions + iDafa head nouns precede)
    # Definite article variants (the ـ lam connector appears separate before Latin words)
    "الـ", "لـ", "للـ", "والـ", "فالـ", "بالـ",
    # Common prepositions and quantifiers preceding technical English nouns
    "من", "في", "على", "إلى", "عن", "مع", "بعد", "قبل", "حول", "خلال",
    "كل", "بكل", "لكل", "وكل", "هذه", "هذا", "هذه", "تلك", "ذلك", "تلك",
    "بعض", "أي", "أحد", "كلا", "جميع", "مختلف", "معظم",
    # Common iDafa head-nouns (noun-of-X construct: safe to translate X)
    "عمق", "عدد", "تشغيل", "بناء", "توسيع", "أخطاء", "دقة", "أداء",
    "حالات", "نتائج", "مخطط", "مخططات", "تحليل", "تصميم", "إنشاء",
    "حجم", "نوع", "أنواع", "مجموعة", "قائمة", "عملية", "تنفيذ",
    "معلمات", "سمات", "خصائص", "مكونات", "بنية", "مستوى", "طبقة",
    "إخراج", "مدخل", "إدخال", "ناتج", "نموذج", "معيار", "مثال",
}


def _build_offsets(text):
    """Map each char offset to whether it is inside prose (editable) — by
    blanking non-prose with to_prose and comparing lengths line by line is
    fragile, so instead we operate on the RAW text but only replace matches
    whose span is ALSO present in the prose projection. Simpler: we edit raw
    text, but gate each match on the same line's prose content."""
    return None  # (kept simple below: per-line prose gate)


def fix_text(text, glossary):
    """Return (new_text, applied:list, manual:list)."""
    translate = glossary.get("translate", {})
    keep_lower = [w for w in glossary.get("keep_lowercase", [])]

    raw_lines = text.split("\n")
    prose_lines = _chk.to_prose(text).split("\n")
    applied, manual = [], []

    for i, (raw, prose) in enumerate(zip(raw_lines, prose_lines)):
        if not prose.strip():
            continue  # non-prose line (code/math/anchor) — never edit
        new = raw

        # 1) decapitalize keep_lowercase terms (Qubit→qubit), not at sentence start
        for kw in keep_lower:
            cap = kw[0].upper() + kw[1:]
            def _decap(m, kw=kw):
                start = m.start()
                prefix = new[:start].rstrip()
                if prefix == "" or prefix.endswith((".", ":", "!", "?", "•", "-", ">", '"')):
                    return m.group(0)  # legit sentence-start cap
                replacement = kw + m.group(0)[len(kw):]  # preserve any trailing s
                applied.append((i + 1, m.group(0), replacement))
                return replacement
            new = re.sub(rf"\b{re.escape(cap)}(s?)\b", _decap, new)

        # 2) translate leaked_en where preceded by a safe determiner
        for concept, spec in translate.items():
            pref = spec["preferred"]
            for en in spec.get("leaked_en", []):
                if en.lower() in _chk.API_IDENTIFIERS:
                    continue
                plural = en.endswith("s")
                target = pref + ("s" if plural else "")
                def _repl(m, en=en, target=target, concept=concept):
                    start = m.start()
                    before = new[:start].rstrip().split()
                    prev = before[-1].lower().strip('"“”*_') if before else ""
                    # skip if part of a name pattern: "Gate Hadamard", quoted, no determiner
                    after = new[m.end():m.end()+15]
                    if prev not in SAFE_DETERMINERS:
                        manual.append((i + 1, m.group(0), "no-safe-determiner"))
                        return m.group(0)
                    if re.match(r'\s+(Hadamard|NOT|PHASE|CNOT|"|“)', after):
                        manual.append((i + 1, m.group(0), "name-pattern"))
                        return m.group(0)
                    applied.append((i + 1, m.group(0), target))
                    # preserve capitalization style: leaked form was Capitalized →
                    # target lowercase (common noun in Spanish mid-sentence)
                    return target
                new = re.sub(rf"\b{re.escape(en)}\b", _repl, new)

        if new != raw:
            raw_lines[i] = new

    return "\n".join(raw_lines), applied, manual


def lint_ok(locale, abs_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "lint-translation.py"),
         "--locale", locale, "--file", str(abs_path)],
        cwd=str(REPO_ROOT), capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


def process_file(locale, rel, glossary, dry_run):
    base = _chk.locale_current_dir(locale)
    p = base / rel
    if not p.exists():
        print(f"  not found: {rel}", file=sys.stderr)
        return 0, 0
    original = p.read_text(encoding="utf-8")
    new, applied, manual = fix_text(original, glossary)
    if new == original:
        return 0, len(manual)
    if dry_run:
        print(f"  [dry] {rel}: would apply {len(applied)} fix(es), "
              f"{len(manual)} left manual")
        for ln, was, to in applied[:8]:
            print(f"        L{ln}: {was!r} → {to!r}")
        return len(applied), len(manual)
    # apply, then lint-gate
    p.write_text(new, encoding="utf-8")
    ok, out = lint_ok(locale, p)
    if not ok:
        p.write_text(original, encoding="utf-8")  # rollback
        print(f"  ✗ {rel}: lint FAILED after fix — rolled back\n{out[:300]}")
        return 0, len(manual)
    print(f"  ✓ {rel}: applied {len(applied)} fix(es), {len(manual)} left manual")
    return len(applied), len(manual)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", required=True)
    ap.add_argument("--file", help="single rel path")
    ap.add_argument("--all", action="store_true", help="all flagged files")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    glossary = _chk.load_glossary(args.locale)
    if glossary is None:
        print(f"No glossary for {args.locale}; run check-glossary-consistency.py --init",
              file=sys.stderr)
        sys.exit(2)

    targets = []
    if args.file:
        targets = [args.file]
    elif args.all:
        for rel, p in _chk.iter_files(args.locale):
            res = _chk.scan_file(p.read_text(encoding="utf-8"), glossary)
            if _chk.file_summary(rel, res)["flagged"]:
                targets.append(rel)
    else:
        ap.error("--file or --all required")

    print(f"{args.locale}: {len(targets)} file(s) to process"
          f"{' (dry-run)' if args.dry_run else ''}")
    tot_applied = tot_manual = 0
    for rel in targets:
        a, m = process_file(args.locale, rel, glossary, args.dry_run)
        tot_applied += a
        tot_manual += m
    print(f"\nTotal: {tot_applied} fix(es) "
          f"{'would be ' if args.dry_run else ''}applied, "
          f"{tot_manual} left for manual/agent review.")


if __name__ == "__main__":
    main()
