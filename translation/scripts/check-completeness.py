#!/usr/bin/env python3
"""
Flag translations that do not carry everything their source carries.

The gap this fills
------------------
Every other gate in this repo checks *markup*. `check.py` compares code spans,
math, URLs, tags, anchors, table rows and fence lines byte-for-byte and bounds
length at 0.3x-2.5x. That is the right job for it and it does it cleanly — but
a translation can drop a whole paragraph, lose a bullet list, answer a
different question or leave an English caption in place without disturbing a
single character of markup. Measured against the 314 defects the nine
positional-drift review rounds repaired, `check.py` flags 2. Not a failure of
`check.py`: nothing occupied the meaning slot at all.

What this is (and is not)
-------------------------
A deterministic *sieve*, not a verdict. It is free, it runs over the whole
corpus, and it costs nothing to re-run in CI — so it can go first and hand a
much smaller set to a model gauge, which is the only thing that can actually
read for meaning. Every subcheck below was scored against
`build-eval-set.py`'s labelled set before it was allowed in; the thresholds are
measurements, not taste. `tests/test_completeness.py` re-scores them, so a
tightening that quietly destroys recall fails CI.

    subcheck              recall on 314   fires on 75,455 faithful
    line-shape                 30.9%              0.19%   (was 33.8% / 0.43%, see REWRAP_Z)
    numbers                    28.3%              0.30%   (was 0.43%, see NUMBER_RE)
    list-items                  4.1%              0.02%
    title-untranslated          2.2%              0.16%   (title=, description=, alt=)
    question-mark              15.0%              0.10%
    length-outlier             23.6%              0.20%
    ------------------------------------------------------------------
    union of the six           70.1%              1.32%
    (union of the first four   53.8%              1.02%)

    neighbour-duplicate         1.7%              0.05%   (needs file context;
                                                           not in the union above)

The 314 are the independently selected positives (the drift rounds). The set
holds 1,417 after #517, #524 and #527 were merged in, but the other 1,103 were
chosen FROM this sieve's findings by the gauge rounds, so recall on them is
circular and the scorer excludes them. What those rows ARE good for is finding
the next subcheck: `question-mark` and `length-outlier` were chosen by scoring
candidates against the 483 of them the first four subchecks missed (14% and
20% of those, respectively), then admitted on the independent rows above.
Corpus-wide the six flag 5,539 entries (1.23% of 451,652); the two new ones
add 621 of those. A blind gauge read of the new flags (at the looser first
cut of the length check) confirmed 104 defects: question-mark 21 of 108
(19%), length-outlier 83 of 2,426 (3.4%, hence the tighter cut recorded at
LENGTH_STATS).

What it looks like on the real corpus (measured 2026-09-09)
----------------------------------------------------------
The table above is measured on the labelled set, whose positives are all
positional drift — the sieve's best case. On an unbiased sample of 6,797
entries scored by BOTH the sieve and the gauge, it does considerably worse:

                        gauge: defective   gauge: fine
      sieve flags                     11            81
      sieve passes                    22         6,683

    corpus defect rate    0.49%   95% CI [0.35%, 0.68%]   (~2,200 entries)
    sieve precision      11.96%   95% CI [6.8%, 20.2%]
    sieve recall         33.33%   95% CI [19.8%, 50.4%]

So roughly one flag in eight is a real defect, and the sieve sees about a
third of what is out there. Both numbers are worse than the labelled set
suggests, for the reason given above: that set asks an easier question.

**This is why the sieve must not be a hard gate.** At 12% precision, failing
CI on its 5,730 corpus findings would demand ~5,000 non-fixes. Use
`--baseline` instead: a ratchet that fails only on findings a change ADDS.
An earlier version of this docstring claimed `title-untranslated` and
`neighbour-duplicate` were clean enough to gate on; the unbiased sample does
not support that, and the claim is withdrawn.

Read the recall honestly too. A fluent, complete, plausible mistranslation of
a technical claim has the right shape, the right numbers and the right length,
and nothing here will ever see it.

Usage:
    python translation/scripts/check-completeness.py --locale de
    python translation/scripts/check-completeness.py --all --json out.json
    python translation/scripts/check-completeness.py --locale de --check title-untranslated
    # the CI ratchet: fails only on findings a change ADDS
    python translation/scripts/check-completeness.py --all \
        --baseline translation/eval/completeness-baseline
    # accept one locale's new findings after reading them (writes only <loc>.txt)
    python translation/scripts/check-completeness.py --locale de \
        --baseline translation/eval/completeness-baseline --accept-new
"""

