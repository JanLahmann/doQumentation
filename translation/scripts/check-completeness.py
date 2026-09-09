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

    subcheck              recall on 314   fires on 64,149 faithful
    line-shape                 33.8%              0.44%
    numbers                    28.3%              0.44%
    list-items                  4.1%              0.02%
    title-untranslated          2.2%              0.14%
    ------------------------------------------------------------------
    union of the four          53.8%              ~1.0%

    neighbour-duplicate         1.7%              0.05%   (needs file context;
                                                           not in the union above)

The 314 are the independently selected positives (the drift rounds). The set
holds 1,147 after #517 and #524 were merged in, but the other 833 were chosen
FROM this sieve's findings by the gauge rounds, so recall on them (82%) is
circular and the scorer excludes them. The noise column did move: the
negatives now cover all 17 locales, and line-shape fires more on ja/ko/th,
where a translator legitimately re-breaks a paragraph.

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
        --baseline translation/eval/completeness-baseline.json
"""

from __future__ import annotations

import argparse
import collections
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

NUMBER_RE = re.compile(r"\d[\d,. ]*")
LIST_ITEM_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+")
TITLE_RE = re.compile(r'title="([^"]*)"')

# A title= of fewer than this many words is usually a label or a proper name
# ("Answer" is caught by other means; "Qiskit" must not be flagged at all).
TITLE_MIN_WORDS = 4
# Below this length two neighbouring entries sharing a msgstr is ordinary
# repetition ("Note", "Example"), not a copied paragraph.
DUPLICATE_MIN_CHARS = 40
# How far to look for the duplicate. Drift moves an entry by one or two slots.
DUPLICATE_WINDOW = 2


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


def check_pair(msgid: str, msgstr: str) -> list[dict]:
    """Subchecks that need only the entry itself. Pure: string in, findings out."""
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
    if a != b:
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

    return findings


def check_file(path: Path) -> list[dict]:
    """Every subcheck over one PO file, including the ones needing neighbours."""
    po = polib.pofile(str(path))
    live = [e for e in po if not e.obsolete and e.msgstr.strip()]
    rel = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else path.name

    findings: list[dict] = []
    for i, e in enumerate(live):
        rows = check_pair(e.msgid, e.msgstr)

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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--locale", help="one locale, e.g. de")
    ap.add_argument("--all", action="store_true", help="every locale under i18n/")
    ap.add_argument("--check", action="append",
                    help="restrict to one subcheck (repeatable): line-shape, numbers, "
                         "list-items, title-untranslated, neighbour-duplicate")
    ap.add_argument("--json", type=Path, help="write the findings to this file")
    ap.add_argument("--write-baseline", type=Path, metavar="PATH",
                    help="record the current findings as the accepted baseline")
    ap.add_argument("--baseline", type=Path, metavar="PATH",
                    help="exit 1 on any finding NOT in this baseline (the CI ratchet)")
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
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(json.dumps({
            "note": ("Findings accepted as pre-existing. This file is a RATCHET, not a "
                     "target: the sieve's measured precision is ~12%, so most of these are "
                     "fine and demanding they be cleared would be wrong. It exists so a "
                     "change cannot ADD a finding unnoticed. Shrink it by fixing real "
                     "defects and re-running --write-baseline; never by loosening a "
                     "subcheck — tests/test_completeness.py scores every subcheck against "
                     "the labelled set for exactly that reason."),
            "count": len(out),
            "keys": sorted({finding_key(r) for r in out}),
        }, indent=1) + "\n", encoding="utf-8")
        print(f"\nbaseline: {len(out)} finding(s) → {args.write_baseline}")
        return 0

    if args.baseline:
        known = set(json.loads(args.baseline.read_text(encoding="utf-8"))["keys"])
        new_rows = [r for r in out if finding_key(r) not in known]
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
              "right about 12% of the time), re-run with --write-baseline to accept them.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
