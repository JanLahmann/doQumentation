#!/usr/bin/env python3
"""Extract every English page (or one) into translation/v2/pot/<page>.pot.

    python3 translation/v2/extract.py            # all pages
    python3 translation/v2/extract.py --page guides/hello-world.mdx
    python3 translation/v2/extract.py --check    # also prove identity render == source

POTs are derived from docs/ and can always be regenerated; they are kept in
git so a sync PR shows, entry by entry, which English segments changed.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", help="one page, relative to docs/")
    ap.add_argument("--check", action="store_true",
                    help="render each POT untranslated and require it to equal the source")
    args = ap.parse_args()

    pages = [args.page] if args.page else io.all_pages()
    if not args.page:
        # A page upstream deleted leaves a template behind; drop it so
        # update.py can drop the matching memories.
        live = {str(io.pot_path(rel)) for rel in pages}
        for stale in io.POT_DIR.rglob("*.pot"):
            if str(stale) not in live:
                stale.unlink()
                print(f"removed template for deleted page: {stale.relative_to(io.POT_DIR)}")
    ok = failed = mismatch = 0
    entries = 0
    for rel in pages:
        try:
            pot = io.extract(rel)
        except io.Po4aError as e:
            failed += 1
            print(f"FAIL {rel}: {str(e).splitlines()[0][:140]}")
            continue
        ok += 1
        entries += sum(1 for e in pot if io.translatable(e))
        if args.check:
            with tempfile.NamedTemporaryFile(suffix=".po", delete=False) as tmp:
                pot.save(tmp.name)
            rendered = io.render(rel, Path(tmp.name), with_marker=False)
            Path(tmp.name).unlink()
            if not io.same_page(rendered, (io.DOCS / rel).read_text(encoding="utf-8")):
                mismatch += 1
                print(f"ROUND-TRIP DIFFERS {rel}")
    print(f"extracted {ok} page(s), {entries} translatable entries; {failed} failed"
          + (f"; {mismatch} round-trip mismatch(es)" if args.check else ""))
    return 1 if failed or mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
