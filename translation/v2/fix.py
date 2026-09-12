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
# When a whole entry sits inside the reviewer's quote, the entry must make up
# at least this share of it. Below that the "containment" is a coincidence of
# common words, not a reference to that entry.
CONTAINS_MIN_SHARE = 0.5


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
  tags and every attribute EXCEPT the prose ones (title=, description=,
  alt=, linkText=), heading anchors like {{#some-anchor}}, MDX comments
  {{/* ... */}}, every $...$ and $$...$$ span.
- title=, description=, alt= and linkText= are the exception because they
  are prose the reader sees (video and image captions, Card descriptions
  and link labels): TRANSLATE them (a product name in a title= stays as it
  is). Never copy such an attribute out of the msgid in English — a
  translated caption replaced by the English one is a silent regression
  that no checker can catch, since these are the attributes not compared
  byte-for-byte.
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
    entry rather than the whole thing.

    The two containment directions are NOT symmetric. `q in target` — the
    reviewer quoted part of an entry — is the intended case and always wins.
    `target in q` — a whole entry sits inside the quote — is only meaningful
    when the entry makes up most of the quote; otherwise any short entry
    whose words happen to appear in a long quote hijacks the match. That is
    not hypothetical: a 300-character quote about density matrices, which
    contains the phrase "General formulation of quantum information", was
    pinned to a two-word heading entry "Quantum information", so the flag
    reached the wrong entry and the real defect was reported as fixed
    without being touched. `prepare` cannot notice — it counts examples that
    matched *something*, and this matched something."""
    # A reviewer who read the paired prose file (sample-deep-review.py writes
    # one per page, entries numbered by PO index) cites the number directly.
    # Trust it when the quoted English is in that entry — a wrong number is
    # worse than no pin, since apply would write the fix onto the wrong text.
    ent = example.get("entry")
    if isinstance(ent, int) and ent >= 0:
        for idx, e in entries:
            if idx == ent:
                q = _norm(example.get("source"))
                if not q or q[:40] in _norm(e.msgid) or difflib.SequenceMatcher(
                        None, q, _norm(e.msgid)[: max(len(q) * 2, 200)]).ratio() >= MATCH_MIN:
                    return idx
                break
    best: tuple[float, int | None] = (0.0, None)
    for quote, attr in ((example.get("source"), "msgid"), (example.get("translation"), "msgstr")):
        q = _norm(quote)
        if len(q) < 12:
            # Too short to match by containment or ratio ("Thus:" is inside
            # half the corpus), but a reviewer who quotes a short entry IN
            # FULL means that entry. Take it when exactly one entry equals
            # the quote; the pl vqe page had four such connectives left in
            # English that no example could reach otherwise.
            exact = [idx for idx, e in entries if _norm(getattr(e, attr)) == q]
            if len(exact) == 1:
                return exact[0]
            continue
        for idx, e in entries:
            target = _norm(getattr(e, attr))
            if not target:
                continue
            if q in target or (target in q and len(target) >= CONTAINS_MIN_SHARE * len(q)):
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
            "verdict": f.get("verdict") or "",
            "examples": [ex for ex in (f.get("examples") or []) if isinstance(ex, dict)],
        })
    return out


def _write_batches(outdir: Path, model: str, n: int, items: list[dict], page: str,
                   note: str, manifest: list[dict]) -> int:
    """Split `items` into batch files fix-NNN-<model>.json (+ .ids.json) and
    append their manifest rows; returns the next batch number."""
    pos = 0
    public = [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]
    for batch in tr.split_batches(public):
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
            "page": page,
            "flagged": sum(1 for it in batch if "review" in it),
            "note": note,
        })
        n += 1
    return n


WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
# A page smaller than this in targeted mode is packed with other small pages:
# an agent call has a fixed cost of ~15k tokens a turn, and a two-entry batch
# would spend it all on the prompt.
PACK_BELOW = 15
# Example types whose defect is page-wide by nature — the same wrong term or
# the wrong pronoun recurs — versus entry-local ones (a dropped qualifier).
SWEEP_TYPES = {"terminology", "register"}


def sweep_terms(examples: list[dict]) -> set[str]:
    """Words the reviewer's correction REMOVED from a quoted translation: the
    wrong rendering. Only from page-wide example types, and never a word the
    English also contains (a kept product name is not a defect)."""
    out: set[str] = set()
    for ex in examples:
        if (ex.get("type") or "").lower() not in SWEEP_TYPES or not ex.get("suggested"):
            continue
        bad = {w.lower() for w in WORD_RE.findall(ex.get("translation") or "")}
        bad -= {w.lower() for w in WORD_RE.findall(ex["suggested"])}
        bad -= {w.lower() for w in WORD_RE.findall(ex.get("source") or "")}
        out |= bad
    return out


def prepare(locale: str, fixes: list[dict], model: str = "sonnet",
            flagged_only: bool = False, mode: str | None = None) -> dict:
    """Build the fix batches.

    mode "page": every translated entry of a flagged page travels, so the
    fixer can repair drift it was not pointed at and must copy the rest back
    verbatim. Measured on th and id (2026-09-12): 1,056 / 972 accepted changes
    out of 19,972 / 16,637 entries sent — 93% of every batch was copied back,
    and the copying was 87% of the wave's output tokens.

    mode "targeted" (default): a page with a FAIL verdict still travels whole;
    any other page sends the pinned entries plus every entry that contains a
    word the reviewer's Terminology/Register corrections removed (the wrong
    term, the wrong pronoun — the defects that recur across a page). On th/id
    that is 27-41% of the entries and catches 73-90% of the changes the page
    mode made outside the pinned entries. Small pages are packed together.

    mode "flagged": the pinned entries alone, packed across pages: right when
    the defect is entry-local and the flags are many — the untranslated-prose
    wave had 2,031 entries on ~880 pages, which as whole pages is ~1,400
    batches and as flagged entries ~25. (`flagged_only=True` is this mode.)"""
    mode = "flagged" if flagged_only else (mode or "targeted")
    if mode not in ("page", "targeted", "flagged"):
        raise ValueError(f"unknown mode {mode!r}")
    flagged_only = mode == "flagged"
    outdir = io.WORK_DIR / locale
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("fix-*.json"):
        old.unlink()
    (outdir / "instructions-fix.md").write_text(fix_instructions(locale), encoding="utf-8")

    manifest: list[dict] = []
    n = 0
    n_items = n_flagged = n_swept = 0
    missing: list[str] = []
    unmatched = 0
    pending: list[dict] = []
    for fx in fixes:
        rel = fx["rel"]
        po_file = io.po_path(locale, rel)
        if not po_file.exists():
            missing.append(rel)
            continue
        po = polib.pofile(str(po_file), wrapwidth=0)
        translated = [(i, e) for i, e in enumerate(po)
                      if e.msgstr.strip() and not e.obsolete]
        # Copy-only entries (bare math, code, an image) are normally left out:
        # there is nothing for a translator to do with them. But their msgstr
        # can still be WRONG — a drifted entry may carry prose prepended to the
        # math it should hold, which check.py passes, since both sides then have
        # the same $$ blocks. Excluding them from matching as well as from the
        # batch meant a reviewer could flag an entry that no fix wave was
        # capable of reaching. Match against everything, and carry a copy-only
        # entry into the batch when — and only when — a reviewer pointed at it.
        entries = [(i, e) for i, e in translated if not tr.is_copy_only(e.msgid)]
        reviews: dict[int, list[str]] = {}
        for ex in fx["examples"]:
            idx = match_example(ex, translated)
            if idx is None:
                unmatched += 1
                continue
            reviews.setdefault(idx, []).append(_review_text(ex))
        whole = mode == "page" or (mode == "targeted" and fx.get("verdict") == "FAIL")
        by_index = dict(entries) if whole else {}
        swept: dict[int, str] = {}
        if mode == "targeted" and not whole:
            terms = sweep_terms(fx["examples"])
            for idx, e in entries:
                if idx in reviews:
                    continue
                for t in terms:
                    m = re.search(rf"\b{re.escape(t)}\b", e.msgstr, re.IGNORECASE)
                    if m:
                        swept[idx] = m.group(0)
                        by_index[idx] = e
                        break
        for idx in reviews:                      # a flagged copy-only entry joins the batch
            if idx not in by_index:
                by_index[idx] = po[idx]
        items = []
        for idx, e in sorted(by_index.items()):
            it = {"msgid": tr.shrink_data_uris(e.msgid), "prev_msgstr": tr.shrink_data_uris(e.msgstr)}
            t = _entry_type(e)
            if t != "Plain text":
                it["type"] = t
            if idx in reviews:
                it["review"] = " | ".join(r for r in reviews[idx] if r) or "flagged by the reviewer"
            elif idx in swept:
                it["review"] = (f"Not quoted by the reviewer, but it contains '{swept[idx]}', a rendering "
                                f"the reviewer corrected elsewhere on this page (see the page note): apply "
                                f"the same correction here if the defect recurs, otherwise copy prev_msgstr back verbatim.")
            it["_id"] = f"{rel}#{idx}"
            items.append(it)
        n_items += len(items)
        n_flagged += len(reviews)
        n_swept += len(swept)
        if mode == "targeted" and not whole and len(items) < PACK_BELOW:
            # A small targeted page shares a batch with other small pages;
            # each note is prefixed with its page so the fixer can tell them apart.
            for it in items:
                it["_note"] = f"[{rel}] {fx['note']}"
            pending.extend(items)
            continue
        if flagged_only:
            # Pinned entries from every page are packed together below: a
            # batch per page would cost a whole agent call for two entries.
            # apply() pairs each string with its id, so a batch may span pages.
            for it in items:
                it["_note"] = fx["note"]
            pending.extend(items)
            continue
        n = _write_batches(outdir, model, n, items, rel, fx["note"], manifest)
    if pending:
        # Packed across pages in page order, split into batches of ordinary
        # size; a batch's note is the notes of the pages it holds.
        pos = 0
        while pos < len(pending):
            chunk = pending[pos:pos + tr.BATCH_ITEMS]
            pos += len(chunk)
            notes = list(dict.fromkeys(it["_note"] for it in chunk))
            n = _write_batches(outdir, model, n, chunk, "(pinned entries across pages)",
                               " ".join(notes), manifest)
    (outdir / "manifest-fix.json").write_text(json.dumps({
        "locale": locale,
        "task": "fix",
        "instructions": str((outdir / "instructions-fix.md").relative_to(io.REPO)),
        "instructions_text": fix_instructions(locale),
        "batches": manifest}, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {"pages": len(fixes) - len(missing), "items": n_items, "flagged": n_flagged,
               "swept": n_swept, "mode": mode,
               "unmatched_examples": unmatched, "batches": len(manifest), "missing_pages": missing}
    print(f"{locale}: {summary['pages']} page(s), {n_items} entries in {len(manifest)} batch(es) [mode {mode}], "
          f"{n_flagged} entries pinned to a reviewer example"
          + (f", {n_swept} swept in for a term the reviewer corrected" if mode == "targeted" else "")
          + f", {unmatched} example(s) not matched (the page note still travels with every batch)")
    for rel in missing:
        print(f"WARNING no PO for {rel}: skipped")
    print(f"manifest: {(outdir / 'manifest-fix.json').relative_to(io.REPO)}")
    return summary



# ── deterministic glossary-leak pass ──────────────────────────────────────
# Ported from the v1 fix-glossary-leaks.py (deleted 2026-09-10: it wrote rendered
# pages, which are derived now). The determiner list is the v1 one; the
# transformation is reimplemented here because the v1 decapitalisation had no
# proper-noun or link-text guard (it turned "la fonction IBM Circuit" into
# "IBM circuit" and "[Qubit initialization]" — an English page title — into
# "[qubit initialization]"). Both were invisible to lint AND to check.py, since
# neither is a code span, URL, tag or math. The prose projection and the API
# identifier list still come from the read-only check-glossary-consistency.py.

# Determiners that, when preceding a leaked noun, mean the surrounding prose
# already carries the gender — so a bare noun swap is safe. (gender-agnostic set
# kept simple: we only swap the noun, not the determiner.)
SAFE_DETERMINERS = {
    # Spanish
    "un", "una", "unos", "unas", "el", "la", "los", "las", "del", "al",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    "nuestro", "nuestra", "nuestros", "nuestras", "cada", "esta", "dicha",
    "su", "sus", "mismo", "misma", "otro", "otra", "otros", "otras",
    "varios", "varias", "algún", "alguna", "ningún", "ninguna",
    # French
    "le", "les", "des", "une", "du", "au", "aux",
    "ce", "cet", "cette", "ces", "mon", "ton", "son", "notre", "votre", "leur",
    "mes", "tes", "ses", "nos", "vos", "leurs",
    "chaque", "aucun", "aucune", "plusieurs", "certains", "certaines",
    "de",
    # Italian
    "il", "lo", "gli", "i", "uno", "della", "dello", "delle", "degli",
    "questa", "questo", "queste", "questi", "quella", "quello", "ogni",
    "nostra", "nostro", "vostra", "vostro", "sua", "suo",
    # Portuguese
    "o", "os", "as", "um", "uns", "umas", "uma", "do", "da", "dos", "das",
    "no", "na", "nas", "este", "esta", "estes", "estas", "esse", "essa",
    "nosso", "nossa", "seu", "qualquer",
    # Ukrainian (articleless; demonstratives/quantifiers precede)
    "цей", "ця", "це", "ці", "той", "та", "те", "ті", "кожен", "кожна",
    "наш", "наша", "ваш", "ваша", "його", "її", "один", "одна", "одне",
    # Polish
    "ten", "ta", "to", "te", "ci", "tej", "tego", "tych", "każdy", "każda",
    "nasz", "nasza", "wasz", "jego", "jej", "jeden", "jedna", "jedno", "danej",
    # Czech
    "této", "tohoto", "těchto", "každý", "každá",
    "náš", "naše", "váš", "jeho", "její", "jeden", "jedna", "jedno", "dané",
    # Romanian (enclitic articles, but determiners precede)
    "niște", "acest", "această", "aceste", "acești", "acel",
    "fiecare", "nostru", "noastră", "vostru", "său",
    # Indonesian / Malay (no articles; demonstratives/quantifiers)
    "sebuah", "suatu", "setiap", "ini", "itu", "satu", "beberapa",
    # Arabic (no articles; definite article الـ attaches; prepositions + iDafa head nouns precede)
    # Definite article variants (the ـ lam connector appears separate before Latin words)
    "الـ", "لـ", "للـ", "والـ", "فالـ", "بالـ",
    # Common prepositions and quantifiers preceding technical English nouns
    "من", "في", "على", "إلى", "عن", "مع", "بعد", "قبل", "حول", "خلال",
    "كل", "بكل", "لكل", "وكل", "هذه", "هذا", "هذه", "تلك", "ذلك", "تلك",
    "بعض", "أي", "أحد", "كلا", "جميع", "مختلف", "معظم",
    # Common iDafa head-nouns (noun-of-X construct: safe to translate X)
    "عمق", "عدد", "تشغيل", "بناء", "توسيع", "أخطاء", "دقة", "أداء",
    "حالات", "نتائج", "مخطط", "مخططات", "تحليل", "تصميم", "إنشاء",
    "حجم", "نوع", "أنواع", "مجموعة", "قائمة", "عملية", "تنفيذ",
    "معلمات", "سمات", "خصائص", "مكونات", "بنية", "مستوى", "طبقة",
    "إخراج", "مدخل", "إدخال", "ناتج", "نموذج", "معيار", "مثال",
}


def _leak_rules():
    import importlib.util
    rel = Path(__file__).resolve().parent.parent / "scripts" / "check-glossary-consistency.py"
    spec = importlib.util.spec_from_file_location("_chk", rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return SAFE_DETERMINERS, m


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
    ap.add_argument("--mode", choices=("page", "targeted", "flagged"), default=None,
                    help="with --prepare: what travels per page. targeted (default): a FAIL page whole, "
                         "any other page its pinned entries plus the entries carrying a term the reviewer "
                         "corrected; page: every entry of every page; flagged: pinned entries only")
    ap.add_argument("--flagged-only", action="store_true",
                    help="with --prepare: same as --mode flagged")
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
        prepare(a.locale, load_fixes(Path(a.fixes)), a.model, a.flagged_only, mode=a.mode)
        return 0
    if a.apply:
        note = a.note or f"doq: fixed after review {date.today().isoformat()}"
        return tr.apply(a.locale, prefix="fix", note=note)
    ap.error("choose --prepare, --apply or --leaks")
    return 2


if __name__ == "__main__":
    sys.exit(main())
