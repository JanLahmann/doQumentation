"""Tests for the v2 pipeline. Run: python3 -m pytest translation/v2/tests -q

Needs po4a and gettext on PATH (brew install po4a gettext / apt install po4a
gettext) and the polib package. Tests that need them skip otherwise.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import po4a_io as io  # noqa: E402
from check import check_entry  # noqa: E402

needs_po4a = pytest.mark.skipif(shutil.which("po4a-translate") is None or shutil.which("msgmerge") is None,
                                reason="po4a / gettext not installed")

SAMPLE_PAGES = [
    "index.mdx",
    "guides/hello-world.mdx",
    "guides/get-started-with-estimator.mdx",          # :::note[Title] with a fence inside
    "learning/courses/quantum-machine-learning/introduction.mdx",
]


def test_check_entry_accepts_faithful_translation():
    assert check_entry("Run `foo` at [x](https://a.b) with $E$.", "Führe `foo` unter [x](https://a.b) mit $E$ aus.") == []


def test_check_entry_compares_fence_lines_by_content():
    opener = "    ```python\n    from x import y\n"
    assert check_entry(opener, opener) == []
    # A msgstr carrying the neighbouring entry's bare closing fence has the
    # same fence-line count but breaks the rendered fence structure.
    assert any("code fence line" in p for p in check_entry(opener, "    code = 1\n    ```\n"))


def test_code_spans_follow_backtick_runs():
    # A double-backtick span no longer pairs its second backtick with the
    # next single-backtick span: the sentence can be reordered in translation.
    en = "**Note:** The ``observables`` kwarg to `partition_problem` is of type `PauliList`. Phases are ignored.\n"
    ja = "**注:** `partition_problem` の ``observables`` kwarg は `PauliList` 型です。位相は無視されます。\n"
    assert check_entry(en, ja) == []
    assert any("inline code" in p for p in check_entry(en, ja.replace("`PauliList`", "PauliList")))
    # inline triple-backtick spans, and a bare URL inside a code span whose
    # closing backtick must not be captured as part of the URL
    assert check_entry("Use ```qc.h()```, then ```qc.measure()```\n", "Utilise ```qc.h()```, puis ```qc.measure()```\n") == []
    en_url = "Specify `qiskit==git+https://github.com/Qiskit/qiskit.git@main` as appropriate.\n"
    assert check_entry(en_url, "필요에 따라 `qiskit==git+https://github.com/Qiskit/qiskit.git@main`을 지정합니다.\n") == []


def test_bare_url_sheds_trailing_punctuation_of_any_script():
    en = "See https://quantum.ibm.com, then continue.\n"
    assert check_entry(en, "راجع https://quantum.ibm.com، ثم تابع.\n") == []          # Arabic comma
    assert check_entry(en, "参照 https://quantum.ibm.com。その後続行。\n") == []          # CJK full stop
    assert any("URL" in p for p in check_entry(en, "See https://quantum.ibm.com/x, then.\n"))


def test_check_entry_rejects_lost_invariants():
    assert any("inline code" in p for p in check_entry("Run `foo`.", "Führe foo aus."))
    assert any("URL" in p for p in check_entry("See [x](https://a.b).", "Siehe [x](https://a.c)."))
    assert any("anchor" in p for p in check_entry("Setup {#setup}", "Einrichtung"))
    assert any("JSX" in p for p in check_entry('<Admonition type="note" title="Hi">', '<Hinweis type="note" title="Hallo">'))
    assert check_entry("Anything", "") == ["empty translation"]


def test_check_entry_rejects_stray_empty_anchor():
    msgid = "$\\sqrt{\\text{NOT}}$ {#sqrttextnot}"
    assert check_entry(msgid, "$\\sqrt{\\text{NOT}}$ {#sqrttextnot}") == []
    assert any("heading anchor" in p for p in check_entry(msgid, "$\\sqrt{\\text{NOT}}$ {#} {#sqrttextnot}"))


def test_check_entry_length_rules_understand_space_less_scripts():
    en = "The IBM Quantum primitives workflow requires circuits and observables to be transformed to only use instructions supported by the QPU."
    th = "ขั้นตอนการทำงานของ IBM Quantum primitives ต้องการให้ Circuit และ observable ถูกแปลงให้ใช้เฉพาะคำสั่งที่รองรับโดย QPU"
    ja = "IBM Quantum プリミティブのワークフローでは、回路とオブザーバブルを QPU がサポートする命令のみを使う形に変換する必要があります。"
    assert check_entry(en, th) == []
    assert check_entry(en, ja) == []
    # a real fragment is still caught
    assert any("shorter" in p for p in check_entry(en, "ต้องการ"))
    assert any("shorter" in p for p in check_entry(en, "auf."))


def test_pre_rules_are_idempotent_and_reversible():
    src = "---\ntitle: T\n---\n\n## Example\n\ntext\n## Example\n:::note[Hi there]\n\nbody\n```python\nx\n```json\n\n:::\n"
    once = io.pre_source(src)
    assert io.pre_source(once) == once
    assert "## Example {#example}" in once and "## Example {#example-1}" in once
    assert '<DoqAdmonition type="note" title="Hi there">' in once and "</DoqAdmonition>" in once
    assert "```json" not in once                       # rule 4: closing fence made bare
    back = io.post_render(once)
    assert ":::note[Hi there]" in back and back.count(":::") == 2


def test_marker_round_trip():
    text = "---\ntitle: T\n---\n\nbody\n"
    stamped = io.add_marker(text, "deadbeef")
    assert "doqumentation-source-hash: deadbeef" in stamped
    assert io.strip_marker(stamped).strip() == text.strip()


@needs_po4a
@pytest.mark.parametrize("rel", SAMPLE_PAGES)
def test_identity_render_equals_source(rel):
    if not (io.DOCS / rel).exists():
        pytest.skip("page not in this checkout")
    pot = io.extract(rel, write=False)
    with tempfile.NamedTemporaryFile(suffix=".po", delete=False) as tmp:
        pot.save(tmp.name)
    rendered = io.render(rel, Path(tmp.name), with_marker=False)
    Path(tmp.name).unlink()
    assert io.same_page(rendered, (io.DOCS / rel).read_text(encoding="utf-8"))
    assert not any(io.is_code_entry(e) for e in pot)


@needs_po4a
def test_bootstrap_from_existing_translation_round_trips():
    rel = "index.mdx"
    tr = io.tr_path("de", rel)
    if not io.is_genuine(tr):
        pytest.skip("no German index in this checkout")
    po = io.gettextize(rel, tr)
    assert all(e.msgstr for e in po if io.translatable(e))
    with tempfile.NamedTemporaryFile(suffix=".po", delete=False) as tmp:
        po.save(tmp.name)
    rendered = io.render(rel, Path(tmp.name))
    Path(tmp.name).unlink()
    assert io.same_page(rendered, tr.read_text(encoding="utf-8"))
    assert "doqumentation-source-hash: " + io.en_hash(rel) in rendered


@needs_po4a
def test_msgmerge_marks_changed_english_fuzzy_and_keeps_previous():
    import polib
    rel = "index.mdx"
    pot = io.extract(rel, write=False)
    target = next(e for e in pot if io.entry_type(e) == "Plain text")
    po = polib.POFile()
    po.metadata = dict(pot.metadata)
    for e in pot:
        po.append(polib.POEntry(msgid=e.msgid, msgstr="X " + e.msgid, comment=e.comment))
    old_msgid = target.msgid
    target.msgid = old_msgid.rstrip("\n") + " (changed)\n"
    d = Path(tempfile.mkdtemp())
    po.save(str(d / "p.po"))
    pot.save(str(d / "p.pot"))
    io.msgmerge(d / "p.po", d / "p.pot")
    merged = polib.pofile(str(d / "p.po"))
    e = next(x for x in merged if x.msgid == target.msgid)
    assert e.fuzzy and e.previous_msgid == old_msgid
    assert sum(1 for x in merged if x.obsolete) == 0
    shutil.rmtree(d)


# ---------------------------------------------------------------------------
# translate.py: batch shape and sizing
# ---------------------------------------------------------------------------

def test_word_changes_shows_only_the_edit_with_context():
    from translate import word_changes
    old = "Run the job on the IBM Quantum Platform with three shots and check the result."
    new = "Run the job on IBM Quantum with four shots and check the result."
    d = word_changes(old, new)
    assert "[-the-]" in d and "[-three-]{+four+}" in d
    assert "check the result" not in d          # unchanged tail is not repeated
    assert word_changes("same text", "same text") == ""


def test_estimate_tokens_counts_structure_and_scripts():
    from translate import estimate_tokens
    prose = "the quick brown fox jumps over the lazy dog " * 50
    assert 1.5 * 450 < estimate_tokens(prose) < 2.2 * 450
    assert estimate_tokens('{"msgid": "' + prose + '"}') > estimate_tokens(prose)
    thai = "ควอนตัม" * 100
    assert estimate_tokens(thai) == pytest.approx(0.5 * 700 + 7.1)   # script chars + the one line number
    assert estimate_tokens(prose + "\n" + prose) > 2 * estimate_tokens(prose) - 1  # a second line adds its number


def test_split_batches_respects_token_and_item_caps():
    from translate import split_batches, estimate_tokens, dump_batch
    items = [{"msgid": f"Sentence number {i} with some words in it. " * 8} for i in range(400)]
    batches = split_batches(items, max_items=120, max_tokens=4000)
    assert [it for b in batches for it in b] == items
    assert all(len(b) <= 120 for b in batches)
    assert all(estimate_tokens(dump_batch(b)) <= 4000 * 1.05 for b in batches)
    assert all(estimate_tokens(dump_batch(b + [items[0]])) > 4000 for b in batches[:-1])   # greedy: no room left
    heavy = [{"msgid": "x", "prev_msgstr": "ควอนตัม" * 4000, "changes": "[-a-]{+b+}"} for _ in range(5)]
    assert all(len(b) == 1 for b in split_batches(heavy, max_tokens=3000))
    wordy = [{"msgid": "word " * 1500} for _ in range(6)]                      # 1,500 words each, few tokens per word
    assert [len(b) for b in split_batches(wordy, max_tokens=10**6, max_words=4000)] == [2, 2, 2]


def test_read_results_positional_and_legacy_shapes():
    import json
    from translate import read_results
    d = Path(tempfile.mkdtemp())
    b = d / "batch-000-sonnet.json"
    b.write_text(json.dumps([{"msgid": "One"}, {"msgid": "Two"}]), encoding="utf-8")
    (d / "batch-000-sonnet.ids.json").write_text(json.dumps(["p.mdx#1", "p.mdx#2"]), encoding="utf-8")
    assert read_results(b) == ([], None)                                   # not filled yet
    out = d / "batch-000-sonnet.out.json"
    out.write_text(json.dumps(["Eins", "Zwei"], ensure_ascii=False), encoding="utf-8")
    assert read_results(b) == ([("p.mdx#1", "Eins"), ("p.mdx#2", "Zwei")], None)
    out.write_text(json.dumps(["Eins"]), encoding="utf-8")                # a dropped item rejects the batch
    pairs, reason = read_results(b)
    assert pairs == [] and "1 translations for 2 items" in reason
    out.write_text(json.dumps([{"id": "p.mdx#2", "msgstr": "Zwei"}]), encoding="utf-8")   # {id, msgstr} still read
    assert read_results(b) == ([("p.mdx#2", "Zwei")], None)
    out.unlink()
    b.write_text(json.dumps([{"id": "p.mdx#1", "msgstr": "Eins"}]), encoding="utf-8")     # filled in place (old runs)
    assert read_results(b) == ([("p.mdx#1", "Eins")], None)
    shutil.rmtree(d)


def test_parse_string_lines_repairs_unescaped_quotes():
    from translate import parse_string_lines
    good = '[\n"Eins",\n"Zwei \\"zitiert\\""\n]\n'
    assert parse_string_lines(good) == (["Eins", 'Zwei "zitiert"'], 0)
    broken = '[\n"Eins",\n"ซึ่งถูก "box" box เหล่านี้",\n"Drei"\n]\n'      # what one agent actually wrote
    assert parse_string_lines(broken) == (["Eins", 'ซึ่งถูก "box" box เหล่านี้', "Drei"], 2)   # 2 quotes escaped
    one_line = '["Eins", "mówi się o „warstwie" bramek, które", "Drei \\"ok\\"", "x "y" z"]'   # Haiku: whole list on one line
    assert parse_string_lines(one_line) == (["Eins", 'mówi się o „warstwie" bramek, które', 'Drei "ok"', 'x "y" z'], 3)
    assert parse_string_lines('[{"id": "x", "msgstr": "y"}]') == (None, 0)   # not a list of strings
    assert parse_string_lines('[\n"Eins",\n{"a": 1}\n]') == (None, 0)


def test_prepare_writes_idless_one_line_batches(monkeypatch):
    import json
    import translate
    d = io.WORK_DIR / "_pytest"                 # manifest paths are repo-relative, so stay inside work/
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    monkeypatch.setattr(io, "WORK_DIR", d)
    monkeypatch.setattr(translate, "_write_direct", lambda locale, direct: 0)
    items = [{"id": f"guides/x.mdx#{i}", "type": "Plain text" if i % 3 else "Title ##",
              "msgid": f"Paragraph {i} explains how the transpiler maps a circuit onto the backend."} for i in range(7)]
    items[1].update({"previous_msgid": "Paragraph 1 explains how the transpiler maps a circuit onto hardware.",
                     "previous_msgstr": "ย่อหน้า 1 อธิบาย"})
    items[2].update({"msgid": "Call `run()` on the backend.", "previous_msgid": "Call `run()` on the device.",
                     "previous_msgstr": "Llama a `ejecutar()` en el dispositivo."})      # bad hint: code span translated
    wl = d / "worklist-zz.json"
    wl.write_text(json.dumps({"items": items}), encoding="utf-8")
    translate.prepare("zz", wl)
    manifest = json.loads((d / "zz" / "manifest.json").read_text(encoding="utf-8"))
    assert [b["model"] for b in manifest["batches"]] == ["haiku", "sonnet"]
    assert manifest["batches"][0]["items"] == 1 and manifest["batches"][1]["items"] == 6   # the bad-hint item went to sonnet
    for b in manifest["batches"]:
        text = (io.REPO / b["file"]).read_text(encoding="utf-8")
        rows = json.loads(text)
        assert text.count("\n") == len(rows) + 2 and b["items"] == len(rows)
        assert b["out"].endswith(".out.json") and b["tokens"] > 0
        ids = json.loads((io.REPO / b["file"]).with_name(Path(b["file"]).name[:-5] + ".ids.json").read_text())
        assert len(ids) == len(rows) and all("id" not in r and "msgstr" not in r for r in rows)
    haiku = json.loads((io.REPO / manifest["batches"][0]["file"]).read_text(encoding="utf-8"))
    assert haiku[0]["prev_msgstr"] == "ย่อหน้า 1 อธิบาย" and "[-hardware.-]{+the backend.+}" in haiku[0]["changes"]
    assert "prev_msgid" not in haiku[0]
    sonnet = json.loads((io.REPO / manifest["batches"][1]["file"]).read_text(encoding="utf-8"))
    assert [r.get("type") for r in sonnet] == ["Title ##", None, "Title ##", None, None, "Title ##"]
    assert not any("prev_msgstr" in r for r in sonnet)                                     # no hint from a failing pair
    shutil.rmtree(d)


def test_parse_string_lines_repairs_early_close_before_comma():
    from translate import parse_string_lines
    # Romanian „…" closed with a plain quote right before a comma: the parser
    # reports "Expecting value", not a delimiter error (ro batches 001, 003)
    one_line = '["Eins", "IBM implementează „pliere digitală", ceea ce înseamnă că", "Drei"]'
    assert parse_string_lines(one_line) == (["Eins", 'IBM implementează „pliere digitală", ceea ce înseamnă că', "Drei"], 1)


def test_repair_code_spans_restores_odd_source_spans_and_drops_added_backticks():
    from translate import repair_code_spans
    en = "Executes them as a single `RuntimeJobV2 ` object with `[NoiseLearnerV3`](/x) in qiskit-ibm-runtime.\n"
    tr = "Le ejecuta como un único objeto `RuntimeJobV2` con `NoiseLearnerV3`](/x) en `qiskit-ibm-runtime`.\n"
    fixed, notes = repair_code_spans(en, tr)
    assert fixed == "Le ejecuta como un único objeto `RuntimeJobV2 ` con `[NoiseLearnerV3`](/x) en qiskit-ibm-runtime.\n"
    assert len(notes) == 3 and check_entry(en, fixed) == []
    # a translated span matches neither rule and is left for the checker to reject
    en2 = "Called `second quantization` here.\n"
    fixed2, notes2 = repair_code_spans(en2, "Genannt `zweite Quantisierung` hier.\n")
    assert notes2 == [] and check_entry(en2, fixed2)
    assert repair_code_spans(en, "unchanged `RuntimeJobV2 ` and `[NoiseLearnerV3`](/x)\n") == ("unchanged `RuntimeJobV2 ` and `[NoiseLearnerV3`](/x)\n", [])


def test_data_uri_placeholders_round_trip():
    from translate import expand_data_uris, shrink_data_uris
    blob = "data:image/jpeg;base64," + "iVBORw0KGgo" * 40
    en = f'- `Sampler` primitive - returns a distribution. E.g.:\n<img width="500" src="{blob}"/>\n'
    slim = shrink_data_uris(en)
    assert blob not in slim and 'src="data:DOQ-BASE64-0"' in slim
    tr = slim.replace("returns a distribution. E.g.:", "mengembalikan distribusi. Contoh:")
    out = expand_data_uris(en, tr)
    assert blob in out and check_entry(en, out) == []


def test_mechanical_transfer_attribute_values_and_leading_close_tags():
    from translate import mechanical_transfer
    old = 'Depth tools.\n<Card\n  title="Operator backpropagation"\n  href="https://qiskit.github.io/qiskit-addon-obp/"\n  linkText="Browse"\n/>\n'
    new = old.replace("https://qiskit.github.io/qiskit-addon-obp/", "https://docs.quantum.ibm.com/addons/qiskit-addon-obp")
    prev = old.replace("Depth tools.", "Nástroje hloubky.").replace('title="Operator backpropagation"', 'title="Zpětná propagace"').replace("Browse", "Procházet")
    assert mechanical_transfer(old, new, prev) == prev.replace("https://qiskit.github.io/qiskit-addon-obp/", "https://docs.quantum.ibm.com/addons/qiskit-addon-obp")
    assert mechanical_transfer(old, old.replace('title="Operator backpropagation"', 'title="OBP"'), prev) is None   # title is translated text
    old2 = "</AccordionItem>\n</Accordion>\nDynamic circuits are powerful tools.\n"
    new2 = "Dynamic circuits are powerful tools.\n"
    prev2 = "</AccordionItem>\n</Accordion>\nCircuitele dinamice sunt instrumente puternice.\n"
    assert mechanical_transfer(old2, new2, prev2) == "Circuitele dinamice sunt instrumente puternice.\n"


def test_match_trailing_newline():
    from translate import match_trailing_newline
    assert match_trailing_newline("A.\n", "B.") == "B.\n"
    assert match_trailing_newline("A.", "B.\n") == "B."
    assert match_trailing_newline("A.\n", "B.\n") == "B.\n"
    assert match_trailing_newline("A.", "B.") == "B."


def test_sweep_po_empties_only_failing_entries():
    import polib
    from translate import sweep_po
    po = polib.POFile()
    po.append(polib.POEntry(msgid="Run `qc.draw()` now.\n", msgstr="Führe `qc.draw()` jetzt aus.\n"))
    po.append(polib.POEntry(msgid="Run `qc.draw()` now.\n", msgstr="Führe `qc.plot()` jetzt aus.\n"))       # code changed
    po.append(polib.POEntry(msgid="See $$x$$ here.\n", msgstr="Siehe hier.\n"))                               # math lost
    po.append(polib.POEntry(msgid="Fuzzy one.\n", msgstr="Wrong `x`.\n", flags=["fuzzy"]))                 # fuzzy: left alone
    po.append(polib.POEntry(msgid="Untranslated.\n", msgstr=""))
    po.append(polib.POEntry(msgid="No newline.", msgstr="Kein Zeilenumbruch.\n"))                 # repaired, not emptied
    emptied = sweep_po(po, "note")
    assert [i for i, _ in emptied] == [1, 2, 5] and po[5].msgstr == "Kein Zeilenumbruch."
    assert po[0].msgstr and not po[1].msgstr and not po[2].msgstr and po[3].msgstr == "Wrong `x`.\n"
    assert po[1].tcomment == "note" and "inline code mismatch" in emptied[0][1][0]


# ── fix.py: review fixes through the PO gate ──

def _fix_module():
    import importlib
    return importlib.import_module("fix")


def _make_po(path: Path, pairs: list[tuple[str, str]]) -> None:
    import polib
    po = polib.POFile(wrapwidth=0)
    po.metadata = {"Content-Type": "text/plain; charset=UTF-8", "Language": "de"}
    for msgid, msgstr in pairs:
        po.append(polib.POEntry(msgid=msgid, msgstr=msgstr, flags=["no-wrap"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    po.save(str(path))


@pytest.fixture
def fix_env(monkeypatch, tmp_path):
    """A throwaway i18n/ + work/ so fix.py and translate.apply touch nothing real."""
    import translate as tr
    fix = _fix_module()
    monkeypatch.setattr(io, "I18N", tmp_path / "i18n")
    monkeypatch.setattr(io, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(io, "REPO", tmp_path)
    pairs = [
        ("Get started with the noise learning helper.", "Einstieg in den Noise-Learning-Helfer."),
        ("The circuit is `transpiled` before it runs.", "Die Circuit wird `transpiled`, bevor sie läuft."),
        ("Run the cell.", "Führe die Zelle aus."),
        ("```python\nx = 1\n```", "```python\nx = 1\n```"),          # copy-only: never in a batch
    ]
    _make_po(io.po_path("de", "guides/noise.mdx"), pairs)
    return fix, tr, pairs


def test_fix_prepare_pins_examples_and_skips_code(fix_env):
    fix, tr, pairs = fix_env
    spec = [{"rel": "guides/noise.mdx", "note": "stiff term",
             "examples": [{"source": "circuit is transpiled before it runs",
                           "why": "calque", "suggested": "Der Schaltkreis"}]}]
    summary = fix.prepare("de", spec)
    assert summary["pages"] == 1 and summary["batches"] == 1
    assert summary["flagged"] == 1 and summary["unmatched_examples"] == 0
    manifest = json.loads((io.WORK_DIR / "de" / "manifest-fix.json").read_text())
    assert manifest["task"] == "fix"
    b = manifest["batches"][0]
    assert b["page"] == "guides/noise.mdx" and b["note"] == "stiff term" and b["flagged"] == 1
    items = json.loads(Path(io.REPO / b["file"]).read_text())
    assert len(items) == 3                                  # the code block stayed out
    assert all("prev_msgstr" in it for it in items)
    flagged = [it for it in items if "review" in it]
    assert len(flagged) == 1 and flagged[0]["msgid"].startswith("The circuit")
    assert "Suggested: Der Schaltkreis" in flagged[0]["review"]
    ids = json.loads(Path(io.REPO / b["file"].replace(".json", ".ids.json")).read_text())
    assert ids == ["guides/noise.mdx#0", "guides/noise.mdx#1", "guides/noise.mdx#2"]


def test_fix_load_accepts_review_records_and_drops_pass(tmp_path):
    fix = _fix_module()
    p = tmp_path / "opus.json"
    p.write_text(json.dumps([
        {"locale": "de", "file": "a.mdx", "verdict": "PASS", "editor_note": "fine", "examples": []},
        {"locale": "de", "file": "b.mdx", "verdict": "FAIL", "editor_note": "inverted", "examples": [{"source": "x"}]},
    ]))
    out = fix.load_fixes(p)
    assert [f["rel"] for f in out] == ["b.mdx"]
    assert out[0]["note"] == "inverted"


def test_fix_apply_writes_only_changed_entries_with_note(fix_env):
    import polib
    fix, tr, pairs = fix_env
    spec = [{"rel": "guides/noise.mdx", "note": "n", "examples": []}]
    fix.prepare("de", spec)
    b = json.loads((io.WORK_DIR / "de" / "manifest-fix.json").read_text())["batches"][0]
    items = json.loads(Path(io.REPO / b["file"]).read_text())
    out = [it["prev_msgstr"] for it in items]
    out[1] = "Der Schaltkreis wird `transpiled`, bevor er läuft."     # one real fix
    Path(io.REPO / b["out"]).write_text("[\n" + ",\n".join(json.dumps(s, ensure_ascii=False) for s in out) + "\n]\n")
    rc = tr.apply("de", prefix="fix", note="doq: fixed after review T")
    assert rc == 0
    po = polib.pofile(str(io.po_path("de", "guides/noise.mdx")))
    assert po[1].msgstr.startswith("Der Schaltkreis") and po[1].tcomment == "doq: fixed after review T"
    assert po[0].msgstr == pairs[0][1] and po[0].tcomment == ""       # untouched, not re-stamped
    assert po[2].msgstr == pairs[2][1] and po[2].tcomment == ""


def test_fix_apply_rejects_checker_violation(fix_env):
    import polib
    fix, tr, pairs = fix_env
    fix.prepare("de", [{"rel": "guides/noise.mdx", "note": "n", "examples": []}])
    b = json.loads((io.WORK_DIR / "de" / "manifest-fix.json").read_text())["batches"][0]
    items = json.loads(Path(io.REPO / b["file"]).read_text())
    out = [it["prev_msgstr"] for it in items]
    out[1] = "Der Schaltkreis wird transpiliert, bevor er läuft."      # dropped the code span
    Path(io.REPO / b["out"]).write_text(json.dumps(out, ensure_ascii=False))
    rc = tr.apply("de", prefix="fix", note="x")
    assert rc == 1
    po = polib.pofile(str(io.po_path("de", "guides/noise.mdx")))
    assert po[1].msgstr == pairs[1][1]                                  # rejected → unchanged


def _mark_fuzzy(page: str, idx: int, prev_msgid: str) -> None:
    import polib
    po = polib.pofile(str(io.po_path("de", page)), wrapwidth=0)
    po[idx].flags.append("fuzzy")
    po[idx].previous_msgid = prev_msgid
    po.save(str(io.po_path("de", page)))


def test_fix_apply_keeps_fuzzy_when_the_agent_copied_it_back(fix_env):
    """A fuzzy entry the fix agent did not touch must STAY fuzzy.

    fuzzy means msgmerge saw the English change and kept the old translation
    pending confirmation; po4a renders English until the flag clears. The
    review-fix prompt tells the agent to copy unflagged entries back verbatim,
    so an unchanged string is not a confirmation — clearing the flag would
    publish a translation of the PREVIOUS English."""
    import polib
    fix, tr, pairs = fix_env
    _mark_fuzzy("guides/noise.mdx", 2, "Run the cell twice.")
    fix.prepare("de", [{"rel": "guides/noise.mdx", "note": "n", "examples": []}])
    b = json.loads((io.WORK_DIR / "de" / "manifest-fix.json").read_text())["batches"][0]
    items = json.loads(Path(io.REPO / b["file"]).read_text())
    out = [it["prev_msgstr"] for it in items]                    # everything copied back verbatim
    Path(io.REPO / b["out"]).write_text(json.dumps(out, ensure_ascii=False))
    assert tr.apply("de", prefix="fix", note="x") == 0
    e = polib.pofile(str(io.po_path("de", "guides/noise.mdx")), wrapwidth=0)[2]
    assert "fuzzy" in e.flags and e.msgstr == pairs[2][1]


def test_fix_apply_clears_fuzzy_when_the_agent_retranslated_it(fix_env):
    """But a fuzzy entry the agent actually rewrote is confirmed, so it ships."""
    import polib
    fix, tr, pairs = fix_env
    _mark_fuzzy("guides/noise.mdx", 2, "Run the cell twice.")
    fix.prepare("de", [{"rel": "guides/noise.mdx", "note": "n", "examples": []}])
    b = json.loads((io.WORK_DIR / "de" / "manifest-fix.json").read_text())["batches"][0]
    items = json.loads(Path(io.REPO / b["file"]).read_text())
    out = [it["prev_msgstr"] for it in items]
    out[2] = "Führe die Zelle aus, dann prüfe das Ergebnis."
    Path(io.REPO / b["out"]).write_text(json.dumps(out, ensure_ascii=False))
    assert tr.apply("de", prefix="fix", note="x") == 0
    e = polib.pofile(str(io.po_path("de", "guides/noise.mdx")), wrapwidth=0)[2]
    assert "fuzzy" not in e.flags and e.msgstr.startswith("Führe die Zelle aus, dann")


def test_translate_apply_still_confirms_an_unchanged_fuzzy_entry(fix_env):
    """The translate path is the opposite case: there the agent was shown the
    entry and asked to translate it, so returning the same string confirms it."""
    import polib
    fix, tr, pairs = fix_env
    _mark_fuzzy("guides/noise.mdx", 2, "Run the cell twice.")
    d = io.WORK_DIR / "de"
    d.mkdir(parents=True, exist_ok=True)
    (d / "batch-000-sonnet.ids.json").write_text(json.dumps(["guides/noise.mdx#2"]))
    (d / "batch-000-sonnet.json").write_text(json.dumps([{"en": "Run the cell."}]))
    (d / "batch-000-sonnet.out.json").write_text(json.dumps([pairs[2][1]], ensure_ascii=False))
    assert tr.apply("de") == 0
    e = polib.pofile(str(io.po_path("de", "guides/noise.mdx")), wrapwidth=0)[2]
    assert "fuzzy" not in e.flags


def test_translate_apply_ignores_fix_batches(fix_env):
    """translate.py --apply must not pick up fix-* files and vice versa."""
    fix, tr, pairs = fix_env
    fix.prepare("de", [{"rel": "guides/noise.mdx", "note": "n", "examples": []}])
    b = json.loads((io.WORK_DIR / "de" / "manifest-fix.json").read_text())["batches"][0]
    items = json.loads(Path(io.REPO / b["file"]).read_text())
    out = [it["prev_msgstr"] for it in items]
    out[2] = "GEÄNDERT"
    Path(io.REPO / b["out"]).write_text(json.dumps(out, ensure_ascii=False))
    assert tr.apply("de") == 0                                          # default prefix: nothing to do
    import polib
    assert polib.pofile(str(io.po_path("de", "guides/noise.mdx")))[2].msgstr == pairs[2][1]
