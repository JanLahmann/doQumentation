#!/usr/bin/env python3
"""
Record page-level review verdicts in the PO files, and report review progress.

Since 2026-09-10 a page's deep-review verdict lives in the header of its PO
file (`X-Doq-Review-Opus: PASS 2026-07-05`), next to the translation it judges.
It is written by the review round itself, before the PR is opened, so the
verdict ships with the fixes and there is no maintainer step after merge.
The v1 `translation/status.json` was retired on 2026-09-10; the sampler
(`sample-deep-review.py`) and the contributor overview
(`contributing-status.py`) read the same headers.

Usage:
    # A finished round: record its verdicts into the locale's PO headers
    python translation/scripts/review-translations.py --record-opus \
        --from-json translation/reviews/opus-<seed>-<handle>.json [--locale de]

    # Progress per locale (reviewed / reviewable pages, pages mid-update)
    python translation/scripts/review-translations.py --progress [--locale de]

A record is `{locale, file, verdict, ...}` as the opus-deep-review workflow
returns it. Only page reads count: PASS, MINOR_ISSUES and FAIL are recorded;
FIXED (a repair round's record — the fixer corrected entries, nobody read the
page for meaning) is skipped, so a repaired page stays eligible for review.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import polib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
I18N_DIR = REPO_ROOT / "i18n"

REVIEW_HEADER = "X-Doq-Review-Opus"
PAGE_VERDICTS = ("PASS", "MINOR_ISSUES", "FAIL")
SKIPPED_VERDICTS = ("FIXED", "SKIPPED")


def _po4a_io():
    spec = importlib.util.spec_from_file_location("po4a_io", REPO_ROOT / "translation" / "v2" / "po4a_io.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_io = _po4a_io()


def _sampler():
    spec = importlib.util.spec_from_file_location("sample_deep_review", SCRIPTS_DIR / "sample-deep-review.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def po_path(locale: str, rel: str) -> Path:
    rel = rel[:-4] if rel.endswith(".mdx") else rel
    return I18N_DIR / locale / "po" / (rel + ".po")


def record_verdict(locale: str, rel: str, verdict: str, when: str,
                   overwrite: bool = True) -> str:
    """Write `X-Doq-Review-Opus: <verdict> <date>` into one PO header, and mark
    every model-written entry stamped BEFORE that date as verified: the reader
    saw it. Entries stamped on the same day — a round's own repairs, applied
    after the read — stay pending for the next delta read.
    Returns 'written', 'kept' (header present and overwrite=False) or 'no-po'."""
    p = po_path(locale, rel)
    if not p.exists():
        return "no-po"
    po = polib.pofile(str(p), wrapwidth=0)
    if po.metadata.get(REVIEW_HEADER) and not overwrite:
        return "kept"
    po.metadata[REVIEW_HEADER] = f"{verdict} {when}".strip()
    for e in po:
        since = _io.pending_since(e)
        if since and when and since < when:
            _io.mark_verified(e, when)
    po.save(str(p))
    return "written"


def record_opus_from_json(json_path: str, only_locale: str | None = None,
                          when: str | None = None) -> dict:
    """Record a round's page verdicts. With `only_locale`, records for any
    other locale are refused (a contributor's PR touches one locale)."""
    raw = sys.stdin.read() if json_path == "-" else Path(json_path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict) and "records" in data:
        data = data["records"]
    if not isinstance(data, list):
        sys.exit("Error: JSON must be an array of {locale, file, verdict, ...}")
    when = when or date.today().isoformat()
    counts = {"written": 0, "skipped": 0, "refused": 0, "no-po": 0, "invalid": 0}
    for item in data:
        locale, rel, verdict = item.get("locale"), item.get("file"), item.get("verdict")
        if verdict in SKIPPED_VERDICTS:
            counts["skipped"] += 1
            continue
        if verdict not in PAGE_VERDICTS or not locale or not rel:
            counts["invalid"] += 1
            print(f"  invalid record: {item!r}"[:200])
            continue
        if only_locale and locale != only_locale:
            counts["refused"] += 1
            continue
        res = record_verdict(locale, rel, verdict, when)
        if res == "no-po":
            counts["no-po"] += 1
            print(f"  no PO for {locale}/{rel}")
        else:
            counts["written"] += 1
            print(f"  {locale}/{rel} → {verdict}")
    print(f"\nRecorded {counts['written']} verdict(s) into PO headers"
          + (f"; skipped {counts['skipped']} repair record(s) (FIXED: not a page read)" if counts["skipped"] else "")
          + (f"; refused {counts['refused']} record(s) outside --locale {only_locale}" if counts["refused"] else "")
          + (f"; {counts['no-po']} without a PO" if counts["no-po"] else "")
          + (f"; {counts['invalid']} invalid" if counts["invalid"] else ""))
    return counts


def show_progress(only_locale: str | None = None, min_lines: int = 1) -> None:
    sdr = _sampler()
    locales = [only_locale] if only_locale else sdr.MAIN_LOCALES
    print(f"{'locale':7} {'reviewed':>9} {'reviewable':>11} {'pct':>5} {'mid-update':>11} {'delta pages':>11} {'unverified':>11} {'rendered':>9}")
    for loc in locales:
        cat = sdr.catalogue(loc)
        rendered = sum(1 for i in cat.values() if i["rendered"])
        reviewable = [i for i in cat.values()
                      if i["rendered"] and not i["fallback"] and i["lines"] >= min_lines]
        done = sum(1 for i in reviewable if i["verdict"])
        pending = sum(1 for i in cat.values() if i["pending"])
        delta = sum(1 for i in reviewable if i["verdict"] and i["unverified"])
        unverified = sum(len(i["unverified"]) for i in cat.values())
        pct = f"{100 * done // len(reviewable)}%" if reviewable else "—"
        note = "" if sdr.is_rendered(cat) else "  (not rendered: run render.py first)"
        print(f"{loc:7} {done:9} {len(reviewable):11} {pct:>5} {pending:11} {delta:11} {unverified:11} {rendered:9}{note}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record-opus", action="store_true",
                   help="record a round's page verdicts into the PO headers (--from-json)")
    g.add_argument("--progress", action="store_true", help="reviewed / reviewable pages per locale")
    ap.add_argument("--from-json", metavar="PATH", help="records file (or - for stdin)")
    ap.add_argument("--locale", help="restrict to one locale; --record-opus refuses records for others")
    ap.add_argument("--date", help="date to stamp instead of today (YYYY-MM-DD)")
    args = ap.parse_args()

    if args.record_opus:
        if not args.from_json:
            ap.error("--record-opus requires --from-json PATH (or -)")
        record_opus_from_json(args.from_json, args.locale, args.date)
    elif args.progress:
        show_progress(args.locale)


if __name__ == "__main__":
    main()
