#!/usr/bin/env python3
"""Write src/config/pageRequirements.json: the pages whose code needs a newer
package version than an image may have, e.g. qiskit-ibm-runtime 0.50.

The install cell and the site's kernel setup only check that a package is
present. A page written for qiskit-ibm-runtime 0.50 (the executor_estimator
`Estimator`, ...) then fails with an ImportError on an image that ships 0.4x
(QuBins 2.5-xl is held below 0.50 by qiskit-serverless). ExecutableCode reads
this file, asks the kernel for the installed version and tells the reader
what to do when it is too old.

A page needs a version when one of its code blocks imports a name that first
appeared in that version (NEW_NAMES below). Each entry was checked against the
released wheels, and the 2026-10-05 sweep's ImportErrors on 2.5-xl are all
covered. Add an entry when a later release adds names the docs start using.

  python3 scripts/make-page-requirements.py          # write the file
  python3 scripts/make-page-requirements.py --check  # CI: fail if it is stale
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
OUT = ROOT / 'src' / 'config' / 'pageRequirements.json'

# distribution -> minimum version -> {module: names first importable there}
NEW_NAMES: dict[str, dict[str, dict[str, set[str]]]] = {
    'qiskit-ibm-runtime': {
        # 0.49 has executor_estimator.EstimatorV2 / executor_sampler.SamplerV2
        # only; 0.50 adds the Estimator/Sampler names and the options models.
        '0.50': {
            'qiskit_ibm_runtime.executor_estimator': {'Estimator'},
            'qiskit_ibm_runtime.executor_sampler': {'Sampler'},
            'qiskit_ibm_runtime.options_models': {
                'DynamicalDecouplingOptions', 'EstimatorOptions', 'MeasureNoiseLearningOptions',
                'PecOptions', 'ResilienceOptions', 'SamplerExecutionOptions', 'SimulatorOptions',
                'TwirlingOptions', 'ZneOptions',
            },
        },
    },
}

FENCE = re.compile(r'^```python[^\n]*\n(.*?)^```', re.M | re.S)
FROM_IMPORT = re.compile(r'^\s*from\s+([\w.]+)\s+import\s+(\([^)]*\)|[^\n#]+)', re.M)


def imported_names(code: str) -> set[tuple[str, str]]:
    out = set()
    for m in FROM_IMPORT.finditer(code):
        for part in m.group(2).strip('()').split(','):
            name = part.split(' as ')[0].strip().strip('\\').strip()
            if name.isidentifier():
                out.add((m.group(1), name))
    return out


def page_url(mdx: Path) -> str:
    """docs/guides/hello-world.mdx -> /guides/hello-world (index.mdx -> its folder)."""
    rel = mdx.relative_to(DOCS).with_suffix('').as_posix()
    if rel.endswith('/index'):
        rel = rel[: -len('/index')]
    return '/' + rel


def compute() -> dict[str, dict[str, str]]:
    pages: dict[str, dict[str, str]] = {}
    for mdx in sorted(DOCS.rglob('*.mdx')):
        names = set()
        for block in FENCE.findall(mdx.read_text(encoding='utf-8')):
            names |= imported_names(block)
        for dist, versions in NEW_NAMES.items():
            for version, modules in versions.items():
                if any(name in modules.get(mod, ()) for mod, name in names):
                    have = pages.setdefault(page_url(mdx), {}).get(dist)
                    if have is None or _key(version) > _key(have):
                        pages[page_url(mdx)][dist] = version
    return pages


def _key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split('.'))


def render(pages: dict[str, dict[str, str]]) -> str:
    data = {
        '_generated_by': 'scripts/make-page-requirements.py from the code blocks in docs/; do not edit by hand',
        'pages': pages,
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='fail if the file is out of date')
    args = ap.parse_args()
    text = render(compute())
    if args.check:
        current = OUT.read_text(encoding='utf-8') if OUT.exists() else ''
        if current != text:
            print(f'{OUT.relative_to(ROOT)} is out of date: run python3 scripts/make-page-requirements.py')
            return 1
        print(f'{OUT.relative_to(ROOT)} is up to date')
        return 0
    OUT.write_text(text, encoding='utf-8')
    n = len(json.loads(text)['pages'])
    print(f'wrote {OUT.relative_to(ROOT)}: {n} pages')
    return 0


if __name__ == '__main__':
    sys.exit(main())
