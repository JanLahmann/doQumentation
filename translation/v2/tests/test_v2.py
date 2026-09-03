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
