"""Shared utilities for the translation pipeline scripts.

Created to de-duplicate logic that had been copy-pasted across the
translation/scripts/*.py files — most importantly the JSX-tag-balance check,
which existed in both validate-translation.py and lint-translation.py and had
DRIFTED (the two gates disagreed on the exact check that gates every translation
PR). Centralizing the primitive here makes them agree by construction.

Also provides the canonical status.json path + load/save helpers and the repo
root, which were re-declared (sometimes twice) in ~7 scripts. New code should
import these; existing scripts can migrate incrementally.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ── Paths ──

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATUS_FILE = REPO_ROOT / "translation" / "status.json"


# ── status.json IO ──

def load_status() -> dict:
    """Load translation/status.json (empty dict if absent)."""
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {}


def save_status(status: dict) -> None:
    """Write translation/status.json with sorted keys + trailing newline."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
