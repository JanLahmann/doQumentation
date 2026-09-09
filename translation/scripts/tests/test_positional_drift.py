"""The positional-drift detector must fire on a real misalignment and stay
quiet on a faithful translation.

Regression guard for the defect clahmann694 identified: bootstrap paired
source and translation by position, so a dropped entry shifted the rest of
the page onto the wrong paragraphs. Nothing else in the pipeline sees this —
the page renders, the German is fluent, and check.py passes it, because a
well-formed translation of the wrong paragraph breaks no structural
invariant. Only meaning is wrong.
"""

import polib
import pytest


def _po(tmp_path, pairs, positional=True):
    """A PO file from (msgid, msgstr) pairs, all stamped as positional."""
    po = polib.POFile()
    for msgid, msgstr in pairs:
        e = polib.POEntry(msgid=msgid, msgstr=msgstr)
        if positional:
            e.tcomment = "doq-bootstrap: positional"
        po.append(e)
    path = tmp_path / "page.po"
    po.save(str(path))
    return path


# Three paragraphs with disjoint anchors, long enough to clear MIN_LEN.
P1 = ("The Variational Quantum Eigensolver (VQE) finds the ground state energy "
      "of a molecular Hamiltonian by minimising over a parameterised ansatz. "
      "This is the workhorse of near-term quantum chemistry on hardware today.")
T1 = ("Der Variational Quantum Eigensolver (VQE) findet die Grundzustandsenergie "
      "eines molekularen Hamiltonoperators durch Minimierung über einen "
      "parametrisierten Ansatz. Dies ist das Arbeitspferd der Quantenchemie.")
P2 = ("Preparing this state directly requires an exponential number of CNOT gates, "
      "which makes the construction resource intensive in practice. We therefore "
      "prefer product states that need only single-qubit operations to build.")
T2 = ("Die direkte Präparation dieses Zustands erfordert eine exponentielle Anzahl "
      "von CNOT-Gates, was die Konstruktion in der Praxis ressourcenintensiv macht. "
      "Wir bevorzugen daher Produktzustände mit Einzelqubit-Operationen.")
P3 = ("Trotterization approximates the exponential of a sum of non-commuting terms "
      "by alternating their individual time-evolution operators over short steps. "
      "The residual discrepancy is known as the Trotter error and shrinks with n.")
T3 = ("Die Trotterisierung approximiert das Exponential einer Summe nicht "
      "kommutierender Terme durch abwechselnde Zeitentwicklungsoperatoren über "
      "kurze Schritte. Die Restabweichung heißt Trotter-Fehler und sinkt mit n.")


def test_faithful_pairing_is_not_flagged(drift, tmp_path):
    path = _po(tmp_path, [(P1, T1), (P2, T2), (P3, T3)])
    assert drift.scan_file(path, "de") == []


def test_shifted_pairing_is_flagged(drift, tmp_path):
    """Every translation moved one entry earlier — the classic slip."""
    path = _po(tmp_path, [(P1, T2), (P2, T3), (P3, T1)])
    found = drift.scan_file(path, "de")
    assert found, "a page shifted by one must produce candidates"
    assert {c["index"] for c in found} & {0, 1}
    assert found[0]["best_fit"] > found[0]["own_fit"]


def test_entries_without_the_marker_are_ignored(drift, tmp_path):
    """The sweep is scoped to bootstrap-paired entries; anything the model
    pipeline wrote has already been through check.py."""
    path = _po(tmp_path, [(P1, T2), (P2, T3), (P3, T1)], positional=False)
    assert drift.scan_file(path, "de") == []


def test_untranslated_entries_are_ignored(drift, tmp_path):
    path = _po(tmp_path, [(P1, ""), (P2, ""), (P3, "")])
    assert drift.scan_file(path, "de") == []


def test_anchor_extraction_keeps_signal_and_drops_noise(drift):
    a = drift.anchors("Use `Sampler` with a QPU at /guides/primitives for 12 shots.")
    assert {"Sampler", "QPU", "/guides/primitives", "12"} <= a
    assert "A" not in a and "THE" not in a


def test_jaccard_is_none_without_anchors(drift):
    """No anchors is absence of evidence — it must not read as a mismatch."""
    assert drift.jaccard(set(), {"VQE"}) is None
    assert drift.jaccard({"VQE"}, {"VQE"}) == 1.0


def test_length_fit_peaks_at_the_locale_ratio(drift):
    exact = drift.length_fit(110, 100, 1.1)
    off = drift.length_fit(200, 100, 1.1)
    assert exact > 0.99
    assert off < exact
    assert drift.length_fit(10, 10, 1.1) is None
