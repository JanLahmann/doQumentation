"""Tests for the v2 pipeline. Run: python3 -m pytest translation/v2/tests -q

Needs po4a and gettext on PATH (brew install po4a gettext / apt install po4a
gettext) and the polib package. Tests that need them skip otherwise.
"""

from __future__ import annotations

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
