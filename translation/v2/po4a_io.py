"""Core of the v2 translation pipeline: MDX <-> PO through po4a.

Everything that touches po4a or the page files lives here so the CLIs stay
thin. Read README.md in this directory first; the short version:

    docs/<page>.mdx  --extract-->  translation/v2/pot/<page>.pot      (English, typed entries)
    pot + existing translation  --bootstrap (po4a-gettextize)-->  i18n/<loc>/po/<page>.po
    pot + po  --render (po4a-translate)-->  i18n/<loc>/docusaurus-plugin-content-docs/current/<page>.mdx

Three pre-rules are applied to a *temporary copy* of every page before po4a
sees it (the files on disk are never modified), and reversed on the rendered
output:

  1. Every heading gets an explicit `{#anchor}` derived from the English text,
     so the anchor is part of the msgid, the translator keeps it, and links
     between pages keep working in every locale.
  2. A `:::note[Title]` … `:::` admonition becomes a
     `<DoqAdmonition type="note" title="Title">` … `</DoqAdmonition>` block.
     po4a cannot parse the bracket form, and its fenced-div parser also fails
     on a code fence inside the block (guides/get-started-with-estimator.mdx);
     it handles JSX-style blocks fine, and the title prop stays translatable
     as part of the tag entry.
  3. A fenced code block or a heading that directly follows a prose line gets
     a blank line before it. CommonMark renders both the same; po4a pairs
     entries differently when the blank line is missing.

  4. A closing fence that carries a language tag ("```json" where a bare
     "```" was meant, a sync-content artifact seen in 17 English pages)
     is made bare. CommonMark treats such a line as content, so those pages
     are actually broken upstream of us; po4a reads the rest of the page as
     code and renders it untranslated.

On the translation side only, stray `{/* c510c407 */}` comment lines left by
an earlier tool are removed before alignment; they have no English
counterpart and would shift every entry after them.

Entries po4a types as fenced code are dropped from every PO: code is never
translated, and po4a-translate renders the English for any entry that is
absent, so dropping them costs nothing and keeps PO files to prose.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import polib

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
I18N = REPO / "i18n"
POT_DIR = REPO / "translation" / "v2" / "pot"
WORK_DIR = REPO / "translation" / "v2" / "work"
DOC_SUB = "docusaurus-plugin-content-docs/current"

MAIN_LOCALES = ["ar", "cs", "de", "es", "fr", "he", "id", "it", "ja",
                "ko", "ms", "pl", "pt", "ro", "th", "tl", "uk"]

PO4A_FORMAT = ["-f", "text", "-o", "markdown", "-o", "neverwrap",
               "-o", "yfm_keys=title,description,sidebar_label",
               "-M", "utf-8"]
PO4A_OUT = ["-L", "utf-8"]        # only gettextize/translate accept -L

MARKER_RE = re.compile(r"^\{/\* doqumentation-source-hash: ([0-9a-f]{8}) \*/\}\n*", re.M)
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"
HEADING_RE = re.compile(r"^(#{1,6}) (.+?)(\s*\{#[^}]+\})?\s*$")
ADM_OPEN_RE = re.compile(r"^:{3,}([a-z]+)(?:\[(.+)\])?\s*$")
ADM_CLOSE_RE = re.compile(r"^:{3,}\s*$")
ADM_TAG = "DoqAdmonition"
STRAY_COMMENT_RE = re.compile(r"^\{/\* [0-9a-f]{8} \*/\}\n*", re.M)
CODE_TYPE_PREFIX = "type: Fenced code block"

_slugify = None


def slugify(text: str) -> str:
    """Docusaurus-compatible slug. Imported from validate-translation.py so v1
    and v2 can never disagree about an anchor."""
    global _slugify
    if _slugify is None:
        spec = importlib.util.spec_from_file_location(
            "validate_translation", REPO / "translation" / "scripts" / "validate-translation.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _slugify = mod.slugify
    return _slugify(text)


class Po4aError(RuntimeError):
    pass


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")   # po4a dies with latin-1 bytes
    noise = ("is deprecated", "drop-in replacement", "Don't give up", "gorgeous", "HOWTO")
    err = "\n".join(l for l in r.stderr.splitlines() if l.strip() and not any(n in l for n in noise))
    if r.returncode != 0 or "Malformed" in err or "Structure disparity" in err or "less strings" in err or "more strings" in err:
        raise Po4aError(err.strip() or f"exit {r.returncode}")
    return r


# ---------------------------------------------------------------------------
# Pre-rules (source side) and post-rules (rendered side)
# ---------------------------------------------------------------------------

def _fence_state(lines: list[str]):
    inside = False
    for i, l in enumerate(lines):
        if re.match(r"^\s*(`{3,}|~{3,})", l):
            yield i, l, True, inside      # (index, line, is_fence_line, was_inside_before)
            inside = not inside
        else:
            yield i, l, False, inside


def _frontmatter_end(lines: list[str]) -> int:
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i
    return -1


def pre_source(text: str) -> str:
    """Apply the pre-rules. Idempotent."""
    lines = text.split("\n")
    fm_end = _frontmatter_end(lines)
    out: list[str] = []
    in_adm = False
    used: dict[str, int] = {}          # Docusaurus numbers repeated slugs: x, x-1, x-2
    for i, l, is_fence, inside in _fence_state(lines):
        if is_fence and inside:
            l = re.sub(r"^(\s*`{3,}).*$", r"\1", l)                  # rule 4
        if is_fence and not inside and out and out[-1].strip() and i > fm_end:
            out.append("")                                            # rule 3 (fence)
        if not inside and not is_fence and i > fm_end:
            m = HEADING_RE.match(l)
            if m:
                if out and out[-1].strip():
                    out.append("")                                    # rule 3 (heading)
                if not m.group(3):
                    slug = slugify(m.group(2))
                    if slug:
                        n = used.get(slug, 0)
                        used[slug] = n + 1
                        if n:
                            slug = f"{slug}-{n}"
                        l = f"{m.group(1)} {m.group(2)} {{#{slug}}}"   # rule 1
                else:
                    used[m.group(3).strip()[2:-1]] = 1
            m = ADM_OPEN_RE.match(l)
            if m and not in_adm:                                      # rule 2
                in_adm = True
                title = f' title="{m.group(2)}"' if m.group(2) else ""
                if out and out[-1].strip():
                    out.append("")
                out.extend([f'<{ADM_TAG} type="{m.group(1)}"{title}>', ""])
                continue
            if in_adm and ADM_CLOSE_RE.match(l):
                in_adm = False
                if out and out[-1].strip():
                    out.append("")
                out.extend([f"</{ADM_TAG}>", ""])
                continue
        out.append(l)
    return "\n".join(out)


ADM_POST_OPEN_RE = re.compile(r'^<' + ADM_TAG + r' type="([a-z]+)"(?: title="(.*?)")?>[ \t]*$', re.M)
ADM_POST_CLOSE_RE = re.compile(r"^</" + ADM_TAG + r">[ \t]*$", re.M)


def post_render(text: str, en_text: str | None = None) -> str:
    """Reverse rules 2 and 4. Rules 1 and 3 are intentionally left in place:
    explicit anchors and a blank line before a fence or heading are valid MDX
    that renders identically, and keeping them makes the rendered file
    self-describing. Rule 4 IS reversed (given the English) so the rendered
    page keeps the same fence lines as its source and v1's fence-count gates
    stay green; fixing the broken closing fences belongs in sync-content."""
    text = ADM_POST_OPEN_RE.sub(lambda m: f":::{m.group(1)}[{m.group(2)}]" if m.group(2) else f":::{m.group(1)}", text)
    text = ADM_POST_CLOSE_RE.sub(":::", text)
    if en_text is not None:
        en_fences = [l for _, l, f, _ in _fence_state(en_text.split("\n")) if f]
        lines = text.split("\n")
        idx = [i for i, l, f, _ in _fence_state(lines) if f]
        if len(idx) == len(en_fences):
            for i, l in zip(idx, en_fences):
                lines[i] = l
            text = "\n".join(lines)
    return text


def strip_marker(text: str) -> str:
    return MARKER_RE.sub("", text)


def clean_translation(text: str) -> str:
    """Translation-side cleanup before alignment: v1 marker and stray hash
    comments have no English counterpart."""
    return STRAY_COMMENT_RE.sub("", strip_marker(text))


def add_marker(text: str, en_hash: str) -> str:
    """Insert the v1 freshness marker after the frontmatter, so v1 tooling
    (freshness check, populate-locale, status) keeps treating the rendered
    file as a genuine, current translation during the migration."""
    text = strip_marker(text)
    lines = text.split("\n")
    fm_end = _frontmatter_end(lines)
    marker = f"{{/* doqumentation-source-hash: {en_hash} */}}"
    if fm_end >= 0:
        return "\n".join(lines[: fm_end + 1] + ["", marker] + lines[fm_end + 1:])
    return marker + "\n\n" + text


def en_hash(rel: str) -> str:
    """Same 8-hex SHA-256 prefix v1 uses, over the untouched docs/ file."""
    return hashlib.sha256((DOCS / rel).read_bytes()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def pot_path(rel: str) -> Path:
    return POT_DIR / (rel[:-4] + ".pot" if rel.endswith(".mdx") else rel + ".pot")


def po_path(locale: str, rel: str) -> Path:
    return I18N / locale / "po" / (rel[:-4] + ".po" if rel.endswith(".mdx") else rel + ".po")


def tr_path(locale: str, rel: str) -> Path:
    return I18N / locale / DOC_SUB / rel


def all_pages() -> list[str]:
    return sorted(str(p.relative_to(DOCS)) for p in DOCS.rglob("*.mdx"))


def is_genuine(path: Path) -> bool:
    return path.exists() and FALLBACK_MARKER not in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# PO hygiene
# ---------------------------------------------------------------------------

def is_code_entry(e: polib.POEntry) -> bool:
    return (e.comment or "").startswith(CODE_TYPE_PREFIX)


def is_import_entry(e: polib.POEntry) -> bool:
    return bool(re.match(r"^\s*(import|export)\s", e.msgid))


def entry_type(e: polib.POEntry) -> str:
    c = (e.comment or "").split("\n")[0]
    return c[len("type: "):] if c.startswith("type: ") else "?"


def translatable(e: polib.POEntry) -> bool:
    """Which entries a translator (human or model) should ever see."""
    if is_code_entry(e) or is_import_entry(e):
        return False
    s = e.msgid.strip()
    if s.startswith("{/*") and s.endswith("*/}"):
        return False
    if s.startswith("<") and not re.search(r'\b(title|label|description|summary)="', s):
        return False              # bare JSX/HTML with no text prop
    return True


def prune(po: polib.POFile) -> polib.POFile:
    """Drop code and import entries. Keeps everything else, including bare
    JSX lines: they are not translatable but harmless, and their presence
    keeps entry indices stable across pages for the reviewer."""
    keep = polib.POFile()
    keep.metadata = dict(po.metadata)
    for e in po:
        if is_code_entry(e) or is_import_entry(e):
            continue
        keep.append(e)
    return keep


CONFLICT_RE = re.compile(r"#-#-#-#-# .*? #-#-#-#-#\n?")
ANCHOR_IN_TEXT_RE = re.compile(r"\s*\{#[^}]+\}")


def adopt(po: polib.POFile) -> polib.POFile:
    """Make a bootstrapped PO safe to render from.

    - A msgid that occurs twice on a page with two different translations
      comes out of po4a as one entry whose msgstr holds both, separated by
      #-#-#-#-# markers. Keep the first; both translate the same English.
    - A heading's anchor comes from the English msgid, never from the
      translation: replace whatever anchor the translation carries."""
    for e in po:
        if CONFLICT_RE.search(e.msgstr):
            parts = [p.strip() for p in CONFLICT_RE.split(e.msgstr) if p.strip()]
            e.msgstr = (parts[0] + ("\n" if e.msgid.endswith("\n") else "")) if parts else ""
            e.tcomment = "doq-bootstrap: msgid repeated on page, first translation kept"
        if entry_type(e).startswith("Title") and e.msgstr:
            m = re.search(r"\{#[^}]+\}", e.msgid)
            if m:
                e.msgstr = ANCHOR_IN_TEXT_RE.sub("", e.msgstr).rstrip() + " " + m.group(0)
        # An inherited translation that lost or altered a tag would break the
        # page; render English for it and let the worklist pick it up.
        if e.msgstr and any("tag mismatch" in p for p in _check(e.msgid, e.msgstr)):
            e.tcomment = "doq-bootstrap: dropped, JSX/HTML tags differ from English: " + e.msgstr[:60].replace("\n", " ")
            e.msgstr = ""
    return po


def _check(msgid: str, msgstr: str) -> list[str]:
    from check import check_entry
    return check_entry(msgid, msgstr)


def set_header(po: polib.POFile, rel: str, locale: str | None, **extra: str) -> None:
    po.metadata.update({
        "Project-Id-Version": "doQumentation",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "MIME-Version": "1.0",
        "X-Doq-Page": rel,
        "X-Doq-EN-Hash": en_hash(rel),
    })
    if locale:
        po.metadata["Language"] = locale
    for k, v in extra.items():
        po.metadata[f"X-Doq-{k}"] = str(v)


# ---------------------------------------------------------------------------
# po4a operations
# ---------------------------------------------------------------------------

def _tmp(text: str, suffix: str = ".mdx") -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="doqv2-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return Path(name)


def extract(rel: str, write: bool = True) -> polib.POFile:
    """docs/<rel> -> POT (fresh, never merged), pruned of code entries."""
    src = _tmp(pre_source((DOCS / rel).read_text(encoding="utf-8")))
    out = _tmp("", ".pot")
    out.unlink()
    try:
        run(["po4a-updatepo"] + PO4A_FORMAT + ["-m", str(src), "-p", str(out)])
        pot = prune(polib.pofile(str(out), wrapwidth=0))
    finally:
        src.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
    for e in pot:
        e.occurrences = []            # temp-file names are noise
    set_header(pot, rel, None, Extracted=date.today().isoformat())
    if write:
        p = pot_path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        pot.save(str(p))
    return pot


FENCE_INFO_RE = re.compile(r"^(\s*`{3,})\S.*$", re.M)


def _plain_fences(text: str) -> str:
    """Give every opening fence the same language tag. Only used while
    aligning: po4a types a ```python block differently from a ```text block
    and refuses to pair them, yet code entries are dropped from the PO anyway.
    A bare ``` is NOT used: po4a does not recognise it as a fence inside a
    JSX-style block and turns the code into plain-text entries. Indented
    fences (inside list items) are left alone: po4a keeps those inside the
    bullet's prose entry, so touching them would change a msgid."""
    lines = text.split("\n")
    out = []
    for i, l, is_fence, inside in _fence_state(lines):
        out.append(re.sub(r"^(`{3,}).*$", r"\1text", l) if is_fence and not inside and not l.startswith((" ", "\t")) else l)
    return "\n".join(out)


