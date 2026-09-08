#!/usr/bin/env python3
"""
Find bootstrap entries whose translation belongs to a *different* paragraph.

The defect
----------
`bootstrap` seeded the v2 PO files from the v1 rendered pages by pairing
source and translation **by position**, and stamped every pair it made that
way with a `# doq-bootstrap: positional` translator comment. Where an entry
was dropped mid-page (a table-row or math mismatch — those carry
`# doq-bootstrap: dropped ...`), everything after it shifted, so a run of
entries ended up carrying the neighbouring paragraph's translation.

The result is the nastiest defect class the project has: the page renders,
the translation is fluent, and `check.py` passes it, because a well-formed
translation of the *wrong* paragraph breaks none of the structural
invariants. Only meaning is wrong.

The marker is not the signal: 133k entries carry it, nearly all correctly
paired. This script scores the pairing instead.

How it scores
-------------
For a positional entry `i`, does some nearby msgid `j` fit this msgstr
better than msgid `i` does? Two independent signals, because neither
alone suffices:

  anchors  tokens that survive translation into every locale — acronyms,
           numbers, inline code, math, URLs, technical proper nouns.
           Decisive when present, silent on plain prose.
  lenfit   a translation's length tracks its source's length times the
           locale's median expansion ratio. Weak per entry, but it is the
           only signal on anchor-free prose — which is exactly where the
           defect hides from every other check we have.

Output is a *candidate list for a gauge*, not a verdict: the signals are
statistical, and a faithful translation that happens to drop an acronym
scores like a misalignment. On `de` roughly two candidates in five are
real. Read them, or run them past a model, before feeding anything to
`fix.py --prepare`.

Usage:
    # one locale to stdout
    python translation/scripts/find-positional-drift.py --locale de

    # every locale, as JSON, plus a per-file summary on stderr
    python translation/scripts/find-positional-drift.py --all --out /tmp/drift.json

    # human-readable, for reading rather than piping
    python translation/scripts/find-positional-drift.py --locale de --print
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from statistics import median

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))   # importable as well as runnable
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
I18N_DIR = REPO_ROOT / "i18n"

ALL_LOCALES = [
    "ar", "cs", "de", "es", "fr", "he", "id", "it", "ja",
    "ko", "ms", "pl", "pt", "ro", "th", "tl", "uk",
]

MARKER = "doq-bootstrap: positional"

# How far a positional slip can plausibly carry an entry. Runs longer than
# this exist but their near end is caught anyway, which is enough to flag
# the page.
WINDOW = 8

# Below this many characters a msgid carries too little signal to judge.
MIN_LEN = 80
# Below this, the length ratio is noise rather than evidence.
MIN_LEN_FOR_RATIO = 60

# An entry fitting its own msgid at least this well is left alone.
OWN_OK = 0.55
# A neighbour must beat the entry's own fit by this much to be worth reporting.
MARGIN = 0.20

CODE = re.compile(r"`([^`]+)`")
MATH = re.compile(r"\$([^$]+)\$")
URL = re.compile(r"https?://[^\s)\"']+|/(?:learning|guides|tutorials|api)/[^\s)\"']+")
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
CAMEL = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:_[A-Za-z0-9_]+|[a-z][A-Z][A-Za-z0-9]*)\b")
NUM = re.compile(r"(?<![\w$\\])\d+(?:\.\d+)?(?![\w])")
# Names that stay recognisable in every locale we ship, including the
# non-Latin ones, because the project keeps them in Latin script.
PROPER = re.compile(
    r"\b(?:Qiskit|Hartree|Fock|Jordan|Wigner|Trotter|Pauli|Hamilton\w*|Bloch|Grover|"
    r"Shor|Clifford|Heisenberg|Ising|Bell|Holstein|Primakoff|Nishimori|Hadamard|"
    r"Toffoli|Kraus|Lindblad|Bernstein|Vazirani|Deutsch|Jozsa|Fourier|Krylov|Rydberg)\b")

# Single letters and words so common they carry no positional information.
STOP = {"I", "A", "IBM", "OR", "AND", "THE", "S", "T", "X", "Y", "Z", "H", "N", "K"}


def anchors(s: str) -> set[str]:
    """Tokens expected to survive translation of `s` into any locale."""
    a: set[str] = set()
    for rx in (CODE, MATH):
        a |= {m.strip() for m in rx.findall(s) if len(m.strip()) > 1}
    a |= set(URL.findall(s)) | set(ACRONYM.findall(s)) | set(CAMEL.findall(s))
    a |= set(NUM.findall(s)) | set(PROPER.findall(s))
    return {x for x in a if x not in STOP}


def jaccard(a: set, b: set) -> float | None:
    """None when either side has no anchors — absence of evidence, not evidence."""
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def length_fit(len_str: int, len_id: int, ratio: float) -> float | None:
    """1.0 when the translation is exactly `ratio` times its source, decaying
    either side. None when both strings are too short to be informative."""
    if len_id < MIN_LEN_FOR_RATIO or len_str < MIN_LEN_FOR_RATIO:
        return None
    return math.exp(-abs(math.log((len_str / len_id) / ratio)) * 1.6)


def is_positional(entry: polib.POEntry) -> bool:
    return MARKER in (entry.tcomment or "")


def scan_file(po_path: Path, locale: str) -> list[dict]:
    po = polib.pofile(str(po_path))
    entries = [e for e in po if e.msgid and not e.obsolete]
    if len(entries) < 3:
        return []

    ids = [anchors(e.msgid) for e in entries]
    strs = [anchors(e.msgstr) if e.msgstr else set() for e in entries]

    # The locale's expansion ratio, measured on this page's long entries so
    # a terse page and a florid one are each judged against themselves.
    ratios = [len(e.msgstr) / len(e.msgid)
              for e in entries if e.msgstr and len(e.msgid) > 120]
    ratio = median(ratios) if len(ratios) >= 5 else 1.0

    def fit(i: int, j: int) -> float | None:
        """How well msgstr[i] fits msgid[j]: the available signals, weighted."""
        parts: list[tuple[float, float]] = []
        a = jaccard(ids[j], strs[i])
        if a is not None:
            parts.append((a, 1.0))
        l = length_fit(len(entries[i].msgstr), len(entries[j].msgid), ratio)
        if l is not None:
            parts.append((l, 0.55))
        if not parts:
            return None
        return sum(v * w for v, w in parts) / sum(w for _, w in parts)

    root = I18N_DIR / locale / "po"
    rel = str(po_path.relative_to(root)) if po_path.is_relative_to(root) else po_path.name

    found = []
    for i, e in enumerate(entries):
        if not e.msgstr or not is_positional(e) or len(e.msgid) < MIN_LEN:
            continue
        own = fit(i, i)
        if own is None or own >= OWN_OK:
            continue
        best_d, best_s = 0, own
        for d in range(-WINDOW, WINDOW + 1):
            j = i + d
            if d == 0 or not (0 <= j < len(entries)):
                continue
            s = fit(i, j)
            if s is not None and s > best_s + MARGIN:
                best_d, best_s = d, s
        if not best_d:
            continue
        found.append({
            "locale": locale,
            "file": rel,
            "index": i,
            "offset": best_d,
            "own_fit": round(own, 3),
            "best_fit": round(best_s, 3),
            "msgid": entries[i].msgid[:400],
            "msgstr": entries[i].msgstr[:400],
            "better_msgid": entries[i + best_d].msgid[:400],
        })
    return found


def scan_locale(locale: str) -> list[dict]:
    root = I18N_DIR / locale / "po"
    if not root.is_dir():
        print(f"WARNING no PO tree for {locale}: skipped", file=sys.stderr)
        return []
    found = []
    for po_path in sorted(root.rglob("*.po")):
        try:
            found.extend(scan_file(po_path, locale))
        except Exception as exc:                       # a malformed PO is a finding of its own
            print(f"  !! {locale}/{po_path.name}: {exc}", file=sys.stderr)
    return found


def report(findings: list[dict]) -> None:
    for c in findings:
        print("=" * 100)
        print(f"{c['locale']}  {c['file']} #{c['index']}   "
              f"own {c['own_fit']} -> {c['best_fit']} at offset {c['offset']:+d}")
        print(f"  EN  : {c['msgid'][:200]}".replace("\n", " "))
        print(f"  LOC : {c['msgstr'][:200]}".replace("\n", " "))
        print(f"  EN{c['offset']:+d}: {c['better_msgid'][:200]}".replace("\n", " "))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--locale", help="one locale to scan")
    g.add_argument("--all", action="store_true", help="scan every locale")
    ap.add_argument("--out", help="write JSON here instead of stdout")
    ap.add_argument("--print", dest="human", action="store_true",
                    help="human-readable report instead of JSON")
    args = ap.parse_args()

    locales = ALL_LOCALES if args.all else [args.locale]
    findings: list[dict] = []
    for loc in locales:
        n0 = len(findings)
        findings.extend(scan_locale(loc))
        print(f"{loc}: {len(findings) - n0} candidate(s)", file=sys.stderr, flush=True)

    by_file: dict[str, int] = {}
    for c in findings:
        by_file[f"{c['locale']}/{c['file']}"] = by_file.get(f"{c['locale']}/{c['file']}", 0) + 1
    print(f"\n{len(findings)} candidate(s) across {len(by_file)} file(s). Densest:",
          file=sys.stderr)
    for name, n in sorted(by_file.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {n:3d}  {name}", file=sys.stderr)
    print("\nThese are candidates, not verdicts — gauge them before fixing.",
          file=sys.stderr)

    if args.human:
        report(findings)
    elif args.out:
        Path(args.out).write_text(json.dumps(findings, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(json.dumps(findings, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
