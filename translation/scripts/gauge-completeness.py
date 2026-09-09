#!/usr/bin/env python3
"""
Ask a model whether each translation carries what its source carries.

Layer 2 of the meaning-and-completeness pass. `check-completeness.py` is a
deterministic sieve: free, corpus-wide, and blind to anything that does not
disturb shape, numbers or captions. This is the part that actually reads.

Read-only, by construction
--------------------------
This script never writes a msgstr. It writes batch files, reads the verdicts
back, and emits a findings file in `fix.py --fixes` shape. Repairs go through
`fix.py --apply` like every other review fix, so they still pass `check.py` and
still land with a provenance comment. (translation/v2/README.md, Hard rules.)

Batches live under `translation/v2/work/gauge/<locale>/`, deliberately NOT in
`work/<locale>/`: `fix.py --prepare` deletes `fix-*.json` there, and a gauge run
outstanding at the time would lose its batches. That has happened once already.

The blind design, and why it matters
------------------------------------
Batch items carry only `msgid`, `msgstr` and an opaque ordinal `n` (items are
shuffled before batching, so `n` says nothing about anything). The gauge is not
told which subcheck fired, or whether an entry was flagged at all — `--sample N`
mixes in randomly chosen entries the sieve passed, indistinguishable from the
rest.

That costs nothing and buys the two numbers we cannot otherwise get:

  precision   of the sieve — how many of its flags a reader agrees with
  miss rate   of the sieve — how many entries it passed are defective anyway

Tell the gauge what the sieve thought and it will mostly agree with it, and
both numbers become worthless. The calibration sample is the only honest
estimate of what the corpus actually looks like; the labelled eval set measures
recall on defects a *previous* method already found, which is a different and
much friendlier question.

Verdicts
--------
  COMPLETE    says what the source says
  MISSING     the source carries something the translation does not
  EXTRA       the translation carries something the source does not
  DIFFERENT   it is about something else — a different paragraph or question
  UNSURE      cannot tell without more context

UNSURE is a first-class answer, not a failure: an entry that is a bare heading
or half a sentence often cannot be judged alone, and a gauge pushed to guess
produces confident noise.

Usage:
    python translation/scripts/check-completeness.py --locale de --json de.json
    python translation/scripts/gauge-completeness.py --locale de --findings de.json \
        --sample 200 --prepare
    # fill translation/v2/work/gauge/de/manifest-gauge.json with the
    # translate-locale workflow (task "gauge"), then:
    python translation/scripts/gauge-completeness.py --locale de --collect \
        --out translation/v2/work/fixes-de-gauge.json
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

try:
    import polib
except ImportError:  # pragma: no cover
    sys.exit("polib is required: pip install polib")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GAUGE_WORK = REPO_ROOT / "translation" / "v2" / "work" / "gauge"


def rel(path: Path) -> str:
    """Repo-relative when it can be, absolute otherwise. relative_to()
    raises for anything outside the repo, which is every path a test
    hands it."""
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


VERDICTS = ("COMPLETE", "MISSING", "EXTRA", "DIFFERENT", "UNSURE")
DEFECTIVE = ("MISSING", "EXTRA", "DIFFERENT")

BATCH_ITEMS = 30
# Long entries are the ones worth reading and the ones that blow a batch's
# context. Split on estimated size as well as count.
BATCH_CHARS = 24000


INSTRUCTIONS = """\
# Completeness gauge — {locale}

Each batch is a JSON list of segments from doQumentation, a {locale} mirror of
IBM Quantum's Qiskit documentation. Every item has the English `msgid` and the
current translation `msgstr`.

Your ONLY question, for each item: **does the translation say what the source
says?** You are not editing, not improving, not rating style. A clumsy but
faithful translation is COMPLETE.

Answer with one verdict per item:

- `COMPLETE`  — carries the same content. Wording, word order and idiom may
                differ freely; that is what translation is.
- `MISSING`   — the source carries something the translation does not: a
                sentence, a clause, a list item, a heading, a figure.
- `EXTRA`     — the translation carries something the source does not, e.g. a
                neighbouring paragraph appended to it.
- `DIFFERENT` — it is about something else entirely: a different paragraph, or
                the answer to a different question. This is the serious one.
- `UNSURE`    — you cannot tell from the item alone.

Judge ONLY the item in front of you. Some items are perfectly fine; most are.
Do not invent a defect to look useful, and do not mark UNSURE to be safe — use
it when the item genuinely cannot be judged alone, such as a bare heading or a
sentence fragment.

