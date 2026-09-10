"""Unit tests and a scored regression for the completeness sieve.

The behaviour tests below pin what each subcheck means. The scored tests at the
bottom are the ones that matter: they replay `check-completeness.py` over the
labelled set `build-eval-set.py` extracts from the review branches and assert
floors on recall and ceilings on noise.

Without them a subcheck can be "tightened" into uselessness and every unit test
still passes — which is exactly how the title= check lost 5 of its 6 real hits
during development, to a copy-only guard that looked obviously correct.
"""

import gzip
import json

import pytest

from pathlib import Path

EVAL_SET = Path(__file__).resolve().parent.parent.parent / "eval" / "completeness-eval.json.gz"


def checks(mod, msgid, msgstr):
    return {f["check"] for f in mod.check_pair(msgid, msgstr)}


# --------------------------------------------------------------------------
# line-shape


def test_line_shape_flags_a_dropped_paragraph(completeness):
    msgid = "The ansatz is a variational circuit.\nIn this lesson you will learn\n- how to build one\n"
    msgstr = "Der Ansatz ist eine variationelle Schaltung.\n"
    assert "line-shape" in checks(completeness, msgid, msgstr)


def test_line_shape_ignores_trailing_blank_lines(completeness):
    assert "line-shape" not in checks(completeness, "One line.\n", "Eine Zeile.\n\n")


def test_line_shape_quiet_on_a_faithful_pair(completeness):
    assert checks(completeness, "A sentence about qubits.\n", "Ein Satz über Qubits.\n") == set()


# --------------------------------------------------------------------------
# numbers


def test_numbers_flags_a_lost_figure(completeness):
    assert "numbers" in checks(
        completeness, "IBM has deployed 20+ quantum computers.\n", "IBM hat Quantencomputer bereitgestellt.\n"
    )


def test_numbers_tolerates_locale_grouping(completeness):
    assert "numbers" not in checks(
        completeness, "a userbase of 600,000+\n", "eine Nutzerbasis von 600.000+\n"
    )


def test_numbers_normalises_eastern_digits(completeness):
    assert "numbers" not in checks(completeness, "3 qubits\n", "٣ كيوبت\n")


# --------------------------------------------------------------------------
# list-items


def test_list_items_flags_a_lost_bullet(completeness):
    msgid = "Goals:\n- one\n- two\n- three\n"
    msgstr = "Ziele:\n- eins\n- zwei\n"
    assert "list-items" in checks(completeness, msgid, msgstr)


# --------------------------------------------------------------------------
# title-untranslated
#
# This is the subcheck the copy-only guard silently broke. An entry that is
# nothing but a tag is byte-identical to its source EXACTLY when its caption
# was never translated, so the guard must not run before this check.


def test_title_flags_an_untranslated_caption(completeness):
    tag = '<IBMVideo id="1" title="Katie McCormick explores Bell\'s theorem using a real quantum computer."/>\n'
    assert "title-untranslated" in checks(completeness, tag, tag)


def test_title_covers_description_and_alt_captions(completeness):
    # de hello-world: the banner's description= sat in English while every
    # other locale had translated it; title= was the only attribute checked.
    en = '<OpenInLabBanner notebookPath="hello-world.ipynb" description="This tutorial was created for doQumentation." />\n'
    assert "title-untranslated" in checks(completeness, en, en)
    de = '<OpenInLabBanner notebookPath="hello-world.ipynb" description="Dieses Tutorial wurde für doQumentation erstellt." />\n'
    assert "title-untranslated" not in checks(completeness, en, de)
    img = '<img src="x.png" alt="The circuit after the second Hadamard gate" />'
    assert "title-untranslated" in checks(completeness, img, img)


def test_title_quiet_when_the_caption_is_translated(completeness):
    msgid = '<IBMVideo id="1" title="Katie McCormick explores Bell\'s theorem here."/>\n'
    msgstr = '<IBMVideo id="1" title="Katie McCormick erforscht hier das Bellsche Theorem."/>\n'
    assert "title-untranslated" not in checks(completeness, msgid, msgstr)