from __future__ import annotations

import argparse
import collections
import math
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    import polib
except ImportError:  # pragma: no cover
    sys.exit("polib is required: pip install polib")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
I18N = REPO_ROOT / "i18n"

# Eastern Arabic, Persian and full-width digits, so a locale that writes them
# is compared on value rather than codepoint. The Arabic pages in the corpus
# happen to use ASCII digits; the CJK locales do use full-width forms.
FOREIGN_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹０１２３４５６７８９",
    "012345678901234567890123456789",
)

# English spells small numbers as words where ja, ko, th and others write the
# digit: "three kinds of node" -> "3種類", "a fourth policy" -> "4 番目". The
# translation gains a digit the source never had, and that is correct
# translation, not a lost figure. So an ADDED small integer is ignored;
# anything else added, and every number MISSING, still counts.
# (Measured: this costs 4.7 points of recall on the labelled set and removes
# ~3,400 spurious ja/ko findings corpus-wide.)
SPELLED_OUT_MAX = 12

# A grouping separator continues a number only before exactly three digits (a
# thousands group); a decimal separator only before digits. The older
# r"\d[\d,. ]*" ran straight through ", ": "in 2023, 1,386 qubits" became the
# single number 20231386 and "May 30, 2024" became 302024, so a translation
# writing "30. Mai 2024" was reported as missing a number. Measured
# 2026-09-30: recall unchanged (28.3%), noise 0.41% -> 0.30%, corpus
# findings 1,393 -> 1,027.
NUMBER_RE = re.compile(r"\d+(?:[,. ]\d{3})*(?:[.,]\d+)?")
LIST_ITEM_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+")
# title= was the original target; description= and alt= carry reader-visible
# prose too (OpenInLabBanner's description, image alt text) and check.py
# exempts them the same way. Widening cost +1 labelled positive, +15 of
# 77,955 negatives (0.14% -> 0.16%) and 56 corpus flags, 2026-09-10.
TITLE_RE = re.compile(r'(?:title|description|alt)="([^"]*)"')

# A title= of fewer than this many words is usually a label or a proper name
# ("Answer" is caught by other means; "Qiskit" must not be flagged at all).
TITLE_MIN_WORDS = 4
# Below this length two neighbouring entries sharing a msgstr is ordinary
# repetition ("Note", "Example"), not a copied paragraph.
DUPLICATE_MIN_CHARS = 40
# How far to look for the duplicate. Drift moves an entry by one or two slots.
DUPLICATE_WINDOW = 2


# A question that became a statement, or the reverse. The question/answer
# slots of the course quizzes are where positional drift bites hardest — an
# answer entry holding the neighbouring question passes every shape check
# because both are one sentence of prose — and the terminal punctuation is
# the one shape they do not share. Measured on the labelled set: fires on
# 14% of the defects the four older subchecks miss, on 0.15% of faithful
# entries, and half of THOSE turned out to be unrepaired defects when read.
QUESTION_MARKS = ("?", "？", "؟")
_TRAILING_NOISE = " \t\n\"'*_)»«”“’‘」』）"


def _is_question(text: str) -> bool:
    return text.rstrip(_TRAILING_NOISE).endswith(QUESTION_MARKS)


