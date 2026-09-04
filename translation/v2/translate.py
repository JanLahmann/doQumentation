#!/usr/bin/env python3
"""Fill the untranslated and fuzzy entries of a locale's PO files.

    python3 translation/v2/translate.py --locale de --prepare
    python3 translation/v2/translate.py --locale de --apply

--prepare sorts the worklist (update.py --json) into tiers, cheapest first:

  copy        entries with nothing to translate (a pure $$ block, a code
              chunk, a citation, an image line): msgid copied to msgstr,
              no model.
  mechanical  fuzzy entries whose English changed only in punctuation
              placement or formatting markers (a comma moved outside $...$,
              bold added): the same edit applied to the previous German,
              accepted only if the checker passes. No model. About 18% of
              the German fuzzy entries were of this kind.
  haiku       fuzzy entries whose English is near-identical to the previous
              one (similarity >= 0.9): a cheap model reuses the previous
              translation with the change applied.
  sonnet      everything else.

The model tiers are written as batches under work/<locale>/, at most 120
items or 6,000 English words each (a batch costs ~50k tokens of fixed
agent overhead whatever its size, so bigger is cheaper per word), with manifest.json listing file, model
and size. Items carry only what a translator needs: id, type, msgid, and the
previous English/translation pair when the fuzzy match is real (similarity
>= 0.6). No page context: it doubled the input and was never used.

--apply reads every batch, runs check.py on each filled item, writes accepted
ones into the PO, and lists rejections. A batch item needs only "id" and
"msgstr"; the other fields are for the translator.

Cost, measured on the German run: an agent that reads the batch, checks
things and re-reads before writing spent about 150k tokens per 4,000 words;
one that reads once and writes once spends about a fifth of that. The
workflow in .claude/workflows/translate-locale.js enforces the latter.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402
from check import check_entry  # noqa: E402

BATCH_WORDS = 6000
BATCH_ITEMS = 120
LANGUAGE_TABLE = io.REPO / "translation" / "translation-prompt.md"


def language_info(locale: str) -> tuple[str, str]:
    if LANGUAGE_TABLE.exists():
        for line in LANGUAGE_TABLE.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            # table columns: | Language | LOCALE | Informal form |
            if len(cells) >= 3 and cells[1] == locale:
                return cells[0], " ".join(cells[2:])
    return locale, ""


def instructions(locale: str) -> str:
    lang, register = language_info(locale)
    return f"""# Translation instructions — {lang} ({locale})

Each batch is a JSON list of segments from doQumentation, a {lang} mirror of
IBM Quantum's Qiskit documentation. For every item write the {lang}
translation of `msgid` into `msgstr`. Change nothing else.

Register: {register or 'informal, as the existing translations use'}.

Rules, each enforced by an automatic checker:
- Keep byte-for-byte: inline code in backticks (including placeholders like
  `<per sub-job overhead>`), URLs, image paths, JSX/HTML tags and every
  attribute other than title=, heading anchors like {{#some-anchor}}, MDX
  comments {{/* ... */}}.
- Math: keep every $...$ span and every $$...$$ block exactly, including the
  number of $$ delimiters (an entry may start or end inside a block; copy
  that part unchanged). Only words inside \\text{{...}} may be translated.
- Keep these terms in English: Qiskit, Qubit, Gate, Circuit, Backend,
  Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum, QPU.
- A `type` of "Title ##" is a heading: translate the text, keep the anchor.
- A `type` starting with "Yaml Front Matter" is page metadata: plain text.
- A JSX tag item with title="...": translate only the title value.
- `prev_msgid`/`prev_msgstr`, when present, are the previous English and
  its {lang}: reuse the previous wording and apply exactly the change the
  new msgid made (renamed products, changed numbers, added or removed
  clauses). If the previous sentence is a different one, translate afresh.
- Every msgstr is a complete translation of its whole msgid, never a
  fragment. If an item is a proper name or code that must stay in English,
  copy msgid into msgstr unchanged.
"""


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Words only: punctuation, markers and $ delimiters are what the
    mechanical tier is allowed to move, so they must not count."""
    return re.sub(r"[^\w]+", " ", s).strip().lower()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b), autojunk=False).ratio()


