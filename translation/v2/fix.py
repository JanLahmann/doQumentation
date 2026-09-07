#!/usr/bin/env python3
"""Apply review findings to the PO files — the v2 fix path.

A deep-review round (CONTRIBUTING-REVIEWS.md) produces per-page findings:
an editor's note and a few quoted examples. Before v2 a Sonnet agent edited
the rendered page in place; since the rendered pages are derived from the
PO files and not in git, such an edit is lost at the next render. This tool
routes the same fix through the PO pipeline instead, reusing the batch
format, the translate-locale workflow and the `translate.py --apply` gate,
so a review fix is just another checked write to a msgstr.

    # 1. write the findings (the review records themselves are accepted):
    #    [{"rel": "guides/foo.mdx", "note": "...", "examples": [
    #        {"source": "<EN quote>", "translation": "<current>",
    #         "why": "...", "suggested": "..."}]}]
    python3 translation/v2/fix.py --locale fr --fixes work/fixes-fr.json --prepare
    #    → work/fr/fix-NNN-sonnet.json (+ .ids.json) and work/fr/manifest-fix.json
    # 2. fill the batches: Workflow translate-locale.js with manifest-fix.json as args
    python3 translation/v2/fix.py --locale fr --apply
    python3 translation/v2/render.py --locale fr

Each batch is one page (or part of one): every translated prose entry of
the page as {msgid, prev_msgstr}, with a "review" field on the entries the
examples point at. The agent returns the corrected msgstr for every item,
copying the unchanged ones verbatim; --apply writes only the entries that
actually changed and pass check.py, and stamps them with a provenance
comment. Nothing else ever writes a msgstr (translation/v2/README.md, Hard
rules).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import date
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402
import translate as tr  # noqa: E402

MATCH_MIN = 0.55        # difflib ratio from which a quoted example is pinned to an entry


def fix_instructions(locale: str) -> str:
    lang, register = tr.language_info(locale)
    return f"""# Review-fix instructions — {lang} ({locale})

Each batch is one page of doQumentation, a {lang} mirror of IBM Quantum's
Qiskit documentation, as a JSON list of segments. Every item carries the
English `msgid` and the CURRENT {lang} translation `prev_msgstr`. A reviewer
has read this page and found defects; the page note is in your prompt and
the items the reviewer quoted carry a `review` field saying what is wrong
and, when known, what it should say.

Your task: return, for every item, the corrected {lang} translation.
- Fix the items with a `review` field, and the same defect wherever else it
  occurs on the page (a wrong term is usually wrong in more than one place).
- Copy every other `prev_msgstr` back VERBATIM. Do not restyle, do not
  improve, do not retranslate what the reviewer did not flag. The apply step
  only writes entries that changed; every unflagged change is a risk with
  no reviewer behind it.
- Never put an English msgid in place of a translation unless the item is a
  proper name or code (then `prev_msgstr` already equals it).

Register: {register or 'informal, as the existing translations use'}.

Rules, each enforced by an automatic checker (a violation rejects the entry):
- Keep byte-for-byte: inline code in backticks, URLs, image paths, JSX/HTML
  tags and every attribute other than title=, heading anchors like
  {{#some-anchor}}, MDX comments {{/* ... */}}, every $...$ and $$...$$ span.
- Keep these terms in English: Qiskit, Qubit, Gate, Circuit, Backend,
  Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum, QPU.
- Every msgstr is a complete translation of its whole msgid, never a
  fragment.
"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", s or "")).strip().lower()


def _entry_type(e: polib.POEntry) -> str:
    t = (e.comment or "").strip()
    if t.startswith("type: "):
        t = t[len("type: "):]
    return t or "Plain text"


def match_example(example: dict, entries: list[tuple[int, polib.POEntry]]) -> int | None:
    """Index (into the PO) of the entry a quoted example points at, or None.

    Tries the English quote against msgid first, then the quoted translation
    against msgstr: containment wins, otherwise the best difflib ratio above
    MATCH_MIN. Quotes are short excerpts, so compare against a window of the
    entry rather than the whole thing."""
    best: tuple[float, int | None] = (0.0, None)
    for quote, attr in ((example.get("source"), "msgid"), (example.get("translation"), "msgstr")):
        q = _norm(quote)
        if len(q) < 12:
            continue
        for idx, e in entries:
            target = _norm(getattr(e, attr))
            if not target:
                continue
            if q in target or target in q:
                return idx
            window = target[: max(len(q) * 2, 200)]
            ratio = difflib.SequenceMatcher(None, q, window).ratio()
            if ratio > best[0]:
                best = (ratio, idx)
    return best[1] if best[0] >= MATCH_MIN else None


def _review_text(ex: dict) -> str:
    parts = []
    if ex.get("type"):
        parts.append(str(ex["type"]))
    if ex.get("why"):
        parts.append(str(ex["why"]))
    if ex.get("suggested"):
        parts.append(f"Suggested: {ex['suggested']}")
    if not parts and ex.get("source"):
        parts.append(f"The reviewer quoted this passage as defective: {ex['source'][:160]}")
    return " ".join(parts)


