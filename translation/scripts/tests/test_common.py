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
    # Point STATUS_FILE at a non-existent path → {} (not a crash).
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


# ── known-mistranslation rules must not fire on untranslated English ───────
# po4a renders the ENGLISH for any entry whose translation is empty or fuzzy,
# so a locale page contains English wherever the translation is missing.
# Translation rules firing there report a defect that is not in any
# translation, and send a contributor to "fix" English that the next render
# regenerates. Seen on fr changelog-quantum-compute-service.mdx:373, where
# "French initialisms take no plural -s" fired on QPUs inside an untranslated
# English sentence.

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_known", Path(__file__).resolve().parent.parent / "check-known-mistranslations.py")
_CHK = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CHK)

SENTENCE = "The new dynamic circuits feature is available on all backends except some QPUs.\n"


def _page(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_rule_skips_a_line_left_in_english_by_po4a(tmp_path, monkeypatch):
    monkeypatch.setattr(_CHK, "REPO", tmp_path)
    _page(tmp_path / "docs", "guides/x.mdx", SENTENCE)
    page = _page(tmp_path / "i18n" / "fr" / _CHK.DOC_SUB, "guides/x.mdx", SENTENCE)
    assert _CHK.scan_file(page, _CHK.rules_for("fr")) == []


def test_rule_still_fires_on_actual_translated_prose(tmp_path, monkeypatch):
    monkeypatch.setattr(_CHK, "REPO", tmp_path)
    _page(tmp_path / "docs", "guides/x.mdx", SENTENCE)
    page = _page(tmp_path / "i18n" / "fr" / _CHK.DOC_SUB, "guides/x.mdx",
                 "La fonctionnalité est disponible sur tous les backends sauf certains QPUs.\n")
    hits = _CHK.scan_file(page, _CHK.rules_for("fr"))
    assert [h[1] for h in hits] == ["QPUs"]