Untranslated English is NOT by itself a defect here: proper names, code, and
terms this project keeps in English (Qiskit, Qubit, Gate, Circuit, Backend,
Transpiler, Session, Sampler, Estimator, PUB, IBM Quantum, QPU) are correct.
An entire prose sentence left in English IS `MISSING`.

For MISSING, EXTRA and DIFFERENT, add a short `note` naming what is wrong —
quote the source phrase that has no counterpart, or say what the translation is
actually about. Ten words is plenty. For COMPLETE and UNSURE leave `note` empty.
"""


def instructions(locale: str) -> str:
    return INSTRUCTIONS.format(locale=locale)


def po_files(locale: str) -> list[Path]:
    return sorted((REPO_ROOT / "i18n" / locale / "po").rglob("*.po"))


def load_findings(path: Path, locale: str) -> dict[str, set[int]]:
    """file -> indices the sieve flagged, for one locale."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, set[int]] = collections.defaultdict(set)
    for r in rows:
        if r.get("locale") not in (None, locale):
            continue
        out[r["file"]].add(r["index"])
    return out


def collect_items(locale: str, flagged: dict[str, set[int]], sample: int,
                  seed: int) -> list[dict]:
    """Flagged entries plus a random calibration sample, shuffled together so
    the gauge cannot tell them apart."""
    items: list[dict] = []
    pool: list[dict] = []
    for path in po_files(locale):
        rel_path = rel(path)
        want = flagged.get(rel_path)
        if want is None and sample <= 0:
            continue
        live = [e for e in polib.pofile(str(path)) if not e.obsolete and e.msgstr.strip()]
        for i, e in enumerate(live):
            row = {"_id": f"{rel_path}#{i}", "_flagged": bool(want and i in want),
                   "msgid": e.msgid, "msgstr": e.msgstr}
            if row["_flagged"]:
                items.append(row)
            elif sample > 0 and e.msgstr.strip() != e.msgid.strip():
                pool.append(row)

    rng = random.Random(seed)
    if sample > 0 and pool:
        items.extend(rng.sample(pool, min(sample, len(pool))))
    rng.shuffle(items)
    return items


def split_batches(items: list[dict]) -> list[list[dict]]:
    out, cur, size = [], [], 0
    for it in items:
        n = len(it["msgid"]) + len(it["msgstr"])
        if cur and (len(cur) >= BATCH_ITEMS or size + n > BATCH_CHARS):
            out.append(cur)
            cur, size = [], 0
        cur.append(it)
        size += n
    if cur:
        out.append(cur)
    return out


