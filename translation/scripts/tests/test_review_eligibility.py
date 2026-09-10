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


def test_import_status_fills_only_missing_headers(recorder, sampler, corpus, monkeypatch):
    monkeypatch.setattr(recorder, "I18N_DIR", corpus / "i18n")
    st = corpus / "status.json"
    st.write_text(json.dumps({"xx": {
        "guides/fresh.mdx": {"review_opus": "PASS", "reviewed_opus": "2026-06-01"},
        "guides/reviewed.mdx": {"review_opus": "FAIL", "reviewed_opus": "2026-06-01"},   # header exists: kept
        "guides/stub.mdx": {"review": "PASS"},                                          # no opus verdict
        "guides/gone.mdx": {"review_opus": "PASS"},
    }, "reviews": {"legacy": {}}}), encoding="utf-8")
    monkeypatch.setattr(recorder, "STATUS_FILE", st)
    counts = recorder.import_status()
    assert counts == {"written": 1, "kept": 1, "no-po": 1}
    cat = sampler.catalogue("xx")
    assert cat["guides/fresh.mdx"]["verdict"] == "PASS"
    assert cat["guides/reviewed.mdx"]["verdict"] == "PASS"       # bootstrap copy kept


def test_contributing_status_counts_from_catalogue(contributing_status, sampler, corpus):
    cats = {"xx": sampler.catalogue("xx")}
    assert contributing_status.reviewed_counts(cats) == {"xx": (1, 4)}   # reviewed, fresh, mid-update, untranslated
    assert contributing_status.rendered_counts(cats) == {"xx": 6}
