#!/usr/bin/env python3
"""
Draw a stratified, seeded, reproducible random sample of translation files for
the Tier-4 Opus deep-review spot-check.

This is the *selection* half of the spot-check. It is deterministic (seeded) so
a run is reproducible, and stratified (round-robin across locales × sections)
so a small sample still touches every language. It writes a JSON sample the
`opus-deep-review` workflow consumes via `args`.

Eligibility (same gating as Tier-3 — never waste Opus on un-reviewable files):
  - genuine translation (no untranslated-fallback marker)
  - FRESH: embedded source-hash matches current EN (STALE/UNKNOWN excluded)
  - validation == PASS and lint in (CLEAN, WARNINGS)
  - not a tiny stub/index file (>= --min-lines, default 40)
Pool is UNIFORM over eligible files (PASS and STALE_REFRESH treated equally),
per the chosen sampling design.

Usage:
    python translation/scripts/sample-deep-review.py \
        --per-locale 5 --seed 20260604 --out /tmp/opus-sample.json
    # then feed the file to the workflow:
    #   Workflow({ name: "opus-deep-review", args: <contents of the JSON> })

    # dry preview (prints the sample, writes nothing):
    python translation/scripts/sample-deep-review.py --per-locale 2 --seed 1 --print
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
STATUS_FILE = REPO_ROOT / "translation" / "status.json"
DOCS_DIR = REPO_ROOT / "docs"
I18N_DIR = REPO_ROOT / "i18n"

MAIN_LOCALES = [
    "de", "es", "uk", "ja", "fr", "it", "pt", "tl", "ar", "he",
    "ms", "id", "th", "ko", "pl", "ro", "cs",
]
DIALECTS = ["swg", "bad", "bar", "ksh", "nds", "gsw", "sax", "bln", "aut"]

SECTIONS = ["tutorials/", "guides/", "learning/courses/", "learning/modules/"]
FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}"

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


def _import_freshness():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "freshness", SCRIPTS_DIR / "check-translation-freshness.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_freshness = _import_freshness()


def _tr_path(locale: str, rel: str) -> Path:
    return I18N_DIR / locale / "docusaurus-plugin-content-docs" / "current" / rel


def is_fresh(locale: str, rel: str) -> bool:
    en = DOCS_DIR / rel
    tr = _tr_path(locale, rel)
    if not (en.exists() and tr.exists()):
        return False
    embedded = _freshness.extract_embedded_hash(tr.read_text(encoding="utf-8"))
    if embedded is None:
        return False
    return embedded == _freshness.compute_source_hash(en.read_text(encoding="utf-8"))


def section_of(rel: str) -> str:
    for s in SECTIONS:
        if rel.startswith(s):
            return s
    return "other/"


# Locale-agnostic leak proxy: capitalized-English domain nouns in prose. These
# tokens are identical across Latin-script locales, so this flags leakage without
# a per-locale glossary. (Non-Latin scripts won't render these — for ja/ko/ar/
# he/th the count is ~0, so --leak-clean simply doesn't exclude them, which is
# the safe default.)
_LEAK_PROXY = re.compile(r"\b(Gate|Gates|Circuit|Circuits|Qubit|Qubits)\b")


def _leak_count(text: str) -> int:
    """Capitalized-English-leak count in prose (uses the detector's prose strip)."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chk", SCRIPTS_DIR / "check-glossary-consistency.py")
        chk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chk)
        prose = chk.to_prose(text)
    except Exception:
        prose = text
    return len(_LEAK_PROXY.findall(prose))


def build_pool(status: dict, locales: list[str], min_lines: int,
               sections: tuple[str, ...] | None = None,
               max_leaks: int | None = None,
               exclude_reviewed: bool = False) -> dict:
    """{locale: [(rel, section, lines), ...]} of eligible files.

    Optional focused filters (for the 'clean-file drift' run):
      sections          — only these section prefixes (e.g. course+module)
      max_leaks         — include only files with <= this many capitalized-English
                          leaks (0 == the strict 'leak-clean' run; None == no cap).
                          Relaxing to a small N (e.g. 2) reaches the lightly-leaky
                          files that strict leak-clean starves once the 0-leak pool
                          drains — pair with a deterministic leak sweep.
      exclude_reviewed  — skip files already carrying a review_opus verdict
    """
    pool: dict[str, list] = {}
    for loc in locales:
        entries = status.get(loc, {})
        eligible = []
        for rel, e in entries.items():
            if e.get("validation") != "PASS":
                continue
            if e.get("lint") not in ("CLEAN", "WARNINGS"):
                continue
            if sections and not rel.startswith(sections):
                continue
            if exclude_reviewed and e.get("review_opus"):
                continue
            tr = _tr_path(loc, rel)
            if not tr.exists():
                continue
            text = tr.read_text(encoding="utf-8")
            if FALLBACK_MARKER in text:
                continue
            lines = len(text.splitlines())
            if lines < min_lines:
                continue
            if not is_fresh(loc, rel):
                continue
            if max_leaks is not None and _leak_count(text) > max_leaks:
                continue
            eligible.append((rel, section_of(rel), lines))
        if eligible:
            pool[loc] = eligible
    return pool


