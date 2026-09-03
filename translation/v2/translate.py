#!/usr/bin/env python3
"""Fill the untranslated and fuzzy entries of a locale's PO files.

Two halves, so the model can be whatever is at hand:

  python3 translation/v2/translate.py --locale de --prepare
      Reads the worklist (update.py --json) and writes batches under
      translation/v2/work/<locale>/batch-NNN.json plus instructions.md. Each
      batch is a JSON list of items with "msgid" and an empty "msgstr". Any
      agent, API script or human fills "msgstr" and leaves the rest alone.

  python3 translation/v2/translate.py --locale de --apply
      Reads every filled batch, runs check.py on each item, writes accepted
      translations into the PO (and clears the fuzzy flag), and lists the
      rejected ones with the reason. Rejected items stay in the worklist for
      the next round; nothing partial is ever written.

  python3 translation/v2/translate.py --locale de --prepare --backend anthropic
      Same as --prepare, then fills the batches through the Anthropic API
      (needs the `anthropic` package and ANTHROPIC_API_KEY). Not exercised in
      the environment this was written in; the batch-file path is.

The instructions given to the model are in instructions.md next to the
batches, derived from translation/translation-prompt.md's language table:
informal register, brand and Qiskit terms kept, inline code, URLs, math,
JSX and {#anchors} preserved verbatim. check.py enforces the preservable
parts mechanically, so the prompt only has to get the language right.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402
from check import check_entry  # noqa: E402

BATCH_WORDS = 4000          # a few pages of prose per model call; agent overhead dominates below that
LANGUAGE_TABLE = io.REPO / "translation" / "translation-prompt.md"


def language_info(locale: str) -> tuple[str, str]:
    """(language name, register note) from the v1 prompt's language table."""
    if LANGUAGE_TABLE.exists():
        for line in LANGUAGE_TABLE.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3 and cells[0] == locale:
                return cells[1], " ".join(cells[2:])
    return locale, ""


def instructions(locale: str) -> str:
    lang, register = language_info(locale)
    return f"""# Translation instructions — {lang} ({locale})

You are given JSON batches of documentation segments from doQumentation, a
{lang} mirror of IBM Quantum's Qiskit documentation. For every item, write
the {lang} translation of `msgid` into `msgstr`. Change nothing else.

Register: {register or 'informal, as the existing translations use'}.

Rules (the checker rejects violations):
- Keep byte-for-byte: inline code in backticks, URLs, image paths, math in
  $...$ and $$...$$, JSX/HTML tags and their attributes other than title=,
  heading anchors like {{#some-anchor}}, MDX comments {{/* ... */}}.
- Keep these terms in English: Qiskit, Qubit, Gate, Circuit, Backend,
  Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum, QPU.
- A `type` of "Title ##" is a heading: translate the text, keep the anchor.
- A `type` starting with "Yaml Front Matter" is page metadata: translate the
  value, no markup.
- An item whose msgid is a JSX tag with a title="..." attribute: translate
  only the title value.
- When `previous_msgid` and `previous_msgstr` are present the English changed
  slightly; produce the translation of the new `msgid`, reusing the previous
  wording wherever it still fits. If the change is punctuation only, the
  previous translation with the same punctuation change is the right answer.
- `context_before` and `context_after` are neighbours, for disambiguation
  only. Do not translate them.
- Do not add explanations, do not merge or split items.

Return the same JSON with `msgstr` filled.
"""


def prepare(locale: str, worklist: Path) -> int:
    data = json.loads(worklist.read_text(encoding="utf-8"))
    items = data["items"]
    outdir = io.WORK_DIR / locale
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("batch-*.json"):
        old.unlink()
    (outdir / "instructions.md").write_text(instructions(locale), encoding="utf-8")
    batches: list[list[dict]] = [[]]
    words = 0
    for it in items:
        w = len(it["msgid"].split())
        if batches[-1] and words + w > BATCH_WORDS:
            batches.append([])
            words = 0
        batches[-1].append({**it, "msgstr": ""})
        words += w
    n = 0
    for i, b in enumerate(batches):
        if not b:
            continue
        (outdir / f"batch-{i:03d}.json").write_text(json.dumps(b, indent=1, ensure_ascii=False), encoding="utf-8")
        n += 1
    print(f"{locale}: {len(items)} items in {n} batch(es) under {outdir.relative_to(io.REPO)}")
    return n


