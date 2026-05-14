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

Steps 4–6 cover the qiskit-addons subtree, which uses a different
relative-image convention (`../images/foo.png`, `../_static/images/foo.png`,
`exp_data/foo.png`). Locale builds duplicate these PNGs into every
`i18n/<loc>/.../qiskit-addons/` because Docusaurus resolves relative refs
against the MDX file's directory.

  Step 4: scan addon MDX (EN + every locale) for relative image refs,
          copy each *referenced* image into `static/img/qiskit-addons/<rel>/`.
          Hard-stop on byte-level conflicts (e.g. a locale's image differs
          from EN's) so the human can rename + edit.
  Step 5: rewrite the relative refs to absolute `/img/qiskit-addons/<rel>`
          paths in every addon MDX (markdown `![alt](path)` and HTML
          `<img src="path">` forms; image extensions only).
  Step 6: delete every image file under `docs/qiskit-addons/` and every
          `i18n/<loc>/.../qiskit-addons/` tree, then prune empty dirs.
          Orphaned images (e.g. stale flat `output_N.png` left from an
          earlier sed-flatten) go away too.

Usage:
  python scripts/migrate_output_imgs.py --step 1   # copy _imgs only
  python scripts/migrate_output_imgs.py --step 2   # rewrite _imgs MDX only
  python scripts/migrate_output_imgs.py --step 3   # delete _imgs dirs only
  python scripts/migrate_output_imgs.py --step 4   # copy addon images
  python scripts/migrate_output_imgs.py --step 5   # rewrite addon MDX
  python scripts/migrate_output_imgs.py --step 6   # delete addon images
  python scripts/migrate_output_imgs.py --all      # all six in order

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


# ---------------------------------------------------------------------------
# Steps 4-6: qiskit-addons relative-image consolidation
# ---------------------------------------------------------------------------

ADDON_IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

# Match markdown `![alt](path)` and HTML `<img src="path">` / `<img src='path'>`.
# Path captured separately. We post-filter on extension and on relative-ness.
_MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
_HTML_IMG_RE = re.compile(r"""<img\b([^>]*?)src=(['"])([^'"]+)\2([^>]*)>""")


def _addon_roots() -> list[Path]:
    """Return every existing qiskit-addons root: docs + every i18n locale."""
    roots: list[Path] = []
    en_root = DOCS / "qiskit-addons"
    if en_root.is_dir():
        roots.append(en_root)
    if I18N.exists():
        for loc in sorted(I18N.iterdir()):
            cand = loc / "docusaurus-plugin-content-docs" / "current" / "qiskit-addons"
            if cand.is_dir():
                roots.append(cand)
    return roots


def _is_relative_image_ref(path: str) -> bool:
    """True iff `path` is a relative URL pointing at an image file."""
    if not path or path[0] in "/#":
        return False
    if path.startswith(("http://", "https://", "data:", "mailto:", "tel:")):
        return False
    # Strip URL fragment/query for extension check
    head = path.split("#", 1)[0].split("?", 1)[0]
    return head.lower().endswith(ADDON_IMG_EXTS)


def _resolve_addon_ref(mdx_path: Path, addon_root: Path, ref: str) -> Path | None:
    """Resolve a relative ref against `mdx_path`'s directory; return path
    relative to `addon_root` if it lands inside the addon tree, else None."""
    head = ref.split("#", 1)[0].split("?", 1)[0]
    target = (mdx_path.parent / head).resolve()
    try:
        rel = target.relative_to(addon_root.resolve())
    except ValueError:
        return None
    return rel


def _iter_addon_image_refs(addon_root: Path):
    """Yield (mdx_path, original_ref, resolved_rel) for every relative image
    ref under one addon root that resolves inside that root."""
    for mdx in sorted(addon_root.rglob("*.mdx")):
        text = mdx.read_text(encoding="utf-8")
        for m in _MD_IMG_RE.finditer(text):
            ref = m.group(2)
            if not _is_relative_image_ref(ref):
                continue
            resolved = _resolve_addon_ref(mdx, addon_root, ref)
            if resolved is not None:
                yield mdx, ref, resolved
        for m in _HTML_IMG_RE.finditer(text):
            ref = m.group(3)
            if not _is_relative_image_ref(ref):
                continue
            resolved = _resolve_addon_ref(mdx, addon_root, ref)
            if resolved is not None:
                yield mdx, ref, resolved


def step4_copy_addon_assets(dry_run: bool = False) -> tuple[int, int, list[str]]:
    """Copy every *referenced* addon image into static/img/qiskit-addons/<rel>.

    Hard-stop on byte mismatch (returns conflicts; caller exits non-zero).
    Locale refs that don't resolve in the locale tree fall back to the EN
    tree at the same relative path — exactly what a serve-time plugin would
    do, but materialized once at migration time.
    Returns (copied, skipped_identical, conflicts).
    """
    dest_root = STATIC_IMG / "qiskit-addons"
    en_root = DOCS / "qiskit-addons"
    copied = 0
    skipped = 0
    conflicts: list[str] = []
    seen: dict[Path, bytes] = {}  # dst -> sha256-hex of authoritative source

    for root in _addon_roots():
        for mdx, ref, rel in _iter_addon_image_refs(root):
            src = (root / rel)
            if not src.is_file():
                # Locale dir missing the asset — fall back to EN.
                en_src = en_root / rel
                if en_src.is_file():
                    src = en_src
                else:
                    conflicts.append(
                        f"MISSING: {mdx.relative_to(REPO)} references {ref} "
                        f"→ neither {(root/rel).relative_to(REPO)} nor "
                        f"{en_src.relative_to(REPO)} exists"
                    )
                    continue
            dst = dest_root / rel
            src_bytes = src.read_bytes()
            src_hash = hashlib.sha256(src_bytes).hexdigest().encode()

            if dst in seen and seen[dst] != src_hash:
                conflicts.append(
                    f"BYTE MISMATCH: {src.relative_to(REPO)} differs from "
                    f"earlier source already copied to {dst.relative_to(REPO)}"
                )
                continue
            seen[dst] = src_hash

            if dst.exists():
                if dst.read_bytes() == src_bytes:
                    skipped += 1
                    continue
                conflicts.append(
                    f"BYTE MISMATCH: {src.relative_to(REPO)} differs from "
                    f"existing {dst.relative_to(REPO)}"
                )
                continue

            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src_bytes)
            copied += 1

    return copied, skipped, conflicts


