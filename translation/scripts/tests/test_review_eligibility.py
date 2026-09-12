"""Review eligibility comes from the PO files, not status.json (2026-09-10).

A page is reviewable when its PO exists, its rendered page is a real
translation of useful length, and no entry is mid-update; it is *unreviewed*
when its PO header carries no X-Doq-Review-Opus. The recorder writes that
header; FIXED records (repair rounds) never do.
"""

import json

import polib
import pytest

HEADER = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Language: xx\\n"
"X-Doq-Page: {rel}\\n"
{extra}
'''

ENTRY = '''
#. type: Plain text
msgid "{msgid}"
msgstr "{msgstr}"
'''


def _write_po(root, rel, entries, extra_header=""):
    p = root / "i18n" / "xx" / "po" / (rel[:-4] + ".po")
    p.parent.mkdir(parents=True, exist_ok=True)
    body = HEADER.format(rel=rel, extra=extra_header)
    for msgid, msgstr, fuzzy in entries:
        body += ("\n#, fuzzy" if fuzzy else "") + ENTRY.format(msgid=msgid, msgstr=msgstr)
    p.write_text(body, encoding="utf-8")
    return p


def _render(root, rel, lines, fallback=False):
    p = root / "i18n" / "xx" / "docusaurus-plugin-content-docs" / "current" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(f"line {i}" for i in range(lines))
    if fallback:
        text = "{/* doqumentation-untranslated-fallback */}\n" + text
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def corpus(tmp_path, sampler, monkeypatch):
    monkeypatch.setattr(sampler, "I18N_DIR", tmp_path / "i18n")
    monkeypatch.setattr(sampler, "REPO_ROOT", tmp_path)
    ok = [("Hello world", "Hallo Welt", False), ("Second paragraph here", "Zweiter Absatz hier", False)]
    _write_po(tmp_path, "guides/reviewed.mdx", ok, '"X-Doq-Review-Opus: PASS 2026-07-05\\n"')
    _write_po(tmp_path, "guides/fresh.mdx", ok, '"X-Doq-Review-Tier3: MINOR_ISSUES\\n"')
    _write_po(tmp_path, "guides/mid-update.mdx", ok + [("Changed English", "Alte Übersetzung", True)])
    _write_po(tmp_path, "guides/untranslated.mdx", ok + [("New English", "", False)])
    _write_po(tmp_path, "guides/stub.mdx", ok)
    _write_po(tmp_path, "guides/fallback.mdx", ok)
    _write_po(tmp_path, "guides/unrendered.mdx", ok)
    for rel in ("reviewed", "fresh", "mid-update", "untranslated"):
        _render(tmp_path, f"guides/{rel}.mdx", 60)
    _render(tmp_path, "guides/stub.mdx", 12)
    _render(tmp_path, "guides/fallback.mdx", 60, fallback=True)
    return tmp_path


def test_catalogue_reads_headers_and_pending_entries(sampler, corpus):
    cat = sampler.catalogue("xx")
    assert set(cat) == {f"guides/{n}.mdx" for n in
                        ("reviewed", "fresh", "mid-update", "untranslated", "stub", "fallback", "unrendered")}
    assert cat["guides/reviewed.mdx"]["verdict"] == "PASS"
    assert cat["guides/reviewed.mdx"]["reviewed"] == "2026-07-05"
    assert cat["guides/fresh.mdx"]["verdict"] is None
    assert cat["guides/fresh.mdx"]["tier3"] == "MINOR_ISSUES"
    assert cat["guides/mid-update.mdx"]["pending"] == 1
    assert cat["guides/untranslated.mdx"]["pending"] == 1
    assert cat["guides/unrendered.mdx"]["rendered"] is False
    assert cat["guides/fallback.mdx"]["fallback"] is True
    assert cat["guides/stub.mdx"]["lines"] == 12


def test_pool_excludes_reviewed_pending_stub_fallback_unrendered(sampler, corpus):
    cat = sampler.catalogue("xx")
    pool = sampler.build_pool({"xx": cat}, min_lines=40, exclude_reviewed=True)
    assert [r[0] for r in pool["xx"]] == ["guides/fresh.mdx"]
    # without --exclude-reviewed the reviewed page is back, nothing else changes
    pool = sampler.build_pool({"xx": cat}, min_lines=40, exclude_reviewed=False)
    assert sorted(r[0] for r in pool["xx"]) == ["guides/fresh.mdx", "guides/reviewed.mdx"]
    # the sample row carries the tier-3 verdict as context
    sample = sampler.draw(pool, per_locale=5, seed=1)
    by = {r["rel"]: r for r in sample}
    assert by["guides/fresh.mdx"]["tier3_verdict"] == "MINOR_ISSUES"


def test_missing_locale_is_an_empty_catalogue(sampler, corpus):
    assert sampler.catalogue("zz") == {}


def test_record_opus_writes_header_and_skips_repairs(recorder, sampler, corpus, monkeypatch, capsys):
    monkeypatch.setattr(recorder, "I18N_DIR", corpus / "i18n")
    records = corpus / "round.json"
    records.write_text(json.dumps([
        {"locale": "xx", "file": "guides/fresh.mdx", "verdict": "MINOR_ISSUES", "issues": 2},
        {"locale": "xx", "file": "guides/stub.mdx", "verdict": "FIXED"},
        {"locale": "xx", "file": "guides/reviewed.mdx", "verdict": "FAIL"},
        {"locale": "yy", "file": "guides/fresh.mdx", "verdict": "PASS"},
        {"locale": "xx", "file": "guides/nope.mdx", "verdict": "PASS"},
    ]), encoding="utf-8")
    counts = recorder.record_opus_from_json(str(records), only_locale="xx", when="2026-09-10")
    assert counts == {"written": 2, "skipped": 1, "refused": 1, "no-po": 1, "invalid": 0}
    cat = sampler.catalogue("xx")
    assert cat["guides/fresh.mdx"]["verdict"] == "MINOR_ISSUES"
    assert cat["guides/fresh.mdx"]["reviewed"] == "2026-09-10"
    assert cat["guides/reviewed.mdx"]["verdict"] == "FAIL"        # a new read overwrites
    assert cat["guides/stub.mdx"]["verdict"] is None              # FIXED is not a page read
    # the header write leaves the entries byte-identical
    po = polib.pofile(str(corpus / "i18n/xx/po/guides/fresh.po"))
    assert [e.msgstr for e in po] == ["Hallo Welt", "Zweiter Absatz hier"]


def test_contributing_status_counts_from_catalogue(contributing_status, sampler, corpus):
    cats = {"xx": sampler.catalogue("xx")}
    assert contributing_status.reviewed_counts(cats) == {"xx": (1, 5)}   # reviewed, fresh, mid-update, untranslated, stub (no length cutoff)
    assert contributing_status.rendered_counts(cats) == {"xx": 6}


# ── delta review: entries a model wrote since the verdict ──────────────────

def _po_with(root, rel, entries, header=""):
    return _write_po(root, rel, entries, header)


def _stamp(root, rel, idx, comment):
    p = root / "i18n" / "xx" / "po" / (rel[:-4] + ".po")
    po = polib.pofile(str(p), wrapwidth=0)
    po[idx].tcomment = comment
    po.save(str(p))


def test_catalogue_lists_unverified_entries_and_delta_mode(sampler, corpus):
    # reviewed on 2026-07-05; one entry fixed after that, one fixed and already verified
    _stamp(corpus, "guides/reviewed.mdx", 0, "doq: fixed after review 2026-09-01")
    _stamp(corpus, "guides/reviewed.mdx", 1, "doq: fixed after review 2026-08-01 · verified 2026-08-15")
    cat = sampler.catalogue("xx")
    r = cat["guides/reviewed.mdx"]
    assert [u["index"] for u in r["unverified"]] == [0]
    assert r["unverified"][0]["since"] == "2026-09-01"
    assert sampler.review_mode(r, 1, exclude_reviewed=True) == "delta"
    assert sampler.review_mode(cat["guides/fresh.mdx"], 1, exclude_reviewed=True) == "full"
    # a sync retranslation stamp counts too
    _stamp(corpus, "guides/reviewed.mdx", 0, "doq: translated after an English change 2026-09-10")
    assert sampler.catalogue("xx")["guides/reviewed.mdx"]["unverified"][0]["since"] == "2026-09-10"


def test_pool_and_draw_carry_delta_entries(sampler, corpus):
    _stamp(corpus, "guides/reviewed.mdx", 0, "doq: fixed after review 2026-09-01")
    cat = sampler.catalogue("xx")
    pool = sampler.build_pool({"xx": cat}, min_lines=1, exclude_reviewed=True)
    rows = {r[0]: r for r in pool["xx"]}
    assert rows["guides/reviewed.mdx"][4] == "delta" and rows["guides/fresh.mdx"][4] == "full"
    sample = sampler.draw(pool, per_locale=10, seed=1)
    by = {r["rel"]: r for r in sample}
    assert by["guides/reviewed.mdx"]["mode"] == "delta"
    assert by["guides/reviewed.mdx"]["delta_entries"] == [
        {"index": 0, "since": "2026-09-01", "en": "Hello world", "tr": "Hallo Welt"}]
    assert by["guides/fresh.mdx"]["mode"] == "full" and "delta_entries" not in by["guides/fresh.mdx"]
    # the stub is in the pool now: no 40-line cutoff
    assert "guides/stub.mdx" in rows


def test_recording_a_verdict_verifies_entries_written_before_it(recorder, sampler, corpus, monkeypatch):
    monkeypatch.setattr(recorder, "I18N_DIR", corpus / "i18n")
    _stamp(corpus, "guides/fresh.mdx", 0, "doq: fixed after review 2026-09-01")      # before the read
    _stamp(corpus, "guides/fresh.mdx", 1, "doq: fixed after review 2026-09-10")      # the round's own repair, same day
    assert recorder.record_verdict("xx", "guides/fresh.mdx", "MINOR_ISSUES", "2026-09-10") == "written"
    po = polib.pofile(str(corpus / "i18n/xx/po/guides/fresh.po"))
    assert po[0].tcomment == "doq: fixed after review 2026-09-01 · verified 2026-09-10"
    assert po[1].tcomment == "doq: fixed after review 2026-09-10"                     # still pending
    cat = sampler.catalogue("xx")
    assert [u["index"] for u in cat["guides/fresh.mdx"]["unverified"]] == [1]
    assert sampler.review_mode(cat["guides/fresh.mdx"], 1, exclude_reviewed=True) == "delta"


def test_write_pair_numbers_prose_entries_and_skips_code(sampler, corpus, tmp_path):
    """The reviewer reads one paired file instead of two full pages: every
    prose entry numbered by PO index, EN then translation, no code."""
    _write_po(corpus, "guides/pair.mdx", [
        ("Intro sentence.", "Satz eins.", False),
        ("```python\\nx = 1\\n```", "```python\\nx = 1\\n```", False),
        ("Second sentence.", "Satz zwei.", False),
    ])
    path, n, words = sampler.write_pair("xx", "guides/pair.mdx")
    text = path.read_text()
    assert path == tmp_path / "translation" / "v2" / "work" / "review" / "xx" / "guides" / "pair.md"
    assert n == 2 and words == 4
    assert "[0]\nEN: Intro sentence.\nXX: Satz eins." in text and "[2]\nEN: Second sentence." in text
    assert "x = 1" not in text


def test_collect_opus_run_reads_journals_and_adds_the_mode(tmp_path):
    import subprocess, sys
    from pathlib import Path
    root = tmp_path / "projects" / "p" / "s" / "subagents" / "workflows" / "wf_1"
    root.mkdir(parents=True)
    lines = [json.dumps({"type": "started", "key": "k"}),
             json.dumps({"type": "result", "result": {"locale": "xx", "file": "a.mdx", "verdict": "PASS", "editor_note": "n"}}),
             json.dumps({"type": "result", "result": {"locale": "xx", "file": "a.mdx", "verdict": "FAIL", "editor_note": "later wins"}}),
             json.dumps({"type": "result", "result": "not a record"})]
    (root / "journal.jsonl").write_text("\n".join(lines))
    sample = tmp_path / "s.json"
    sample.write_text(json.dumps({"files": [{"rel": "a.mdx", "mode": "delta", "delta_entries": [{"index": 4}]}]}))
    out = tmp_path / "out.json"
    script = Path(__file__).resolve().parent.parent / "collect-opus-run.py"
    r = subprocess.run([sys.executable, str(script), "--run", "wf_1", "--sample", str(sample), "--out", str(out),
                        "--journal-root", str(tmp_path / "projects")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    recs = json.loads(out.read_text())
    assert len(recs) == 1 and recs[0]["verdict"] == "FAIL" and recs[0]["delta_indices"] == [4]
