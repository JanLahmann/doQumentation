#!/usr/bin/env python3
"""
Run check.py over every committed PO entry and fail on any violation.

Why this exists
---------------
`check.py` is the pipeline's structural gate: every msgstr that `translate.py`
or `fix.py` writes must pass it. But it only ever ran on WRITES. The one-time
`bootstrap` migration seeded ~450k entries without it, and on 2026-09-09 an
audit found 87 of them still failing — a dropped `</Accordion>`, MDX comments
that did not match the source, lost URLs — the same ~5 English source entries
broken the same way in all 17 locales. Nothing had ever looked.

Those 87 are now 0, and this script keeps it there. Unlike the completeness
sieve (`check-completeness.py`, ~12% precision, wired as a ratchet), `check.py`
is the gate itself talking: a failure here is a real structural defect by
construction, so demanding zero is legitimate.

Usage:
    python translation/scripts/audit-check-py.py            # all locales
    python translation/scripts/audit-check-py.py --locale de
Exit status 1 on any failing entry, with each one listed.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

try:
    import polib
except ImportError:  # pragma: no cover
    sys.exit("polib is required: pip install polib")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "translation" / "v2"))
import check  # noqa: E402  (translation/v2/check.py)

I18N = REPO_ROOT / "i18n"


def failing_entries(po_path: Path) -> list[tuple[int, str, str]]:
    """(index, first problem, msgid head) for every live entry check.py rejects."""
    out = []
    live = [e for e in polib.pofile(str(po_path)) if not e.obsolete and e.msgstr.strip()]
    for i, e in enumerate(live):
        problems = check.check_entry(e.msgid, e.msgstr)
        if problems:
            out.append((i, problems[0], e.msgid.strip()[:70]))
    return out


def audit(locales: list[str]) -> int:
    total = 0
    per_locale: collections.Counter = collections.Counter()
    for loc in locales:
        for po_path in sorted((I18N / loc / "po").rglob("*.po")):
            rel = po_path.relative_to(I18N / loc / "po")
            for idx, problem, head in failing_entries(po_path):
                total += 1
                per_locale[loc] += 1
                print(f"FAIL {loc} {rel}#{idx}: {problem}")
                print(f"     EN {head!r}")
    if total:
        summary = ", ".join(f"{k} {v}" for k, v in sorted(per_locale.items()))
        print(f"\n{total} entr{'y' if total == 1 else 'ies'} fail check.py ({summary}).")
        print("Repair through fix.py --fixes (never by hand); see CONTRIBUTING-REVIEWS.md step 6.")
        return 1
    print(f"check.py: 0 failing entries across {len(locales)} locale(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--locale", help="one locale; default is every locale under i18n/")
    args = ap.parse_args()
    if args.locale:
        locales = [args.locale]
    else:
        locales = sorted(p.parent.name for p in I18N.glob("*/po") if p.is_dir())
    return audit(locales)


if __name__ == "__main__":
    raise SystemExit(main())
