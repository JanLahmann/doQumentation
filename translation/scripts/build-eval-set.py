#!/usr/bin/env python3
"""
Build a labelled evaluation set for the meaning-and-completeness checks.

Why this exists
---------------
Every gate in this repo is a *markup* gate. `check.py` compares code spans,
math, URLs, tags, anchors, table rows and fence lines byte-for-byte and bounds
length at 0.3x-2.5x; lint, mdxcheck, check-wrong-language and
check-known-mistranslations sit at the same level. None of them asks whether a
translation says what its source says, and a fluent translation of the *wrong*
paragraph passes all of them.

Any check that tries to close that gap needs to be measurable, or it is just a
hunch with a threshold. This script produces the ruler.

Where the labels come from
--------------------------
The review rounds recorded in `translation/reviews/` did exactly the labelling
we need, as a side effect of doing the work. On a review branch, every PO entry
whose msgstr *changed* was judged defective by a reviewer and repaired; every
entry a reviewing agent read on those same pages and deliberately copied back
unchanged was judged faithful. Diffing the branch against its merge base
recovers both sets:

    positives   (msgid, defective msgstr, repaired msgstr)   — must be flagged
    negatives   (msgid, faithful msgstr)                     — must not be

Both are needed. Recall alone rewards a check that flags everything; noise
alone rewards a check that flags nothing.

Caveats a reader of the numbers must keep in mind
-------------------------------------------------
- The positives are defects a *particular* method found (the positional-drift
  sweeps). Recall measured here is recall on that class, not on every way a
  translation can be wrong. A fluent, complete, plausible mistranslation of a
  technical claim is not in this set, because nothing we ran could see it.
- The negatives come from drift-affected pages, not from a uniform sample of
  the corpus, so a noise rate measured here need not hold corpus-wide. Check
  the real flag count with `check-completeness.py --all` before trusting it.
- "Faithful" means an agent read it and let it stand. That is good evidence,
  not proof: the `title=` subcheck fires on 15 negatives and all 15 turned out
  to be genuine untranslated captions nobody had noticed.

Usage:
    python translation/scripts/build-eval-set.py
    python translation/scripts/build-eval-set.py --base main --head HEAD
    python translation/scripts/build-eval-set.py --out translation/eval/set.json
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import subprocess
import sys
from pathlib import Path

try:
    import polib
except ImportError:  # pragma: no cover - dependency is documented in the README
    sys.exit("polib is required: pip install polib")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Committed, not regenerated. Once this branch merges, merge-base(HEAD, main)
# IS HEAD and the diff that produced these labels is empty — the set cannot be
# rebuilt from main. Gzipped because it is ~9 MB of PO prose that compresses to
# ~2 MB and never needs to be read by anything but the scorer.
DEFAULT_OUT = REPO_ROOT / "translation" / "eval" / "completeness-eval.json.gz"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout


def merge_base(head: str) -> str:
    for ref in ("origin/main", "main"):
        try:
            return git("merge-base", head, ref).strip()
        except subprocess.CalledProcessError:
            continue
    sys.exit("no merge base against origin/main or main; pass --base explicitly")


def changed_po_files(base: str, head: str) -> list[str]:
    out = git("diff", "--name-only", base, head, "--", "i18n")
    return [p for p in out.split("\n") if p.endswith(".po")]


def entries_at(rev: str, path: str) -> dict[tuple[str, str | None], str] | None:
    """msgstr of every live entry of `path` as of `rev`, keyed by identity."""
    try:
        blob = git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return None  # the file did not exist at `rev`
    return {(e.msgid, e.msgctxt): e.msgstr for e in polib.pofile(blob) if not e.obsolete}


def build(base: str, head: str) -> dict:
    positives: list[dict] = []
    negatives: list[dict] = []

    for rel in changed_po_files(base, head):
        old = entries_at(base, rel)
        if old is None:
            continue  # a wholly new PO file has no "before" to label against
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        locale = Path(rel).parts[1]
        for e in polib.pofile(str(path)):
            if e.obsolete or not e.msgstr.strip():
                continue
            key = (e.msgid, e.msgctxt)
            if key not in old:
                continue
            before = old[key]
            if not before.strip():
                continue  # filled in from empty: a translation, not a repair
            row = {"locale": locale, "file": rel, "msgid": e.msgid}
            if before != e.msgstr:
                positives.append({**row, "defective": before, "repaired": e.msgstr})
            else:
                negatives.append({**row, "msgstr": e.msgstr})

    return {
        "base": base,
        "head": git("rev-parse", head).strip(),
        "note": (
            "positives: msgstrs a reviewer judged defective and repaired. "
            "negatives: msgstrs a reviewing agent read on the same pages and "
            "deliberately left unchanged. See the module docstring for what "
            "these labels do and do not prove."
        ),
        "positives": positives,
        "negatives": negatives,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--base", help="revision to diff from (default: merge base with main)")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stats", action="store_true", help="print the per-locale breakdown")
    args = ap.parse_args()

    base = args.base or merge_base(args.head)
    data = build(base, args.head)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if args.out.suffix == ".gz":
        # mtime=0 so an unchanged set produces an identical blob and does not
        # show up as a spurious diff on every rebuild.
        with gzip.GzipFile(args.out, "wb", compresslevel=9, mtime=0) as fh:
            fh.write(blob.encode("utf-8"))
    else:
        args.out.write_text(blob, encoding="utf-8")

    pos, neg = data["positives"], data["negatives"]
    shown = (args.out.relative_to(REPO_ROOT)
             if args.out.is_relative_to(REPO_ROOT) else args.out)
    print(f"{shown}: {len(pos)} positive(s), {len(neg)} negative(s)")
    if args.stats:
        per = collections.Counter(p["locale"] for p in pos)
        print("  positives per locale: " + ", ".join(f"{k} {v}" for k, v in sorted(per.items())))
    if not pos:
        print("  WARNING: no positives — is this branch a review branch with merged fixes?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
