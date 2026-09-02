#!/usr/bin/env python3
"""Migrate translations from <details>/<summary> to <Accordion>/<AccordionItem>.

Upstream replaced the raw HTML disclosure widget with the Accordion component.
English has 115 files using <Accordion> and only 4 still using <details>;
translations were never migrated, so 699 (locale, file) pairs still render the
old widget — and, worse, still carry instructions like "click the triangle to
reveal the solution" describing a triangle the Accordion does not have.

The transform is anchored to English, not guessed. English has already migrated
these files, so for each translated <details> block the corresponding
<AccordionItem title="..."> in the English file says what that block became.
676 of the 699 affected files have exact positional parity between the two, so
the mapping is by order; the 23 that do not are skipped and reported rather than
guessed at.

Two outcomes, decided by the English title:

  English title == "Answer"  -> Q&A. English moves the question OUT of the
    widget as ordinary prose and titles the item "Answer":
      QUESTION\n\n<Accordion>\n<AccordionItem title="Risposta">\n\nANSWER\n\n...
    The title uses the block's own bold label (__Risposta:__ -> "Risposta") so
    the existing wording is preserved, falling back to the locale's most common
    label when a block has none. This case is why the naive transform is wrong:
    turning the question into the title would title an accordion with a whole
    paragraph and lose English's structure.

  any other title       -> Titled. The summary text becomes the title, kept in
    the target language rather than copied from English:
      <summary><b>Versioni dei pacchetti</b></summary>
      -> <AccordionItem title="Versioni dei pacchetti">

Conservative by construction: a block whose skeleton is not recognised is left
untouched and counted, never guessed at. Run with --report first to see the
split, and check the skipped count before applying.

    python3 translation/scripts/migrate-details-to-accordion.py --report
    python3 translation/scripts/migrate-details-to-accordion.py --locale it --apply

Only files whose English counterpart has NO <details> are eligible — English
still uses it legitimately in 4 files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DOCS = REPO / "docs"
I18N = REPO / "i18n"
DOC_SUB = "docusaurus-plugin-content-docs/current"

MAIN_LOCALES = ["ar", "cs", "de", "es", "fr", "he", "id", "it", "ja",
                "ko", "ms", "pl", "pt", "ro", "th", "tl", "uk"]

# "click the triangle to reveal" and its translations. The instruction describes
# the old widget's disclosure triangle, which the Accordion does not have, so
# English deleted it. Only removed when it directly precedes a block being
# migrated — never on its own.
TRIANGLE = re.compile(
    r"triangl|triangol|triángulo|triângulo|trojúhelník|Dreieck|trikutnyk|трикут|"
    r"треуголь|삼각형|三角|สามเหลี่ยม|tatsulok|segitiga|trójkąt|triunghi|משולש|مثلث",
    re.I,
)

BOLD_LABEL = re.compile(r"^\s*(?:__|\*\*)\s*(.+?)\s*[:：]?\s*(?:__|\*\*)\s*$")


def jsx_title(text: str) -> str:
    """Make summary/label text safe inside title="...".

    Double quotes would terminate the attribute and break the MDX parse, so they
    become single quotes; markup that only makes sense as a block is stripped.
    """
    t = re.sub(r"</?b>|</?strong>", "", text).strip()
    t = t.replace('"', "'")
    t = re.sub(r"\s+", " ", t)
    return t.rstrip(":：").strip()


def migrate_block(inner: str, en_title: str, answer_label: str) -> tuple[str, str] | None:
    """(replacement, shape) for one <details> body, decided by the EN title."""
    m = re.search(r"<summary>\s*(.*?)\s*</summary>(.*)$", inner, re.S)
    if not m:
        return None
    summary = m.group(1).strip()
    rest = m.group(2)

    # A bold label directly under </summary> is the answer heading; it becomes
    # the item title, so it must not also remain in the body.
    rest_lines = rest.split("\n")
    label, body_start = None, 0
    for i, ln in enumerate(rest_lines):
        if not ln.strip():
            continue
        lm = BOLD_LABEL.match(ln)
        if lm:
            label = jsx_title(lm.group(1))
            body_start = i + 1
        break
    body = "\n".join(rest_lines[body_start:]).strip("\n")
    if not body:
        return None

    # A short bold label under </summary> ("__Answer:__", "__Hints:__",
    # "__Guidance:__") marks the Q&A shape, whatever English titled it — English
    # uses Answer, Hints and Guidance interchangeably here and all three move the
    # prompt out of the widget. Keying on the label rather than on
    # en_title == "Answer" is what stops grovers.mdx being left half-migrated:
    # its "Hints" blocks took the titled branch and were rejected for having a
    # 300-character summary, which is a prompt, not a title.
    # The length bound keeps a merely bolded opening sentence from being read as
    # a label.
    is_qa = (label is not None and len(label) <= 40) or \
            en_title.strip().lower() in ("answer", "hints", "guidance")
    if is_qa and summary:
        title = label or answer_label
        return (f"{summary}\n\n<Accordion>\n<AccordionItem title=\"{title}\">\n\n{body}\n\n"
                f"</AccordionItem>\n</Accordion>", "qa")

    # Titled: the summary is the title, in the target language.
    title = jsx_title(summary) or label
    if not title or len(title) > 200:
        return None
    if label and not summary:
        title = label
    return (f"<Accordion>\n<AccordionItem title=\"{title}\">\n\n{body}\n\n"
            f"</AccordionItem>\n</Accordion>", "titled")


def migrate_text(text: str, en_titles: list[str], answer_label: str,
                 en_has_instruction: bool = False) -> tuple[str, dict]:
    """Rewrite every <details> block, pairing each with EN's title by position."""
    stats = {"qa": 0, "titled": 0, "skipped": 0, "instruction": 0}
    blocks = list(re.finditer(r"[ \t]*<details>\n?(.*?)</details>[ \t]*", text, re.S))

    # A file can be PARTLY migrated already — some blocks are <AccordionItem>,
    # the rest still <details>. Counting only <details> against EN's item total
    # then reports a false mismatch and skips a file that is perfectly mappable:
    # id/asymmetric-key-cryptography has 8 details + 5 AccordionItems = EN's 13.
    # Pair by DOCUMENT ORDER over both kinds, and migrate only the <details>.
    existing = [(m.start(), "item") for m in re.finditer(r"<AccordionItem\b", text)]
    ordered = sorted([(m.start(), "details") for m in blocks] + existing)
    if len(ordered) != len(en_titles):
        stats["skipped"] = len(blocks)
        return text, stats                      # parity broken — never guess
    title_for = {}
    bi = 0
    for (pos, kind), en_title in zip(ordered, en_titles):
        if kind == "details":
            title_for[blocks[bi].start()] = en_title
            bi += 1

    out, pos = [], 0
    for m in blocks:
        en_title = title_for[m.start()]
        rep = migrate_block(m.group(1), en_title, answer_label)
        if rep is None:
            stats["skipped"] += 1
            continue
        replacement, shape = rep
        stats[shape] += 1
        head = text[pos:m.start()]
        hl = head.rstrip("\n").split("\n")
        # Only drop the instruction if ENGLISH dropped it. Removing it
        # unconditionally deleted a line English still has from 49 translations
        # across three files (skqd.mdx, introduction-to-quantum-computing.mdx,
        # how-to-become-quantum-ready.mdx) — and shifting the paragraph
        # alignment that way also produced a false "paragraph inflation"
        # validation failure in tl. Same per-file test the survey-paragraph
        # removal uses: compare against this file's own English counterpart.
        if (not en_has_instruction and hl
                and TRIANGLE.search(hl[-1]) and not hl[-1].lstrip().startswith("#")):
            hl = hl[:-1]
            stats["instruction"] += 1
            head = "\n".join(hl) + "\n\n"
        out.append(head)
        out.append(replacement)
        pos = m.end()
    out.append(text[pos:])
    result = "".join(out)

    # English groups CONSECUTIVE items inside a single <Accordion> — e.g.
    # guides/defaults-and-configuration-options.mdx holds five <AccordionItem>s
    # in one wrapper. Emitting a wrapper per block instead inflates the file by
    # two lines each, which pushed ko and th past the 15% line-count threshold.
    # Blocks separated by prose (every Q&A, whose question sits between them)
    # are left alone, matching English.
    result = re.sub(r"</AccordionItem>\n</Accordion>\n+<Accordion>\n<AccordionItem",
                    "</AccordionItem>\n<AccordionItem", result)
    return result, stats