def step5_rewrite_addon_mdx(dry_run: bool = False) -> tuple[int, int]:
    """Rewrite relative image refs in every addon MDX to /img/qiskit-addons/<rel>.

    Returns (files_changed, total_replacements).
    """
    files_changed = 0
    total = 0

    for root in _addon_roots():
        for mdx in sorted(root.rglob("*.mdx")):
            original = mdx.read_text(encoding="utf-8")
            n = 0

            def md_repl(m: re.Match) -> str:
                nonlocal n
                alt, ref, title = m.group(1), m.group(2), m.group(3) or ""
                if not _is_relative_image_ref(ref):
                    return m.group(0)
                rel = _resolve_addon_ref(mdx, root, ref)
                if rel is None:
                    return m.group(0)
                n += 1
                return f"![{alt}](/img/qiskit-addons/{rel.as_posix()}{title})"

            def html_repl(m: re.Match) -> str:
                nonlocal n
                pre, quote, ref, post = m.group(1), m.group(2), m.group(3), m.group(4)
                if not _is_relative_image_ref(ref):
                    return m.group(0)
                rel = _resolve_addon_ref(mdx, root, ref)
                if rel is None:
                    return m.group(0)
                n += 1
                return f"<img{pre}src={quote}/img/qiskit-addons/{rel.as_posix()}{quote}{post}>"

            new = _MD_IMG_RE.sub(md_repl, original)
            new = _HTML_IMG_RE.sub(html_repl, new)

            if new != original:
                files_changed += 1
                total += n
                if not dry_run:
                    mdx.write_text(new, encoding="utf-8")

    return files_changed, total


def step6_delete_addon_images(dry_run: bool = False) -> tuple[int, int]:
    """Delete every image file under each addon root, then prune empty dirs.

    Returns (files_deleted, dirs_removed).
    """
    files_deleted = 0
    dirs_removed = 0

    for root in _addon_roots():
        # Collect images first so we don't mutate during traversal
        imgs = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in ADDON_IMG_EXTS]
        for img in imgs:
            if not dry_run:
                img.unlink()
            files_deleted += 1

        # Prune empty dirs bottom-up. Keep `root` itself.
        all_dirs = sorted(
            (p for p in root.rglob("*") if p.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        )
        for d in all_dirs:
            if not any(d.iterdir()):
                if not dry_run:
                    d.rmdir()
                dirs_removed += 1

    return files_deleted, dirs_removed


def verify_addons() -> list[str]:
    """Final assertions. Returns a list of failure messages (empty = pass)."""
    failures: list[str] = []

    for root in _addon_roots():
        leftover = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in ADDON_IMG_EXTS]
        for p in leftover:
            failures.append(f"image left behind: {p.relative_to(REPO)}")

        for mdx in root.rglob("*.mdx"):
            text = mdx.read_text(encoding="utf-8")
            for m in _MD_IMG_RE.finditer(text):
                ref = m.group(2)
                if _is_relative_image_ref(ref):
                    failures.append(f"relative image ref in {mdx.relative_to(REPO)}: {ref}")
            for m in _HTML_IMG_RE.finditer(text):
                ref = m.group(3)
                if _is_relative_image_ref(ref):
                    failures.append(f"relative <img src> in {mdx.relative_to(REPO)}: {ref}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, choices=[1, 2, 3, 4, 5, 6], help="run a single step")
    parser.add_argument("--all", action="store_true", help="run steps 1-6 in order")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.step and not args.all:
        parser.error("specify --step N or --all")

    steps = [args.step] if args.step else [1, 2, 3, 4, 5, 6]
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
        elif s == 4:
            copied, skipped, conflicts = step4_copy_addon_assets(dry_run=args.dry_run)
            print(f"[step 4] copied={copied} skipped_identical={skipped} conflicts={len(conflicts)}")
            for c in conflicts:
                print(f"  CONFLICT: {c}")
            if conflicts:
                print("Aborting: resolve conflicts (rename divergent images, edit only the affected locale's MDX) and re-run.")
                return 2
        elif s == 5:
            files, repls = step5_rewrite_addon_mdx(dry_run=args.dry_run)
            print(f"[step 5] files_changed={files} replacements={repls}")
        elif s == 6:
            files, dirs = step6_delete_addon_images(dry_run=args.dry_run)
            print(f"[step 6] files_deleted={files} empty_dirs_removed={dirs}")
            if not args.dry_run:
                fails = verify_addons()
                if fails:
                    print(f"[verify] FAILED ({len(fails)} issues):")
                    for f in fails:
                        print(f"  ✗ {f}")
                    return 3
                print("[verify] OK — no relative addon image refs left, no stray addon images.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