def is_copy_only(msgid: str) -> bool:
    """Nothing a translator could change: math, code, citations, images."""
    s = msgid.strip()
    if not s:
        return False
    if s.startswith("!["):
        return True
    stripped = re.sub(r"\$\$.*?\$\$", "", s, flags=re.S)
    stripped = re.sub(r"\$[^$\n]+\$", "", stripped)
    stripped = re.sub(r"`[^`\n]+`", "", stripped)
    stripped = re.sub(r"\\[A-Za-z]+", "", stripped)
    if s.count("$$") % 2 == 1:          # an entry that opens or closes inside a block
        stripped = re.sub(r"\$\$.*$", "", stripped, flags=re.S) if s.find("$$") > 0 else ""
    words = re.findall(r"[A-Za-z]{3,}", stripped)
    return len(words) <= 1


def mechanical_transfer(prev_msgid: str, msgid: str, prev_msgstr: str) -> str | None:
    """When the English changed only in punctuation placement or in the
    emphasis markers around a leading phrase, apply the same edit to the
    previous translation. Returns None for any other change, or when the
    result fails the checker."""
    if _norm(prev_msgid) != _norm(msgid) or not prev_msgstr.strip():
        return None
    cand = prev_msgstr
    inside_old = re.search(r"[,.;:!?]\s*\$(?!\$)", prev_msgid)
    inside_new = re.search(r"[,.;:!?]\s*\$(?!\$)", msgid)
    if inside_old and not inside_new:
        cand = re.sub(r"([,.;:!?])\s*\$(?!\$)", r"$\1", cand)          # "$X,$" -> "$X$,"
    m_new = re.match(r"^(\*\*|__)(.+?)\1", msgid)
    m_old = re.match(r"^(\*\*|__)(.+?)\1", prev_msgid)
    if m_new and not m_old and not re.match(r"^(\*\*|__)", cand):
        phrase = m_new.group(2)
        cut = None
        if m_new.end() >= len(msgid.rstrip()):                       # whole entry emphasised
            cut = len(cand.rstrip())
        else:
            for punct in ("?", "!", ":", "."):
                if phrase.rstrip().endswith(punct) and punct in cand:
                    cut = cand.index(punct) + 1
                    break
        if cut is None:
            return None
        cand = m_new.group(1) + cand[:cut] + m_new.group(1) + cand[cut:]
    if _norm(cand) != _norm(prev_msgstr):
        return None
    return cand if not check_entry(msgid, cand) else None


def _write_direct(locale: str, direct: dict[str, list[tuple[int, str, str]]]) -> int:
    n = 0
    for page, fills in direct.items():
        po_file = io.po_path(locale, page)
        po = polib.pofile(str(po_file), wrapwidth=0)
        for idx, msgstr, note in fills:
            e = po[idx]
            if e.msgid.endswith("\n") and not msgstr.endswith("\n"):
                msgstr += "\n"
            e.msgstr = msgstr
            e.flags = [f for f in e.flags if f != "fuzzy"]
            e.previous_msgid = None
            e.tcomment = note
            n += 1
        po.save(str(po_file))
    return n


