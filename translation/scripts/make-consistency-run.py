#!/usr/bin/env python3
"""Bake a consistency-fix spec list into a runnable copy of fix-consistency.js."""
import argparse, json
from pathlib import Path
REPO=Path(__file__).resolve().parent.parent.parent
TEMPLATE=REPO/".claude"/"workflows"/"fix-consistency.js"
NEEDLE="\nconst FIXES = null\n"
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixes",required=True); ap.add_argument("--out",required=True)
    a=ap.parse_args()
    fixes=json.loads(Path(a.fixes).read_text())
    t=TEMPLATE.read_text()
    if t.count(NEEDLE)!=1: raise SystemExit(f"expected 1 marker, found {t.count(NEEDLE)}")
    Path(a.out).write_text(t.replace(NEEDLE,"\nconst FIXES = "+json.dumps(fixes,ensure_ascii=False)+"\n",1))
    print(f"Wrote {a.out} ({len(fixes)} files baked)")
if __name__=="__main__": main()