# A translation far shorter than its source, judged against how long that
# locale's translations usually run. The ratio is a poor absolute signal
# (check.py's 0.3x-2.5x bound is deliberately loose: ja runs at ~0.6x the
# source, tl at ~1.1x) but a good relative one. The threshold was set by
# reading the corpus, not the eval set: at 2.5 sd under the locale's median
# the labelled set promised 0.7% noise, but a blind gauge over all 2,426
# corpus flags confirmed only 83 (3.4%) — the "faithful" negatives are just
# less compressed than the corpus at large. Precision by band:
#     z < -4.0        253 flags   46 real   18.2%
#     -4.0 .. -3.5    228 flags   10 real    4.4%
#     -3.5 .. -3.0    478 flags   11 real    2.3%
#     -3.0 .. -2.5  1,467 flags   16 real    1.1%
# So the cut is -3.5: 481 flags at 11.6%, in line with the other subchecks,
# keeping 56 of the 83. Fixed constants rather than a live calibration so
# the ratchet baseline stays stable: (median, sd) of log(len(msgstr)/
# len(msgid)) over the eval set's 75k faithful entries with a source of
# >= 40 chars, 2026-09-09.
# Rebuild after a large re-translation of a locale:
#   python3 -c "import gzip,json,math,statistics as st,collections; d=json.load(gzip.open(
#   'translation/eval/completeness-eval.json.gz')); b=collections.defaultdict(list)
#   [b[n['locale']].append(math.log(len(n['msgstr'])/len(n['msgid']))) for n in d['negatives'] if len(n['msgid'])>=40]
#   print({l:(round(st.median(v),2),round(st.pstdev(v),2)) for l,v in sorted(b.items())})"
LENGTH_STATS = {
    "ar": (-0.13, 0.13), "cs": (-0.02, 0.08), "de": (0.07, 0.09), "es": (0.07, 0.08),
    "fr": (0.09, 0.09), "he": (-0.18, 0.13), "id": (0.02, 0.08), "it": (0.07, 0.08),
    "ja": (-0.53, 0.34), "ko": (-0.47, 0.30), "ms": (0.04, 0.08), "pl": (0.00, 0.09),
    "pt": (0.03, 0.07), "ro": (0.03, 0.08), "th": (-0.08, 0.12), "tl": (0.11, 0.10),
    "uk": (0.00, 0.11),
}
LENGTH_MIN_SOURCE = 40
LENGTH_Z = -3.5


def _length_problem(msgid: str, msgstr: str, locale: str | None) -> str | None:
    if not locale or locale not in LENGTH_STATS or len(msgid) < LENGTH_MIN_SOURCE:
        return None
    median, sd = LENGTH_STATS[locale]
    z = (math.log(max(1, len(msgstr)) / len(msgid)) - median) / sd
    if z >= LENGTH_Z:
        return None
    return (f"translation is {len(msgstr) / len(msgid):.0%} the length of its source; "
            f"{locale} runs at ~{math.exp(median):.0%} (z={z:.1f})")


# Course pages put one sentence per line, so a line the translation lacks is
# usually a sentence it lacks — but a translator also legitimately joins two
# short lines into one sentence. The two differ in length: a dropped sentence
# leaves the translation short for its locale, a re-wrap does not. So fewer
# lines than the source is reported only when the translation is also shorter
# than this many sd under its locale's usual ratio. More lines than the
# source, and any entry without a locale, keep the plain line count.
# Measured 2026-09-30 on the labelled set: recall 33.8% -> 30.9%, noise
# 0.44% -> 0.19%; corpus findings 3,387 -> 1,340.
REWRAP_Z = -0.5


def _rewrapped(msgid: str, msgstr: str, a: int, b: int, locale: str | None) -> bool:
    if b > a or not locale or locale not in LENGTH_STATS or not msgid:
        return False
    median, sd = LENGTH_STATS[locale]
    z = (math.log(max(1, len(msgstr)) / len(msgid)) - median) / sd
    return z >= REWRAP_Z


def _nonempty_lines(text: str) -> int:
    return len([ln for ln in text.split("\n") if ln.strip()])


