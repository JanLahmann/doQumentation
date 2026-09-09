"""Tests for the completeness gauge (layer 2).

Two properties matter more than the rest and both are easy to lose in a
refactor:

- the batch a model sees must carry NO hint of which entries the sieve flagged,
  or the calibration sample stops measuring anything;
- a verdict list that does not line up with its batch must be realigned on the
  batch ordinal, or discarded — never zipped short, or every judgement after
  the gap is attributed to the wrong entry, a silent corruption that reads as a
  plausible finding.
"""

import json

import pytest


def _write_batch_pair(dirpath, n_ids, verdicts):
    ids = [{"id": f"i18n/xx/po/a.po#{i}", "flagged": i % 2 == 0} for i in range(n_ids)]
    (dirpath / "gauge-000-sonnet.ids.json").write_text(json.dumps(ids), encoding="utf-8")
    (dirpath / "gauge-000-sonnet.out.json").write_text(json.dumps(verdicts), encoding="utf-8")


# --------------------------------------------------------------------------
# batching


def test_split_batches_respects_the_item_cap(gauge):
    items = [{"msgid": "a", "msgstr": "b"} for _ in range(70)]
    batches = gauge.split_batches(items)
    assert all(len(b) <= gauge.BATCH_ITEMS for b in batches)
    assert sum(len(b) for b in batches) == 70


def test_split_batches_splits_on_size_too(gauge):
    big = {"msgid": "x" * 9000, "msgstr": "y" * 9000}
    batches = gauge.split_batches([big] * 4)
    assert len(batches) > 1, "a batch of very long entries must be split on size"


def test_split_batches_never_drops_an_item(gauge):
    items = [{"msgid": "x" * (i * 300), "msgstr": "y"} for i in range(40)]
    assert sum(len(b) for b in gauge.split_batches(items)) == len(items)


# --------------------------------------------------------------------------
# blindness


def test_the_batch_file_hides_which_entries_were_flagged(gauge, tmp_path, monkeypatch):
    """The whole point of the calibration sample. If a flag leaks into the
    batch the model sees, it will agree with the sieve and both the precision
    and the miss rate become meaningless."""
    monkeypatch.setattr(gauge, "GAUGE_WORK", tmp_path)
    monkeypatch.setattr(gauge, "po_files", lambda loc: [])

    items = [
        {"_id": "a.po#1", "_flagged": True, "msgid": "One.", "msgstr": "Eins."},
        {"_id": "a.po#2", "_flagged": False, "msgid": "Two.", "msgstr": "Zwei."},
    ]
    monkeypatch.setattr(gauge, "collect_items", lambda *a, **k: items)
    gauge.prepare("xx", None, 1, 0, "sonnet")

    batch = (tmp_path / "xx" / "gauge-000-sonnet.json").read_text(encoding="utf-8")
    assert "flagged" not in batch and "_id" not in batch
    for row in json.loads(batch):
        # "n" is an opaque ordinal for realigning verdicts; items are shuffled
        # before batching, so it carries no information about flag status.
        assert set(row) == {"n", "msgid", "msgstr"}


# --------------------------------------------------------------------------
# reading verdicts back


def test_a_short_verdict_list_discards_the_whole_batch(gauge, tmp_path):
    _write_batch_pair(tmp_path, 3, [{"verdict": "COMPLETE"}, {"verdict": "MISSING"}])
    rows, problems = gauge.read_verdicts(tmp_path)
    assert rows == []
    assert problems and "discarded" in problems[0]


def test_matching_lengths_are_joined_in_order(gauge, tmp_path):
    _write_batch_pair(tmp_path, 3, [
        {"verdict": "COMPLETE", "note": ""},
        {"verdict": "DIFFERENT", "note": "about the next paragraph"},
        {"verdict": "UNSURE", "note": ""},
    ])
    rows, problems = gauge.read_verdicts(tmp_path)
    assert problems == []
    assert [r["verdict"] for r in rows] == ["COMPLETE", "DIFFERENT", "UNSURE"]
    assert rows[1]["id"].endswith("#1")
    assert rows[1]["note"] == "about the next paragraph"


