#!/usr/bin/env python3
"""Post-build checks on a built Docusaurus site (one locale).

Each check guards a defect that every page-level gate passed and only a
visitor noticed (UX review, 2026-10-08):

  1. download   every docs page with `notebook_path` front matter has its
                notebook at build/notebooks/<path> (the "Download ↓" target;
                it 404'd on all 219 notebook pages for months).
  2. describe   no <meta name="description"> carries the translation
                pipeline's `doqumentation-source-hash` marker (translated
                pages showed it as their search snippet).
  3. rtl-math   in an RTL build, KaTeX stays left-to-right. rtlcss flips a
                plain `direction: ltr` to `rtl`, which mirrored every
                equation on the ar and he sites.

    python3 scripts/check-built-site.py [--build build] [--docs docs]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FM_NOTEBOOK = re.compile(r'^notebook_path:\s*"?([^"\n]+?)"?\s*$', re.M)
META_DESC = re.compile(r'<meta[^>]+name="description"[^>]*>', re.I)
KATEX_RTL = re.compile(r'\[dir=rtl\][^{}]*\.katex[^{}]*\{[^}]*direction:\s*rtl', re.I)


def check_downloads(build: Path, docs: Path) -> list[str]:
    errors = []
    for mdx in sorted(docs.rglob('*.mdx')):
        head = mdx.read_text(encoding='utf-8')[:2000]
        m = FM_NOTEBOOK.search(head)
        if not m:
            continue
        path = m.group(1).strip()
        stem = path[:-len('.ipynb')] if path.endswith('.ipynb') else path
        if '/' not in stem:
            stem = f'tutorials/{stem}'
        target = build / 'notebooks' / f'{stem}.ipynb'
        if not target.is_file():
            errors.append(f'download: {mdx.relative_to(docs)} → /notebooks/{stem}.ipynb is missing')
    return errors


def check_descriptions(build: Path) -> list[str]:
    errors = []
    for html in build.rglob('*.html'):
        text = html.read_text(encoding='utf-8', errors='replace')
        for tag in META_DESC.findall(text[:20000]):
            if 'doqumentation-source-hash' in tag:
                errors.append(f'describe: {html.relative_to(build)} has the source-hash marker as its description')
                break
    return errors


def check_rtl_math(build: Path) -> list[str]:
    errors = []
    for css in build.rglob('*.css'):
        if KATEX_RTL.search(css.read_text(encoding='utf-8', errors='replace')):
            errors.append(f'rtl-math: {css.relative_to(build)} sets KaTeX to direction: rtl (add /* rtl:ignore */)')
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--build', default='build', type=Path)
    ap.add_argument('--docs', default='docs', type=Path)
    args = ap.parse_args()
    if not args.build.is_dir():
        print(f'no build directory at {args.build}', file=sys.stderr)
        return 2
    errors = check_downloads(args.build, args.docs) + check_descriptions(args.build) + check_rtl_math(args.build)
    for e in errors[:50]:
        print(e)
    if len(errors) > 50:
        print(f'... and {len(errors) - 50} more')
    print(f'check-built-site: {len(errors)} problem(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