def _numbers(text: str) -> collections.Counter:
    """Numeric tokens as a multiset, grouping separators removed so 600,000 and
    600.000 compare equal across locale conventions."""
    text = text.translate(FOREIGN_DIGITS)
    return collections.Counter(re.sub(r"[,. ]", "", n) for n in NUMBER_RE.findall(text))


def _number_problem(msgid: str, msgstr: str) -> str | None:
    """Numbers the translation lost, plus any it gained that a spelled-out
    English numeral cannot explain."""
    na, nb = _numbers(msgid), _numbers(msgstr)
    missing = sorted((na - nb).elements())
    added = sorted(k for k in (nb - na).elements()
                   if not (k.isdigit() and int(k) <= SPELLED_OUT_MAX))
    parts = []
    if missing:
        parts.append("missing " + ", ".join(missing[:5]))
    if added:
        parts.append("added " + ", ".join(added[:5]))
    return "; ".join(parts) or None


def check_pair(msgid: str, msgstr: str, locale: str | None = None) -> list[dict]:
    """Subchecks that need only the entry itself. Pure: string in, findings out.

    `locale` is optional and only feeds `length-outlier`, which is judged
    against that locale's usual source-to-translation ratio; without it the
    subcheck stays silent."""
    findings: list[dict] = []
    if not msgstr.strip():
        return findings

    ta, tb = TITLE_RE.findall(msgid), TITLE_RE.findall(msgstr)
    if len(ta) != len(tb):
        findings.append({
            "check": "title-untranslated",
            "detail": f"source has {len(ta)} title= attribute(s), translation {len(tb)}",
        })
    else:
        # title= is the ONE attribute check.py does not compare byte-for-byte,
        # because it is prose the reader sees and must be translated. That
        # exemption is also why an English caption can sit in a translated page
        # indefinitely: no other check looks at it.
        #
        # This subcheck runs BEFORE the copy-only guard below, and must: an
        # entry that is nothing but <IBMVideo title="..."/> is byte-identical
        # to its source precisely WHEN the caption was never translated. Guard
        # it as a copy and the check flags nothing (measured: recall 6 -> 1).
        for x, y in zip(ta, tb):
            if x == y and len(x.split()) >= TITLE_MIN_WORDS:
                findings.append({
                    "check": "title-untranslated",
                    "detail": f"caption still in the source language: {x[:60]!r}",
                })

    if msgstr.strip() == msgid.strip():
        # Proper names and code chunks po4a hands over as prose are legitimately
        # left in English, and the three prose subchecks below would compare
        # such an entry against itself and say nothing. A wholly untranslated
        # prose entry is check-wrong-language's and lint's business.
        return findings

    a, b = _nonempty_lines(msgid), _nonempty_lines(msgstr)
    if a != b and not _rewrapped(msgid, msgstr, a, b, locale):
        findings.append({
            "check": "line-shape",
            "detail": f"source has {a} non-empty line(s), translation {b}",
        })

    np_ = _number_problem(msgid, msgstr)
    if np_:
        findings.append({"check": "numbers", "detail": np_})

    la, lb = len(LIST_ITEM_RE.findall(msgid)), len(LIST_ITEM_RE.findall(msgstr))
    if la != lb:
        findings.append({
            "check": "list-items",
            "detail": f"source has {la} list item(s), translation {lb}",
        })

    qa, qb = _is_question(msgid), _is_question(msgstr)
    if qa != qb:
        findings.append({
            "check": "question-mark",
            "detail": ("source is a question, translation is not" if qa
                       else "translation is a question, source is not"),
        })

    lp = _length_problem(msgid, msgstr, locale)
    if lp:
        findings.append({"check": "length-outlier", "detail": lp})

    return findings


