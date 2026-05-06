"""Consolidate per-notebook output PNGs into a single `static/img/` tree.

One-shot migration:
  Step 1: copy every `_<stem>_imgs/output_N.png` from `docs/` and every
          `i18n/<loc>/.../current/.../_<stem>_imgs/output_N.png` to
          `static/img/<section>/<stem-slug>/output_N.png`. Skip identical
          bytes; warn on locale-vs-EN byte mismatches (a bug if any).
  Step 2: rewrite every `.mdx` under `docs/` and `i18n/`, replacing
          `](./_<stem>_imgs/output_N.png)` with
          `](/img/<section>/<stem-slug>/output_N.png)`.
  Step 3: delete every `_*_imgs/` dir under `docs/` and `i18n/`.

Usage:
  python scripts/migrate_output_imgs.py --step 1   # copy only
  python scripts/migrate_output_imgs.py --step 2   # rewrite MDX only
  python scripts/migrate_output_imgs.py --step 3   # delete dirs only
  python scripts/migrate_output_imgs.py --all      # all three in order

Idempotent: each step is safe to re-run.
"""
import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
I18N = REPO / "i18n"
STATIC_IMG = REPO / "static" / "img"

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(stem: str) -> str:
    return SLUG_RE.sub("-", stem.lower()).strip("-")


def section_for_mdx(mdx_path: Path) -> str:
    """Derive '<section>' (e.g. 'workshop', 'qiskit-addons/cutting') for an MDX file.
    For docs/<sub>/foo.mdx -> '<sub>'. For i18n/<loc>/.../current/<sub>/foo.mdx -> '<sub>'.
    """
    rel = mdx_path.relative_to(REPO)
    parts = rel.parts
    if parts[0] == "docs":
        return "/".join(parts[1:-1])
    if parts[0] == "i18n":
        # i18n/<loc>/docusaurus-plugin-content-docs/current/<section>/<file>.mdx
        idx = parts.index("current")
        return "/".join(parts[idx + 1:-1])
    raise ValueError(f"unexpected mdx path: {mdx_path}")


def section_for_imgdir(imgdir: Path) -> str:
    rel = imgdir.relative_to(REPO)
    parts = rel.parts
    if parts[0] == "docs":
        return "/".join(parts[1:-1])
    if parts[0] == "i18n":
        idx = parts.index("current")
        return "/".join(parts[idx + 1:-1])
    raise ValueError(f"unexpected imgdir path: {imgdir}")


def stem_from_imgdir(imgdir: Path) -> str:
    """Recover original notebook stem from `_<stem>_imgs` dir name."""
    name = imgdir.name
    assert name.startswith("_") and name.endswith("_imgs")
    return name[1:-len("_imgs")]


def step1_copy(dry_run: bool = False) -> tuple[int, int, list[str]]:
    """Copy every PNG from every _<stem>_imgs dir into static/img/<section>/<slug>/.
    Returns (copied, skipped_identical, warnings)."""
    copied = 0
    skipped = 0
    warnings: list[str] = []
    # Track destination -> source byte hash for cross-locale identity check
    seen: dict[Path, str] = {}

    for root in (DOCS, I18N):
        if not root.exists():
            continue
        for imgdir in sorted(root.rglob("_*_imgs")):
            if not imgdir.is_dir():
                continue
            section = section_for_imgdir(imgdir)
            stem = stem_from_imgdir(imgdir)
            stem_slug = slug(stem)
            dst_dir = STATIC_IMG / section / stem_slug
            for png in sorted(imgdir.glob("*.png")):
                dst = dst_dir / png.name
                src_bytes = png.read_bytes()
                src_hash = hashlib.sha256(src_bytes).hexdigest()
                # Cross-locale identity check
                if dst in seen and seen[dst] != src_hash:
                    warnings.append(f"BYTE MISMATCH: {png} differs from earlier source for {dst}")
                seen[dst] = src_hash
                if dst.exists():
                    if dst.read_bytes() == src_bytes:
                        skipped += 1
                        continue
                    # exists but differs — overwrite (keep latest)
                if not dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(src_bytes)
                copied += 1

    return copied, skipped, warnings


# Match `](./_<stem>_imgs/<file>)` where file is output_N.png (or any png) and stem may
# contain spaces/punctuation but no `/` and no closing paren.
REWRITE_RE = re.compile(
    r"\]\(\./_([^/)]+)_imgs/([^)]+\.png)\)"
)


def step2_rewrite(dry_run: bool = False) -> tuple[int, int]:
    """Rewrite all .mdx files. Returns (files_changed, total_replacements)."""
    files_changed = 0
    total_repl = 0

    targets: list[Path] = []
    for root in (DOCS, I18N):
        if not root.exists():
            continue
        targets.extend(sorted(root.rglob("*.mdx")))

    for mdx in targets:
        try:
            section = section_for_mdx(mdx)
        except ValueError:
            continue
        original = mdx.read_text(encoding="utf-8")
        n_in_file = 0

        def repl(m: re.Match) -> str:
            nonlocal n_in_file
            stem = m.group(1)
            fname = m.group(2)
            n_in_file += 1
            return f"](/img/{section}/{slug(stem)}/{fname})"

        new = REWRITE_RE.sub(repl, original)
        if new != original:
            files_changed += 1
            total_repl += n_in_file
            if not dry_run:
                mdx.write_text(new, encoding="utf-8")

    return files_changed, total_repl


def step3_delete(dry_run: bool = False) -> int:
    """Delete every _<stem>_imgs/ dir under docs/ and i18n/."""
    n = 0
    for root in (DOCS, I18N):
        if not root.exists():
            continue
        for imgdir in sorted(root.rglob("_*_imgs"), reverse=True):
            if imgdir.is_dir():
                if not dry_run:
                    shutil.rmtree(imgdir)
                n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, choices=[1, 2, 3], help="run a single step")
    parser.add_argument("--all", action="store_true", help="run steps 1, 2, 3 in order")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.step and not args.all:
        parser.error("specify --step N or --all")

    steps = [args.step] if args.step else [1, 2, 3]
    for s in steps:
        if s == 1:
            copied, skipped, warnings = step1_copy(dry_run=args.dry_run)
            print(f"[step 1] copied={copied} skipped_identical={skipped} warnings={len(warnings)}")
            for w in warnings:
                print(f"  WARNING: {w}")
        elif s == 2:
            files, repls = step2_rewrite(dry_run=args.dry_run)
            print(f"[step 2] files_changed={files} replacements={repls}")
        elif s == 3:
            n = step3_delete(dry_run=args.dry_run)
            print(f"[step 3] dirs_deleted={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
