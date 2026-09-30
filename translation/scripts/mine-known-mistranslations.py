#!/usr/bin/env python3
"""Candidates for check-known-mistranslations.py, mined from the review records.

A deep-review round fixes a wrong term on the pages it happened to sample; the
same wrong term usually sits on pages no round has read yet. Every
Terminology example in translation/reviews/opus-*.json records the wrong
rendering and the reviewer's correction. This groups those corrections by
(locale, wrong -> right) term swap, keeps the ones reviewers made on several
different pages, and counts how often the wrong form still occurs in the
current PO files — the pages where it would be caught for free.

It proposes; it never edits. A candidate becomes a rule in
check-known-mistranslations.py only after every remaining occurrence has
been read against its English and the wrong form is never right in that
locale's Qiskit docs (the checker's own bar: a blanket replace must be safe).

    python3 translation/scripts/mine-known-mistranslations.py --locale ar
    python3 translation/scripts/mine-known-mistranslations.py --min-pages 3 --json out.json
"""

from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
import sys
from pathlib import Path

import polib

REPO = Path(__file__).resolve().parent.parent.parent
REVIEWS = REPO / "translation" / "reviews"
I18N = REPO / "i18n"
WORD_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
# Scripts written without spaces, or with combining vowel signs \w does not
# match, cannot be split into words this way (Thai came out as fragments).
UNSEGMENTED = {"th", "ja"}


def swaps(example: dict) -> list[tuple[str, str]]:
    """(wrong, right) phrase pairs one Terminology example corrects: runs of
    at most three words replaced by at most three, none shared with the
    English (a kept product name is not a defect)."""
    before = [w.lower() for w in WORD_RE.findall(example.get("translation") or "")]
    after = [w.lower() for w in WORD_RE.findall(example.get("suggested") or "")]
    if not before or not after:
        return []
    source = {w.lower() for w in WORD_RE.findall(example.get("source") or "")}
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes():
        if op != "replace" or i2 - i1 > 3 or j2 - j1 > 3:
            continue
        wrong = [w for w in before[i1:i2] if w not in source]
        if wrong and max(len(w) for w in wrong) >= 3:
            out.append((" ".join(before[i1:i2]), " ".join(after[j1:j2])))
    return out


def mine(locales: set[str] | None, min_pages: int) -> list[dict]:
    seen: dict[tuple[str, str, str], set[str]] = collections.defaultdict(set)
    whys: dict[tuple[str, str, str], str] = {}
    for f in sorted(REVIEWS.glob("opus-*.json")):
        try:
            recs = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(recs, dict):
            recs = recs.get("records", [])
        for r in recs:
            loc = r.get("locale")
            if not loc or loc in UNSEGMENTED or (locales and loc not in locales):
                continue
            for ex in r.get("examples") or []:
                if not isinstance(ex, dict) or (ex.get("type") or "").lower() != "terminology":
                    continue
                for wrong, right in swaps(ex):
                    key = (loc, wrong, right)
                    seen[key].add(r["file"])
                    whys.setdefault(key, (ex.get("why") or "")[:200])
    cands = [(k, pages) for k, pages in seen.items() if len(pages) >= min_pages]
    out = []
    corpora: dict[str, list[tuple[str, str, str]]] = {}
    for (loc, wrong, right), pages in sorted(cands, key=lambda kv: -len(kv[1])):
        if loc not in corpora:
            corpora[loc] = []
            for p in sorted((I18N / loc / "po").rglob("*.po")):
                for e in polib.pofile(str(p), wrapwidth=0):
                    if e.msgstr and not e.obsolete:
                        corpora[loc].append((str(p.relative_to(I18N / loc / "po")), e.msgid, e.msgstr))
        rx = re.compile(r"(?<!\w)" + r"\W+".join(map(re.escape, wrong.split())) + r"(?!\w)", re.IGNORECASE)
        hits = [(page, msgid, msgstr) for page, msgid, msgstr in corpora[loc] if rx.search(msgstr)]
        out.append({"locale": loc, "wrong": wrong, "right": right, "review_pages": len(pages),
                    "remaining": len(hits), "remaining_pages": len({h[0] for h in hits}),
                    "why": whys[(loc, wrong, right)],
                    "examples": [{"page": h[0], "en": h[1][:160], "tr": h[2][:160]} for h in hits[:3]]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", action="append", help="restrict to this locale (repeatable)")
    ap.add_argument("--min-pages", type=int, default=3,
                    help="a swap must have been made on at least this many pages (default 3)")
    ap.add_argument("--json", type=Path, help="write the candidates here")
    a = ap.parse_args()
    cands = mine(set(a.locale) if a.locale else None, a.min_pages)
    for c in cands:
        print(f"{c['locale']}  {c['wrong']!r} -> {c['right']!r}: corrected on {c['review_pages']} page(s); "
              f"{c['remaining']} occurrence(s) remain on {c['remaining_pages']} page(s)")
        if c["why"]:
            print(f"      why: {c['why'][:150]}")
    if a.json:
        a.json.write_text(json.dumps(cands, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n{len(cands)} candidate(s). Read every remaining occurrence against its English before "
          "adding one to check-known-mistranslations.py: a blanket replace must be safe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
