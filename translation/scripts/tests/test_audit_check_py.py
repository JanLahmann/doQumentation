"""The corpus-wide check.py gate: exit 1 on any failing entry, 0 otherwise.

Thin wrapper, so the tests are thin too — they pin the two things that make
it a gate rather than a report: it walks every live entry, and its exit code
follows check.py's verdict.
"""

import polib


def _write_po(path, pairs):
    po = polib.POFile()
    po.metadata = {"Content-Type": "text/plain; charset=UTF-8"}
    for msgid, msgstr in pairs:
        po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    po.save(str(path))


def test_clean_corpus_exits_zero(audit_check_py, tmp_path, monkeypatch, capsys):
    (tmp_path / "xx" / "po").mkdir(parents=True)
    _write_po(tmp_path / "xx" / "po" / "a.po", [
        ("Run `foo` at [x](https://a.b).", "Führe `foo` unter [x](https://a.b) aus."),
        ("</AccordionItem>\n</Accordion>\n", "</AccordionItem>\n</Accordion>\n"),
    ])
    monkeypatch.setattr(audit_check_py, "I18N", tmp_path)
    assert audit_check_py.audit(["xx"]) == 0
    assert "0 failing" in capsys.readouterr().out


def test_a_dropped_tag_fails_the_gate_and_is_named(audit_check_py, tmp_path, monkeypatch, capsys):
    (tmp_path / "xx" / "po").mkdir(parents=True)
    _write_po(tmp_path / "xx" / "po" / "a.po", [
        ("Fine.", "Gut."),
        ("</AccordionItem>\n</Accordion>\n", "</AccordionItem>\n"),   # the real 87-entry class
    ])
    monkeypatch.setattr(audit_check_py, "I18N", tmp_path)
    assert audit_check_py.audit(["xx"]) == 1
    out = capsys.readouterr().out
    assert "FAIL xx a.po#1" in out
    assert "JSX tag mismatch" in out
    assert "fix.py" in out, "the failure message must point at the sanctioned repair path"


def test_untranslated_entries_are_skipped_not_failed(audit_check_py, tmp_path, monkeypatch):
    # An empty msgstr is not a structural defect; it is untranslated, which is
    # someone else's gate. check.py itself says "empty translation" — the
    # auditor must not turn every untranslated entry into a red CI.
    (tmp_path / "xx" / "po").mkdir(parents=True)
    _write_po(tmp_path / "xx" / "po" / "a.po", [("Source.", "")])
    monkeypatch.setattr(audit_check_py, "I18N", tmp_path)
    assert audit_check_py.audit(["xx"]) == 0
