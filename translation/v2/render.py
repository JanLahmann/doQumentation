#!/usr/bin/env python3
"""Render locale MDX pages from the English source and the locale's PO files.

    python3 translation/v2/render.py --locale de                 # in place, every page with a PO
    python3 translation/v2/render.py --locale de --out-dir /tmp/de-preview
    python3 translation/v2/render.py --locale de --page guides/hello-world.mdx

Writes i18n/<locale>/docusaurus-plugin-content-docs/current/<page>.mdx, which
is where Docusaurus and every v1 tool expect a translation. The v1 freshness
marker is written too, with the hash of the English the page was rendered
from, so v1's freshness check, status and populate-locale keep working while
both pipelines coexist.

A page whose PO has untranslated or fuzzy entries still renders: those
segments come out in English. Pages without a PO are left alone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--page")
    ap.add_argument("--out-dir", help="write here instead of into i18n/ (same relative layout)")
    args = ap.parse_args()

    pages = [args.page] if args.page else io.all_pages()
    done = missing = failed = 0
    for rel in pages:
        po = io.po_path(args.locale, rel)
        if not po.exists():
            missing += 1
            continue
        out = Path(args.out_dir) / rel if args.out_dir else io.tr_path(args.locale, rel)
        try:
            io.render(rel, po, out)
            done += 1
        except io.Po4aError as e:
            failed += 1
            print(f"FAIL {rel}: {str(e).splitlines()[0][:140]}")
    print(f"{args.locale}: rendered {done}, no PO {missing}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