def gettextize(rel: str, translated: Path) -> polib.POFile:
    """Align docs/<rel> with an existing translation into a PO. Raises
    Po4aError when po4a cannot pair the structures; diagnose() says where."""
    src = _tmp(_plain_fences(pre_source((DOCS / rel).read_text(encoding="utf-8"))))
    tr = _tmp(_plain_fences(pre_source(clean_translation(translated.read_text(encoding="utf-8")))))
    out = _tmp("", ".po")
    out.unlink()
    try:
        run(["po4a-gettextize"] + PO4A_FORMAT + PO4A_OUT + ["-m", str(src), "-l", str(tr), "-p", str(out)])
        po = prune(polib.pofile(str(out), wrapwidth=0))
    finally:
        for p in (src, tr, out):
            p.unlink(missing_ok=True)
    for e in po:
        e.occurrences = []
        e.flags = [f for f in e.flags if f != "fuzzy"]   # these ARE the live translations
    return adopt(po)


def entry_sequence(text: str) -> list[tuple[str, str]]:
    """[(type, first 60 chars)] as po4a sees a page. Used to explain a
    bootstrap failure in terms a developer can act on."""
    src = _tmp(pre_source(text))
    out = _tmp("", ".po")
    out.unlink()
    try:
        run(["po4a-updatepo"] + PO4A_FORMAT + ["-m", str(src), "-p", str(out)])
        po = polib.pofile(str(out), wrapwidth=0)
    finally:
        src.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
    return [(entry_type(e), e.msgid.strip().replace("\n", " ")[:60]) for e in po]


