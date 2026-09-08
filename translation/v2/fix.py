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



# ── deterministic glossary-leak pass (the PO port of
#    translation/scripts/fix-glossary-leaks.py, which wrote rendered pages) ──

def _leak_rules():
    """SAFE_DETERMINERS and the prose projection come from the v1 script; the
    transformation itself is reimplemented here because the v1 decapitalisation
    had no proper-noun or link-text guard (it turned "la fonction IBM Circuit"
    into "IBM circuit" and "[Qubit initialization]" — an English page title —
    into "[qubit initialization]"). Both were invisible to lint AND to check.py,
    since neither is a code span, URL, tag or math."""
    import importlib.util
    root = Path(__file__).resolve().parent.parent
    out = {}
    for key, rel in (("leak", "scripts/fix-glossary-leaks.py"),
                     ("chk", "scripts/check-glossary-consistency.py")):
        spec = importlib.util.spec_from_file_location(f"_{key}", root / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        out[key] = m
    return out["leak"].SAFE_DETERMINERS, out["chk"]


_LINK_TEXT = re.compile(r"\[[^\]]*\]")
_EMPHASIS = re.compile(r"\*\*[^*\n]+\*\*|\*[^*\n]+\*|_[^_\n]+_")


def _protected_spans(text: str) -> list[tuple[int, int]]:
    """Spans whose capitalisation belongs to something other than running prose,
    all observed as false positives on real fr content:

    - markdown link text — usually quotes an English page title verbatim;
    - emphasis — used here for cited lesson/section titles and UI labels
      (*Circuits quantiques*, **Fonctions de Circuit**);
    - markdown table rows and HTML <td>/<th> cells — header and label cells
      are capitalised by convention (`| Exemple | Qubits | Ansatz |`, and
      "menu deroulant Qubit" naming a UI control).
    """
    spans = [(m.start(), m.end()) for m in _LINK_TEXT.finditer(text)]
    spans += [(m.start(), m.end()) for m in _EMPHASIS.finditer(text)]
    pos = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("|") or "<td" in line or "<th" in line:
            spans.append((pos, pos + len(line)))   # table cell: a label, not prose
        pos += len(line)
    return spans


def _decapitalise(text: str, terms: list[str], determiners: set[str]) -> tuple[str, list[str]]:
    """Lowercase a wrongly-capitalised common noun, skipping: the start of the
    entry, the start of a sentence, markdown link text, and any position whose
    preceding word is itself capitalised (a proper name such as "IBM Circuit")."""
    hits: list[str] = []
    for kw in terms:
        cap = kw[0].upper() + kw[1:]

        def _sub(m, kw=kw):
            start = m.start()
            for a, b in _protected_spans(text):
                if a <= start < b:
                    return m.group(0)                        # inside link text
            prefix = text[:start].rstrip()
            if prefix == "" or prefix.endswith((".", ":", "!", "?", "\u2022", "-", ">", '"')):
                return m.group(0)                            # legitimate capital
            # Walk back to the last word character: stripping "(" off "(CLOPS"
            # used to leave an empty token and disable this guard, which let
            # "CLOPS (Circuit Layer Operations Per Second)" through.
            words = re.findall(r"[^\W\d_]+", prefix, re.UNICODE)
            prev = words[-1] if words else ""
            if prev and prev[0].isupper() and prev.lower() not in determiners:
                return m.group(0)                            # "IBM Circuit": a name
            after = re.match(r"\s+([^\W\d_]+)", text[m.end():], re.UNICODE)
            if after and after.group(1)[0].isupper():
                return m.group(0)                            # "Circuit CHSH", an expansion
            hits.append(f"{m.group(0)} -> {kw}{m.group(0)[len(kw):]}")
            return kw + m.group(0)[len(kw):]

        text = re.sub(rf"\b{re.escape(cap)}(s?)\b", _sub, text)
    return text, hits


def leak_fix_text(msgstr: str, glossary: dict, case_only: bool = False) -> tuple[str, list[str], int]:
    """Return (new_msgstr, applied, manual_count) for one PO entry."""
    determiners, chk = _leak_rules()
    prose = chk.to_prose(msgstr)
    if not prose.strip():
        return msgstr, [], 0                                  # nothing but code/math/tags
    new, hits = _decapitalise(msgstr, list(glossary.get("keep_lowercase", [])), determiners)
    manual = 0
    if not case_only:
        for _concept, spec in (glossary.get("translate") or {}).items():
            pref = spec["preferred"]
            for en in spec.get("leaked_en", []):
                if en.lower() in chk.API_IDENTIFIERS:
                    continue
                target = pref + ("s" if en.endswith("s") else "")

                def _sub(m, en=en, target=target):
                    nonlocal manual
                    start = m.start()
                    for a, b in _protected_spans(new):
                        if a <= start < b:
                            manual += 1
                            return m.group(0)
                    before = new[:start].rstrip().split()
                    prev = before[-1].lower().strip('"\u201c\u201d*_') if before else ""
                    if prev not in determiners:
                        manual += 1
                        return m.group(0)
                    if re.match(r'\s+(Hadamard|NOT|PHASE|CNOT|"|\u201c)', new[m.end():m.end() + 15]):
                        manual += 1
                        return m.group(0)
                    hits.append(f"{m.group(0)} -> {target}")
                    return target

                new = re.sub(rf"\b{re.escape(en)}\b", _sub, new)
    return new, hits, manual


def load_glossary(locale: str) -> dict | None:
    # Resolved per call: the glossary is DATA under io.REPO, which tests repoint.
    # Binding it at import time silently reads the real repo's glossary instead.
    p = io.REPO / "translation" / "glossary" / f"{locale}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def leaks(locale: str, dry_run: bool = True, note: str | None = None,
          case_only: bool = False) -> dict:
    """Apply the safe subset of glossary-leak fixes to the PO msgstrs.

    Deterministic: no model. Every changed entry still goes through check.py,
    so an edit that lands inside a code span, a URL, math or a tag is rejected
    rather than written. Fuzzy entries are skipped — their English has changed
    and they are not live until a translator confirms them.
    """
    glossary = load_glossary(locale)
    if glossary is None:
        print(f"No glossary for {locale} (translation/glossary/{locale}.json).", file=sys.stderr)
        return {"pages": 0, "applied": 0, "manual": 0, "rejected": 0}
    note = note or f"doq: glossary leak fixed {date.today().isoformat()}"
    applied = manual = rejected = pages = 0
    for po_path in sorted((io.I18N / locale / "po").rglob("*.po")):
        po = polib.pofile(str(po_path), wrapwidth=0)
        changed = False
        for e in po:
            if e.obsolete or not e.msgstr.strip() or "fuzzy" in e.flags:
                continue
            if tr.is_copy_only(e.msgid):
                continue
            if _entry_type(e).startswith("Title"):
                continue          # a heading: its capital is correct by definition
            new, got, man = leak_fix_text(e.msgstr, glossary, case_only=case_only)
            manual += man
            if new == e.msgstr or not got:
                continue
            problems = tr.check_entry(e.msgid, new)
            if problems:
                rejected += 1
                print(f"REJECT {po_path.name}: {'; '.join(problems)}")
                continue
            applied += len(got)
            if not dry_run:
                e.msgstr = new
                e.tcomment = note
            changed = True
            for h in got[:3]:
                print(f"  {'[dry] ' if dry_run else ''}{po_path.stem}: {h}")
        if changed:
            pages += 1
            if not dry_run:
                po.save(str(po_path))
    verb = "would apply" if dry_run else "applied"
    print(f"{locale}: {verb} {applied} fix(es) across {pages} page(s), "
          f"{manual} left for review, {rejected} rejected by check.py")
    return {"pages": pages, "applied": applied, "manual": manual, "rejected": rejected}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--fixes", help="fix spec or review records JSON (required with --prepare)")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--leaks", action="store_true",
                    help="deterministic glossary-leak pass over the PO msgstrs "
                         "(no model); writes only with --write")
    ap.add_argument("--write", action="store_true",
                    help="with --leaks: actually write (default is a dry run)")
    ap.add_argument("--case-only", action="store_true",
                    help="with --leaks: apply only the keep_lowercase "
                         "decapitalisations, skip the glossary translate rules")
    ap.add_argument("--model", default="sonnet", choices=("sonnet", "opus", "haiku"))
    ap.add_argument("--note", default=None,
                    help="provenance comment written on every changed entry "
                         "(default: 'doq: fixed after review <today>')")
    a = ap.parse_args()
    if a.locale not in io.MAIN_LOCALES:
        ap.error(f"unknown locale {a.locale}")
    if a.leaks:
        leaks(a.locale, dry_run=not a.write, note=a.note, case_only=a.case_only)
        return 0
    if a.prepare:
        if not a.fixes:
            ap.error("--prepare needs --fixes")
        prepare(a.locale, load_fixes(Path(a.fixes)), a.model)
        return 0
    if a.apply:
        note = a.note or f"doq: fixed after review {date.today().isoformat()}"
        return tr.apply(a.locale, prefix="fix", note=note)
    ap.error("choose --prepare, --apply or --leaks")
    return 2


if __name__ == "__main__":
    sys.exit(main())
