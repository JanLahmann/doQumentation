"""Claim parsing for the "Who is working on what" table."""
import importlib.util
from pathlib import Path

import pytest

_P = Path(__file__).resolve().parents[1] / "contributing-status.py"
_spec = importlib.util.spec_from_file_location("contributing_status", _P)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

FORM = "### Locale\n\n{loc}\n\n### What you will do\n\n{what}\n\n### Rough scope\n\n40 pages"


@pytest.fixture(autouse=True)
def locales(monkeypatch):
    monkeypatch.setattr(cs, "_known_locales", lambda: {"ar", "de", "ja", "pl", "th"})


@pytest.mark.parametrize("field,want", [
    ("de", "de"),
    ("ja — reviewing", "ja"),
    ("all 17 (ar cs de es fr he id it ja ko ms pl pt ro th tl uk) for sweep 6", "all"),
    ("ar and pl", "ar, pl"),
    ("ar de ja pl th", "all"),
    ("whatever is left", "?"),
])
def test_locale_field(field, want):
    assert cs.parse_claim("claim: something", FORM.format(loc=field, what="review (x)"))[0] == want


def test_title_fallback_and_track():
    assert cs.parse_claim("Claim: de translation", "") == ("de", "translate")
    assert cs.parse_claim("claim: de", FORM.format(loc="de", what="translate new pages"))[1] == "translate"
    assert cs.parse_claim("claim: de", "") == ("de", "?")
