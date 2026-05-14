"""Shared MDX prose-unit extractor.

Used by:
  - lint-translation.py::check_english_prose_drift  (strict mode)
  - validate-translation.py::check_drift            (lenient mode)
  - bootstrap-passage-hashes.py                     (lenient mode)
  - update-en-passage-hashes.py                     (lenient mode)

A "unit" is a paragraph, list item, or heading — i.e. a single semantic
chunk of prose. Code blocks, frontmatter, math, JSX/HTML blocks, image
markdown, MDX comments, and blockquotes are skipped so they don't pollute
the comparison.

Two modes:

  strict (default for the lint check):
    Min 120 chars, min 10 alphabetic words, min 60 alphabetic chars.
    Skips bibliography-style citations and recommended-reading links.
    Right when you want a high-confidence "this is real prose" signal,
    e.g. when matching a TR unit against EN to flag untranslated copy.

  lenient (for drift detection):
    Min 30 chars, min 3 alphabetic words.
    Keeps citation/link entries because if a citation changes in EN the
    translator needs to know.
    Right when you want to detect *any* meaningful EN edit.
"""

from __future__ import annotations

import hashlib
import re

# ---------------------------------------------------------------------------
# Block-element classification
# ---------------------------------------------------------------------------

INLINE_HTML_TAGS = {
    "a", "b", "br", "code", "em", "i", "img", "span", "strong",
    "sub", "sup", "kbd", "mark", "small", "tt",
}

# Boilerplate text known to be intentionally English across translations.
# Used by the strict mode only — we don't want it counting as a prose match.
_STRICT_ALLOWLIST_SUBSTRINGS = (
    "This survey is provided by IBM Quantum",
    "DO NOT EDIT THIS CELL",
    "The code on this page was developed using the following requirements",
    "is licensed under the Apache License",
    "Any modifications or derivative works of this must retain",
    "arxiv.org/",
    "IBM and the IBM logo are trademarks",
)

# First-line prefixes that mark a unit as code masquerading as prose
# (escaped fences inside JSX, etc.).
_STRICT_ALLOWLIST_PREFIXES = (
    "import ", "from qiskit", "service = QiskitRuntimeService",
    "backend = service.least_busy", "rng = ", "mat = ", "mats = ",
    "circuit = ", "circuits = ", "observable = ", "sampler.options",
    "print(", "!pip install", "# Added by doQumentation",
    "pm = generate_preset", "estimator = Estimator",
)

# Patterns that look like bibliography citations / recommended-reading links.
_CITATION_PATTERNS = [
    re.compile(r"^\\?\[\^?\d+\\?\]\s*:?\s*\S"),
    re.compile(r"^\[\[?ref\s*\d+"),
    re.compile(r"^\[[A-Z][a-zA-Z\-]+(?:\s+[a-zA-Z]+)?\s+et\s+al\.,?\s*\d{4}\]"),
    re.compile(r"^[A-Z][a-zA-Z\-]+,\s+[A-Z][a-zA-Z\-]+(,\s+|\s+and\s+|\s+[A-Z]\.)"),
    re.compile(r"^[A-Z]\.\s+[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?,\s+[A-Z]"),
    re.compile(r"^[A-Z][a-zA-Z\-]+,\s+[A-Z]\.\s*([A-Z]\.\s*)?(and\s+|&\s+)"),
    re.compile(r"^[A-Z][a-z]+\s+[A-Z][a-zA-Z\-]+\s+and\s+[A-Z][a-z]+"),
    re.compile(r"^IBM Quantum\s+\["),
]


def _is_strict_allowlisted(text: str) -> bool:
    for p in _STRICT_ALLOWLIST_SUBSTRINGS:
        if p in text:
            return True
    first_line = text.splitlines()[0].strip() if text else ""
    for p in _STRICT_ALLOWLIST_PREFIXES:
        if first_line.startswith(p):
            return True
    return False


def _is_pure_link(text: str) -> bool:
    t = text.strip()
    if not t.startswith("["):
        return False
    return bool(re.match(r"^\[(.+)\]\((https?://[^\s)]+)\)\s*\.?\s*$", t))


def _looks_like_citation(text: str) -> bool:
    first_line = text.splitlines()[0].strip() if text else ""
    for p in _CITATION_PATTERNS:
        if p.match(first_line):
            return True
    return False


def _is_jsx_block_line(s: str) -> bool:
    if not s.startswith("<"):
        return False
    m = re.match(r"<(/?)([A-Za-z][A-Za-z0-9]*)", s)
    if not m:
        return False
    tag = m.group(2)
    if tag[0].isupper():
        return True
    if tag.lower() in INLINE_HTML_TAGS:
        return False
    return True


def _looks_like_math_line(s: str) -> bool:
    if s.startswith("$$") or s.endswith("$$"):
        return True
    if s.startswith("$") and s.count("$") >= 2:
        return True
    for tok in (r"\begin{", r"\end{", r"\frac", r"\pi", r"\rangle", r"\langle"):
        if tok in s:
            return True
    return False


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(
    r"[A-Za-zÀ-ɏЀ-ӿ؀-ۿ֐-׿가-힯぀-ヿ一-鿿]+"
)