def test_a_bare_string_verdict_is_accepted(gauge, tmp_path):
    _write_batch_pair(tmp_path, 2, ["COMPLETE", "missing"])
    rows, _ = gauge.read_verdicts(tmp_path)
    assert [r["verdict"] for r in rows] == ["COMPLETE", "MISSING"]


def test_an_unknown_verdict_becomes_unsure_not_a_defect(gauge, tmp_path):
    # Guessing "DIFFERENT" from a malformed reply would invent review work.
    _write_batch_pair(tmp_path, 1, [{"verdict": "probably fine?"}])
    rows, _ = gauge.read_verdicts(tmp_path)
    assert rows[0]["verdict"] == "UNSURE"


def test_an_unparseable_out_file_is_reported_not_raised(gauge, tmp_path):
    (tmp_path / "gauge-000-sonnet.ids.json").write_text('[{"id": "a.po#0", "flagged": true}]')
    (tmp_path / "gauge-000-sonnet.out.json").write_text("not json at all")
    rows, problems = gauge.read_verdicts(tmp_path)
    assert rows == []
    assert problems and "unparseable" in problems[0]


def test_an_unfilled_batch_is_reported(gauge, tmp_path):
    (tmp_path / "gauge-000-sonnet.ids.json").write_text('[{"id": "a.po#0", "flagged": true}]')
    rows, problems = gauge.read_verdicts(tmp_path)
    assert rows == []
    assert problems and "not filled" in problems[0]


# --------------------------------------------------------------------------
# the gauge never writes a translation


def test_the_module_has_no_msgstr_write_path(gauge):
    """Hard rule: only translate.py --apply and fix.py write a msgstr. The
    gauge emits findings; a save() creeping in here would bypass check.py."""
    import inspect

    src = inspect.getsource(gauge)
    assert ".save(" not in src
    assert "msgstr =" not in src


@pytest.mark.parametrize("verdict", ["MISSING", "EXTRA", "DIFFERENT"])
def test_defective_verdicts_are_the_ones_that_become_fixes(gauge, verdict):
    assert verdict in gauge.DEFECTIVE


@pytest.mark.parametrize("verdict", ["COMPLETE", "UNSURE"])
def test_complete_and_unsure_never_become_fixes(gauge, verdict):
    assert verdict not in gauge.DEFECTIVE


# --------------------------------------------------------------------------
# ordinal realignment
#
# Three of the first seven real gauge batches returned N+1 objects: one extra
# COMPLETE, nothing marking which. Position alone cannot recover from that, so
# every batch item carries an opaque ordinal the verdict must echo.


def _pair_with_ordinals(dirpath, n_ids, verdicts):
    ids = [{"id": f"i18n/xx/po/a.po#{i}", "flagged": False} for i in range(n_ids)]
    (dirpath / "gauge-000-sonnet.ids.json").write_text(json.dumps(ids), encoding="utf-8")
    (dirpath / "gauge-000-sonnet.out.json").write_text(json.dumps(verdicts), encoding="utf-8")


def test_an_extra_object_is_realigned_not_discarded(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 3, [
        {"n": 0, "verdict": "COMPLETE"},
        {"n": 1, "verdict": "DIFFERENT", "note": "wrong paragraph"},
        {"verdict": "COMPLETE"},                       # the spurious extra
        {"n": 2, "verdict": "MISSING", "note": "lost a clause"},
    ])
    rows, problems = gauge.read_verdicts(tmp_path)
    assert [r["verdict"] for r in rows] == ["COMPLETE", "DIFFERENT", "MISSING"]
    assert any("realigned" in p for p in problems)