def load_fixes(path: Path) -> list[dict]:
    """Accept the step-6 fix spec or raw review records (opus-*.json)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "records" in data:
        data = data["records"]
    out = []
    for f in data:
        rel = f.get("rel") or f.get("file")
        if not rel:
            continue
        if f.get("verdict") == "PASS":
            continue
        out.append({
            "rel": rel,
            "note": f.get("note") or f.get("editor_note") or "",
            "examples": [ex for ex in (f.get("examples") or []) if isinstance(ex, dict)],
        })
    return out


def prepare(locale: str, fixes: list[dict], model: str = "sonnet") -> dict:
    outdir = io.WORK_DIR / locale
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("fix-*.json"):
        old.unlink()
    (outdir / "instructions-fix.md").write_text(fix_instructions(locale), encoding="utf-8")

    manifest: list[dict] = []
    n = 0
    n_items = n_flagged = 0
    missing: list[str] = []
    unmatched = 0
    for fx in fixes:
        rel = fx["rel"]
        po_file = io.po_path(locale, rel)
        if not po_file.exists():
            missing.append(rel)
            continue
        po = polib.pofile(str(po_file), wrapwidth=0)
        entries = [(i, e) for i, e in enumerate(po)
                   if e.msgstr.strip() and not e.obsolete and not tr.is_copy_only(e.msgid)]
        reviews: dict[int, list[str]] = {}
        for ex in fx["examples"]:
            idx = match_example(ex, entries)
            if idx is None:
                unmatched += 1
                continue
            reviews.setdefault(idx, []).append(_review_text(ex))
        items = []
        for idx, e in entries:
            it = {"msgid": tr.shrink_data_uris(e.msgid), "prev_msgstr": tr.shrink_data_uris(e.msgstr)}
            t = _entry_type(e)
            if t != "Plain text":
                it["type"] = t
            if idx in reviews:
                it["review"] = " | ".join(r for r in reviews[idx] if r) or "flagged by the reviewer"
            it["_id"] = f"{rel}#{idx}"
            items.append(it)
        n_items += len(items)
        n_flagged += len(reviews)
        pos = 0
        for batch in tr.split_batches([{k: v for k, v in it.items() if k != "_id"} for it in items]):
            ids = [it["_id"] for it in items[pos:pos + len(batch)]]
            pos += len(batch)
            name = f"fix-{n:03d}-{model}.json"
            text = tr.dump_batch(batch)
            (outdir / name).write_text(text, encoding="utf-8")
            (outdir / f"fix-{n:03d}-{model}.ids.json").write_text(json.dumps(ids, indent=0), encoding="utf-8")
            manifest.append({
                "file": str((outdir / name).relative_to(io.REPO)),
                "out": str((outdir / f"fix-{n:03d}-{model}.out.json").relative_to(io.REPO)),
                "model": model, "items": len(batch),
                "words": sum(len(it["msgid"].split()) for it in batch),
                "tokens": round(tr.estimate_tokens(text)),
                "page": rel,
                "flagged": sum(1 for it in batch if "review" in it),
                "note": fx["note"],
            })
            n += 1
    (outdir / "manifest-fix.json").write_text(json.dumps({
        "locale": locale,
        "task": "fix",
        "instructions": str((outdir / "instructions-fix.md").relative_to(io.REPO)),
        "instructions_text": fix_instructions(locale),
        "batches": manifest}, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {"pages": len(fixes) - len(missing), "items": n_items, "flagged": n_flagged,
               "unmatched_examples": unmatched, "batches": len(manifest), "missing_pages": missing}
    print(f"{locale}: {summary['pages']} page(s), {n_items} entries in {len(manifest)} batch(es), "
          f"{n_flagged} entries pinned to a reviewer example, {unmatched} example(s) not matched "
          f"(the page note still travels with every batch)")
    for rel in missing:
        print(f"WARNING no PO for {rel}: skipped")
    print(f"manifest: {(outdir / 'manifest-fix.json').relative_to(io.REPO)}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--fixes", help="fix spec or review records JSON (required with --prepare)")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--model", default="sonnet", choices=("sonnet", "opus", "haiku"))
    ap.add_argument("--note", default=None,
                    help="provenance comment written on every changed entry "
                         "(default: 'doq: fixed after review <today>')")
    a = ap.parse_args()
    if a.locale not in io.MAIN_LOCALES:
        ap.error(f"unknown locale {a.locale}")
    if a.prepare:
        if not a.fixes:
            ap.error("--prepare needs --fixes")
        prepare(a.locale, load_fixes(Path(a.fixes)), a.model)
        return 0
    if a.apply:
        note = a.note or f"doq: fixed after review {date.today().isoformat()}"
        return tr.apply(a.locale, prefix="fix", note=note)
    ap.error("choose --prepare or --apply")
    return 2


if __name__ == "__main__":
    sys.exit(main())