def test_title_ignores_short_labels(completeness):
    # "Answer" or a product name repeated verbatim is not evidence of anything.
    tag = '<AccordionItem title="Qiskit">\n'
    assert "title-untranslated" not in checks(completeness, tag, tag)


def test_copy_only_entry_is_not_prose_checked(completeness):
    # A proper name po4a hands over as prose is legitimately left in English;
    # the prose subchecks must stay silent rather than compare it to itself.
    assert checks(completeness, "IBM Quantum Network", "IBM Quantum Network") == set()


# --------------------------------------------------------------------------
# neighbour-duplicate (needs file context, so it goes through check_file)


def test_neighbour_duplicate_flags_a_copied_paragraph(completeness, tmp_path):
    shared = "Eine hinreichend lange übersetzte Passage, die zweimal auftaucht."
    po = tmp_path / "x.po"
    po.write_text(
        'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        f'msgid "First source paragraph."\nmsgstr "{shared}"\n\n'
        f'msgid "A different second source paragraph."\nmsgstr "{shared}"\n',
        encoding="utf-8",
    )
    found = {f["check"] for f in completeness.check_file(po)}
    assert "neighbour-duplicate" in found


def test_neighbour_duplicate_ignores_short_repeats(completeness, tmp_path):
    po = tmp_path / "y.po"
    po.write_text(
        'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Note"\nmsgstr "Hinweis"\n\n'
        'msgid "Note about something else"\nmsgstr "Hinweis"\n',
        encoding="utf-8",
    )
    found = {f["check"] for f in completeness.check_file(po)}
    assert "neighbour-duplicate" not in found


# --------------------------------------------------------------------------
# question-mark


def test_question_flags_an_answer_sitting_in_a_question_slot(completeness):
    # cs qft.mdx: the entry for the question held the next entry's answer.
    assert "question-mark" in checks(
        completeness,
        "What computational state superposition would correspond to a QFT with peaks on every odd binary number?\n",
        "Kdybys aplikoval/a QFT na stav $\\psi$, uviděl/a bys vrcholy na každém lichém binárně číslovaném stavu.\n",
    )


def test_question_accepts_arabic_and_fullwidth_marks(completeness):
    assert "question-mark" not in checks(completeness, "Which one?\n", "أيهما؟\n")
    assert "question-mark" not in checks(completeness, "Which one?\n", "どちらですか？\n")


def test_question_ignores_trailing_emphasis_and_quotes(completeness):
    assert "question-mark" not in checks(completeness, "**Why?**\n", "**Warum?**\n")
    assert "question-mark" not in checks(completeness, 'He asked "why?"\n', 'Er fragte „warum?“\n')


def test_question_quiet_on_matching_statements(completeness):
    assert "question-mark" not in checks(completeness, "Run the cell.\n", "Führe die Zelle aus.\n")


# --------------------------------------------------------------------------
# length-outlier


LONG_EN = ("We start with a graph, which consists of a collection of vertices (or nodes), "
           "some of which are connected by edges, and ask for the cut of maximum weight.\n")


def test_length_flags_a_translation_far_below_the_locale_norm(completeness):
    rows = completeness.check_pair(LONG_EN, "Маємо граф.\n", "uk")
    assert "length-outlier" in {r["check"] for r in rows}


def test_length_is_judged_per_locale(completeness):
    # A Japanese translation runs at ~60% of its source; the same ratio in
    # Tagalog, which runs at ~110%, is an outlier.
    short = "グラフから始め、最大重みのカットを求めます。ある頂点は辺で結ばれています。頂点の集合です。\n"
    assert "length-outlier" not in {r["check"] for r in completeness.check_pair(LONG_EN, short, "ja")}
    assert "length-outlier" in {r["check"] for r in completeness.check_pair(LONG_EN, short, "tl")}


def test_length_is_silent_without_a_locale_or_on_short_sources(completeness):
    assert "length-outlier" not in checks(completeness, LONG_EN, "Маємо граф.\n")
    assert "length-outlier" not in {r["check"] for r in completeness.check_pair("Short source.\n", "X\n", "uk")}


