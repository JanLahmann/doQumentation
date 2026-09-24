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


# ── is_fence / extract_code_blocks (CommonMark closing-fence rule) ──

@pytest.mark.parametrize("line,in_block,expected", [
    ("```", False, True),               # bare opening fence
    ("```python", False, True),         # opening fence with info string
    ("```", True, True),                # bare closing fence
    ("```  ", True, True),              # trailing whitespace still bare
    ("```json", True, False),           # info string → content, not a delimiter
    ("```python{{ .Response }}", True, False),
    ("print('```')", False, False),     # not at line start
    ("text", True, False),
])
def test_is_fence(validate, line, in_block, expected):
    assert validate.is_fence(line, in_block) is expected


def test_extract_code_blocks_non_bare_close_is_content(validate):
    # The Modelfile pathology (guides/qiskit-code-assistant.mdx): a
    # ```-prefixed line with an info string inside an open block must not
    # close it, or every later block mis-pairs.
    md = (
        "```\nFROM foo\nTEMPLATE \"\"\"\n```python{{ .Response }}\n\"\"\"\n```\n\n"
        "prose\n\n```python\nx = 1\n```\n"
    )
    blocks = validate.extract_code_blocks(md)
    assert len(blocks) == 2
    assert "```python{{ .Response }}" in blocks[0][1]
    assert blocks[1][1].strip().startswith("```python")


def test_extract_code_blocks_plain_pairing_unchanged(validate):
    md = "```python\na\n```\n\ntext\n\n```\nb\n```\n"
    assert len(validate.extract_code_blocks(md)) == 2


# ── sync-content.py: _tag_untagged_code_blocks must never touch a closing fence ──

def test_tagger_does_not_rewrite_closing_fence(sync_content):
    # Regression: the old regex matched from the CLOSING fence of block 1
    # across the MDX comment to the OPENING fence of block 2 and rewrote the
    # closing fence to ```json, which swallowed the next section into the
    # code block (live on guides/custom-backend until 2026-09-07).
    src = (
        "```python\n%config x\n```\n\n"
        "{/* cspell:ignore foo */}\n\n"
        "## Heading\n\n"
        "```\nqiskit[all]~=2.5\n```\n"
    )
    assert sync_content._tag_untagged_code_blocks(src) == src


def test_tagger_does_not_rewrite_closing_fence_before_inline_math(sync_content):
    src = "```\nTest accuracy: 100.0%\n```\n\n$100\\%$ accuracy!\n\n```python\nimport x\n```\n"
    assert sync_content._tag_untagged_code_blocks(src) == src


@pytest.mark.parametrize("body,lang", [
    ('{"a": 1}', "json"),
    ("$ pip install x", "bash"),
    ("%pip install x", "bash"),
    ("pip install x", "bash"),
    ("import numpy", "python"),
    ("from x import y", "python"),
    ("qiskit[all]~=2.5", None),          # no heuristic → left bare
])
def test_tagger_tags_bare_opening_fence(sync_content, body, lang):
    out = sync_content._tag_untagged_code_blocks(f"```\n{body}\n```\n")
    first = out.split("\n")[0]
    assert first == (f"```{lang}" if lang else "```")


def test_tagger_preserves_indent_and_skips_tagged_and_math(sync_content):
    src = "  ```\n  {\"a\": 1}\n  ```\n\n```python\n{}\n```\n\n```\n$$x$$\n```\n"
    out = sync_content._tag_untagged_code_blocks(src)
    assert out.split("\n")[0] == "  ```json"
    assert "```python\n{}\n```" in out
    assert "```\n$$x$$\n```" in out