def draw(pool: dict, per_locale: int, seed: int, focus: str | None = None) -> list[dict]:
    """Stratified within locale: round-robin across sections, seeded-random
    within each section bucket. Reproducible for a given (pool, seed)."""
    rng = random.Random(seed)
    sample = []
    for loc in sorted(pool):  # sorted → deterministic locale order
        files = pool[loc]
        # bucket by section
        buckets: dict[str, list] = {}
        for rel, sec, lines in files:
            buckets.setdefault(sec, []).append((rel, sec, lines))
        for sec in buckets:
            rng.shuffle(buckets[sec])
        # round-robin across sections until we have per_locale (or run out)
        order = sorted(buckets)  # deterministic section order
        picked = []
        i = 0
        while len(picked) < per_locale and any(buckets[s] for s in order):
            sec = order[i % len(order)]
            if buckets[sec]:
                picked.append(buckets[sec].pop())
            i += 1
        for rel, sec, lines in picked:
            rec = {
                "locale": loc,
                "rel": rel,
                "section": sec,
                "lines": lines,
                "locale_name": LOCALE_NAME.get(loc, loc),
                "register": REGISTER.get(loc, "informal register"),
                "tier3_verdict": _STATUS_CACHE.get(loc, {}).get(rel, {}).get("review", "?"),
            }
            if focus:
                rec["focus"] = focus
            sample.append(rec)
    return sample


# populated in main() before draw() so each sample row can carry its prior
# Tier-3 verdict as context for the Opus agent.
_STATUS_CACHE: dict = {}


def main():
    ap = argparse.ArgumentParser(description="Stratified seeded sample for Opus deep review")
    ap.add_argument("--per-locale", type=int, default=5,
                    help="files per locale (default 5)")
    ap.add_argument("--seed", type=int, required=True,
                    help="PRNG seed (reproducible; rotate for a fresh sample)")
    ap.add_argument("--min-lines", type=int, default=40,
                    help="skip stubs shorter than this (default 40)")
    ap.add_argument("--include-dialects", action="store_true",
                    help="also sample the 9 German dialects (default: main 17 only)")
    ap.add_argument("--sections", default=None,
                    help="comma-separated section prefixes to restrict to "
                         "(e.g. 'learning/courses/,learning/modules/')")
    ap.add_argument("--leak-clean", action="store_true",
                    help="only files with 0 capitalized-English leaks — isolates "
                         "Opus on semantic drift, not leakage (== --max-leaks 0)")
    ap.add_argument("--max-leaks", type=int, default=None,
                    help="include files with <= N capitalized-English leaks "
                         "(reaches lightly-leaky files once the 0-leak pool drains; "
                         "pair with a deterministic leak sweep). Overridden to 0 by "
                         "--leak-clean.")
    ap.add_argument("--drift-focus", action="store_true",
                    help="force the drift-focused Opus prompt even without "
                         "--leak-clean (tells the agent to ignore kept-English "
                         "leaks and hunt semantic drift). Implied by --leak-clean.")
    ap.add_argument("--exclude-reviewed", action="store_true",
                    help="skip files already carrying a review_opus verdict")
    ap.add_argument("--out", help="write sample JSON here")
    ap.add_argument("--print", action="store_true", dest="do_print",
                    help="print the sample to stdout")
    args = ap.parse_args()

    if not STATUS_FILE.exists():
        print("status.json not found", file=sys.stderr)
        sys.exit(1)
    status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    _STATUS_CACHE.update(status)

    locales = MAIN_LOCALES + (DIALECTS if args.include_dialects else [])
    sections = tuple(s for s in (args.sections or "").split(",") if s) or None
    # --leak-clean is exactly --max-leaks 0; an explicit --max-leaks relaxes it.
    max_leaks = 0 if args.leak_clean else args.max_leaks
    pool = build_pool(status, locales, args.min_lines, sections=sections,
                      max_leaks=max_leaks,
                      exclude_reviewed=args.exclude_reviewed)
    eligible_total = sum(len(v) for v in pool.values())

    # Drift focus tells the agent to spend its read on the irreducible class
    # (semantic drift + hallucination) and ignore kept-English leaks. It's the
    # default under leak-clean; with --max-leaks the few leaks are swept
    # deterministically, so keep the drift prompt when --drift-focus is set.
    focus = "drift" if (args.leak_clean or args.drift_focus) else None
    sample = draw(pool, args.per_locale, args.seed, focus=focus)

    if args.leak_clean:
        mode = "leak-clean-drift"
    elif max_leaks is not None:
        mode = f"maxleaks{max_leaks}" + ("-drift" if focus == "drift" else "")
    else:
        mode = "general"

    payload = {
        "seed": args.seed,
        "per_locale": args.per_locale,
        "mode": mode,
        "eligible_total": eligible_total,
        "sample_size": len(sample),
        "files": sample,
    }

    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"Wrote {len(sample)} files (seed={args.seed}) → {args.out}")
        print(f"  eligible pool: {eligible_total} files across {len(pool)} locales")

    if args.do_print or not args.out:
        by_loc: dict[str, list] = {}
        for f in sample:
            by_loc.setdefault(f["locale"], []).append(f"{f['rel']} ({f['lines']}L)")
        print(f"\nSample (seed={args.seed}, {len(sample)} files, "
              f"pool={eligible_total}):")
        for loc in sorted(by_loc):
            print(f"  [{loc}] " + ", ".join(by_loc[loc]))


if __name__ == "__main__":
    main()
