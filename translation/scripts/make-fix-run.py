#!/usr/bin/env python3
"""Bake a B-fix spec list into a runnable copy of fix-misleading-translations.js.
Same pattern as make-opus-run.py (Workflow args don't pass through scriptPath)."""
import argparse, json
from pathlib import Path
REPO=Path(__file__).resolve().parent.parent.parent
TEMPLATE=REPO/".claude"/"workflows"/"fix-misleading-translations.js"
# Full-line match so a mention of the marker in a comment can't be hit first.
NEEDLE="\nconst FIXES = null\n"
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixes",required=True); ap.add_argument("--out",required=True)
    a=ap.parse_args()
    fixes=json.loads(Path(a.fixes).read_text())
    t=TEMPLATE.read_text()
    n=t.count(NEEDLE)
    if n!=1: raise SystemExit(f"expected exactly 1 marker line, found {n}")
    Path(a.out).write_text(t.replace(NEEDLE,"\nconst FIXES = "+json.dumps(fixes,ensure_ascii=False)+"\n",1))
    print(f"Wrote {a.out} ({len(fixes)} fixes baked)")
if __name__=="__main__": main()