def prepare(locale: str, worklist: Path) -> dict:
    data = json.loads(worklist.read_text(encoding="utf-8"))
    items = data["items"]
    outdir = io.WORK_DIR / locale
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("batch-*.json"):
        old.unlink()
    (outdir / "instructions.md").write_text(instructions(locale), encoding="utf-8")

    tiers: dict[str, list] = {"copy": [], "mechanical": [], "haiku": [], "sonnet": []}
    direct: dict[str, list[tuple[int, str, str]]] = {}
    for it in items:
        page, idx = it["id"].rsplit("#", 1)
        if is_copy_only(it["msgid"]):
            tiers["copy"].append(it)
            direct.setdefault(page, []).append((int(idx), it["msgid"], "doq: copied, nothing translatable"))
            continue
        sim = similarity(it["previous_msgid"], it["msgid"]) if it.get("previous_msgid") else 0.0
        if sim >= 0.9:
            cand = mechanical_transfer(it["previous_msgid"], it["msgid"], it.get("previous_msgstr", ""))
            if cand is not None:
                tiers["mechanical"].append(it)
                direct.setdefault(page, []).append((int(idx), cand, "doq: mechanical transfer from the previous translation"))
                continue
        slim = {"id": it["id"], "type": it["type"], "msgid": it["msgid"], "msgstr": ""}
        if sim >= 0.6:
            slim["prev_msgid"] = it["previous_msgid"]
            slim["prev_msgstr"] = it.get("previous_msgstr", "")
        tiers["haiku" if sim >= 0.9 else "sonnet"].append(slim)

    n_direct = _write_direct(locale, direct)

    manifest: list[dict] = []
    n = 0
    for model in ("haiku", "sonnet"):
        batch: list[dict] = []
        words = 0
        for it in tiers[model] + [None]:
            if it is None or (batch and (len(batch) >= BATCH_ITEMS or words + len(it["msgid"].split()) > BATCH_WORDS)):
                if batch:
                    name = f"batch-{n:03d}-{model}.json"
                    (outdir / name).write_text(json.dumps(batch, indent=1, ensure_ascii=False), encoding="utf-8")
                    manifest.append({"file": str((outdir / name).relative_to(io.REPO)), "model": model,
                                     "items": len(batch), "words": words})
                    n += 1
                batch, words = [], 0
            if it is not None:
                batch.append(it)
                words += len(it["msgid"].split())
    (outdir / "manifest.json").write_text(json.dumps({
        "locale": locale,
        "instructions": str((outdir / "instructions.md").relative_to(io.REPO)),
        # inlined so a translator agent needs no Read for it: one turn less per batch
        "instructions_text": instructions(locale),
        "batches": manifest}, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {k: len(v) for k, v in tiers.items()}
    summary["batches"] = len(manifest)
    summary["words_to_model"] = sum(b["words"] for b in manifest)
    print(f"{locale}: copy {summary['copy']}, mechanical {summary['mechanical']} (written directly: {n_direct}); "
          f"haiku {summary['haiku']}, sonnet {summary['sonnet']} in {len(manifest)} batch(es), "
          f"{summary['words_to_model']} English words to a model")
    print(f"manifest: {(outdir / 'manifest.json').relative_to(io.REPO)}")
    return summary


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply(locale: str) -> int:
    outdir = io.WORK_DIR / locale
    accepted = rejected = skipped = 0
    by_page: dict[str, list[tuple[int, str]]] = {}
    cache: dict[str, polib.POFile] = {}
    for bpath in sorted(outdir.glob("batch-*.json")):
        for it in json.loads(bpath.read_text(encoding="utf-8")):
            if not it.get("msgstr", "").strip():
                skipped += 1
                continue
            page, idx = it["id"].rsplit("#", 1)
            if page not in cache:
                cache[page] = polib.pofile(str(io.po_path(locale, page)), wrapwidth=0)
            problems = check_entry(cache[page][int(idx)].msgid, it["msgstr"])
            if problems:
                rejected += 1
                print(f"REJECT {it['id']}: {'; '.join(problems)}")
                continue
            by_page.setdefault(page, []).append((int(idx), it["msgstr"]))
    for page, fills in by_page.items():
        po = cache[page]
        for idx, msgstr in fills:
            e = po[idx]
            if e.msgid.endswith("\n") and not msgstr.endswith("\n"):
                msgstr += "\n"
            e.msgstr = msgstr
            e.flags = [f for f in e.flags if f != "fuzzy"]
            e.previous_msgid = None
            e.tcomment = "doq: kept in English by the translator (name or code)" if msgstr.strip() == e.msgid.strip() else ""
            accepted += 1
        po.save(str(io.po_path(locale, page)))
    print(f"{locale}: accepted {accepted}, rejected {rejected}, unfilled {skipped}")
    return 1 if rejected else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--worklist", help="default translation/v2/work/worklist-<locale>.json")
    args = ap.parse_args()
    if not (args.prepare or args.apply):
        ap.error("--prepare and/or --apply")
    rc = 0
    if args.prepare:
        wl = Path(args.worklist) if args.worklist else io.WORK_DIR / f"worklist-{args.locale}.json"
        if not wl.exists():
            sys.exit(f"no worklist at {wl}; run update.py --locale {args.locale} --json {wl}")
        prepare(args.locale, wl)
    if args.apply:
        rc = apply(args.locale)
    return rc


if __name__ == "__main__":
    sys.exit(main())