def test_out_of_order_verdicts_land_on_the_right_entries(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 3, [
        {"n": 2, "verdict": "MISSING"},
        {"n": 0, "verdict": "COMPLETE"},
        {"n": 1, "verdict": "EXTRA"},
    ])
    rows, _ = gauge.read_verdicts(tmp_path)
    got = {r["id"]: r["verdict"] for r in rows}
    assert got["i18n/xx/po/a.po#0"] == "COMPLETE"
    assert got["i18n/xx/po/a.po#1"] == "EXTRA"
    assert got["i18n/xx/po/a.po#2"] == "MISSING"


def test_a_missing_ordinal_skips_only_that_entry(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 3, [
        {"n": 0, "verdict": "COMPLETE"},
        {"n": 2, "verdict": "MISSING"},
        {"n": 3, "verdict": "COMPLETE"},   # out of range: no item 3
    ])
    rows, problems = gauge.read_verdicts(tmp_path)
    assert {r["id"].rsplit("#", 1)[1] for r in rows} == {"0", "2"}
    assert any("no verdict for item" in p for p in problems)


def test_the_batch_file_carries_the_ordinal(gauge, tmp_path, monkeypatch):
    monkeypatch.setattr(gauge, "GAUGE_WORK", tmp_path)
    monkeypatch.setattr(gauge, "po_files", lambda loc: [])
    items = [{"_id": f"a.po#{i}", "_flagged": False, "msgid": "x", "msgstr": "y"}
             for i in range(3)]
    monkeypatch.setattr(gauge, "collect_items", lambda *a, **k: items)
    gauge.prepare("xx", None, 1, 0, "sonnet")
    rows = json.loads((tmp_path / "xx" / "gauge-000-sonnet.json").read_text(encoding="utf-8"))
    assert [r["n"] for r in rows] == [0, 1, 2]
    assert all(set(r) == {"n", "msgid", "msgstr"} for r in rows), "still no flag leak"


def test_mismatched_length_without_ordinals_still_discards(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 3, [{"verdict": "COMPLETE"}, {"verdict": "COMPLETE"}])
    rows, problems = gauge.read_verdicts(tmp_path)
    assert rows == []
    assert any("discarded" in p for p in problems)


# --------------------------------------------------------------------------
# comma-less output
#
# "One object per line" in the prompt reliably produced a bracketed list of
# newline-separated objects with NO commas — 12 of 19 batches on the first real
# ro run. The judgements were fine; only the separators were missing, so they
# are recovered rather than thrown away.


def test_commaless_object_list_is_recovered(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 3, [])
    (tmp_path / "gauge-000-sonnet.out.json").write_text(
        '[\n{"n": 0, "verdict": "COMPLETE", "note": ""}\n'
        '{"n": 1, "verdict": "MISSING", "note": "lost a clause"}\n'
        '{"n": 2, "verdict": "COMPLETE", "note": ""}\n]\n',
        encoding="utf-8")
    rows, problems = gauge.read_verdicts(tmp_path)
    assert [r["verdict"] for r in rows] == ["COMPLETE", "MISSING", "COMPLETE"]
    assert problems == []


def test_trailing_commas_are_tolerated(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 2, [])
    (tmp_path / "gauge-000-sonnet.out.json").write_text(
        '[\n{"n": 0, "verdict": "COMPLETE"},\n{"n": 1, "verdict": "EXTRA"},\n]\n',
        encoding="utf-8")
    rows, _ = gauge.read_verdicts(tmp_path)
    assert [r["verdict"] for r in rows] == ["COMPLETE", "EXTRA"]


def test_genuine_garbage_is_still_reported(gauge, tmp_path):
    _pair_with_ordinals(tmp_path, 1, [])
    (tmp_path / "gauge-000-sonnet.out.json").write_text(
        "I could not complete this task.", encoding="utf-8")
    rows, problems = gauge.read_verdicts(tmp_path)
    assert rows == []
    assert problems and "unparseable" in problems[0]