def prepare(locale: str, findings: Path | None, sample: int, seed: int,
            model: str) -> int:
    flagged = load_findings(findings, locale) if findings else {}
    items = collect_items(locale, flagged, sample, seed)
    if not items:
        print(f"{locale}: nothing to gauge", file=sys.stderr)
        return 1

    outdir = GAUGE_WORK / locale
    outdir.mkdir(parents=True, exist_ok=True)
    for old in list(outdir.glob("gauge-*.json")) + list(outdir.glob("manifest-gauge.json")):
        old.unlink()
    (outdir / "instructions-gauge.md").write_text(instructions(locale), encoding="utf-8")

    manifest = []
    for n, batch in enumerate(split_batches(items)):
        name = f"gauge-{n:03d}-{model}.json"
        # "n" is an opaque ordinal the verdict list must echo back. Three of the
        # first seven ro batches returned N+1 objects — one extra COMPLETE, no
        # marker saying which — and a positional join would have attributed
        # every judgement after the insertion to the wrong entry. The ordinal
        # says nothing about whether an entry was flagged (items are shuffled),
        # so it costs no blindness.
        body = [{"n": i, "msgid": it["msgid"], "msgstr": it["msgstr"]}
                for i, it in enumerate(batch)]
        (outdir / name).write_text(
            "[\n" + ",\n".join(json.dumps(b, ensure_ascii=False) for b in body) + "\n]\n",
            encoding="utf-8")
        (outdir / f"gauge-{n:03d}-{model}.ids.json").write_text(
            json.dumps([{"id": it["_id"], "flagged": it["_flagged"]} for it in batch], indent=0),
            encoding="utf-8")
        manifest.append({
            "file": rel(outdir / name),
            "out": rel(outdir / f"gauge-{n:03d}-{model}.out.json"),
            "model": model,
            "items": len(batch),
            "chars": sum(len(b["msgid"]) + len(b["msgstr"]) for b in body),
        })

    (outdir / "manifest-gauge.json").write_text(json.dumps({
        "locale": locale,
        "task": "gauge",
        "instructions": rel(outdir / "instructions-gauge.md"),
        "instructions_text": instructions(locale),
        "batches": manifest,
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    n_flag = sum(1 for it in items if it["_flagged"])
    print(f"{locale}: {len(items)} entries ({n_flag} flagged, {len(items) - n_flag} calibration) "
          f"in {len(manifest)} batch(es)")
    print(f"manifest: {rel(outdir / 'manifest-gauge.json')}")
    return 0


def _verdict_of(v) -> tuple[str, str]:
    if isinstance(v, str):
        v = {"verdict": v}
    verdict = str(v.get("verdict", "")).strip().upper()
    # An unrecognised reply becomes UNSURE, never a defect: guessing DIFFERENT
    # from a malformed answer would invent review work out of nothing.
    return (verdict if verdict in VERDICTS else "UNSURE"), str(v.get("note", "")).strip()


def read_verdicts(outdir: Path) -> tuple[list[dict], list[str]]:
    """Join each batch's verdicts back onto its ids by the ordinal the batch
    carried, falling back to position only when the whole list lines up.

    Never zip a mismatched list short: a verdict list with one object too many
    (which happened on 3 of the first 7 batches) would otherwise attribute every
    judgement after the insertion to the wrong entry — a silent corruption that
    reads as a plausible finding."""
    rows: list[dict] = []
    problems: list[str] = []
    for ids_path in sorted(outdir.glob("gauge-*.ids.json")):
        out_path = Path(str(ids_path).replace(".ids.json", ".out.json"))
        ids = json.loads(ids_path.read_text(encoding="utf-8"))
        if not out_path.exists():
            problems.append(f"{out_path.name}: not filled")
            continue
        try:
            got = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{out_path.name}: unparseable ({exc})")
            continue
        if not isinstance(got, list):
            problems.append(f"{out_path.name}: not a JSON list — discarded")
            continue

        by_n = {}
        for v in got:
            if isinstance(v, dict) and isinstance(v.get("n"), int):
                by_n.setdefault(v["n"], v)
        if len(by_n) >= len(ids):
            missing = [i for i in range(len(ids)) if i not in by_n]
            if missing:
                problems.append(
                    f"{out_path.name}: no verdict for item(s) {missing[:5]} — those skipped")
            for i, meta in enumerate(ids):
                if i not in by_n:
                    continue
                verdict, note = _verdict_of(by_n[i])
                rows.append({**meta, "verdict": verdict, "note": note})
            if len(got) != len(ids):
                problems.append(
                    f"{out_path.name}: {len(got)} object(s) for {len(ids)} item(s), "
                    "realigned on the batch ordinal")
            continue

        if len(got) == len(ids):
            for meta, v in zip(ids, got):
                verdict, note = _verdict_of(v)
                rows.append({**meta, "verdict": verdict, "note": note})
            continue

        problems.append(
            f"{out_path.name}: {len(got)} verdict(s) for {len(ids)} item(s) and no usable "
            "ordinals — batch discarded")
    return rows, problems


def collect(locale: str, out_path: Path | None) -> int:
    outdir = GAUGE_WORK / locale
    if not outdir.exists():
        print(f"{locale}: no gauge run under {outdir}", file=sys.stderr)
        return 1
    rows, problems = read_verdicts(outdir)
    for p in problems:
        print(f"WARNING {p}", file=sys.stderr)
    if not rows:
        print(f"{locale}: no verdicts read", file=sys.stderr)
        return 1

    flagged = [r for r in rows if r["flagged"]]
    calib = [r for r in rows if not r["flagged"]]
    print(f"{locale}: {len(rows)} verdict(s) — {len(flagged)} on sieve flags, "
          f"{len(calib)} on calibration entries")
    for label, group in (("sieve flags", flagged), ("calibration", calib)):
        if not group:
            continue
        per = collections.Counter(r["verdict"] for r in group)
        bad = sum(per[v] for v in DEFECTIVE)
        print(f"  {label:12s} " + ", ".join(f"{v} {per[v]}" for v in VERDICTS if per[v])
              + f"   → defective {bad}/{len(group)} = {bad / len(group):.1%}")
    if flagged and calib:
        prec = sum(1 for r in flagged if r["verdict"] in DEFECTIVE) / len(flagged)
        miss = sum(1 for r in calib if r["verdict"] in DEFECTIVE) / len(calib)
        print(f"\n  sieve precision  {prec:.1%}   (flags the gauge agrees with)")
        print(f"  sieve miss rate  {miss:.1%}   (entries it passed that are defective anyway)")
        if miss:
            print(f"  → extrapolated defect load: {miss:.1%} of the locale's entries")

    if out_path:
        by_file: dict[str, list[dict]] = collections.defaultdict(list)
        for r in rows:
            if r["verdict"] not in DEFECTIVE:
                continue
            rel, idx = r["id"].rsplit("#", 1)
            by_file[rel].append({"idx": int(idx), "verdict": r["verdict"], "note": r["note"]})
        fixes = []
        for rel, hits in sorted(by_file.items()):
            page = rel.split("/po/", 1)[-1].replace(".po", ".mdx")
            fixes.append({
                "rel": page,
                "note": (
                    f"Completeness gauge: {len(hits)} entr(y/ies) on this page were read "
                    "against their English source and judged not to carry the same content. "
                    "Each flagged item's `review` field says what is wrong. Fix those; copy "
                    "every other entry back verbatim."
                ),
                "examples": [{"source": "", "translation": "", "why": ""} for _ in hits],
                "_gauge": hits,
            })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(fixes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {sum(len(f['_gauge']) for f in fixes)} finding(s) over "
              f"{len(fixes)} page(s) to {out_path}")
        print("NOTE: examples need their source/translation text filled from the PO before "
              "fix.py can match them; use --emit-fixes for that.")
    return 0


def emit_fixes(locale: str, out_path: Path) -> int:
    """Same as --collect's file, but with each example's real source and
    translation text read out of the PO so `fix.py --prepare` can match it."""
    outdir = GAUGE_WORK / locale
    rows, problems = read_verdicts(outdir)
    for p in problems:
        print(f"WARNING {p}", file=sys.stderr)
    by_file: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r["verdict"] in DEFECTIVE:
            rel, idx = r["id"].rsplit("#", 1)
            by_file[rel].append({"idx": int(idx), "verdict": r["verdict"], "note": r["note"]})

    fixes = []
    for rel, hits in sorted(by_file.items()):
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        live = [e for e in polib.pofile(str(path)) if not e.obsolete and e.msgstr.strip()]
        examples = []
        for h in hits:
            if h["idx"] >= len(live):
                continue
            e = live[h["idx"]]
            examples.append({
                "source": e.msgid,
                "translation": e.msgstr,
                "why": f"{h['verdict']}: {h['note']}" if h["note"] else h["verdict"],
            })
        if not examples:
            continue
        fixes.append({
            "rel": rel.split("/po/", 1)[-1].replace(".po", ".mdx"),
            "note": (
                f"Completeness gauge: {len(examples)} entr(y/ies) on this page were read against "
                "their English source and judged not to carry the same content — the `review` "
                "field on each says what is wrong. Fix those and the same defect wherever else "
                "it occurs; copy every other entry back VERBATIM. An unreviewed edit to a "
                "correct translation is a defect of its own."
            ),
            "examples": examples,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{locale}: {sum(len(f['examples']) for f in fixes)} finding(s) over {len(fixes)} "
          f"page(s) → {rel(out_path)}")
    print(f"next: python3 translation/v2/fix.py --locale {locale} "
          f"--fixes {rel(out_path)} --prepare")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--locale", required=True)
    ap.add_argument("--findings", type=Path, help="check-completeness.py --json output")
    ap.add_argument("--sample", type=int, default=0,
                    help="calibration entries the sieve did NOT flag, mixed in blind")
    ap.add_argument("--seed", type=int, default=20260909)
    ap.add_argument("--model", default="sonnet", choices=("sonnet", "opus", "haiku"))
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--emit-fixes", type=Path, metavar="PATH",
                    help="write a fix.py --fixes file with the text filled in")
    ap.add_argument("--out", type=Path, help="with --collect: write the raw findings here")
    args = ap.parse_args()

    if args.prepare:
        if not args.findings and args.sample <= 0:
            ap.error("--prepare needs --findings and/or --sample")
        return prepare(args.locale, args.findings, args.sample, args.seed, args.model)
    if args.emit_fixes:
        return emit_fixes(args.locale, args.emit_fixes)
    if args.collect:
        return collect(args.locale, args.out)
    ap.error("pass --prepare, --collect or --emit-fixes")


if __name__ == "__main__":
    raise SystemExit(main())
