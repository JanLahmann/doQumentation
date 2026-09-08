"""The deep-review leak filter must not count terms the house style KEEPS.

Regression guard for a real defect: translate.py told every translator to keep
Qiskit/Qubit/Gate/Circuit… in English, while sample-deep-review.py counted each
of those as a "capitalized-English leak" and excluded the page from review —
holding 154 de / 92 he / 70 cs pages out of the programme for complying with
the house style. Both sides now read _common.KEEP_ENGLISH_TERMS.
"""

import json


def test_kept_english_terms_are_not_leaks(common):
    for term in ("Qubit", "Qubits", "Gate", "Gates", "Circuit", "Circuits",
                 "Qiskit", "QPU", "Backend", "Estimator"):
        assert common.is_kept_english(term), term


def test_ordinary_words_are_not_kept_english(common):
    for term in ("Ansatz", "Hamiltonian", "Workflow", "Sirkuit"):
        assert not common.is_kept_english(term)


def test_leak_terms_drop_kept_english_and_keep_the_rest(sampler, tmp_path, monkeypatch):
    monkeypatch.setattr(sampler, "REPO_ROOT", tmp_path)
    d = tmp_path / "translation" / "glossary"
    d.mkdir(parents=True)
    (d / "xx.json").write_text(json.dumps({"translate": {
        "gate": {"preferred": "porte", "leaked_en": ["Gate", "Gates"]},      # kept English now
        "workflow": {"preferred": "flux", "leaked_en": ["Workflow"]},        # a real leak
    }}), encoding="utf-8")
    assert sampler._leak_terms("xx") == ["Workflow"]


def test_leak_count_is_zero_without_a_glossary(sampler, tmp_path, monkeypatch):
    """No recorded leaks for the locale is an honest 0, not a proxy guess."""
    monkeypatch.setattr(sampler, "REPO_ROOT", tmp_path)
    assert sampler._leak_terms("xx") == []
    assert sampler._leak_count("Le Circuit et le Qubit partout. " * 20, "xx") == 0


def test_leak_count_counts_a_real_leak(sampler, tmp_path, monkeypatch):
    monkeypatch.setattr(sampler, "REPO_ROOT", tmp_path)
    d = tmp_path / "translation" / "glossary"
    d.mkdir(parents=True)
    (d / "xx.json").write_text(json.dumps({"translate": {
        "workflow": {"preferred": "flux", "leaked_en": ["Workflow"]}}}), encoding="utf-8")
    assert sampler._leak_count("Le Workflow ici. Un Workflow là. Un Circuit.", "xx") == 2