def _passes_strict(text: str) -> bool:
    if len(text) < 120:
        return False
    if _is_strict_allowlisted(text):
        return False
    if _is_pure_link(text):
        return False
    if _looks_like_citation(text):
        return False
    stripped = re.sub(r"`[^`]*`", "", text)
    stripped = re.sub(r"\$[^$\n]+\$", "", stripped)
    stripped = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", stripped)
    stripped = re.sub(r"<[^>]+>", "", stripped)
    words = _WORD_RE.findall(stripped)
    if len(words) < 10:
        return False
    alpha_chars = sum(c.isalpha() for c in stripped)
    if alpha_chars < 60:
        return False
    return True


def _passes_lenient(text: str) -> bool:
    if len(text) < 30:
        return False
    # Skip code-shaped lines that escaped fenced-block detection.
    # These prefixes are the same set we use for strict — code masquerading
    # as prose due to single-line backtick fences or indented fences in JSX.
    first_line = text.splitlines()[0].strip() if text else ""
    for p in _STRICT_ALLOWLIST_PREFIXES:
        if first_line.startswith(p):
            return False
    stripped = re.sub(r"`[^`]*`", "", text)
    stripped = re.sub(r"\$[^$\n]+\$", "", stripped)
    stripped = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", stripped)
    stripped = re.sub(r"<[^>]+>", "", stripped)
    words = _WORD_RE.findall(stripped)
    if len(words) < 3:
        return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_units(content: str, *, mode: str = "strict") -> list[str]:
    """Return prose units (paragraphs, list items, headings) from MDX content.

    mode="strict"  — only high-signal prose (≥120 chars, ≥10 words, not a
                     citation or boilerplate). Use when matching TR-to-EN
                     for untranslated copy-paste.
    mode="lenient" — every unit ≥30 chars. Use for drift detection so any
                     meaningful EN edit is caught.
    """
    if mode not in {"strict", "lenient"}:
        raise ValueError(f"unknown mode: {mode!r}")

    lines = content.splitlines()
    units: list[str] = []
    cur: list[str] = []
    in_code = False
    in_fm = False
    fm_seen = 0
    in_math = False

    def flush():
        nonlocal cur
        if cur:
            units.append("\n".join(cur).strip())
            cur = []

    for raw in lines:
        s_left = raw.lstrip()
        s = raw.strip()
        # Fenced code (any indent)
        if s_left.startswith("```"):
            in_code = not in_code
            flush()
            continue
        if in_code:
            continue
        # 4-space indented code (Markdown alt syntax), but not list continuations
        if raw.startswith("    ") and not s.startswith(("-", "*")) and not re.match(r"^\d+\.", s):
            flush()
            continue
        # Frontmatter
        if s == "---":
            fm_seen += 1
            in_fm = fm_seen < 2
            flush()
            continue
        if in_fm:
            continue
        # Display math
        if s == "$$":
            in_math = not in_math
            flush()
            continue
        if in_math:
            continue
        # Skip JSX blocks, images, tables, MDX comments, blockquotes, math-only
        if (
            s.startswith(("![", "|", "{/*", "> "))
            or _is_jsx_block_line(s)
            or _looks_like_math_line(s)
        ):
            flush()
            continue
        # Headings are their own units (drift detection wants them)
        if s.startswith("#"):
            flush()
            units.append(s)
            continue
        # Blank line ends a unit
        if not s:
            flush()
            continue
        # Each bullet/numbered item starts a new unit
        if re.match(r"^[-*]\s", s) or re.match(r"^\d+\.\s", s):
            flush()
            cur.append(s)
            continue
        cur.append(s)
    flush()

    out: list[str] = []
    filt = _passes_strict if mode == "strict" else _passes_lenient
    for u in units:
        # Strip leading list marker so a TR-with-different-spacing still matches
        u2 = re.sub(r"^([-*]\s+|\d+\.\s+)", "", u)
        # Keep headings as-is (don't strip ###)
        if u.lstrip().startswith("#"):
            u2 = u
        if filt(u2):
            out.append(u2)
    return out


def hash_unit(unit: str) -> str:
    """Stable SHA1 hex digest of a unit. Whitespace-normalized."""
    # Collapse internal runs of whitespace so wrapping changes don't shift hashes
    normalized = re.sub(r"\s+", " ", unit).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def hash_units(content: str, *, mode: str = "lenient") -> dict[str, str]:
    """Return {hash: preview} for an MDX file (content-addressed, NOT positional).

    Earlier versions used positional IDs like `para:7`, which made the result
    fragile under insertions — inserting one paragraph at the top shifted
    every subsequent ID and made the drift report claim "everything changed."
    Content-addressed IDs are insert/delete-stable: a moved paragraph keeps
    its identity, and drift becomes a set difference rather than a position
    diff.
    """
    units = extract_units(content, mode=mode)
    result: dict[str, str] = {}
    for u in units:
        preview = re.sub(r"\s+", " ", u).strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."
        h = hash_unit(u)
        # Collisions are theoretical with a 16-hex SHA1; if a file genuinely
        # repeats the same paragraph twice we keep the first preview.
        if h not in result:
            result[h] = preview
    return result
