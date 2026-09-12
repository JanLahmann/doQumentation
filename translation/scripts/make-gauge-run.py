#!/usr/bin/env python3
"""
Bake a round's FAIL verdicts into a runnable copy of the refute-fails workflow.

For each FAIL record the cited examples are pinned to PO entries (the same
matcher fix.py uses, so an `entry` number from the paired-file read is exact)
and those entries travel inline with two neighbours on each side — the
refuters read passages, not pages. Usage:

    python3 translation/scripts/make-gauge-run.py --records translation/reviews/opus-<SEED>-<HANDLE>.json \\
        --locale <LOCALE> --out /tmp/gauge-<SEED>-wf.js
    # then:  Workflow({ scriptPath: "/tmp/gauge-<SEED>-wf.js" })
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import polib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO_ROOT / ".claude" / "workflows" / "refute-fails.js"
NEEDLE = "const BAKED = null"
CONTEXT = 2          # neighbours on each side of a cited entry


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_fix = _load("fix", REPO_ROOT / "translation" / "v2" / "fix.py")
_sampler = _load("sample_deep_review", REPO_ROOT / "translation" / "scripts" / "sample-deep-review.py")


def passages(locale: str, rel: str, examples: list[dict]) -> tuple[list[dict], int]:
    po = polib.pofile(str(_fix.io.po_path(locale, rel)), wrapwidth=0)
    translated = [(i, e) for i, e in enumerate(po) if e.msgstr.strip() and not e.obsolete]
    cited = set()
    for ex in examples:
        idx = _fix.match_example(ex, translated)
        if idx is not None:
            cited.add(idx)
            ex["entry"] = idx
    prose = [i for i, e in translated if not _fix.tr.is_copy_only(e.msgid)]
    take = set()
    for c in cited:
        if c in prose:
            k = prose.index(c)
            take.update(prose[max(0, k - CONTEXT): k + CONTEXT + 1])
        else:
            take.add(c)
    out = [{"entry": i, "cited": i in cited, "en": po[i].msgid.rstrip()[:2500], "tr": po[i].msgstr.rstrip()[:2500]}
           for i in sorted(take)]
    return out, len(cited)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", required=True, help="the round's records file (opus-<seed>-<handle>.json)")
    ap.add_argument("--locale", required=True)
    ap.add_argument("--out", required=True, help="runnable workflow .js")
    ap.add_argument("--agent", default=None, help="custom agent type for the refuters (e.g. reviewer)")
    a = ap.parse_args()
    data = json.loads(Path(a.records).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "records" in data:
        data = data["records"]
    fails = []
    for r in data:
        if r.get("verdict") != "FAIL" or r.get("locale") != a.locale:
            continue
        exs = [ex for ex in (r.get("examples") or []) if isinstance(ex, dict)]
        ps, pinned = passages(a.locale, r["file"], exs)
        pair = _sampler.pair_path(a.locale, r["file"])
        if not pair.exists():
            _sampler.write_pair(a.locale, r["file"])
        fails.append({"file": r["file"], "editor_note": r.get("editor_note", ""), "examples": exs,
                      "passages": ps, "pair": str(pair.relative_to(REPO_ROOT))})
        print(f"  {r['file']}: {len(exs)} example(s), {pinned} pinned, {len(ps)} passage(s)")
    if not fails:
        raise SystemExit(f"no FAIL records for {a.locale} in {a.records}")
    payload = {"locale": a.locale, "locale_name": _sampler.LOCALE_NAME.get(a.locale, a.locale), "fails": fails}
    if a.agent:
        payload["agentType"] = a.agent
    tpl = TEMPLATE.read_text(encoding="utf-8")
    assert NEEDLE in tpl
    Path(a.out).write_text(tpl.replace(NEEDLE, "const BAKED = " + json.dumps(payload, ensure_ascii=False), 1),
                           encoding="utf-8")
    print(f"Wrote {a.out}: {len(fails)} FAIL(s) → Workflow({{ scriptPath: \"{a.out}\" }})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