def en_accordion_titles(rel: str) -> list[str]:
    p = DOCS / rel
    if not p.exists():
        return []
    return re.findall(r'<AccordionItem\s+title="(.*?)"', p.read_text(encoding="utf-8"), re.S)


def learn_answer_labels() -> dict[str, str]:
    """Each locale's own word for "Answer", from the bold labels already in use.

    Several locales use two forms (ar الجواب/الإجابة, ja 解答/答え), so a block's
    own label always wins; this is only the fallback for blocks that have none.
    """
    out: dict[str, str] = {}
    for loc in MAIN_LOCALES:
        root = I18N / loc / DOC_SUB
        if not root.exists():
            continue
        counts: dict[str, int] = {}
        for p in root.rglob("*.mdx"):
            t = p.read_text(encoding="utf-8")
            if "<details>" not in t:
                continue
            for m in re.finditer(r"<details>(.*?)</details>", t, re.S):
                after = re.search(r"</summary>(.*)$", m.group(1), re.S)
                if not after:
                    continue
                for ln in after.group(1).split("\n"):
                    if not ln.strip():
                        continue
                    lm = BOLD_LABEL.match(ln)
                    if lm:
                        k = jsx_title(lm.group(1))
                        counts[k] = counts.get(k, 0) + 1
                    break
        if counts:
            out[loc] = max(counts.items(), key=lambda kv: kv[1])[0]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--locale", action="append")
    ap.add_argument("--file", help="one EN-relative path")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true", help="totals only")
    args = ap.parse_args()

    en_has_details = {}
    for p in DOCS.rglob("*.mdx"):
        en_has_details[str(p.relative_to(DOCS))] = "<details>" in p.read_text(encoding="utf-8")

    answer_labels = learn_answer_labels()
    total = {"qa": 0, "titled": 0, "skipped": 0, "instruction": 0}
    files = 0
    parity_skipped = []
    for loc in (args.locale or MAIN_LOCALES):
        root = I18N / loc / DOC_SUB
        if not root.exists():
            continue
        fallback = answer_labels.get(loc, "Answer")
        for p in sorted(root.rglob("*.mdx")):
            rel = str(p.relative_to(root))
            if args.file and rel != args.file:
                continue
            if en_has_details.get(rel) is not False:
                continue                      # EN still uses <details> here
            text = p.read_text(encoding="utf-8")
            if "<details>" not in text:
                continue
            titles = en_accordion_titles(rel)
            en_text = (DOCS / rel).read_text(encoding="utf-8")
            new_text, st = migrate_text(text, titles, fallback,
                                        en_has_instruction=bool(TRIANGLE.search(en_text)))
            if new_text == text:
                if st["skipped"]:
                    parity_skipped.append(
                        f"{loc}/{rel} (TR={st['skipped']} blocks, EN={len(titles)} items)")
                    total["skipped"] += st["skipped"]
                continue
            files += 1
            for k in total:
                total[k] += st[k]
            if not args.report:
                print(f"  {'MIGRATE' if args.apply else 'would migrate'} {loc}/{rel}  "
                      f"qa={st['qa']} titled={st['titled']} skipped={st['skipped']}")
            if args.apply:
                p.write_text(new_text, encoding="utf-8")

    print(f"\n{'applied' if args.apply else 'DRY RUN'}: {files} file(s) migrated")
    print(f"  Q&A blocks        : {total['qa']}")
    print(f"  titled blocks     : {total['titled']}")
    print(f"  instruction lines : {total['instruction']}")
    print(f"  SKIPPED blocks    : {total['skipped']}")
    if parity_skipped:
        print(f"\n  {len(parity_skipped)} file(s) skipped for TR/EN count mismatch "
              f"(never guessed):")
        for s in parity_skipped[:8]:
            print(f"    {s}")
        if len(parity_skipped) > 8:
            print(f"    … and {len(parity_skipped) - 8} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
