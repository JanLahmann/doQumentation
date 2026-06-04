"""Tests for the shared JSX-tag-balance primitive (_common.jsx_tag_imbalances).

This is the de-drifted core that both validate-translation.py and
lint-translation.py now share — it gates every translation PR, so it gets the
most coverage. A regression here either lets a build-breaking tag mismatch
through, or false-flags a file that actually builds.
"""

import pytest


def imbalances(common, content):
    return common.jsx_tag_imbalances(content)


# ── Balanced cases → no findings ──

@pytest.mark.parametrize("content", [
    "",
    "no jsx here at all",
    "<details>x</details>",
    "<Accordion><AccordionItem>q</AccordionItem></Accordion>",
    "<Tabs><TabItem>a</TabItem><TabItem>b</TabItem></Tabs>",
    "<details>\nmultiline\n</details>",
    "<details open>attrs</details>",            # opener with attributes
    "<Admonition type='note'>x</Admonition>",
])
def test_balanced_yields_nothing(common, content):
    assert imbalances(common, content) == []


# ── Self-closing tags are excluded from opener counts ──

@pytest.mark.parametrize("content", [
    "<Tabs />",
    "<Tabs/>",
    "<TabItem value='x' />",
])
def test_self_closing_not_counted_as_open(common, content):
    assert imbalances(common, content) == []


# ── Imbalances → flagged with correct (tag, opens, closes) ──

def test_orphan_closer(common):
    assert imbalances(common, "text </Accordion> more") == [("Accordion", 0, 1)]


def test_unclosed_opener(common):
    assert imbalances(common, "<details>never closed") == [("details", 1, 0)]


def test_extra_closer(common):
    # one open, two closes
    out = imbalances(common, "<Tabs>x</Tabs></Tabs>")
    assert ("Tabs", 1, 2) in out


def test_multiple_tags_each_reported(common):
    out = dict((t, (o, c)) for t, o, c in
               imbalances(common, "<details>x</Accordion>"))
    assert out["details"] == (1, 0)
    assert out["Accordion"] == (0, 1)


# ── Fence false-positive guard: a tag shown inside ``` inflates BOTH counts ──

def test_tag_in_code_fence_does_not_false_flag(common):
    content = "<details>real</details>\n```\n<details>example</details>\n```"
    # both the real and the fenced pair are balanced → no finding
    assert imbalances(common, content) == []


# ── validate + lint agree by construction (the whole point of the de-drift) ──

# ── status.json helpers (shared load/save) ──

def test_load_status_missing_returns_empty(common, tmp_path, monkeypatch):
    # Point STATUS_FILE at a non-existent path → {} (not a crash). This is the
    # behavior the bootstrap-passage-hashes migration relies on.
    monkeypatch.setattr(common, "STATUS_FILE", tmp_path / "nope.json")
    assert common.load_status() == {}


def test_save_then_load_roundtrips(common, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "STATUS_FILE", tmp_path / "status.json")
    data = {"de": {"guides/x.mdx": {"validation": "PASS"}}}
    common.save_status(data)
    assert common.load_status() == data


def test_validate_and_lint_agree(common, validate, lint):
    samples = [
        "<details>x</details>",                  # balanced
        "text </Accordion> orphan",              # imbalanced
        "<Tabs><TabItem>a</TabItem></Tabs>",     # nested balanced
        "<AccordionItem>unclosed",               # imbalanced
    ]
    for s in samples:
        v_failed = not validate.check_jsx_tag_balance(s).passed
        l_findings = lint.check_jsx_tag_balance(s.split("\n"))
        l_failed = len(l_findings) > 0
        assert v_failed == l_failed, f"validate/lint disagree on: {s!r}"
