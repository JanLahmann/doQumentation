"""Tests for pure helper functions in validate-translation.py.

These take strings → values and gate every translation PR. No IO.
"""

import pytest


# ── slugify (heading → Docusaurus anchor) ──

@pytest.mark.parametrize("text,expected", [
    ("Hello World", "hello-world"),
    ("Foo `bar` Baz", "foo-bar-baz"),          # backticks stripped
    ("Title {#custom-anchor}", "title"),        # existing anchor stripped
    ("**Bold** heading", "bold-heading"),       # markdown bold stripped
    ("Already-lower", "already-lower"),
])
def test_slugify(validate, text, expected):
    assert validate.slugify(text) == expected


# ── parse_frontmatter ──

def test_parse_frontmatter_basic(validate):
    fm = validate.parse_frontmatter("---\ntitle: Hi\nslug: /x\n---\nbody")
    assert fm["title"] == "Hi"
    assert fm["slug"] == "/x"


def test_parse_frontmatter_absent(validate):
    assert validate.parse_frontmatter("no frontmatter here") == {}


# ── count_jsx_tags ──

def test_count_jsx_tags_counts_opens(validate):
    counts = validate.count_jsx_tags("<Card /><Tabs></Tabs>")
    assert counts["Card"] == 1
    assert counts["Tabs"] == 1


def test_count_jsx_tags_zero_for_absent(validate):
    counts = validate.count_jsx_tags("plain text")
    assert all(v == 0 for v in counts.values())


# ── extract_link_urls ──

def test_extract_link_urls(validate):
    urls = [u for _, u in validate.extract_link_urls("see [a](/x) and [b](http://y)")]
    assert urls == ["/x", "http://y"]


def test_extract_link_urls_none(validate):
    assert validate.extract_link_urls("no links") == []


# ── check_jsx_tag_balance returns a CheckResult ──

def test_check_jsx_tag_balance_pass(validate):
    assert validate.check_jsx_tag_balance("<details>x</details>").passed


def test_check_jsx_tag_balance_fail(validate):
    r = validate.check_jsx_tag_balance("orphan </Accordion>")
    assert not r.passed
    assert r.details  # has a per-tag detail line
