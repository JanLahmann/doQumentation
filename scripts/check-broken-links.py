#!/usr/bin/env python3
"""Broken-link ratchet over a Docusaurus build log.

`onBrokenLinks: 'warn'` lets the build pass with dead links, and for months
nobody read the warning: ~90 dead links sat in the English guides (UX review
2026-10-09). This reads the build's "broken links" and "broken anchors"
lists and fails when one appears that is not in the baseline, so a change
can only shrink the list. Entries that are gone are reported; shrink the
baseline with --update.

    npm run build -- --locale en 2>&1 | tee build.log
    python3 scripts/check-broken-links.py --log build.log
    python3 scripts/check-broken-links.py --log build.log --update   # after reading the new ones

One line per finding: `<kind>\t<source page>\t<target>`, sorted.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).resolve().parent / 'broken-links-baseline-en.txt'
SECTION = re.compile(r'Exhaustive list of all broken (links|anchors) found:')
SOURCE = re.compile(r'^- Broken (?:link|anchor) on source page path = (.+?):\s*$')
TARGET = re.compile(r'^\s+-> linking to (.+?)(?: \(resolved as: .*\))?\s*$')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def parse_log(text: str) -> set[str]:
    found = set()
    kind = source = None
    for raw in text.splitlines():
        line = ANSI.sub('', raw).rstrip()
        m = SECTION.search(line)
        if m:
            kind, source = m.group(1)[:-1], None  # "link" / "anchor"
            continue
        if kind is None:
            continue
        m = SOURCE.match(line)
        if m:
            source = m.group(1)
            continue
        m = TARGET.match(line)
        if m and source:
            found.add(f'{kind}\t{source}\t{m.group(1)}')
            continue
        if line.strip() and not line.startswith((' ', '-')):
            kind = source = None  # end of the list
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--log', required=True, type=Path, help='output of `docusaurus build`')
    ap.add_argument('--baseline', type=Path, default=DEFAULT_BASELINE)
    ap.add_argument('--update', action='store_true', help='rewrite the baseline from this log')
    args = ap.parse_args()

    text = args.log.read_text(encoding='utf-8', errors='replace')
    if '[SUCCESS] Generated static files' not in text and 'Generated static files in' not in text:
        print(f'{args.log} is not the log of a finished build', file=sys.stderr)
        return 2
    found = parse_log(text)
    if args.update:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(''.join(f'{e}\n' for e in sorted(found)), encoding='utf-8')
        print(f'wrote {len(found)} entries to {args.baseline}')
        return 0

    baseline = set()
    if args.baseline.is_file():
        baseline = {l for l in args.baseline.read_text(encoding='utf-8').splitlines() if l.strip()}
    new = sorted(found - baseline)
    gone = sorted(baseline - found)
    for kind in ('link', 'anchor'):
        n = sum(1 for e in found if e.startswith(kind + '\t'))
        b = sum(1 for e in baseline if e.startswith(kind + '\t'))
        print(f'broken {kind}s: {n} (baseline {b})')
    if gone:
        print(f'\n{len(gone)} baseline entr{"y is" if len(gone) == 1 else "ies are"} fixed; '
              'shrink the baseline with --update:')
        for e in gone[:20]:
            print('  fixed: ' + e.replace('\t', '  '))
        if len(gone) > 20:
            print(f'  ... and {len(gone) - 20} more')
    if new:
        print(f'\n{len(new)} NEW broken link(s)/anchor(s), not in {args.baseline.name}:')
        for e in new:
            print('  new: ' + e.replace('\t', '  '))
        print('\nFix them (plugins/content-fixes rewrites link forms at build time), or, after '
              'reading them, accept them with --update.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