# --------------------------------------------------------------------------
# scored regression against the labelled set


@pytest.fixture(scope="module")
def labelled():
    if not EVAL_SET.exists():
        pytest.skip(
            f"{EVAL_SET} missing — run translation/scripts/build-eval-set.py "
            "on a branch carrying merged review fixes"
        )
    with gzip.open(EVAL_SET, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if not data["positives"]:
        pytest.skip("eval set has no positives")
    return data


def independent_positives(labelled):
    """The positives that can measure the sieve's recall.

    The set is a union of review rounds (`build-eval-set.py --extend`), and
    the gauge rounds chose what to read FROM the sieve's own findings. A defect
    repaired in one of those rounds is a defect the sieve flagged, by
    construction — scoring recall on it says 82% and means nothing. Only rounds
    whose candidates came from elsewhere (the positional-drift detector, a
    full-page review) count. `sources[].selection` says which is which."""
    sieve_heads = {s["head"][:12] for s in labelled.get("sources", []) if s.get("selection") == "sieve"}
    rows = [p for p in labelled["positives"] if p.get("src", "")[:12] not in sieve_heads]
    if not rows:
        pytest.skip("eval set has no independently selected positives")
    return rows


# Floors and ceilings, not exact values: the set grows every review round, so
# pinning exact counts would make every round fail this file. These are set a
# few points below the measured figures recorded in the script's docstring.
#
# `numbers` was deliberately lowered from 0.34 to 0.24 (measured 38.5% -> 28.3%)
# when the check stopped counting an ADDED small integer as a defect. English
# spells small numbers as words where ja and ko write the digit, so the old rule
# reported ~3,400 findings in those two locales alone, none of them real. A
# check nobody can use in a third of the corpus is worse than one that misses
# 5 points of recall. Lower a floor only with a reason of that kind, recorded
# here — never to make this file go green.
#
# `line-shape`'s ceiling was raised from 0.004 to 0.006 when the negatives grew
# from 14,311 entries on 8 Latin/Cyrillic-script locales to 64,149 on all 17:
# measured 0.44%, almost all of it on ja/ko/th, where a translator legitimately
# re-breaks a paragraph. The union ceiling was set from the same measurement.
#
# `question-mark` and `length-outlier` were admitted 2026-09-09 after scoring
# against the 483 labelled defects the four older subchecks missed: 14% and
# 20% of those respectively. length-outlier's cut was then tightened from
# z<-2.5 to z<-3.5 on a blind corpus read (3.4% precision at -2.5, 11.6% at
# -3.5): 23.6% recall on the independent rows at 0.20% noise.
FLOORS = {"line-shape": 0.30, "numbers": 0.24, "list-items": 0.03, "title-untranslated": 0.015,
          "question-mark": 0.10, "length-outlier": 0.10}
CEILINGS = {"line-shape": 0.006, "numbers": 0.012, "list-items": 0.002, "title-untranslated": 0.004,
            "question-mark": 0.003, "length-outlier": 0.010}
UNION_RECALL_FLOOR = 0.55
UNION_NOISE_CEILING = 0.025


def _checks_of(completeness, row, msgstr):
    return {f["check"] for f in completeness.check_pair(row["msgid"], msgstr, row.get("locale"))}


def _score(completeness, labelled):
    pos = [_checks_of(completeness, p, p["defective"]) for p in independent_positives(labelled)]
    neg = [_checks_of(completeness, n, n["msgstr"]) for n in labelled["negatives"]]
    return pos, neg


def test_each_subcheck_holds_its_recall_floor(completeness, labelled):
    pos, _ = _score(completeness, labelled)
    for name, floor in FLOORS.items():
        got = sum(name in h for h in pos) / len(pos)
        assert got >= floor, f"{name} recall fell to {got:.1%}, floor {floor:.1%}"


def test_each_subcheck_stays_under_its_noise_ceiling(completeness, labelled):
    _, neg = _score(completeness, labelled)
    for name, ceiling in CEILINGS.items():
        got = sum(name in h for h in neg) / len(neg)
        assert got <= ceiling, f"{name} noise rose to {got:.2%}, ceiling {ceiling:.2%}"


def test_the_union_is_worth_running(completeness, labelled):
    pos, neg = _score(completeness, labelled)
    recall = sum(1 for h in pos if h) / len(pos)
    noise = sum(1 for h in neg if h) / len(neg)
    assert recall >= UNION_RECALL_FLOOR, f"union recall fell to {recall:.1%}"
    assert noise <= UNION_NOISE_CEILING, f"union noise rose to {noise:.2%}"


def test_sieve_selected_rounds_are_excluded_from_recall(labelled):
    """Guards the scorer itself: if a gauge round's rows ever count towards
    recall, the floors become self-fulfilling and stop meaning anything."""
    sieve_heads = {s["head"][:12] for s in labelled.get("sources", []) if s.get("selection") == "sieve"}
    if not sieve_heads:
        pytest.skip("no sieve-selected round in the set yet")
    counted = {p.get("src", "")[:12] for p in independent_positives(labelled)}
    assert not (counted & sieve_heads)
    assert len(independent_positives(labelled)) < len(labelled["positives"])


def test_the_sieve_beats_the_markup_gate_it_supplements(completeness, labelled):
    """The premise of the whole script: check.py cannot see this defect class.

    Scored on the independently selected rows only. The rest of the set
    includes the check.py-to-zero wave (#524), whose 87 repairs are markup
    defects by definition and would say nothing about meaning."""
    import sys

    sys.path.insert(0, str(EVAL_SET.parent.parent / "v2"))
    import check as markup_gate

    pos = independent_positives(labelled)
    markup_hits = sum(1 for p in pos if markup_gate.check_entry(p["msgid"], p["defective"]))
    sieve_hits = sum(1 for p in pos if completeness.check_pair(p["msgid"], p["defective"]))
    assert markup_hits / len(pos) < 0.05
    assert sieve_hits > 10 * markup_hits


def test_a_repaired_translation_is_mostly_left_alone(completeness, labelled):
    """Firing on the reviewer-approved repair is the worst failure mode: it
    would send a correct translation back for another pass."""
    pos = labelled["positives"]
    fires = sum(1 for p in pos if completeness.check_pair(p["msgid"], p["repaired"]))
    assert fires / len(pos) <= 0.05, f"fires on {fires}/{len(pos)} repaired translations"


# --------------------------------------------------------------------------
# the ratchet
#
# The sieve's measured precision on an unbiased corpus sample is ~12%, so it
# must never be a cleanliness gate — failing CI on its 5,700 findings would
# demand ~5,000 non-fixes. The baseline turns it into a ratchet: new findings
# fail, known ones do not.


def test_finding_key_ignores_the_entry_index(completeness):
    """Inserting a paragraph upstream renumbers every entry below it. If the
    key included the index, that would present the whole tail of the file as
    new findings and the ratchet would cry wolf on every real edit."""
    a = {"file": "i18n/de/po/a.po", "check": "line-shape", "msgid": "Source.", "index": 3}
    b = {**a, "index": 91}
    assert completeness.finding_key(a) == completeness.finding_key(b)


def test_finding_key_separates_check_file_and_msgid(completeness):
    base = {"file": "i18n/de/po/a.po", "check": "line-shape", "msgid": "Source."}
    keys = {
        completeness.finding_key(base),
        completeness.finding_key({**base, "check": "numbers"}),
        completeness.finding_key({**base, "file": "i18n/fr/po/a.po"}),
        completeness.finding_key({**base, "msgid": "Other source."}),
    }
    assert len(keys) == 4


def test_finding_key_cannot_be_confused_by_field_concatenation(completeness):
    # A naive "a" + "b" + "c" key would collide these two.
    x = {"file": "i18n/de/po/a.po", "check": "line", "msgid": "shape"}
    y = {"file": "i18n/de/po/a.po", "check": "lineshape", "msgid": ""}
    assert completeness.finding_key(x) != completeness.finding_key(y)
