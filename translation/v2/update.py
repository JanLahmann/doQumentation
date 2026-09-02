#!/usr/bin/env python3
"""After an English sync: bring every PO up to date and print the worklist.

    python3 translation/v2/extract.py                    # fresh POTs from the new docs/
    python3 translation/v2/update.py --locale de         # msgmerge + summary
    python3 translation/v2/update.py --locale de --json translation/v2/work/worklist-de.json

For each page with a PO, `msgmerge --previous` against the new POT:
  - unchanged English  -> entry carried, nothing to do
  - near-identical     -> entry kept but marked fuzzy, old English kept as `#| msgid`
  - new English        -> empty entry
  - removed English    -> entry dropped
Pages with no PO yet (new upstream pages) are reported; render shows them in
English until they are translated.

The worklist is what translate.py consumes: every fuzzy or empty entry that
a translator should see (code, imports and bare JSX are never listed).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402


def worklist(locale: str, pages: list[str]) -> tuple[list[dict], Counter, list[str]]:
    items: list[dict] = []
    counts: Counter = Counter()
    no_po: list[str] = []
    for rel in pages:
        pot = io.pot_path(rel)
        po = io.po_path(locale, rel)
        if not pot.exists():
            continue
        if not po.exists():
            no_po.append(rel)
            counts["pages without PO"] += 1
            continue
        io.msgmerge(po, pot)
        p = polib.pofile(str(po), wrapwidth=0)
        for idx, e in enumerate(p):
            if not io.translatable(e):
                continue
            counts["entries"] += 1
            if e.fuzzy:
                counts["fuzzy"] += 1
            elif not e.msgstr.strip():
                counts["untranslated"] += 1
            else:
                counts["translated"] += 1
                continue
            items.append({
                "id": f"{rel}#{idx}",
                "page": rel,
                "type": io.entry_type(e),
                "msgid": e.msgid,
                "previous_msgid": e.previous_msgid or "",
                "previous_msgstr": e.msgstr if e.fuzzy else "",
                "context_before": p[idx - 1].msgid if idx > 0 else "",
                "context_after": p[idx + 1].msgid if idx + 1 < len(p) else "",
            })
    return items, counts, no_po


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--page")
    ap.add_argument("--json", help="write the worklist here")
    args = ap.parse_args()

    pages = [args.page] if args.page else io.all_pages()
    items, counts, no_po = worklist(args.locale, pages)
    print(f"{args.locale}: {counts['translated']} translated, {counts['fuzzy']} fuzzy, "
          f"{counts['untranslated']} untranslated of {counts['entries']} entries; "
          f"{counts['pages without PO']} page(s) without a PO")
    pages_touched = len({i['page'] for i in items})
    words = sum(len(i["msgid"].split()) for i in items)
    print(f"worklist: {len(items)} entries on {pages_touched} page(s), {words} English words")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"locale": args.locale, "items": items, "pages_without_po": no_po},
                                              indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"written: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