def check_file(path: Path) -> list[dict]:
    """Every subcheck over one PO file, including the ones needing neighbours."""
    po = polib.pofile(str(path))
    live = [e for e in po if not e.obsolete and e.msgstr.strip()]
    rel = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else path.name

    # i18n/<locale>/po/... — the locale feeds the length subcheck. A file
    # outside that layout (a test fixture) simply gets no length verdict.
    parts = path.resolve().parts
    locale = parts[parts.index("i18n") + 1] if "i18n" in parts and parts.index("i18n") + 1 < len(parts) else None

    findings: list[dict] = []
    for i, e in enumerate(live):
        rows = check_pair(e.msgid, e.msgstr, locale)

        # Positional drift often leaves one paragraph's translation sitting on
        # two adjacent entries. Neither copy breaks any structural rule, so
        # only the repetition itself gives it away.
        if len(e.msgstr.strip()) >= DUPLICATE_MIN_CHARS:
            for d in range(-DUPLICATE_WINDOW, DUPLICATE_WINDOW + 1):
                j = i + d
                if d == 0 or not (0 <= j < len(live)):
                    continue
                other = live[j]
                if other.msgid != e.msgid and other.msgstr.strip() == e.msgstr.strip():
                    rows.append({
                        "check": "neighbour-duplicate",
                        "detail": f"same translation as entry #{j} ({'next' if d > 0 else 'previous'})",
                    })
                    break

        for r in rows:
            findings.append({
                "file": rel,
                "index": i,
                "msgid": e.msgid,
                "msgstr": e.msgstr,
                **r,
            })
    return findings


def finding_key(row: dict) -> str:
    """A finding's identity, stable across edits elsewhere in the file.

    NOT the entry index: inserting a paragraph upstream renumbers every entry
    below it and would present the whole tail as new. The msgid is the stable
    handle — it is the source text, and it changes only when the English does.
    """
    return hashlib.sha1(
        "\x00".join((row["file"], row["check"], row["msgid"])).encode("utf-8")
    ).hexdigest()[:16]


def locale_files(locale: str) -> list[Path]:
    return sorted((I18N / locale / "po").rglob("*.po"))


def all_locales() -> list[str]:
    return sorted(p.parent.name for p in I18N.glob("*/po") if p.is_dir())


BASELINE_NOTE = (
    "# Completeness findings accepted as pre-existing for one locale, one key per\n"
    "# line (check-completeness.py finding_key). A RATCHET, not a target: the\n"
    "# sieve's measured precision is ~12%, so most of these are fine. A change may\n"
    "# not ADD a finding unnoticed. Shrink it by fixing real defects; add to it\n"
    "# with --accept-new after reading each new finding. One file per locale, so\n"
    "# rounds on different locales never conflict here.\n"
)


def load_baseline(path: Path) -> set[str]:
    """Accepted keys from a per-locale baseline directory (<loc>.txt files),
    or from the legacy single JSON file."""
    if path.is_dir():
        return set().union(*(load_baseline_file(f) for f in sorted(path.glob("*.txt"))))
    return set(json.loads(path.read_text(encoding="utf-8"))["keys"])


