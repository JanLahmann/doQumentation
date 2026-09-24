"""Shared utilities for the translation pipeline scripts.

Created to de-duplicate logic that had been copy-pasted across the
translation/scripts/*.py files — most importantly the JSX-tag-balance check,
which existed in both validate-translation.py and lint-translation.py and had
DRIFTED (the two gates disagreed on the exact check that gates every translation
PR). Centralizing the primitive here makes them agree by construction.

Also provides the repo root and the rendered-page helpers the review scripts
share.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# ── House style: terms kept in English in every locale ──

# Settled 2026-09-08 by the maintainer: these stay English in prose. The list is
# shared so the translator instructions (translation/v2/translate.py) and the
# deep-review leak filter (sample-deep-review.py) cannot drift apart — before
# this, translate.py told translators to KEEP these terms while the sampler
# counted every one of them as a "leak" and excluded the page from review
# (154 de / 92 he / 70 cs pages).
KEEP_ENGLISH_TERMS = (
    "Qiskit", "Qubit", "Gate", "Circuit", "Backend",
    "Transpiler", "Session", "Sampler", "Estimator", "PUB", "IBM Quantum", "QPU",
)


def is_kept_english(word: str) -> bool:
    """True for a term the house style keeps in English (any case, any plural)."""
    w = word.strip().rstrip("s").casefold()
    return any(w == t.rstrip("s").casefold() for t in KEEP_ENGLISH_TERMS)


# ── v2: the rendered locale pages are build output, not source ──

RENDERED_PAGES_ARE_DERIVED = """\
Since the v2 pipeline (translation/v2/README.md) the pages under
i18n/<locale>/docusaurus-plugin-content-docs/current/ are RENDERED from
the PO files by render.py at build time. They are not tracked in git, and
any edit written there is silently discarded at the next render.
"""


def refuse_rendered_page_write(tool: str, instead: str) -> None:
    """Abort a legacy in-place fixer that would write a rendered locale page.

    These tools predate v2, when the rendered pages WERE the source. Leaving
    them runnable is worse than removing them: they report success, the site
    never changes, and the operator believes the defect is fixed.
    """
    import sys as _sys
    print(f"{tool}: refusing to write rendered locale pages.\n\n"
          f"{RENDERED_PAGES_ARE_DERIVED}\n"
          f"Do this instead:\n  {instead}\n", file=_sys.stderr)
    _sys.exit(2)


# ── Paths ──

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# A rendered translation carries the hash of the English it was rendered
# from (translation/v2/render.py writes it; populate-locale marks English
# fallbacks instead). The review scripts use the pair to skip a page whose
# English moved since the render. Formerly in check-translation-freshness.py.
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"
HASH_PATTERN = re.compile(r"\{/\* doqumentation-source-hash: ([a-f0-9]{8}) \*/\}")


def compute_source_hash(content: str) -> str:
    """First 8 hex chars of the SHA-256 of an English page's content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]


def extract_embedded_hash(content: str) -> str | None:
    """The source hash a rendered translation carries, or None."""
    m = HASH_PATTERN.search(content)
    return m.group(1) if m else None


# ── JSX tag balance (the de-drifted primitive) ──

# Paired block-JSX tags whose openers must equal closers or the locale build
# aborts ("Unexpected closing tag"). Kept in ONE place so validate + lint agree.
PAIRED_JSX_TAGS = (
    "details", "Accordion", "AccordionItem", "Admonition",
    "Tabs", "TabItem", "content", "summary",
)


def jsx_tag_imbalances(content: str) -> list[tuple[str, int, int]]:
    """Return [(tag, opens, closes)] for every PAIRED_JSX_TAG where opens != closes.

    Raw count across the whole file — deliberately NO fence-stripping and NO EN
    comparison. An unequal open/close count is always a parse error: a closing
    tag with no opener (or an opener with no closer) aborts the build. A tag
    shown inside a ``` fence inflates BOTH counts equally, so fences can't cause
    a false positive. Self-closing `<Tag .../>` are excluded from opens.

    This is the single source of truth for both validate-translation.py's
    check_jsx_tag_balance (CheckResult shape) and lint-translation.py's
    check_jsx_tag_balance (finding-tuple shape) — they format this output, they
    don't re-implement the counting.
    """
    imbalances = []
    for tag in PAIRED_JSX_TAGS:
        # All `<Tag…>` occurrences (with or without attributes), then subtract the
        # self-closing `<Tag…/>` ones. The opener pattern must allow the tag to be
        # immediately followed by `>` OR by `/>` OR by ` …>`, so that a space-less
        # self-close like `<Tabs/>` is counted by `all_opens` (and then removed by
        # `self_close`) — otherwise it would yield opens = -1 and false-flag.
        all_opens = len(re.findall(r'<%s(?:\s[^>]*?)?/?>' % tag, content))
        self_close = len(re.findall(r'<%s(?:\s[^>]*?)?/>' % tag, content))
        opens = all_opens - self_close
        closes = content.count("</%s>" % tag)
        if opens != closes:
            imbalances.append((tag, opens, closes))
    return imbalances
