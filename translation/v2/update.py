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
import re
import sys
from collections import Counter
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402


BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _norm_line(s: str) -> str:
    return BULLET_RE.sub("", s.strip())


def split_block_hint(msgid: str, old: list[tuple[str, str]]) -> tuple[str, str] | None:
    """The translation a new entry already has when its English was one line
    of a paragraph that upstream split apart.

    Measured on the first real sync (de, 2026-09-10): 121 of 127 "untranslated"
    entries were bullets that had been lines of an intro-plus-list paragraph;
    msgmerge matches whole entries, so the old block was dropped and every
    bullet came back as new work, though its German sat in the dropped msgstr.

    Returns (old_line, translated_line) when the old block's translation has
    the same number of lines as its English (so line i answers line i) and
    the line is found in exactly one way; None otherwise. A bullet marker
    the old line carried is removed from the translation too, since po4a's
    Bullet entries carry the text without it."""
    key = _norm_line(msgid)
    if not key:
        return None
    found = None
    for old_id, old_str in old:
        id_lines = [l for l in old_id.splitlines() if l.strip()]
        if len(id_lines) < 2:
            continue
        str_lines = [l for l in old_str.splitlines() if l.strip()]
        if len(str_lines) != len(id_lines):
            continue
        for i, line in enumerate(id_lines):
            if _norm_line(line) != key:
                continue
            tr = str_lines[i]
            cand = (line.strip(), _norm_line(tr) if BULLET_RE.match(line) else tr.strip())
            if found is not None and found != cand:
                return None          # the line occurs in two blocks with different translations
            found = cand
    return found


def worklist(locale: str, pages: list[str], init_missing: bool = False) -> tuple[list[dict], Counter, list[str]]:
    items: list[dict] = []
    counts: Counter = Counter()
    no_po: list[str] = []
    for rel in pages:
        pot = io.pot_path(rel)
        po = io.po_path(locale, rel)
        if not pot.exists():
            continue
        if not po.exists():
            if not init_missing:
                no_po.append(rel)
                counts["pages without PO"] += 1
                continue
            # New upstream page: seed an empty memory from the POT so its
            # entries appear on the worklist like any other untranslated ones.
            seed = polib.pofile(str(pot), wrapwidth=0)
            io.set_header(seed, rel, locale, Bootstrap="new-page")
            po.parent.mkdir(parents=True, exist_ok=True)
            seed.save(str(po))
            counts["pages seeded"] += 1
        # What the page said before the merge: msgmerge drops an entry whose
        # English is gone, and a paragraph upstream split into bullets is gone
        # as a whole even though every line of it is still on the page.
        before = polib.pofile(str(po), wrapwidth=0)
        old_pairs = [(e.msgid, e.msgstr) for e in before
                     if e.msgstr.strip() and not e.fuzzy and io.translatable(e)]
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
            item = {
                "id": f"{rel}#{idx}",
                "page": rel,
                "type": io.entry_type(e),
                "msgid": e.msgid,
                "previous_msgid": e.previous_msgid or "",
                "previous_msgstr": e.msgstr if e.fuzzy else "",
                "context_before": p[idx - 1].msgid if idx > 0 else "",
                "context_after": p[idx + 1].msgid if idx + 1 < len(p) else "",
            }
            if not e.fuzzy and old_pairs:
                hint = split_block_hint(e.msgid, old_pairs)
                if hint:
                    item["previous_msgid"], item["previous_msgstr"] = hint
                    item["transfer"] = "split-block"
                    counts["split-block hints"] += 1
            items.append(item)
    return items, counts, no_po


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--page")
    ap.add_argument("--json", help="write the worklist here")
    ap.add_argument("--init-missing", action="store_true",
                    help="seed an empty PO for pages that have none (new upstream pages)")
    args = ap.parse_args()

    pages = [args.page] if args.page else io.all_pages()
    if not args.page:
        live = {str(io.po_path(args.locale, rel)) for rel in pages}
        for stale in (io.I18N / args.locale / "po").rglob("*.po"):
            if str(stale) not in live:
                stale.unlink()
                print(f"removed memory for deleted page: {stale.relative_to(io.I18N / args.locale / 'po')}")
    items, counts, no_po = worklist(args.locale, pages, args.init_missing)
    print(f"{args.locale}: {counts['translated']} translated, {counts['fuzzy']} fuzzy, "
          f"{counts['untranslated']} untranslated of {counts['entries']} entries; "
          f"{counts['pages without PO']} page(s) without a PO, {counts['pages seeded']} seeded")
    pages_touched = len({i['page'] for i in items})
    words = sum(len(i["msgid"].split()) for i in items)
    print(f"worklist: {len(items)} entries on {pages_touched} page(s), {words} English words"
          + (f"; {counts['split-block hints']} carry a translation from a paragraph the English split"
             if counts["split-block hints"] else ""))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"locale": args.locale, "items": items, "pages_without_po": no_po},
                                              indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"written: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
