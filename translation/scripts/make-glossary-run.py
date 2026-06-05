#!/usr/bin/env python3
"""Bake a locale list into a runnable copy of curate-and-fix-glossary.js."""
import argparse, json
from pathlib import Path
REPO=Path(__file__).resolve().parent.parent.parent
TEMPLATE=REPO/".claude"/"workflows"/"curate-and-fix-glossary.js"
NEEDLE="\nconst LOCALES = null\n"
NAMES={'de':'German','es':'Spanish','fr':'French','it':'Italian','pt':'Portuguese','uk':'Ukrainian','pl':'Polish','cs':'Czech','ro':'Romanian','ja':'Japanese','ko':'Korean','ar':'Arabic','he':'Hebrew','th':'Thai','ms':'Malay','id':'Indonesian','tl':'Tagalog'}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--locales",required=True,help="comma-separated locale codes")
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    locs=[{"locale":l,"locale_name":NAMES.get(l,l)} for l in a.locales.split(",") if l]
    t=TEMPLATE.read_text()
    if t.count(NEEDLE)!=1: raise SystemExit(f"expected exactly 1 marker, found {t.count(NEEDLE)}")
    Path(a.out).write_text(t.replace(NEEDLE,"\nconst LOCALES = "+json.dumps(locs,ensure_ascii=False)+"\n",1))
    print(f"Wrote {a.out} ({len(locs)} locales)")
if __name__=="__main__": main()
