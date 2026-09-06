#!/usr/bin/env python3
"""Fill the untranslated and fuzzy entries of a locale's PO files.

    python3 translation/v2/translate.py --locale de --sweep
    python3 translation/v2/translate.py --locale de --prepare
    python3 translation/v2/translate.py --locale de --apply

--sweep runs check.py over every translated, non-fuzzy entry of the locale
and empties the ones that fail (msgstr cleared, a translator comment says
why), so the next update.py lists them for retranslation. Needed once per
locale bootstrapped before adopt() applied the full checker (#477: all but
de): the Thai sweep found 193 of 26,509 entries, 150 of them positional
bootstrap pairs whose $$ block sat in the neighbouring entry, which the
render passed and the MDX compile then failed on. Run it again after any
tightening of check.py.

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

The model tiers are written as batches under work/<locale>/: at most 120
items (the 64k output cap), at most BATCH_WORDS of English (the Write of
the translations must finish inside the prompt cache's lifetime; a 30k-token
Write did not, and its final turn re-sent 60k tokens fresh) and at most
BATCH_TOKENS as the agent's Read tool will present the file (line-numbered; the tool refuses files above
25k tokens, and an agent that then reads in slices costs ten times a clean
one: the first Thai run spent 0.6 to 0.8 M tokens on each of three such
batches). A batch costs ~40k tokens of fixed agent overhead whatever its
size, so batches are as large as the cap allows. manifest.json lists file,
output file, model and size.

Batch items carry only what a translator needs and nothing it does not:
msgid; type when it is not plain text; for a real fuzzy match (similarity
>= 0.6) the previous translation and a word diff of the English change
instead of the whole previous English. No id (a sidecar .ids.json keeps
the order), no empty msgstr placeholder, no page context, one item per
line: JSON structure and line numbers cost more tokens than the English
itself, so a batch of 120 items reads at about 60% of the earlier format.

The agent writes its translations as a JSON list of strings, in order, to
the batch's .out.json. --apply pairs them positionally with the ids (a
count mismatch rejects the whole batch), runs check.py on each, writes
accepted ones into the PO, and lists rejections. Older shapes, a list of
{id, msgstr} in the .out.json or in the batch file itself, are still read.

Cost, measured on the German run: an agent that reads the batch, checks
things and re-reads before writing spent about 150k tokens per 4,000 words;
one that reads once and writes once spends about a fifth of that. The
workflow in .claude/workflows/translate-locale.js enforces the latter.
"""

from __future__ import annotations

import argparse
import difflib
import itertools
import json
import re
import sys
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402
from check import _code_spans, check_entry  # noqa: E402