def load_baseline_file(f: Path) -> set[str]:
    return {l.strip() for l in f.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")}


def write_locale_baseline(directory: Path, locale: str, keys: set[str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / f"{locale}.txt"
    f.write_text(BASELINE_NOTE + "".join(k + "\n" for k in sorted(keys)), encoding="utf-8")
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--locale", help="one locale, e.g. de")
    ap.add_argument("--all", action="store_true", help="every locale under i18n/")
    ap.add_argument("--check", action="append",
                    help="restrict to one subcheck (repeatable): line-shape, numbers, "
                         "list-items, title-untranslated, neighbour-duplicate")
    ap.add_argument("--json", type=Path, help="write the findings to this file")
    ap.add_argument("--write-baseline", type=Path, metavar="DIR",
                    help="record the current findings of each scanned locale as its accepted "
                         "baseline (DIR/<locale>.txt); other locales' files are left alone")
    ap.add_argument("--baseline", type=Path, metavar="PATH",
                    help="exit 1 on any finding NOT in this baseline (the CI ratchet): a "
                         "per-locale directory, or the legacy single JSON file")
    ap.add_argument("--accept-new", action="store_true",
                    help="with a --baseline directory: add every new finding's key to its "
                         "locale's file instead of failing. Read the findings first.")
    ap.add_argument("--limit", type=int, default=40, help="findings to print per locale (0 = all)")
    args = ap.parse_args()

    if not args.locale and not args.all:
        ap.error("pass --locale <loc> or --all")
    locales = all_locales() if args.all else [args.locale]

    out: list[dict] = []
    for loc in locales:
        files = locale_files(loc)
        if not files:
            print(f"{loc}: no PO files under i18n/{loc}/po", file=sys.stderr)
            continue
        found: list[dict] = []
        scanned = 0
        for f in files:
            try:
                rows = check_file(f)
            except OSError as exc:  # an unreadable PO is the renderer's problem, not ours
                print(f"{loc}: cannot read {f}: {exc}", file=sys.stderr)
                continue
            scanned += 1
            found.extend(rows)
        if args.check:
            found = [r for r in found if r["check"] in args.check]
        for r in found:
            r["locale"] = loc
        out.extend(found)

        per = collections.Counter(r["check"] for r in found)
        summary = ", ".join(f"{k} {v}" for k, v in sorted(per.items())) or "nothing"
        print(f"{loc}: {len(found)} finding(s) over {scanned} file(s) — {summary}")
        shown = found if args.limit == 0 else found[: args.limit]
        for r in shown:
            page = r["file"].split("/po/", 1)[-1]
            print(f"  {r['check']:20s} {page}#{r['index']}: {r['detail']}")
            print(f"      EN {r['msgid'][:100]!r}")
            print(f"      TR {r['msgstr'][:100]!r}")
        if args.limit and len(found) > args.limit:
            print(f"  … {len(found) - args.limit} more (use --limit 0)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {len(out)} finding(s) to {args.json}")

    if args.write_baseline:
        if args.write_baseline.suffix == ".json":
            ap.error("--write-baseline takes the per-locale directory "
                     "(translation/eval/completeness-baseline), not a .json file")
        for loc in locales:
            keys = {finding_key(r) for r in out if r["locale"] == loc}
            f = write_locale_baseline(args.write_baseline, loc, keys)
            print(f"baseline: {len(keys)} key(s) → {f}")
        return 0

    if args.baseline:
        known = load_baseline(args.baseline)
        new_rows = [r for r in out if finding_key(r) not in known]
        if new_rows and args.accept_new:
            if not args.baseline.is_dir():
                ap.error("--accept-new needs the per-locale baseline directory")
            for loc in sorted({r["locale"] for r in new_rows}):
                f = args.baseline / f"{loc}.txt"
                have = load_baseline_file(f) if f.exists() else set()
                add = {finding_key(r) for r in new_rows if r["locale"] == loc}
                write_locale_baseline(args.baseline, loc, have | add)
                print(f"\naccepted {len(add - have)} new key(s) for {loc} → {f}")
                for r in new_rows:
                    if r["locale"] == loc:
                        page = r["file"].split("/po/", 1)[-1]
                        print(f"  {r['check']:20s} {page}#{r['index']}: {r['detail']}")
            return 0
        if not new_rows:
            print(f"\nratchet: no new findings ({len(out)} known, baseline {len(known)})")
            return 0
        print(f"\nratchet: {len(new_rows)} NEW finding(s) not in the baseline:")
        for r in new_rows[:25]:
            page = r["file"].split("/po/", 1)[-1]
            print(f"  {r['locale']} {r['check']:20s} {page}#{r['index']}: {r['detail']}")
            print(f"      EN {r['msgid'][:90]!r}")
            print(f"      TR {r['msgstr'][:90]!r}")
        if len(new_rows) > 25:
            print(f"  … {len(new_rows) - 25} more")
        print("\nIf these are real, fix them. If they are the sieve being wrong (it is "
              "right about 12% of the time), re-run with --accept-new to accept them "
              "(it writes only the affected locales' files).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
