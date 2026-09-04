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
TABLE_ROW_RE = re.compile(r"^\s*\|", re.M)
FENCE_LINE_RE = re.compile(r"^\s*```", re.M)


TEXT_IN_MATH_RE = re.compile(r"\\(?:text|mathrm|textrm|mbox)\{[^}]*\}")
# Scripts written without spaces between words (Thai, Japanese kana/kanji,
# Chinese, Korean): a whitespace word count sees one "word" per sentence and
# the length rules below would reject every real translation (th sync
# 2026-09-04: 115 of 219 accepted-quality entries rejected as fragments).
NO_SPACE_SCRIPT_RE = re.compile(r"[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
CHARS_PER_WORD_EQUIV = 4


def _length_units(text: str) -> float:
    """Word count, with runs of space-less script counted as one word per
    CHARS_PER_WORD_EQUIV characters (Thai runs ~6 chars per English word,
    Japanese ~2.5; 4 keeps both inside the 0.3x-2.5x window)."""
    cont = len(NO_SPACE_SCRIPT_RE.findall(text))
    spaced = len(NO_SPACE_SCRIPT_RE.sub(" ", text).split())
    return spaced + cont / CHARS_PER_WORD_EQUIV



def _math(text: str) -> Counter:
    """Math spans with \\text{...} contents masked: words inside math are
    translated (heads -> Kopf) and that is correct."""
    display = DISPLAY_MATH_RE.findall(text)
    rest = DISPLAY_MATH_RE.sub("", text)
    spans = display + INLINE_MATH_RE.findall(rest)
    return Counter(TEXT_IN_MATH_RE.sub(r"\\text{}", m) for m in spans)


def _math_problem(msgid: str, msgstr: str) -> str | None:
    """Display math ($$...$$) must match exactly: a dropped block leaves the
    page's $$ delimiters unbalanced and MDX then reads the rest as an
    expression (it broke the German phase-estimation page). Inline spans
    are compared as a multiset, tolerating a merge or split of one span
    ($X$ ... $0$ -> $X = 0$), but never a lost formula."""
    # Delimiter count first: one $$ more or less than the source unbalances
    # the page. Then block CONTENT with whitespace collapsed and \text{}
    # masked: whitespace inside a block is free to change, the formula is
    # not. A split block (odd number of $$: po4a cut a display block at a
    # blank line) is pure math, so the whole entry must match that way.
    if msgid.count("$$") != msgstr.count("$$"):
        return (f"display math mismatch: {msgid.count('$$')} $$ delimiter(s) in source, "
                f"{msgstr.count('$$')} in translation")
    def _norm(t: str) -> str:
        return re.sub(r"\s+", " ", TEXT_IN_MATH_RE.sub(r"\\text{}", t)).strip()

    def _starts_in_math(t: str) -> bool:
        """po4a can cut a display block at a blank line, so an entry may open
        inside math. Decide from the head before the first $$, with inline
        $...$ removed so a formula in the prose does not count."""
        head = INLINE_MATH_RE.sub("", t.split("$$")[0])
        return bool(re.search(r"\\[A-Za-z]+|[&^_]", head)) and \
            not re.search(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}\s+[A-Za-z]{4,}", re.sub(r"\\[A-Za-z]+", "", head))

    def _math_parts(t: str, first: int) -> list[str]:
        parts = t.split("$$")
        return sorted(_norm(x) for x in parts[first::2]) if len(parts) > 1 else []

    # The structure (which segments are math) is decided by the source and
    # imposed on the translation, which must have the same delimiters anyway.
    first = 0 if (msgid.count("$$") % 2 == 1 and _starts_in_math(msgid)) else 1
    if _math_parts(msgid, first) != _math_parts(msgstr, first):
        return "display math mismatch: $$ block content differs from source"
    a, b = _math(msgid), _math(msgstr)
    if a == b:
        return None
    na, nb = sum(a.values()), sum(b.values())
    if na and nb == 0:
        return "math mismatch: all math dropped"
    if abs(na - nb) <= 1 and nb >= na - 1:
        return None
    missing = list((a - b).elements())
    return "math mismatch: " + (f"missing {', '.join(repr(m[:40]) for m in missing[:3])}" if missing else f"{na} spans in source, {nb} in translation")


PROSE_SPAN_RE = re.compile(r"^`[\s.,;:!?)]|[\s.,;:(]`$")


def _code_spans(text: str) -> Counter:
    """Inline code spans, ignoring the artefact an odd backtick produces: with
    "`a` and `b`" tokenised one backtick off, the prose between two spans
    ("` and `", "`. So for this problem: `") is caught as a span. Real code
    does not start or end with whitespace or sentence punctuation, so those
    are dropped from both sides."""
    return Counter(m for m in INLINE_CODE_RE.findall(text) if not PROSE_SPAN_RE.search(m))


def _code_problem(msgid: str, msgstr: str) -> str | None:
    if msgid.count("`") % 2 == 1:
        # Unbalanced source: span contents cannot be paired reliably; the
        # translation must at least keep the same number of backticks.
        if msgid.count("`") != msgstr.count("`"):
            return f"inline code mismatch: {msgid.count('`')} backticks in source, {msgstr.count('`')} in translation"
        return None
    a, b = _code_spans(msgid), _code_spans(msgstr)
    if a == b:
        return None
    missing, extra = list((a - b).elements()), list((b - a).elements())
    detail = []
    if missing:
        detail.append("missing " + ", ".join(repr(m[:40]) for m in missing[:3]))
    if extra:
        detail.append("added " + ", ".join(repr(e[:40]) for e in extra[:3]))
    return "inline code mismatch: " + "; ".join(detail)


def _urls(text: str) -> Counter:
    # A bare URL followed by punctuation is captured with it; the comma or
    # full stop belongs to the sentence and may move in translation.
    return Counter((a or b).rstrip(".,;:") for a, b in URL_RE.findall(text))


def check_entry(msgid: str, msgstr: str) -> list[str]:
    """Return a list of human-readable problems; empty means the entry passes."""
    problems: list[str] = []
    if not msgstr.strip():
        return ["empty translation"]
    # An identical msgstr is not rejected: proper names and code chunks that
    # po4a hands over as prose are legitimately left in English, and an empty
    # entry would render the same English anyway. apply() annotates them.

    pairs = [
        ("URL", _urls(msgid), _urls(msgstr)),
        ("image path", Counter(IMAGE_RE.findall(msgid)), Counter(IMAGE_RE.findall(msgstr))),
        ("JSX tag", Counter(JSX_TAG_RE.findall(msgid)), Counter(JSX_TAG_RE.findall(msgstr))),
        ("HTML tag", Counter(HTML_TAG_RE.findall(msgid)), Counter(HTML_TAG_RE.findall(msgstr))),
        ("heading anchor", Counter(ANCHOR_RE.findall(msgid)), Counter(ANCHOR_RE.findall(msgstr))),
        ("MDX comment", Counter(MDX_EXPR_RE.findall(msgid)), Counter(MDX_EXPR_RE.findall(msgstr))),
    ]
    # Structure inside one entry: a table or a bullet with a fence must keep
    # its row / fence-line count, or the page fails the build-time lint.
    for name, rx in (("table row", TABLE_ROW_RE), ("code fence line", FENCE_LINE_RE)):
        a, b = len(rx.findall(msgid)), len(rx.findall(msgstr))
        if a != b:
            problems.append(f"{name} count mismatch: source {a}, translation {b}")
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

    mp = _math_problem(msgid, msgstr)
    if mp:
        problems.append(mp)
    cp = _code_problem(msgid, msgstr)
    if cp:
        problems.append(cp)

    m = DOQ_PREFIX_RE.match(msgid)
    if m and not msgstr.startswith(m.group(1)):
        problems.append(f"must keep the {m.group(1)} prefix")

    # A translation that balloons is usually an explanation, not a translation;
    # one that collapses is a fragment (positional bootstrap once paired a
    # sentence with the tail "auf." of its neighbour).
    en_words = _length_units(msgid)
    tr_words = _length_units(msgstr)
    if en_words >= 30 and tr_words > 2.5 * en_words:
        problems.append("translation more than 2.5x the source length")
    if en_words >= 12 and tr_words < 0.3 * en_words and msgstr.strip() != msgid.strip():
        problems.append("translation shorter than 30% of the source")
    return problems


if __name__ == "__main__":  # tiny self-test
    assert check_entry("Run `foo` at [x](https://a.b).", "Führe `foo` unter [x](https://a.b) aus.") == []
    assert check_entry("Run `foo`.", "Führe foo aus.") == ["inline code mismatch: missing '`foo`'"]
    assert check_entry("IBM Quantum Compute Service (Manager, Administrator)", "IBM Quantum Compute Service (Manager, Administrator)") == []
    assert "prefix" in check_entry("DOQ-ADMONITION-TITLE: Note", "Hinweis")[0]
    assert check_entry("Let $\\text{heads}$ be $X$ and $0$.", "Sei $\\text{Kopf}$ gleich $X = 0$.") == []
    assert any("math" in p for p in check_entry("Then $E = mc^2$ holds.", "Dann gilt E = mc2."))
    assert any("display math" in p for p in check_entry("We get\n$$\nx = 1\n$$\nso", "Wir erhalten also"))
    assert check_entry("We get\n$$\nx = 1\n$$\nso", "Wir erhalten\n$$\nx  =  1\n$$\nalso") == []
    assert any("display math" in p for p in check_entry("$$\n\\sum x\n=\n", "$$\n\\sum y\n=\n"))
    assert check_entry("Here is the sum\n$$\n\\sum x\n=\n", "Hier ist die Summe\n$$\n\\sum x\n=\n") == []
    assert check_entry("\\end{cases}\n$$\nwhich shows the claim.", "\\end{cases}\n$$\nwas die Behauptung zeigt.") == []
    print("check.py self-test ok")
