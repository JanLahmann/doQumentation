#!/usr/bin/env python3
"""
Draw a stratified, seeded, reproducible random sample of translation pages for
the Tier-4 Opus deep review, and describe every page of a locale the way the
review programme sees it.

This is the *selection* half of the review. It is deterministic (seeded) so a
run is reproducible, and stratified (round-robin across sections) so a small
sample still touches every part of the corpus. It writes a JSON sample the
`opus-deep-review` workflow consumes via `args`.

Where the facts come from (since 2026-09-10, no `status.json`):
  - the locale's PO files under i18n/<locale>/po/ are the corpus: one page
    per PO, the page-level Opus verdict in the header
    (`X-Doq-Review-Opus: PASS 2026-07-05`, written by
    `review-translations.py --record-opus` when a review round ships), and
    the entries say whether the page is mid-update (fuzzy or empty);
  - the rendered page under i18n/<locale>/…/current/ says how long it is and
    whether it is an English fallback. Render the locale first
    (`translation/v2/render.py --locale X`).

Eligibility:
  - has a PO and a rendered page that is not an untranslated fallback
  - no fuzzy or empty translatable entry (the page would render English there)
  - at least --min-lines rendered lines (default 1: every page with prose;
    the old 40-line stub cutoff hid the index and landing pages whose Card
    captions turned out to be where English reversions hide)
  - with --exclude-reviewed: either no Opus verdict in the PO header yet
    (a FULL read), or a verdict plus entries a model wrote since it — a
    fix wave's repairs, a sync's retranslations — that no reviewer has read
    (a DELTA read: the page for context, judgement on those entries only)

Usage:
    python translation/scripts/sample-deep-review.py \
        --locale de --per-locale 25 --seed 20260910 --exclude-reviewed \
        --out /tmp/opus-sample.json
    # then feed the file to the workflow:
    #   Workflow({ name: "opus-deep-review", args: <contents of the JSON> })

    # dry preview (prints the sample, writes nothing):
    python translation/scripts/sample-deep-review.py --per-locale 2 --seed 1 --print
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import polib

sys.path.insert(0, str(Path(__file__).resolve().parent))   # importable as well as runnable
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

MAIN_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "ms", "id", "th", "ko", "pl", "ro", "cs",
]
DIALECTS: list[str] = []   # the 9 German dialect locales were removed 2026-09-05

SECTIONS = ["tutorials/", "guides/", "learning/courses/", "learning/modules/"]
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

# PO header fields. Tier3 is the v1 Haiku verdict copied at bootstrap and no
# longer written; Opus is the page-level deep-review verdict and the only
# field eligibility reads.
REVIEW_HEADER = "X-Doq-Review-Opus"
TIER3_HEADER = "X-Doq-Review-Tier3"
PAGE_VERDICTS = ("PASS", "MINOR_ISSUES", "FAIL")

# Per-locale register one-liner (mirrors review-tier4-opus-prompt.md) so the
# workflow can build a self-contained agent prompt without re-reading a file.
REGISTER = {
    "de": 'informal "du" — not Sie/Ihnen/Verwenden Sie',
    "es": 'informal "tú" — not usted/consulte/utilice/ejecute',
    "fr": 'informal "tu" — not vous/votre/veuillez',
    "it": 'informal "tu" — not Lei/consulti/utilizzi',
    "pt": 'casual "você" — not o senhor/a senhora/vossa',
    "uk": 'informal "ти" — not Ви/Вам/Ваш',
    "pl": 'informal "ty" — not Pan/Pani/Państwo/proszę uprzejmie',
    "cs": 'informal "ty" — not Vy/Vám/Vás/račte (Chceš-li is fine)',
    "ro": 'informal "tu" — not dumneavoastră/dvs./vă rog',
    "ja": "polite desu/masu, no keigo — not ございます/いただく/ご覧ください",
    "ko": "해요체 — not honorific/humble (하십시오체, 드리)",
    "ar": "informal anta/anti — not formal antum",
    "he": "informal — not biblical/over-formal register",
    "th": "casual — no polite particles ครับ/ค่ะ",
    "ms": 'standard "anda" — casual "kamu" is a MINOR, not FAIL',
    "id": '"Anda"/"kamu" — not bapak/ibu deferential',
    "tl": "casual — no po/opo formality",
}
LOCALE_NAME = {
    "de": "German", "es": "Spanish", "fr": "French", "it": "Italian",
    "pt": "Portuguese", "uk": "Ukrainian", "pl": "Polish", "cs": "Czech",
    "ro": "Romanian", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
    "he": "Hebrew", "th": "Thai", "ms": "Malay", "id": "Indonesian",
    "tl": "Tagalog",
}


def _import_by_path(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_common = _import_by_path("_common", SCRIPTS_DIR / "_common.py")
_po4a_io = _import_by_path("po4a_io", REPO_ROOT / "translation" / "v2" / "po4a_io.py")


def _tr_path(locale: str, rel: str) -> Path:
    return I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel


def po_dir(locale: str) -> Path:
    return I18N_DIR / locale / "po"


def section_of(rel: str) -> str:
    for s in SECTIONS:
        if rel.startswith(s):
            return s
    return "other/"


def split_verdict(value: str | None) -> tuple[str | None, str | None]:
    """'PASS 2026-07-05' -> ('PASS', '2026-07-05'); 'PASS' -> ('PASS', None)."""
    if not value:
        return None, None
    parts = value.split()
    return parts[0], (parts[1] if len(parts) > 1 else None)


def catalogue(locale: str) -> dict[str, dict]:
    """Every page of a locale as the review programme sees it, keyed by the
    English path (`guides/foo.mdx`).

    verdict / reviewed  the page-level Opus verdict and its date from the PO
                        header, None when the page was never read
    tier3               the v1 Haiku verdict copied at bootstrap (context only)
    pending             translatable entries that are fuzzy or empty: the page
                        is mid-update and renders English there
    unverified          entries a model wrote (dated stamp) that no reviewer
                        has read since: [{index, since, msgid, msgstr}]
    rendered / lines / fallback
                        from the rendered page when it exists
    """
    out: dict[str, dict] = {}
    base = po_dir(locale)
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*.po")):
        rel = str(p.relative_to(base))[:-3] + ".mdx"
        po = polib.pofile(str(p), wrapwidth=0)
        verdict, reviewed = split_verdict(po.metadata.get(REVIEW_HEADER))
        tier3, _ = split_verdict(po.metadata.get(TIER3_HEADER))
        pending = 0
        unverified = []
        for idx, e in enumerate(po):
            if not _po4a_io.translatable(e):
                continue
            if e.fuzzy or not e.msgstr.strip():
                pending += 1
            since = _po4a_io.pending_since(e)
            if since:
                unverified.append({"index": idx, "since": since, "msgid": e.msgid, "msgstr": e.msgstr})
        info = {"rel": rel, "section": section_of(rel), "verdict": verdict,
                "reviewed": reviewed, "tier3": tier3, "pending": pending,
                "unverified": unverified,
                "rendered": False, "lines": 0, "fallback": False}
        tr = _tr_path(locale, rel)
        if tr.exists():
            text = tr.read_text(encoding="utf-8")
            info.update(rendered=True, lines=len(text.splitlines()),
                        fallback=FALLBACK_MARKER in text)
        out[rel] = info
    return out


def is_rendered(cat: dict[str, dict]) -> bool:
    """A locale counts as rendered when most of its pages are on disk (index.mdx
    alone, a hand-kept page, is not a rendered locale)."""
    have = sum(1 for i in cat.values() if i["rendered"])
    return have >= max(10, len(cat) // 4)


# Leaks: what a locale's glossary records as wrongly left in English, minus
# the terms the house style keeps in English (_common.KEEP_ENGLISH_TERMS).
# Settled 2026-09-08: Qubit/Gate/Circuit are KEPT, so they are not leaks and
# must not exclude a page from review — counting them had held 154 de / 92 he
# / 70 cs pages out of the deep review for following the house style. A locale
# with nothing recorded has a leak count of 0, which is the honest answer.

def _leak_terms(locale: str) -> list[str]:
    from _common import is_kept_english
    p = REPO_ROOT / "translation" / "glossary" / f"{locale}.json"
    if not p.exists():
        return []
    g = json.loads(p.read_text(encoding="utf-8"))
    terms = []
    for spec in (g.get("translate") or {}).values():
        terms += [t for t in spec.get("leaked_en", []) if not is_kept_english(t)]
    return sorted(set(terms))


def _leak_count(text: str, locale: str) -> int:
    """Leak count in prose for one locale (uses the detector's prose strip)."""
    terms = _leak_terms(locale)
    if not terms:
        return 0
    try:
        chk = _import_by_path("chk", SCRIPTS_DIR / "check-glossary-consistency.py")
        prose = chk.to_prose(text)
    except Exception:
        prose = text
    pat = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b")
    return len(pat.findall(prose))


def review_mode(info: dict, min_lines: int, exclude_reviewed: bool) -> str | None:
    """'full' (read the whole page), 'delta' (a verdict stands; judge only the
    entries written since it), or None when the page is not eligible."""
    if not info["rendered"] or info["fallback"]:
        return None
    if info["lines"] < min_lines:
        return None
    if info["pending"]:
        return None
    if not info["verdict"]:
        return "full"
    if info["unverified"]:
        return "delta"
    return None if exclude_reviewed else "full"


def eligible(info: dict, min_lines: int, exclude_reviewed: bool) -> bool:
    return review_mode(info, min_lines, exclude_reviewed) is not None


def build_pool(catalogues: dict[str, dict], min_lines: int,
               sections: tuple[str, ...] | None = None,
               max_leaks: int | None = None,
               exclude_reviewed: bool = False) -> dict:
    """{locale: [(rel, section, lines, tier3, mode, unverified), ...]} of eligible pages.

      catalogues        {locale: catalogue(locale)}
      sections          only these section prefixes (e.g. course+module)
      max_leaks         include only pages with <= this many recorded glossary
                        leaks (0 == the strict 'leak-clean' run; None == no cap)
      exclude_reviewed  skip pages already carrying an Opus verdict
    """
    pool: dict[str, list] = {}
    for loc, cat in catalogues.items():
        rows = []
        for rel, info in cat.items():
            if sections and not rel.startswith(sections):
                continue
            mode = review_mode(info, min_lines, exclude_reviewed)
            if mode is None:
                continue
            if max_leaks is not None:
                text = _tr_path(loc, rel).read_text(encoding="utf-8")
                if _leak_count(text, loc) > max_leaks:
                    continue
            rows.append((rel, info["section"], info["lines"], info["tier3"] or "?", mode,
                         info["unverified"] if mode == "delta" else []))
        if rows:
            pool[loc] = rows
    return pool


def draw(pool: dict, per_locale: int, seed: int, focus: str | None = None) -> list[dict]:
    """Stratified within locale: round-robin across sections, seeded-random
    within each section bucket. Reproducible for a given (pool, seed)."""
    rng = random.Random(seed)
    sample = []
    for loc in sorted(pool):  # sorted → deterministic locale order
        buckets: dict[str, list] = {}
        for row in pool[loc]:
            buckets.setdefault(row[1], []).append(row)
        for sec in buckets:
            rng.shuffle(buckets[sec])
        order = sorted(buckets)  # deterministic section order
        picked = []
        i = 0
        while len(picked) < per_locale and any(buckets[s] for s in order):
            sec = order[i % len(order)]
            if buckets[sec]:
                picked.append(buckets[sec].pop())
            i += 1
        for rel, sec, lines, tier3, mode, unverified in picked:
            rec = {
                "locale": loc,
                "rel": rel,
                "section": sec,
                "lines": lines,
                "locale_name": LOCALE_NAME.get(loc, loc),
                "register": REGISTER.get(loc, "informal register"),
                "tier3_verdict": tier3,
                "mode": mode,
            }
            if mode == "delta":
                # The reviewer gets the page for context and these entries to
                # judge; text is capped so a sample file stays a prompt, not a corpus.
                rec["delta_entries"] = [{"index": u["index"], "since": u["since"],
                                         "en": u["msgid"][:1500], "tr": u["msgstr"][:1500]} for u in unverified]
            if focus:
                rec["focus"] = focus
            sample.append(rec)
    return sample


def main():
    ap = argparse.ArgumentParser(description="Stratified seeded sample for Opus deep review")
    ap.add_argument("--per-locale", type=int, default=5,
                    help="pages per locale (default 5)")
    ap.add_argument("--seed", type=int, required=True,
                    help="PRNG seed (reproducible; rotate for a fresh sample)")
    ap.add_argument("--min-lines", type=int, default=1,
                    help="skip rendered pages shorter than this (default 1: every page with prose)")
    ap.add_argument("--include-dialects", action="store_true",
                    help="also sample non-main locales (none at present)")
    ap.add_argument("--sections", default=None,
                    help="comma-separated section prefixes to restrict to "
                         "(e.g. 'learning/courses/,learning/modules/')")
    ap.add_argument("--leak-clean", action="store_true",
                    help="only pages with 0 recorded glossary leaks (== --max-leaks 0)")
    ap.add_argument("--max-leaks", type=int, default=None,
                    help="include pages with <= N recorded glossary leaks. "
                         "Overridden to 0 by --leak-clean.")
    ap.add_argument("--drift-focus", action="store_true",
                    help="force the drift-focused Opus prompt even without "
                         "--leak-clean (tells the agent to ignore kept-English "
                         "leaks and hunt semantic drift). Implied by --leak-clean.")
    ap.add_argument("--exclude-reviewed", action="store_true",
                    help="skip pages whose verdict stands with nothing written since; pages with a "
                         "verdict AND unverified model-written entries stay in, as delta reads")
    ap.add_argument("--locale", action="append", metavar="LOCALE",
                    help="restrict the sample to this locale (repeatable). "
                         "Lets an external contributor own one locale outright, "
                         "so their fixes touch a disjoint i18n/ subtree and can "
                         "never conflict with another round.")
    ap.add_argument("--out", help="write sample JSON here")
    ap.add_argument("--print", action="store_true", dest="do_print",
                    help="print the sample to stdout")
    args = ap.parse_args()

    locales = MAIN_LOCALES + (DIALECTS if args.include_dialects else [])
    if args.locale:
        unknown = [l for l in args.locale if l not in locales]
        if unknown:
            print(f"unknown locale(s): {', '.join(unknown)}\n"
                  f"known: {', '.join(locales)}", file=sys.stderr)
            sys.exit(1)
        locales = [l for l in locales if l in set(args.locale)]
    sections = tuple(s for s in (args.sections or "").split(",") if s) or None

    catalogues = {loc: catalogue(loc) for loc in locales}
    missing = [loc for loc, cat in catalogues.items() if not cat]
    if missing:
        for loc in missing:
            print(f"no PO files under i18n/{loc}/po/ — is the clone complete?", file=sys.stderr)
        sys.exit(1)

    # The rendered pages are derived from the PO files and not in git
    # (translation/v2/README.md). On a fresh clone nothing is under
    # i18n/<locale>/…/current/, and the pool would silently come back empty.
    # Say so, and say what to run, instead of reporting "0 eligible".
    unrendered = [loc for loc, cat in catalogues.items() if not is_rendered(cat)]
    if unrendered:
        for loc in unrendered:
            print(f"no rendered pages for {loc} under i18n/{loc}/docusaurus-plugin-content-docs/current/ — "
                  f"run: python3 translation/v2/render.py --locale {loc}", file=sys.stderr)
        sys.exit(2)

    # --leak-clean is exactly --max-leaks 0; an explicit --max-leaks relaxes it.
    max_leaks = 0 if args.leak_clean else args.max_leaks
    pool = build_pool(catalogues, args.min_lines, sections=sections,
                      max_leaks=max_leaks,
                      exclude_reviewed=args.exclude_reviewed)
    eligible_total = sum(len(v) for v in pool.values())

    # Drift focus tells the agent to spend its read on the irreducible class
    # (semantic drift + hallucination) and ignore kept-English leaks.
    focus = "drift" if (args.leak_clean or args.drift_focus) else None
    sample = draw(pool, args.per_locale, args.seed, focus=focus)

    if args.leak_clean:
        mode = "leak-clean-drift"
    elif max_leaks is not None:
        mode = f"maxleaks{max_leaks}" + ("-drift" if focus == "drift" else "")
    else:
        mode = "general"

    n_delta = sum(1 for f in sample if f["mode"] == "delta")
    payload = {
        "seed": args.seed,
        "per_locale": args.per_locale,
        "mode": mode,
        "eligible_total": eligible_total,
        "sample_size": len(sample),
        "delta_pages": n_delta,
        "delta_entries": sum(len(f.get("delta_entries", [])) for f in sample),
        "files": sample,
    }

    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"Wrote {len(sample)} pages (seed={args.seed}) → {args.out}"
              + (f" — {n_delta} in delta mode ({payload['delta_entries']} entries to judge)" if n_delta else ""))
        print(f"  eligible pool: {eligible_total} pages across {len(pool)} locales")

    if args.do_print or not args.out:
        by_loc: dict[str, list] = {}
        for f in sample:
            by_loc.setdefault(f["locale"], []).append(f"{f['rel']} ({f['lines']}L)")
        print(f"\nSample (seed={args.seed}, {len(sample)} pages, "
              f"pool={eligible_total}):")
        for loc in sorted(by_loc):
            print(f"  [{loc}] " + ", ".join(by_loc[loc]))


if __name__ == "__main__":
    main()
