#!/usr/bin/env python3
"""Build i18n/<locale>/po/<page>.po from the translations that already exist.

    python3 translation/v2/bootstrap.py --locale de              # every genuine page
    python3 translation/v2/bootstrap.py --locale de --page guides/hello-world.mdx
    python3 translation/v2/bootstrap.py --locale de --verify     # also render and compare

Run this BEFORE merging an English sync: alignment needs the English the
translation was made from. Two strategies, in order:

  exact      po4a-gettextize pairs the two files entry by entry and refuses
             if their structures differ. Everything it produces is trusted.
  positional our fallback for pages po4a refuses: pair the type sequences of
             the prose entries with difflib and adopt only the runs that
             match; entries inside an insertion or replacement stay
             untranslated. The page renders with English for those.

Every PO records how it was made (X-Doq-Bootstrap: exact|positional) and, when
translation/status.json has verdicts for the page, the v1 review verdicts, so
nothing that was reviewed has to be reviewed again.

The report at translation/v2/work/bootstrap-<locale>.json lists every page
with its strategy, entry counts and, for failures, where the structures
diverge. Read it before trusting the locale.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402

STATUS = io.REPO / "translation" / "status.json"


def positional(rel: str, translated: Path) -> tuple[polib.POFile, int, int]:
    """Pair prose entries by type sequence. Returns (po, paired, total)."""
    en = io.entries_of((io.DOCS / rel).read_text(encoding="utf-8"))
    tr = io.entries_of(io.clean_translation(translated.read_text(encoding="utf-8")))
    sm = difflib.SequenceMatcher(None, [io.entry_type(e) for e in en],
                                 [io.entry_type(e) for e in tr], autojunk=False)
    po = polib.POFile()
    paired = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        for k, e in enumerate(en[i1:i2]):
            entry = polib.POEntry(msgid=e.msgid, comment=e.comment, flags=[f for f in e.flags if f != "fuzzy"])
            if tag == "equal":
                entry.msgstr = tr[j1 + k].msgstr or tr[j1 + k].msgid
                entry.tcomment = "doq-bootstrap: positional"
                paired += 1
            po.append(entry)
    return io.adopt(po), paired, len(en)


def review_meta(locale: str, rel: str, status: dict) -> dict[str, str]:
    e = status.get(locale, {}).get(rel, {})
    out = {}
    if e.get("review"):
        out["Review-Tier3"] = f"{e['review']} {e.get('reviewed', '')}".strip()
    if e.get("review_opus"):
        out["Review-Opus"] = f"{e['review_opus']} {e.get('reviewed_opus', '')}".strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--page")
    ap.add_argument("--verify", action="store_true", help="render from the PO and compare with the current file")
    ap.add_argument("--no-positional", action="store_true", help="exact strategy only")
    args = ap.parse_args()

    status = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    pages = [args.page] if args.page else io.all_pages()
    report: dict[str, dict] = {}
    counts = {"exact": 0, "positional": 0, "failed": 0, "skipped": 0}
    entries_total = entries_done = 0
    verified = verify_ok = 0

    for rel in pages:
        tr = io.tr_path(args.locale, rel)
        if not io.is_genuine(tr):
            counts["skipped"] += 1
            continue
        try:
            io.extract(rel)                     # keep the POT current for msgmerge later
        except io.Po4aError as e:
            report[rel] = {"strategy": "failed", "reason": "extract: " + str(e).splitlines()[0][:200]}
            counts["failed"] += 1
            continue
        strategy = "exact"
        try:
            po = io.gettextize(rel, tr)
            paired, total = len(po), len(po)
        except io.Po4aError:
            if args.no_positional:
                report[rel] = {"strategy": "failed", "reason": io.diagnose(rel, tr)}
                counts["failed"] += 1
                continue
            strategy = "positional"
            po, paired, total = positional(rel, tr)
            if paired == 0:
                report[rel] = {"strategy": "failed", "reason": io.diagnose(rel, tr)}
                counts["failed"] += 1
                continue
        io.set_header(po, rel, args.locale, Bootstrap=strategy, BootstrapDate=date.today().isoformat(),
                      **review_meta(args.locale, rel, status))
        out = io.po_path(args.locale, rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        po.save(str(out))
        counts[strategy] += 1
        entries_total += total
        entries_done += paired
        entry = {"strategy": strategy, "entries": total, "paired": paired}
        if strategy == "positional":
            entry["reason"] = io.diagnose(rel, tr)
        if args.verify:
            verified += 1
            rendered = io.render(rel, out)
            same = io.same_page(rendered, tr.read_text(encoding="utf-8"))
            entry["render_matches_current"] = same
            verify_ok += same
        report[rel] = entry

    io.WORK_DIR.mkdir(parents=True, exist_ok=True)
    rpath = io.WORK_DIR / f"bootstrap-{args.locale}.json"
    rpath.write_text(json.dumps({"locale": args.locale, "date": date.today().isoformat(),
                                 "counts": counts, "entries_total": entries_total,
                                 "entries_paired": entries_done, "pages": report},
                                indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{args.locale}: exact {counts['exact']}, positional {counts['positional']}, "
          f"failed {counts['failed']}, skipped(not genuine) {counts['skipped']}; "
          f"entries paired {entries_done}/{entries_total} "
          f"({100 * entries_done / max(entries_total, 1):.1f}%)")
    if args.verify:
        print(f"render matches current file: {verify_ok}/{verified}")
    print(f"report: {rpath.relative_to(io.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