def fill_with_anthropic(locale: str, model: str) -> None:
    try:
        import anthropic  # type: ignore
    except ImportError:
        sys.exit("pip install anthropic, and set ANTHROPIC_API_KEY")
    client = anthropic.Anthropic()
    outdir = io.WORK_DIR / locale
    system = (outdir / "instructions.md").read_text(encoding="utf-8")
    for bpath in sorted(outdir.glob("batch-*.json")):
        batch = json.loads(bpath.read_text(encoding="utf-8"))
        if all(it["msgstr"] for it in batch):
            continue
        msg = client.messages.create(
            model=model, max_tokens=16000, system=system,
            messages=[{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}])
        text = "".join(getattr(part, "text", "") for part in msg.content)
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            print(f"{bpath.name}: no JSON in reply, left unfilled")
            continue
        filled = json.loads(m.group(0))
        by_id = {it["id"]: it.get("msgstr", "") for it in filled}
        for it in batch:
            it["msgstr"] = by_id.get(it["id"], "")
        bpath.write_text(json.dumps(batch, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{bpath.name}: filled {sum(1 for it in batch if it['msgstr'])}/{len(batch)}")


def apply(locale: str) -> int:
    outdir = io.WORK_DIR / locale
    accepted = rejected = skipped = 0
    by_page: dict[str, list[tuple[int, str]]] = {}
    for bpath in sorted(outdir.glob("batch-*.json")):
        for it in json.loads(bpath.read_text(encoding="utf-8")):
            if not it.get("msgstr", "").strip():
                skipped += 1
                continue
            problems = check_entry(it["msgid"], it["msgstr"])
            if problems:
                rejected += 1
                print(f"REJECT {it['id']}: {'; '.join(problems)}")
                continue
            page, idx = it["id"].rsplit("#", 1)
            by_page.setdefault(page, []).append((int(idx), it["msgstr"]))
    for page, fills in by_page.items():
        po_file = io.po_path(locale, page)
        po = polib.pofile(str(po_file), wrapwidth=0)
        for idx, msgstr in fills:
            e = po[idx]
            if e.msgid.endswith("\n") and not msgstr.endswith("\n"):
                msgstr += "\n"
            e.msgstr = msgstr
            e.flags = [f for f in e.flags if f != "fuzzy"]
            e.previous_msgid = None
            if msgstr.strip() == e.msgid.strip():
                e.tcomment = "doq: kept in English by the translator (name or code)"
            accepted += 1
        po.save(str(po_file))
    print(f"{locale}: accepted {accepted}, rejected {rejected}, unfilled {skipped}")
    return 1 if rejected else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--worklist", help="default translation/v2/work/worklist-<locale>.json")
    ap.add_argument("--backend", choices=["batchfile", "anthropic"], default="batchfile")
    ap.add_argument("--model", default="claude-sonnet-5")
    args = ap.parse_args()
    if not (args.prepare or args.apply):
        ap.error("--prepare and/or --apply")
    rc = 0
    if args.prepare:
        wl = Path(args.worklist) if args.worklist else io.WORK_DIR / f"worklist-{args.locale}.json"
        if not wl.exists():
            sys.exit(f"no worklist at {wl}; run update.py --locale {args.locale} --json {wl}")
        prepare(args.locale, wl)
        if args.backend == "anthropic":
            fill_with_anthropic(args.locale, args.model)
    if args.apply:
        rc = apply(args.locale)
    return rc


if __name__ == "__main__":
    sys.exit(main())
