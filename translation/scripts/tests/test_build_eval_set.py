"""`build-eval-set.py --extend`: the union of review rounds into one labelled set.

Only the pure merge is tested; `build()` itself needs git and PO files. What
matters about the merge is what it must NOT do: count a defect twice, keep an
entry as "faithful" after a later round repaired it, or lose the record of
which round (and which selection method) a row came from — the scorer in
test_completeness.py excludes sieve-selected rounds from recall on exactly
that record.
"""


def _row(file, msgid, **kw):
    return {"locale": "xx", "file": file, "msgid": msgid, **kw}


def _set(base, head, positives, negatives, sources=None):
    d = {"base": base, "head": head, "positives": positives, "negatives": negatives}
    if sources is not None:
        d["sources"] = sources
    return d


def test_positives_dedupe_on_file_msgid_and_defective_text(eval_set_builder):
    old = _set("b0", "h1", [_row("a.po", "S", defective="v0", repaired="v1", src="h1")], [])
    new = _set("h1", "h2", [
        _row("a.po", "S", defective="v0", repaired="v2", src="h2"),   # same defect, seen from a wider range
        _row("a.po", "S", defective="v1", repaired="v2", src="h2"),   # the FIRST repair was itself defective
    ], [], sources=[{"base": "h1", "head": "h2", "selection": "sieve"}])
    new["selection"] = "sieve"
    out = eval_set_builder.extend(old, new)
    assert [(p["defective"], p["src"]) for p in out["positives"]] == [("v0", "h1"), ("v1", "h2")]


def test_a_negative_repaired_in_a_later_round_is_no_longer_faithful(eval_set_builder):
    old = _set("b0", "h1", [], [_row("a.po", "S", msgstr="v0", src="h1"), _row("a.po", "T", msgstr="t0", src="h1")])
    new = _set("h1", "h2", [_row("a.po", "S", defective="v0", repaired="v1", src="h2")], [],
               sources=[{"base": "h1", "head": "h2", "selection": "independent"}])
    new["selection"] = "independent"
    out = eval_set_builder.extend(old, new)
    assert [n["msgid"] for n in out["negatives"]] == ["T"]
    assert [p["msgid"] for p in out["positives"]] == ["S"]


def test_sources_record_every_round_and_its_selection(eval_set_builder):
    # A set written before `sources` existed is a drift-round set: independent.
    old = _set("b0", "h1", [_row("a.po", "S", defective="v0", repaired="v1")], [])
    new = _set("h1", "h2", [], [], sources=[{"base": "h1", "head": "h2", "selection": "sieve"}])
    new["selection"] = "sieve"
    out = eval_set_builder.extend(old, new)
    assert out["sources"] == [
        {"base": "b0", "head": "h1", "selection": "independent"},
        {"base": "h1", "head": "h2", "selection": "sieve"},
    ]
    assert out["head"] == "h2" and out["base"] == "b0"
    # Extending again appends rather than rebuilding the list.
    third = _set("h2", "h3", [], [], sources=[{"base": "h2", "head": "h3", "selection": "independent"}])
    third["selection"] = "independent"
    assert len(eval_set_builder.extend(out, third)["sources"]) == 3
