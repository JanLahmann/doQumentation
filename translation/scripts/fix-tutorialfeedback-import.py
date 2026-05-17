#!/usr/bin/env python3
"""
Fix the TutorialFeedback-import-misplacement defect class.

Long-standing legacy translation error (was mis-labelled the "576 i18n
tutorials missing TutorialFeedback widget" issue — that framing was
disproven; see memory project_tutorial_feedback_drift). REAL root cause:
in many translated tutorials the line

    import TutorialFeedback from '@site/src/components/TutorialFeedback';

is misplaced DEEP in the file, INSIDE an open code fence, instead of
right after the frontmatter (+ source-hash comment) where EN has it
(~EN line 8). That breaks validate-translation's code-block alignment
("Code blocks: N block(s) differ") and is OUTSIDE any upstream-sync
hunk, so the git-diff retranslation pipeline structurally cannot fix it
— this scoped, deterministic relocation is the correct tool.

Idempotent: removes every TutorialFeedback import line, then re-inserts
exactly one immediately after the frontmatter close + any source-hash
comment + blank, matching EN layout. Only acts on files where EN itself
has the import (true for all tutorials). Verifies the result lands at
fence-open == 0 (outside code) before writing.

Usage:
  # dry-run a locale's tutorials
  python translation/scripts/fix-tutorialfeedback-import.py --locale de
  # apply
  python translation/scripts/fix-tutorialfeedback-import.py --locale de --apply
  # all locales
  python translation/scripts/fix-tutorialfeedback-import.py --all-locales --apply
  # single file
  python translation/scripts/fix-tutorialfeedback-import.py --file tutorials/chsh-inequality.mdx --locale de --apply
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
I18N = REPO / "i18n"
IMPORT_LINE = "import TutorialFeedback from '@site/src/components/TutorialFeedback';"


def _fence_open_before(lines: list[str], idx: int) -> int:
    return sum(1 for l in lines[:idx] if l.strip().startswith("```")) % 2


def fix_text(en_text: str, tr_text: str) -> tuple[str | None, str]:
    """Return (new_tr_text or None if no change needed, reason)."""
    if IMPORT_LINE not in en_text:
        return None, "EN has no TutorialFeedback import — skip"
    tr = tr_text.split("\n")
    have = [i for i, l in enumerate(tr) if l.strip() == IMPORT_LINE]
    # already correct? exactly one, outside any code fence, in the head region
    if len(have) == 1 and _fence_open_before(tr, have[0]) == 0 and have[0] < 15:
        return None, "already correctly placed"
    # 1. strip every existing import line
    stripped = [l for l in tr if l.strip() != IMPORT_LINE]
    # 2. find frontmatter close (2nd '---')
    fm = [i for i, l in enumerate(stripped) if l.strip() == "---"][:2]
    if len(fm) < 2:
        return None, "no frontmatter — skip (manual)"
    ins = fm[1] + 1
    # skip a source-hash comment and blank lines right after frontmatter
    while ins < len(stripped) and (
        stripped[ins].strip().startswith("{/*") or stripped[ins].strip() == ""
    ):
        ins += 1
    stripped[ins:ins] = [IMPORT_LINE, ""]
    # 3. verify
    new = stripped
    pos = [i for i, l in enumerate(new) if l.strip() == IMPORT_LINE]
    if len(pos) != 1 or _fence_open_before(new, pos[0]) != 0:
        return None, f"verify failed (pos={pos}) — NOT writing"
    return "\n".join(new), f"relocated import to line {pos[0] + 1}"


def iter_targets(locale: str | None, all_locales: bool, single: str | None):
    locales = (
        [d.name for d in sorted(I18N.iterdir()) if d.is_dir()]
        if all_locales else [locale]
    )
    for loc in locales:
        base = I18N / loc / "docusaurus-plugin-content-docs" / "current"
        if single:
            cands = [base / single]
        else:
            cands = sorted((base / "tutorials").glob("*.mdx")) if (base / "tutorials").exists() else []
        for tr_path in cands:
            if not tr_path.exists():
                continue
            rel = str(tr_path.relative_to(base))
            yield loc, rel, DOCS / rel, tr_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locale")
    ap.add_argument("--all-locales", action="store_true")
    ap.add_argument("--file", help="single rel path e.g. tutorials/chsh-inequality.mdx")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    a = ap.parse_args()
    if not a.all_locales and not a.locale:
        ap.error("need --locale or --all-locales")

    changed = skipped = errors = 0
    for loc, rel, en_path, tr_path in iter_targets(a.locale, a.all_locales, a.file):
        if not en_path.exists():
            continue
        new, why = fix_text(en_path.read_text(encoding="utf-8"),
                             tr_path.read_text(encoding="utf-8"))
        if new is None:
            if "skip" in why or "already" in why:
                skipped += 1
            else:
                errors += 1
                print(f"  ! {loc}/{rel}: {why}")
            continue
        changed += 1
        print(f"  {'FIX ' if a.apply else 'WOULD FIX '}{loc}/{rel}: {why}")
        if a.apply:
            tr_path.write_text(new, encoding="utf-8")
    print(f"\n{'applied' if a.apply else 'dry-run'}: "
          f"{changed} relocated, {skipped} ok/skip, {errors} need-manual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
