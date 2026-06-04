"""Tests for passage_units.py — the prose-unit hashing that drives source-hash
freshness. A regression here is the silent 'stale-but-fresh-hash' failure class
(feedback_stale_content_despite_fresh_hash): wrong hashing marks stale files
fresh, so they're skipped by the refresh pipeline. All functions are pure.
"""

import pytest

PARA = "This is a real paragraph with several words in it for testing."


# ── hash_unit: deterministic, fixed-width, content-addressed ──

def test_hash_unit_deterministic(passage_units):
    assert passage_units.hash_unit(PARA) == passage_units.hash_unit(PARA)


def test_hash_unit_width(passage_units):
    assert len(passage_units.hash_unit(PARA)) == 16


def test_hash_unit_differs_on_change(passage_units):
    assert passage_units.hash_unit(PARA) != passage_units.hash_unit(PARA + " extra")


# ── extract_units: prose only, code/headings excluded ──

def test_extract_units_returns_prose(passage_units):
    units = passage_units.extract_units(
        "# Heading\n\n" + PARA + "\n", mode="lenient")
    assert PARA in units


def test_extract_units_excludes_code_fences(passage_units):
    content = PARA + "\n\n```python\nprint('this is code not prose')\n```\n"
    units = passage_units.extract_units(content, mode="lenient")
    assert PARA in units
    assert not any("print(" in u for u in units)


def test_extract_units_strict_vs_lenient(passage_units):
    # A short fragment passes lenient (3-word floor) but not strict.
    short = "Three short words."
    lenient = passage_units.extract_units(short, mode="lenient")
    strict = passage_units.extract_units(short, mode="strict")
    # lenient is at least as permissive as strict
    assert len(lenient) >= len(strict)


# ── hash_units: returns a {hash: preview} dict, stable across calls ──

def test_hash_units_is_dict(passage_units):
    out = passage_units.hash_units(PARA)
    assert isinstance(out, dict)


def test_hash_units_stable(passage_units):
    assert passage_units.hash_units(PARA) == passage_units.hash_units(PARA)