def entries_of(text: str, drop_code: bool = True) -> list[polib.POEntry]:
    """po4a's entries for any page text (English or translated), pre-rules
    applied. The positional bootstrap fallback pairs these by type sequence."""
    src = _tmp(_plain_fences(pre_source(text)))
    out = _tmp("", ".po")
    out.unlink()
    try:
        run(["po4a-updatepo"] + PO4A_FORMAT + ["-m", str(src), "-p", str(out)])
        po = polib.pofile(str(out), wrapwidth=0)
    finally:
        src.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
    for e in po:
        e.occurrences = []
    return [e for e in po if not (drop_code and (is_code_entry(e) or is_import_entry(e)))]


def diagnose(rel: str, translated: Path) -> str:
    """First point where the English and translated entry sequences diverge."""
    import difflib
    a = entry_sequence(_plain_fences((DOCS / rel).read_text(encoding="utf-8")))
    b = entry_sequence(_plain_fences(clean_translation(translated.read_text(encoding="utf-8"))))
    sm = difflib.SequenceMatcher(None, [x[0] for x in a], [x[0] for x in b], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        en = "; ".join(f"{t}: {m!r}" for t, m in a[i1:i2][:2]) or "-"
        tr = "; ".join(f"{t}: {m!r}" for t, m in b[j1:j2][:2]) or "-"
        return f"{tag} at EN entry {i1} / TR entry {j1}: EN {en} | TR {tr}"
    return f"entry counts differ ({len(a)} vs {len(b)}) but types align; po4a saw a finer difference"


def render(rel: str, po: Path, out: Path | None = None, with_marker: bool = True) -> str:
    """docs/<rel> + PO -> locale MDX text (and file, if out is given).
    Fuzzy and missing entries render as English, so a page is never blocked
    on an unfinished translation; it just shows English for that segment."""
    src = _tmp(pre_source((DOCS / rel).read_text(encoding="utf-8")))
    dst = _tmp("", ".mdx")
    try:
        run(["po4a-translate"] + PO4A_FORMAT + PO4A_OUT + ["-m", str(src), "-p", str(po), "-l", str(dst), "-k", "0"])
        text = post_render(dst.read_text(encoding="utf-8"), (DOCS / rel).read_text(encoding="utf-8"))
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)
    if with_marker:
        text = add_marker(text, en_hash(rel))
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    return text