BATCH_ITEMS = 120
BATCH_WORDS = 4000        # ~20k output tokens: a 30k-token Write outlived the prompt cache (residual th batch: final turn re-sent 60k fresh)
BATCH_TOKENS = 18000      # the Read tool refuses 25k; the estimate was within 6% on 21 old-format batches but up to 20% under on the compact format (2 measured)
PREV_MIN = 0.6            # fuzzy similarity from which the previous translation is worth showing
HAIKU_MIN = 0.9           # near-identical English: the cheap model applies the change
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
  `<per sub-job overhead>`, and even when the code looks wrong, such as
  `PassManagers` or `batch.details() method`), URLs, image paths, JSX/HTML
  tags and every attribute other than title=, heading anchors like
  {{#some-anchor}}, MDX comments {{/* ... */}}.
- Backticked code spans must be copied EXACTLY as in the English, never
  translated, never merged with surrounding text, and none may be added:
  the checker rejects the whole entry if the set of backtick spans differs
  at all from the source.
- Math: keep every $...$ span and every $$...$$ block exactly, including the
  number of $$ delimiters (an entry may start or end inside a block; copy
  that part unchanged). Only words inside \\text{{...}} may be translated.
- Keep these terms in English: Qiskit, Qubit, Gate, Circuit, Backend,
  Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum, QPU.
- An item without `type` is plain text. A `type` of "Title ##" is a
  heading: translate the text, keep the anchor. A `type` starting with
  "Yaml Front Matter" is page metadata: plain text.
- A JSX tag item with title="...": translate only the title value.
- `prev_msgstr`, when present, is the {lang} of an earlier version of this
  msgid and `changes` shows how the English changed since, as
  [-removed-]{{+added+}} with a few words of context: reuse the previous
  wording and apply exactly those changes (renamed products, changed
  numbers, added or removed clauses). If the changes show a different
  sentence altogether, translate afresh.
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


def word_changes(old: str, new: str, context: int = 2) -> str:
    """The English change as [-removed-]{+added+} hunks with a few words of
    context, joined by ' … '. Shorter than the whole previous English and
    exactly what the translator is asked to apply."""
    a, b = old.split(), new.split()
    hunks = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        before = " ".join(a[max(0, i1 - context):i1])
        after = " ".join(a[i2:i2 + context])
        mid = ""
        if i2 > i1:
            mid += "[-" + " ".join(a[i1:i2]) + "-]"
        if j2 > j1:
            mid += "{+" + " ".join(b[j1:j2]) + "+}"
        hunks.append(" ".join(x for x in (before, mid, after) if x))
    return " … ".join(hunks)


def estimate_tokens(text: str) -> float:
    """Tokens the model sees for a file the Read tool presents line-numbered.
    Fitted (non-negative least squares) on 21 batches of the first Thai run
    whose Read cost was recorded: within 6% on every one. Non-ASCII script
    weight is a guess on the safe side; the fit had too few points to pin it."""
    numbered = "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(text.split("\n")))
    words = len(re.findall(r"[A-Za-z]+", numbered))
    digit_runs = len(re.findall(r"\d+", numbered))
    symbols = sum(1 for c in numbered if ord(c) < 128 and not c.isalnum() and not c.isspace())
    non_ascii = sum(1 for c in numbered if ord(c) >= 128)
    return 1.62 * words + 7.1 * digit_runs + 0.99 * symbols + 0.5 * non_ascii


def dump_batch(items: list[dict]) -> str:
    """One item per line: the Read tool numbers every line, and each number
    costs more than the whitespace pretty-printing would save."""
    return "[\n" + ",\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n]\n"


def split_batches(items: list[dict], max_items: int = BATCH_ITEMS, max_tokens: float = BATCH_TOKENS,
                  max_words: int = BATCH_WORDS) -> list[list[dict]]:
    """Greedy, order-preserving. The token cap is on the batch file as
    written by dump_batch, one numbered line per item, so it holds whatever
    the items carry (the estimate is linear, so it is summed per line). The
    word cap bounds the output side: the Write of a batch's translations
    must finish inside the prompt cache's lifetime, or the final turn
    re-sends the whole context fresh."""
    batches: list[list[dict]] = []
    batch: list[dict] = []
    total = 0.0
    words = 0
    for it in items:
        cost = estimate_tokens(json.dumps(it, ensure_ascii=False) + ",")
        n_words = len(it["msgid"].split())
        if batch and (len(batch) >= max_items or total + cost > max_tokens or words + n_words > max_words):
            batches.append(batch)
            batch, total, words = [], 0.0, 0
        batch.append(it)
        total += cost
        words += n_words
    if batch:
        batches.append(batch)
    return batches


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


ATTR_RE = re.compile(r'\b([A-Za-z][\w:-]*)="([^"\n]*)"')
CLOSE_TAGS_RE = re.compile(r"^(?:\s*</[A-Za-z][\w.]*>)+\s*")


def _attr_transfer(prev_msgid: str, msgid: str, prev_msgstr: str) -> str | None:
    """The English changed only attribute values of JSX/HTML tags (the Card
    hrefs of guides/addons moving to docs.quantum.ibm.com: 3 entries in
    every locale, and the agents kept reusing the old href from the hint).
    The same substitutions on the previous translation. title= is
    translated text and disqualifies the entry."""
    if ATTR_RE.sub(r'\1=""', prev_msgid) != ATTR_RE.sub(r'\1=""', msgid):
        return None
    old, new = ATTR_RE.findall(prev_msgid), ATTR_RE.findall(msgid)
    cand, changed = prev_msgstr, False
    for (on, ov), (nn, nv) in zip(old, new):
        if on != nn:
            return None
        if ov == nv:
            continue
        if on == "title" or f'{on}="{ov}"' not in cand:
            return None
        cand = cand.replace(f'{on}="{ov}"', f'{on}="{nv}"', 1)
        changed = True
    return cand if changed else None


def _leading_close_tags_transfer(prev_msgid: str, msgid: str, prev_msgstr: str) -> str | None:
    """po4a merges a JSX closing tag with the paragraph after it when no
    blank line separates them; when the English gains that blank line the
    tags leave the entry (guides/execute-dynamic-circuits, one entry per
    locale). Drop the same tags from the front of the previous translation."""
    m = CLOSE_TAGS_RE.match(prev_msgid)
    if not m or _norm(prev_msgid[m.end():]) != _norm(msgid):
        return None
    m2 = CLOSE_TAGS_RE.match(prev_msgstr)
    if not m2 or re.findall(r"</[\w.]+>", m.group(0)) != re.findall(r"</[\w.]+>", m2.group(0)):
        return None
    return prev_msgstr[m2.end():]


def mechanical_transfer(prev_msgid: str, msgid: str, prev_msgstr: str) -> str | None:
    """When the English changed only in punctuation placement, in the
    emphasis markers around a leading phrase, in tag attribute values, or by
    losing a leading run of closing tags, apply the same edit to the
    previous translation. Returns None for any other change, or when the
    result fails the checker."""
    if not prev_msgstr.strip():
        return None
    for rule in (_attr_transfer, _leading_close_tags_transfer):
        cand = rule(prev_msgid, msgid, prev_msgstr)
        if cand is not None and not check_entry(msgid, cand):
            return cand
    if _norm(prev_msgid) != _norm(msgid):
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


def match_trailing_newline(msgid: str, msgstr: str) -> str:
    """gettext requires msgid and msgstr to agree on a trailing newline;
    po4a refuses the whole file otherwise (one French page, 2026-09-05:
    the agent ended a translation with a newline the source did not have)."""
    if msgid.endswith("\n") and not msgstr.endswith("\n"):
        return msgstr + "\n"
    if not msgid.endswith("\n"):
        return msgstr.rstrip("\n")
    return msgstr


CODE_SPAN_RE = re.compile(r"^(`+)(.*)\1$", re.S)
CODE_SPAN_STRIP_RE = re.compile(r"`+[^`\n]*`+")


def _span_inner(span: str) -> str:
    m = CODE_SPAN_RE.match(span)
    return m.group(2) if m else span


def repair_code_spans(msgid: str, msgstr: str) -> tuple[str, list[str]]:
    """Two agent habits the checker rejects, undone deterministically before
    the check (seen on the same entries in every locale). An agent tidies a
    code span the English left odd — `RuntimeJobV2 ` with its trailing
    space, the upstream typo `[NoiseLearnerV3` — so a span in the
    translation that equals a missing source span up to whitespace and
    brackets is replaced by the source span. And an agent backticks a bare
    product name — qiskit-ibm-runtime, Executor, SabreLayout — so a span
    the source lacks, whose text appears bare in the source, loses its
    backticks. A translated span (`第二量子化`) matches neither rule and
    stays rejected. Returns (msgstr, notes); the caller keeps the result
    only when it then passes the checker."""
    src, dst = _code_spans(msgid), _code_spans(msgstr)
    extra = dst - src
    if not extra:
        return msgstr, []
    # unfiltered: `RuntimeJobV2 ` ends in a space, so the checker's prose
    # filter drops it from the source side, yet it is exactly what has to
    # be restored when the agent wrote `RuntimeJobV2`. Keys are normalised
    # to single backticks; the literal spans are what gets edited.
    missing = _code_spans(msgid, prose_filter=False) - dst
    literal_src = list(_code_spans(msgid, prose_filter=False, raw=True))
    bare = CODE_SPAN_STRIP_RE.sub(" ", msgid)
    notes = []

    def norm(raw: str) -> str:
        return "`" + _span_inner(raw) + "`"

    for raw, count in _code_spans(msgstr, raw=True).items():
        if norm(raw) not in extra:
            continue
        inner = _span_inner(raw)
        key = inner.strip().strip("[]")
        targets = {m for m in missing if _span_inner(m).strip().strip("[]") == key}
        if len(targets) == 1:
            target = targets.pop()
            target_raw = next((s for s in literal_src if norm(s) == target), target)
            for _ in range(min(count, missing[target])):
                msgstr = msgstr.replace(raw, target_raw, 1)
                missing[target] -= 1
            notes.append(f"{raw!r} restored to {target_raw!r}")
        elif inner.strip() and inner.strip() in bare:
            for _ in range(count):
                msgstr = msgstr.replace(raw, inner, 1)
            notes.append(f"backticks dropped around {inner!r}")
    return msgstr, notes


DATA_URI_RE = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")
DATA_URI_PLACEHOLDER = "data:DOQ-BASE64-{}"
DATA_URI_PLACEHOLDER_RE = re.compile(r"data:DOQ-BASE64-(\d+)")


def shrink_data_uris(text: str) -> str:
    """A base64 inline image (two bullets of guides/primitives carry a 60 and
    a 130 KB one) is replaced by a numbered placeholder in what the model
    reads; expand_data_uris puts the original back from the msgid on apply.
    Before this, each was a one-item batch the Read tool refused (est.
    143k tokens) and had to be filled by hand."""
    n = itertools.count()
    return DATA_URI_RE.sub(lambda m: DATA_URI_PLACEHOLDER.format(next(n)), text)


def expand_data_uris(msgid: str, msgstr: str) -> str:
    blobs = DATA_URI_RE.findall(msgid)
    return DATA_URI_PLACEHOLDER_RE.sub(
        lambda m: blobs[int(m.group(1))] if int(m.group(1)) < len(blobs) else m.group(0), msgstr)


def _write_direct(locale: str, direct: dict[str, list[tuple[int, str, str]]]) -> int:
    n = 0
    for page, fills in direct.items():
        po_file = io.po_path(locale, page)
        po = polib.pofile(str(po_file), wrapwidth=0)
        for idx, msgstr, note in fills:
            e = po[idx]
            e.msgstr = match_trailing_newline(e.msgid, msgstr)
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
        if sim >= HAIKU_MIN:
            cand = mechanical_transfer(it["previous_msgid"], it["msgid"], it.get("previous_msgstr", ""))
            if cand is not None:
                tiers["mechanical"].append(it)
                direct.setdefault(page, []).append((int(idx), cand, "doq: mechanical transfer from the previous translation"))
                continue
        slim = {"msgid": shrink_data_uris(it["msgid"])}
        if it["type"] != "Plain text":
            slim["type"] = it["type"]
        prev_ok = (sim >= PREV_MIN and it.get("previous_msgstr", "").strip()
                   # a previous translation that fails the checker against its own
                   # English (a translated code span, a lost URL) is not a hint: the
                   # agent reuses its wording and the same rejection repeats forever
                   and not check_entry(it["previous_msgid"], it["previous_msgstr"]))
        if prev_ok:
            slim["changes"] = word_changes(shrink_data_uris(it["previous_msgid"]), slim["msgid"])
            slim["prev_msgstr"] = shrink_data_uris(it["previous_msgstr"])
        slim["_id"] = it["id"]          # stripped before writing; kept in the .ids.json sidecar
        tiers["haiku" if prev_ok and sim >= HAIKU_MIN else "sonnet"].append(slim)

    n_direct = _write_direct(locale, direct)

    manifest: list[dict] = []
    n = 0
    for model in ("haiku", "sonnet"):
        pos = 0
        for batch in split_batches([{k: v for k, v in it.items() if k != "_id"} for it in tiers[model]]):
            ids = [it["_id"] for it in tiers[model][pos:pos + len(batch)]]
            pos += len(batch)
            name = f"batch-{n:03d}-{model}.json"
            text = dump_batch(batch)
            (outdir / name).write_text(text, encoding="utf-8")
            (outdir / f"batch-{n:03d}-{model}.ids.json").write_text(json.dumps(ids, indent=0), encoding="utf-8")
            words = sum(len(it["msgid"].split()) for it in batch)
            manifest.append({"file": str((outdir / name).relative_to(io.REPO)),
                             "out": str((outdir / f"batch-{n:03d}-{model}.out.json").relative_to(io.REPO)),
                             "model": model, "items": len(batch), "words": words,
                             "tokens": round(estimate_tokens(text))})
            n += 1
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

BATCH_NAME = re.compile(r"^batch-\d+-[a-z]+\.json$")


def repair_inner_quotes(text: str, limit: int = 50) -> tuple[str, int]:
    """Escape unescaped double quotes inside JSON strings, one at a time,
    guided by where the parser stops: at "Expecting ',' delimiter" the
    quote that closed the string too early is the last one before the
    error position. Seen from Haiku: Polish „warstwie" quotes, whole list
    on one line. Returns (text, quotes escaped)."""
    fixed = 0
    while fixed < limit:
        try:
            json.loads(text)
            return text, fixed
        except json.JSONDecodeError as exc:
            q = text.rfind('"', 0, exc.pos)
            if exc.msg.startswith("Expecting ',' delimiter"):
                pass
            elif exc.msg.startswith("Expecting value") and text[q + 1:exc.pos].strip() == ",":
                # the quote closed the string early right before a comma, so
                # the parser took the comma as a separator and then found
                # prose where a value should start: Romanian „…", ceea ce
                # (ro batches 001 and 003, whole list on one line)
                pass
            else:
                return text, fixed
            if q <= 0:
                return text, fixed
            text = text[:q] + '\\"' + text[q + 1:]
            fixed += 1
    return text, fixed


def parse_string_lines(text: str) -> tuple[list[str] | None, int]:
    """A JSON list of strings, one per line, as the agent is told to write
    it. When the file as a whole does not parse, first escape the inner
    quotes the parser trips on (repair_inner_quotes), then fall back to
    line-by-line decoding (each line one string). Both failures seen in
    practice are unescaped quotes inside a string.
    Returns (strings, repairs made) or (None, 0)."""
    try:
        res = json.loads(text)
        return (res, 0) if isinstance(res, list) and all(isinstance(r, str) for r in res) else (None, 0)
    except json.JSONDecodeError:
        pass
    repaired_text, n = repair_inner_quotes(text)
    if n:
        try:
            res = json.loads(repaired_text)
            if isinstance(res, list) and all(isinstance(r, str) for r in res):
                return res, n
        except json.JSONDecodeError:
            pass
    out, repaired = [], 0
    for line in text.splitlines():
        line = line.strip().rstrip(",").strip()
        if line in ("", "[", "]"):
            continue
        try:
            val = json.loads(line)
        except json.JSONDecodeError:
            if not (line.startswith('"') and line.endswith('"') and len(line) >= 2):
                return None, 0
            inner = re.sub(r'(?<!\\)"', r'\\"', line[1:-1])
            try:
                val = json.loads('"' + inner + '"')
            except json.JSONDecodeError:
                return None, 0
            repaired += 1
        if not isinstance(val, str):
            return None, 0
        out.append(val)
    return out, repaired


def read_results(bpath: Path) -> tuple[list[tuple[str, str]], str | None]:
    """(id, msgstr) pairs of one batch, or ([], reason) when the batch as a
    whole cannot be used. Accepts, in this order: <batch>.out.json as a list
    of strings paired positionally with <batch>.ids.json (a count mismatch
    rejects the batch: a dropped item would shift every later one);
    <batch>.out.json as a list of {id, msgstr}; the batch file itself
    filled in place with {id, msgstr} (the shape before .out.json)."""
    stem = bpath.name[:-len(".json")]
    out_path = bpath.with_name(stem + ".out.json")
    ids_path = bpath.with_name(stem + ".ids.json")
    try:
        items = json.loads(bpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:                # a truncated or mis-escaped in-place Write
        return [], f"invalid JSON: {exc}"
    if out_path.exists():
        text = out_path.read_text(encoding="utf-8")
        strings, repaired = parse_string_lines(text)
        if strings is not None:
            if repaired:
                print(f"NOTE {out_path.name}: {repaired} line(s) with unescaped quotes repaired")
            ids = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else [it.get("id") for it in items]
            if len(strings) != len(ids) or any(i is None for i in ids):
                return [], f"{len(strings)} translations for {len(ids)} items"
            return list(zip(ids, strings)), None
        try:
            res = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], f"invalid JSON in {out_path.name}: {exc}"
        if isinstance(res, list) and all(isinstance(r, dict) and "id" in r for r in res):
            return [(r["id"], r.get("msgstr", "")) for r in res], None
        return [], f"unrecognised content in {out_path.name}"
    if items and all(isinstance(it, dict) and "id" in it and "msgstr" in it for it in items):
        return [(it["id"], it["msgstr"]) for it in items], None
    return [], None                      # not filled yet


def sweep_po(po: polib.POFile, note: str) -> list[tuple[int, list[str]]]:
    """Empty every translated, non-fuzzy entry that fails check_entry; first
    repair a trailing-newline mismatch in place (gettext rejects the file
    otherwise). Returns (index, problems) of the entries changed."""
    emptied = []
    for i, e in enumerate(po):
        if e.obsolete or e.fuzzy or not e.msgstr:
            continue
        fixed = match_trailing_newline(e.msgid, e.msgstr)
        if fixed != e.msgstr:                      # deterministic repair, not a retranslation
            e.msgstr = fixed
            emptied.append((i, ["trailing newline repaired"]))
            continue
        problems = check_entry(e.msgid, e.msgstr)
        if problems:
            e.msgstr = ""
            e.previous_msgid = None
            e.tcomment = note
            emptied.append((i, problems))
    return emptied


def sweep(locale: str) -> int:
    from datetime import date
    note = f"doq: emptied {date.today().isoformat()}, previous translation failed check.py"
    n_checked = n_emptied = 0
    classes: dict[str, int] = {}
    root = io.po_path(locale, "index.mdx").parent
    for po_file in sorted(root.rglob("*.po")):
        po = polib.pofile(str(po_file), wrapwidth=0)
        n_checked += sum(1 for e in po if e.msgstr and not e.fuzzy and not e.obsolete)
        emptied = sweep_po(po, note)
        if emptied:
            po.save(str(po_file))
            n_emptied += len(emptied)
            for _, problems in emptied:
                for pr in problems:
                    classes[pr.split(":")[0]] = classes.get(pr.split(":")[0], 0) + 1
    print(f"{locale}: checked {n_checked} entries, emptied or repaired {n_emptied}")
    for k, v in sorted(classes.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")
    if n_emptied:
        print(f"next: update.py --locale {locale} --json translation/v2/work/worklist-{locale}.json, then --prepare")
    return 0


def apply(locale: str) -> int:
    outdir = io.WORK_DIR / locale
    accepted = rejected = skipped = 0
    by_page: dict[str, list[tuple[int, str]]] = {}
    cache: dict[str, polib.POFile] = {}
    for bpath in sorted(p for p in outdir.glob("batch-*.json") if BATCH_NAME.match(p.name)):
        pairs, reason = read_results(bpath)
        if reason:
            rejected += 1
            print(f"REJECT {bpath.name} (whole batch): {reason}")
            continue
        if not pairs:
            skipped += len(json.loads(bpath.read_text(encoding="utf-8")))
            continue
        for ident, msgstr in pairs:
            if not (msgstr or "").strip():
                skipped += 1
                continue
            page, idx = ident.rsplit("#", 1)
            if page not in cache:
                cache[page] = polib.pofile(str(io.po_path(locale, page)), wrapwidth=0)
            msgid = cache[page][int(idx)].msgid
            msgstr = expand_data_uris(msgid, msgstr)
            problems = check_entry(msgid, msgstr)
            if problems:
                repaired_str, notes = repair_code_spans(msgid, msgstr)
                if notes and not check_entry(msgid, repaired_str):
                    print(f"NOTE {ident}: {'; '.join(notes)}")
                    msgstr, problems = repaired_str, []
            if problems:
                rejected += 1
                print(f"REJECT {ident}: {'; '.join(problems)}")
                continue
            by_page.setdefault(page, []).append((int(idx), msgstr))
    for page, fills in by_page.items():
        po = cache[page]
        for idx, msgstr in fills:
            e = po[idx]
            e.msgstr = match_trailing_newline(e.msgid, msgstr)
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
    ap.add_argument("--sweep", action="store_true", help="empty translated entries that fail check.py")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--worklist", help="default translation/v2/work/worklist-<locale>.json")
    args = ap.parse_args()
    if not (args.prepare or args.apply or args.sweep):
        ap.error("--sweep, --prepare and/or --apply")
    rc = 0
    if args.sweep:
        sweep(args.locale)
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
