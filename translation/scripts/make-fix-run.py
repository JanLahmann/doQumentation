#!/usr/bin/env python3
"""
Bake one or more batch manifests into runnable copies of the translate-locale
workflow, for a fix wave (or a translation fill) over one or many locales.

The Workflow runner does not reliably pass a large `args` payload through when a
workflow is invoked by scriptPath, and a manifest carries each locale's whole
instruction text. Like make-opus-run.py, this embeds the arguments in a
standalone copy of the workflow instead. Several manifests become one run:
every batch is tagged with its locale and each locale's rules travel once in
`instructions_by_locale`, which translate-locale.js already reads, so a
multi-locale wave keeps every locale's register line.

Usage:
    python3 translation/v2/fix.py --locale th --fixes F.json --prepare
    python3 translation/scripts/make-fix-run.py \\
        --manifest translation/v2/work/th/manifest-fix.json --out /tmp/fix-th.js
    # then:  Workflow({ scriptPath: "/tmp/fix-th.js" })

    # a wave over several locales, at most 10 batches per workflow:
    python3 translation/scripts/make-fix-run.py --per-workflow 10 \\
        --manifest translation/v2/work/de/manifest-fix.json \\
        --manifest translation/v2/work/fr/manifest-fix.json --out /tmp/fix-wave.js
    # writes /tmp/fix-wave-0.js, /tmp/fix-wave-1.js, … when the batches do not fit in one

Batches whose output file already holds a list of the right length are left
out (--all keeps them), so re-running this after an interrupted wave bakes
only what is still missing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO_ROOT / ".claude" / "workflows" / "translate-locale.js"
SPLIT = "\n// args = contents"


def filled(batch: dict) -> bool:
    """The batch's output is on disk and holds one string per item."""
    out = REPO_ROOT / batch["out"] if not Path(batch["out"]).is_absolute() else Path(batch["out"])
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, list) and len(data) == batch["items"]


def collect(manifests: list[Path], keep_filled: bool) -> tuple[str, dict[str, str], list[dict], int]:
    """(task, rules per locale, batches tagged with their locale, batches skipped as filled)."""
    tasks, rules, batches, skipped = set(), {}, [], 0
    for path in manifests:
        m = json.loads(path.read_text(encoding="utf-8"))
        tasks.add(m.get("task", "translate"))
        loc = m["locale"]
        rules[loc] = m.get("instructions_text") or f"Follow the rules in {m['instructions']} (read it once first)."
        for b in m["batches"]:
            if not keep_filled and filled(b):
                skipped += 1
                continue
            batches.append(dict(b, locale=b.get("locale", loc)))
    if len(tasks) != 1:
        raise SystemExit(f"manifests mix tasks {sorted(tasks)}: bake a fix wave and a translation fill separately")
    return tasks.pop(), rules, batches, skipped


def bake(template: str, name: str, task: str, rules: dict[str, str], batches: list[dict], agent: str) -> str:
    head, body = template.split(SPLIT, 1)
    head = re.sub(r"name: '[^']*'", f"name: '{name}'", head, count=1)
    locales = sorted({b["locale"] for b in batches})
    args = {"locale": locales[0], "task": task, "agentType": agent,
            "instructions_by_locale": {l: rules[l] for l in locales}, "batches": batches}
    # The template reads the global `args`; the baked copy reads the constant.
    body = re.sub(r"\bargs\b", "BAKED_ARGS", SPLIT.lstrip("\n") + body)
    return head + "\nconst BAKED_ARGS = " + json.dumps(args, ensure_ascii=False) + "\n" + body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", action="append", required=True, type=Path,
                    help="a manifest-fix.json or manifest.json (repeatable, one per locale)")
    ap.add_argument("--out", required=True, type=Path, help="output .js path")
    ap.add_argument("--per-workflow", type=int, default=0, metavar="N",
                    help="split into several workflows of at most N batches (default: one)")
    ap.add_argument("--agent", default="translator",
                    help="agent type (default: translator, .claude/agents/translator.md)")
    ap.add_argument("--all", action="store_true", help="also bake batches whose output is already filled")
    args = ap.parse_args()

    task, rules, batches, skipped = collect(args.manifest, args.all)
    if skipped:
        print(f"  {skipped} batch(es) already filled, left out (--all keeps them)")
    if not batches:
        print("nothing to bake: every batch is filled")
        return 0
    size = args.per_workflow or len(batches)
    parts = [batches[i:i + size] for i in range(0, len(batches), size)]
    template = TEMPLATE.read_text(encoding="utf-8")
    stem = args.out.with_suffix("")
    for i, part in enumerate(parts):
        out = args.out if len(parts) == 1 else stem.with_name(f"{stem.name}-{i}").with_suffix(".js")
        name = f"{task}-{stem.name}" + (f"-{i}" if len(parts) > 1 else "")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(bake(template, name, task, rules, part, args.agent), encoding="utf-8")
        locs = sorted({b["locale"] for b in part})
        print(f"Wrote {out}: {len(part)} batch(es), {sum(b['items'] for b in part)} item(s), locale(s) {' '.join(locs)}")
        print(f'  run: Workflow({{ scriptPath: "{out}" }})')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