def msgmerge(po: Path, pot: Path) -> None:
    """Update a PO against a fresh POT: unchanged entries carried, near matches
    marked fuzzy with the previous msgid kept (#| msgid), removed entries
    dropped. This is the whole 'what changed since the last sync' step."""
    run(["msgmerge", "--update", "--backup=none", "--no-wrap", "--previous",
         "--quiet", str(po), str(pot)])
    run(["msgattrib", "--no-obsolete", "--no-wrap", "-o", str(po), str(po)])


# ---------------------------------------------------------------------------
# Comparison helper used by bootstrap --verify and the tests
# ---------------------------------------------------------------------------

def body_lines(text: str) -> list[str]:
    """Lines after the frontmatter, blank lines and the marker removed, right-
    stripped. Two pages with equal body_lines render identically in MDX."""
    text = strip_marker(text)
    lines = text.split("\n")
    fm_end = _frontmatter_end(lines)
    lines = lines[fm_end + 1:] if fm_end >= 0 else lines
    return [l.rstrip() for l in lines if l.strip()]


def same_page(a: str, b: str) -> bool:
    """Equal modulo blank lines, marker, frontmatter quoting and the anchors
    rule 1 adds to headings."""
    def norm(text: str) -> list[str]:
        ls = body_lines(pre_source(text))
        return [HEADING_RE.sub(lambda m: f"{m.group(1)} {m.group(2)}", l) for l in ls]
    return norm(a) == norm(b)