# --------------------------------------------------------------------------
# gauge validation mode
#
# The sieve is scored against the labelled set directly. The gauge is a model,
# so it has to be asked — show it both the defective and the repaired msgstr of
# every labelled entry, unlabelled, and see what it says. Without this a
# calibration run reporting 0% defective is unreadable: clean locale, or a
# gauge that says COMPLETE to everything?


def test_eval_set_mode_presents_both_versions_unlabelled(gauge, tmp_path):
    import gzip

    path = tmp_path / "set.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump({"positives": [
            {"locale": "de", "file": "i18n/de/po/a.po", "msgid": "Source.",
             "defective": "Falsch.", "repaired": "Richtig."},
        ], "negatives": []}, fh)

    items = gauge.eval_set_items(path, None, 0)
    assert len(items) == 2
    assert {it["_truth"] for it in items} == {"defective", "faithful"}
    assert {it["msgstr"] for it in items} == {"Falsch.", "Richtig."}
    # the model sees neither the truth label nor the flag
    assert all(set(it) == {"_id", "_flagged", "_truth", "msgid", "msgstr"} for it in items)


def test_eval_set_mode_can_narrow_to_one_locale(gauge, tmp_path):
    import gzip

    path = tmp_path / "set.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump({"positives": [
            {"locale": "de", "file": "a.po", "msgid": "s", "defective": "x", "repaired": "y"},
            {"locale": "ro", "file": "b.po", "msgid": "s", "defective": "x", "repaired": "y"},
        ], "negatives": []}, fh)

    assert len(gauge.eval_set_items(path, "de", 0)) == 2
    assert len(gauge.eval_set_items(path, None, 0)) == 4


# --------------------------------------------------------------------------
# emit-fixes
#
# The last link in the chain: gauge verdicts -> a fix.py --fixes file. It broke
# on first use because a loop variable named `rel` shadowed the module's rel()
# helper, so nothing exercised the summary line until a real run hit it.


def test_emit_fixes_writes_a_fix_py_shaped_file(gauge, tmp_path, monkeypatch, capsys):
    po_dir = tmp_path / "i18n" / "xx" / "po"
    po_dir.mkdir(parents=True)
    (po_dir / "a.po").write_text(
        'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "The source sentence."\nmsgstr "Eine falsche Übersetzung."\n\n'
        'msgid "Another source sentence."\nmsgstr "Eine gute Übersetzung."\n',
        encoding="utf-8")

    work = tmp_path / "work"
    (work / "xx").mkdir(parents=True)
    (work / "xx" / "gauge-000-sonnet.ids.json").write_text(json.dumps([
        {"id": "i18n/xx/po/a.po#0", "flagged": True},
        {"id": "i18n/xx/po/a.po#1", "flagged": True},
    ]), encoding="utf-8")
    (work / "xx" / "gauge-000-sonnet.out.json").write_text(json.dumps([
        {"n": 0, "verdict": "DIFFERENT", "note": "about the next paragraph"},
        {"n": 1, "verdict": "COMPLETE", "note": ""},
    ]), encoding="utf-8")

    monkeypatch.setattr(gauge, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gauge, "GAUGE_WORK", work)

    out = tmp_path / "fixes.json"
    assert gauge.emit_fixes("xx", out) == 0          # must not raise
    fixes = json.loads(out.read_text(encoding="utf-8"))

    assert len(fixes) == 1
    assert set(fixes[0]) == {"rel", "note", "examples"}
    assert fixes[0]["rel"] == "a.mdx"
    # only the DIFFERENT entry becomes a finding; COMPLETE is left alone
    assert len(fixes[0]["examples"]) == 1
    ex = fixes[0]["examples"][0]
    assert set(ex) == {"source", "translation", "why"}
    assert ex["source"] == "The source sentence."
    assert ex["translation"] == "Eine falsche Übersetzung."
    assert "DIFFERENT" in ex["why"] and "next paragraph" in ex["why"]
