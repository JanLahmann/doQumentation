"""Per-entry checks for a translated PO entry.

A translation is accepted only if everything that must survive translation
byte-for-byte is still there: inline code spans, URLs, math, JSX tags, heading
anchors, MDX expressions and the DOQ- prefixes the pre-rules introduce. The
checks are deliberately multiset comparisons, not positional ones: word order
changes between languages, the set of invariants must not.

    from check import check_entry
    problems = check_entry(msgid, msgstr)     # [] means accepted

Kept free of po4a and file I/O so it can be unit-tested on strings.
"""

from __future__ import annotations

import re
from collections import Counter

INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
URL_RE = re.compile(r"\]\(([^)\s]+)\)|(?<![`\w])(https?://[^\s)>\]]+)")
DISPLAY_MATH_RE = re.compile(r"\$\$[^$]+\$\$")
INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)[^$\n]+\$(?!\$)")
JSX_TAG_RE = re.compile(r"</?[A-Z][A-Za-z0-9]*\b")
HTML_TAG_RE = re.compile(r"</?(?:a|b|i|em|strong|code|span|div|br|img|sup|sub|kbd|details|summary|p|ul|ol|li|table|thead|tbody|tr|td|th|pre|iframe|video|figure|figcaption)\b")
ANCHOR_RE = re.compile(r"\{#[^}]+\}")
MDX_EXPR_RE = re.compile(r"\{/\*.*?\*/\}")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
DOQ_PREFIX_RE = re.compile(r"^(DOQ-[A-Z-]+:)")


def _math(text: str) -> Counter:
    display = DISPLAY_MATH_RE.findall(text)
    rest = DISPLAY_MATH_RE.sub("", text)
    return Counter(display) + Counter(INLINE_MATH_RE.findall(rest))


def _urls(text: str) -> Counter:
    return Counter(a or b for a, b in URL_RE.findall(text))


def check_entry(msgid: str, msgstr: str) -> list[str]:
    """Return a list of human-readable problems; empty means the entry passes."""
    problems: list[str] = []
    if not msgstr.strip():
        return ["empty translation"]
    if msgstr.strip() == msgid.strip() and len(msgid.split()) >= 4:
        problems.append("translation identical to source")

    pairs = [
        ("inline code", Counter(INLINE_CODE_RE.findall(msgid)), Counter(INLINE_CODE_RE.findall(msgstr))),
        ("URL", _urls(msgid), _urls(msgstr)),
        ("image path", Counter(IMAGE_RE.findall(msgid)), Counter(IMAGE_RE.findall(msgstr))),
        ("math", _math(msgid), _math(msgstr)),
        ("JSX tag", Counter(JSX_TAG_RE.findall(msgid)), Counter(JSX_TAG_RE.findall(msgstr))),
        ("HTML tag", Counter(HTML_TAG_RE.findall(msgid)), Counter(HTML_TAG_RE.findall(msgstr))),
        ("heading anchor", Counter(ANCHOR_RE.findall(msgid)), Counter(ANCHOR_RE.findall(msgstr))),
        ("MDX comment", Counter(MDX_EXPR_RE.findall(msgid)), Counter(MDX_EXPR_RE.findall(msgstr))),
    ]
    for name, a, b in pairs:
        if a != b:
            missing = list((a - b).elements())
            extra = list((b - a).elements())
            detail = []
            if missing:
                detail.append("missing " + ", ".join(repr(m[:40]) for m in missing[:3]))
            if extra:
                detail.append("added " + ", ".join(repr(e[:40]) for e in extra[:3]))
            problems.append(f"{name} mismatch: " + "; ".join(detail))

    m = DOQ_PREFIX_RE.match(msgid)
    if m and not msgstr.startswith(m.group(1)):
        problems.append(f"must keep the {m.group(1)} prefix")

    # A translation that balloons is usually an explanation, not a translation.
    en_words = len(msgid.split())
    if en_words >= 30 and len(msgstr.split()) > 2.5 * en_words:
        problems.append("translation more than 2.5x the source length")
    return problems


if __name__ == "__main__":  # tiny self-test
    assert check_entry("Run `foo` at [x](https://a.b).", "Führe `foo` unter [x](https://a.b) aus.") == []
    assert check_entry("Run `foo`.", "Führe foo aus.") == ["inline code mismatch: missing '`foo`'"]
    assert "prefix" in check_entry("DOQ-ADMONITION-TITLE: Note", "Hinweis")[0]
    print("check.py self-test ok")
