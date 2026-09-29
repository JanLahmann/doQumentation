"""translate.is_copy_only: what the copy tier may fill without a model."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from translate import is_copy_only  # noqa: E402


@pytest.mark.parametrize("msgid", [
    # JSX closers after a fence: tag names are markup, not words
    '```python\nx = 1\n```\n</TabItem>\n</Tabs>\n',
    '```python\nx = 1\n```\n  </TabItem>\n  <TabItem value="package-table-cfg">\n',
    '<OpenInLabBanner notebookPath="tutorials/chsh-inequality.ipynb" />\n',
    '<span id="executor-primitive"></span>\n',
    '<div className="hero-banner">\n',
])
def test_markup_alone_is_copy_only(msgid):
    assert is_copy_only(msgid)


@pytest.mark.parametrize("msgid", [
    # a prose attribute is a translation however short
    '<Admonition type="tip" title="Recommendations">\n',
    '<TabItem value="Valid" label="Valid">\n',
    '<img src="/x.avif" alt="Circuit" />\n',
    # removing tags must not open the one-word allowance to real prose:
    # "Default" is translated in 150 entries across the locales
    '**Default**: `False`\n  </AccordionItem>\n',
    '```text\nquantum.cloud.ibm.com\n```\n- IBM Quantum Compute Service - region eu-de:\n',
])
def test_text_a_reader_sees_is_not_copy_only(msgid):
    assert not is_copy_only(msgid)


def test_a_less_than_sign_in_math_is_not_a_tag():
    # tags are stripped after math, so $a <b$ cannot hide the prose around it
    msgid = "For $a <b$ and $c >d$ the bound holds whenever the circuit is shallow.\n"
    assert not is_copy_only(msgid)
    assert is_copy_only("$$\n\\langle a <b | c \\rangle\n$$\n")
