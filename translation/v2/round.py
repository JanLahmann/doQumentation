#!/usr/bin/env python3
"""A review round as one resumable state machine, one git worktree per locale.

    python3 translation/v2/round.py start --locales ar,pl --per-locale 80 --order risk \\
        --handle JanLahmann --claim 725
    #   run each printed Workflow; then, per locale:
    python3 translation/v2/round.py collect  --seed S --locale ar --run wf_… [--run wf_…]
    python3 translation/v2/round.py gauge    --seed S --locale ar --result gauge.json   # only if it had FAILs
    python3 translation/v2/round.py prepare  --seed S --locale ar                       # bakes the fill
    python3 translation/v2/round.py finish   --seed S --locale ar                       # apply, render, gates
    python3 translation/v2/round.py accept   --seed S --locale ar --note "numbers written as words"
    python3 translation/v2/round.py repair   --seed S --locale ar --spec spec.json    # a real loss: flagged pass
    python3 translation/v2/round.py verify   --seed S --locale ar [--run wf_…]          # re-read the FAIL pages' fixes
    python3 translation/v2/round.py ship     --seed S --locale ar                       # commit, push, PR body
    python3 translation/v2/round.py status   --seed S
    python3 translation/v2/round.py cleanup  --seed S --locale ar                       # after the PR merged

Why a driver. A round used to run in one shared checkout and be copied into a
branch at the end, with its state in a dozen hand-kept files. Every incident
of the rounds of 2026-09-22..30 came from that:

- a stale shared checkout sampled pl pages as unreviewed that main had read;
- a branch carried another round's unmerged changes (82 files, not 41),
  and a round could not ship until the previous one merged;
- the ratchet compared against an old baseline, so commit messages claimed
  keys "added" that main already had;
- waiters triggered on stale logs; a second fix pass overwrote the first's
  log; a hand-kept results file in the wrong format put "upheld 1" in a
  message where the gauge had upheld 5.

Here each locale gets its own worktree on a branch from origin/main, created
at `start` and used for every step, so nothing is ever copied between
checkouts and no round depends on another. Every step runs the worktree's
own scripts (they locate the repo from their own path), records what it did
in one JSON state file, and refuses to run out of order. Commit messages and
PR bodies are built from that state and the records, never typed.

State lives in translation/v2/work/rounds/<seed>/ (ignored), next to the
baked workflow scripts. Worktrees default to $TMPDIR/doq-rounds/.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROUNDS = REPO / "translation" / "v2" / "work" / "rounds"
PY = sys.executable
# The Workflow tool rejects a script over 512 KiB; a delta-heavy sample of 80
# pages inlines ~600 KiB of entries. Stay under with a margin.
MAX_SCRIPT_BYTES = 450_000


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and r.returncode:
        sys.exit(f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def state_dir(seed: str) -> Path:
    return ROUNDS / str(seed)


def load_state(seed: str) -> dict:
    f = state_dir(seed) / "state.json"
    if not f.exists():
        sys.exit(f"no round {seed}: {f} does not exist")
    return json.loads(f.read_text(encoding="utf-8"))


def save_state(st: dict) -> None:
    d = state_dir(st["seed"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "state.json.tmp"
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(d / "state.json")


def locale_state(st: dict, locale: str, expect: str | tuple[str, ...]) -> dict:
    if locale not in st["locales"]:
        sys.exit(f"{locale} is not in round {st['seed']} ({', '.join(st['locales'])})")
    ls = st["locales"][locale]
    allowed = (expect,) if isinstance(expect, str) else expect
    if ls["stage"] not in allowed:
        sys.exit(f"{locale} is at stage '{ls['stage']}', this step needs {' or '.join(allowed)}")
    return ls


def script(wt: Path, rel: str) -> str:
    return str(wt / rel)


def records_path(st: dict, locale: str) -> Path:
    return Path(st["locales"][locale]["worktree"]) / "translation" / "reviews" / \
        f"opus-{st['seed']}-{locale}-{st['handle']}.json"


def baseline_path(wt: Path) -> Path:
    d = wt / "translation" / "eval" / "completeness-baseline"
    return d if d.is_dir() else wt / "translation" / "eval" / "completeness-baseline.json"


# Keys whose values are repo-relative paths an agent will Read or Write.
PATH_KEYS = ("pair", "file", "out", "instructions")


def absolutize(obj, wt: Path):
    """Rewrite every repo-relative path under PATH_KEYS to an absolute path in
    the worktree. Agents resolve relative paths against the session's working
    directory, which is the main checkout, not the worktree: left relative, a
    reader reads that checkout's stale pair file and a fixer writes its output
    there. (Caught by the driver's first end-to-end test.)"""
    if isinstance(obj, dict):
        return {k: (str(wt / v) if k in PATH_KEYS and isinstance(v, str) and v and not v.startswith("/")
                    else absolutize(v, wt)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [absolutize(x, wt) for x in obj]
    return obj


def absolutize_file(path: Path, wt: Path) -> None:
    path.write_text(json.dumps(absolutize(json.loads(path.read_text(encoding="utf-8")), wt),
                               ensure_ascii=False, indent=1), encoding="utf-8")


def absolutize_baked(js: Path, wt: Path, keys: tuple[str, ...] = ("pair",)) -> None:
    """The same for a baked gauge script, whose payload is one JSON literal.
    Only `pair` there is a path: its `file` is the page name the gauge's
    result reports back, and must stay as the records have it."""
    text = js.read_text(encoding="utf-8")
    for key in keys:
        text = re.sub(rf'"{key}": ?"(?!/)([^"]+)"', lambda m: f'"{key}": "{wt / m.group(1)}"', text)
    js.write_text(text, encoding="utf-8")


def workflow_call(path: Path) -> str:
    return f'Workflow({{ scriptPath: "{path}" }})'


# ---------------------------------------------------------------------------
# pure helpers (tested)
# ---------------------------------------------------------------------------

def split_sample(sample: dict, sizes: list[int], limit: int) -> list[dict]:
    """Split a sample's files into consecutive parts whose estimated baked size
    (`sizes`, one per file, plus a fixed overhead) stays under `limit`."""
    parts, cur, cur_size = [], [], 0
    overhead = 60_000
    for f, n in zip(sample["files"], sizes):
        if cur and cur_size + n + overhead > limit:
            parts.append(cur)
            cur, cur_size = [], 0
        cur.append(f)
        cur_size += n
    if cur:
        parts.append(cur)
    return [{**sample, "files": p, "sample_size": len(p)} for p in parts]


def parse_apply(text: str, locale: str) -> dict:
    m = re.search(rf"^{locale}: accepted (\d+), rejected (\d+), unfilled (\d+)(?:, unchanged (\d+))?", text, re.M)
    if not m:
        return {"ok": False, "log": text[-2000:]}
    return {"ok": True, "accepted": int(m.group(1)), "rejected": int(m.group(2)),
            "unfilled": int(m.group(3)), "unchanged": int(m.group(4) or 0),
            "rejects": re.findall(r"^REJECT (\S+): (.*)$", text, re.M),
            "english": re.findall(r"^WARNING (\S+): translation replaced by the English source.*?: (.*)$",
                                  text, re.M)}


def parse_ratchet(text: str, locale: str) -> list[str]:
    """The NEW-finding lines of a ratchet run (empty when it is clean)."""
    return [l.strip() for l in text.splitlines() if l.startswith(f"  {locale} ")]


def _cut(text: str, n: int) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def short(rel: str) -> str:
    return rel.replace("learning/courses/", "").removesuffix(".mdx")


def fail_line(rec: dict) -> str:
    exs = sorted(rec.get("examples") or [],
                 key=lambda e: (e.get("type") or "") not in ("Drift", "Terminology", "Mistranslation"))
    for e in exs:
        why = (e.get("why") or "").strip()
        if why:
            quote = (f'"{_cut(e.get("source", ""), 90)}" was «{_cut(e.get("translation", ""), 90)}». '
                     if e.get("source") and e.get("translation") else "")
            return f"- {short(rec['file'])}: {quote}{_cut(why, 260)}"
    return f"- {short(rec['file'])}"


def build_message(locale: str, seed: str, records: list[dict], ls: dict, claim: str | None,
                  trailers: list[str]) -> tuple[str, str]:
    """(commit message, PR body) from the records and the locale's state."""
    c = collections.Counter(r["verdict"] for r in records)
    n = len(records)
    fails = [r for r in records if r["verdict"] == "FAIL"]
    upheld = [r for r in fails if r.get("gauge") != "refuted"]
    refuted = [r for r in fails if r.get("gauge") == "refuted"]
    lines = [f"Opus page read of {n} pages: {c['FAIL']} FAIL, {c['MINOR_ISSUES']} MINOR_ISSUES, {c['PASS']} PASS"]
    if not fails:
        lines[0] += ", so no gauge run."
    else:
        g = []
        if upheld:
            g.append(f"upheld {len(upheld)}")
        if refuted:
            g.append(f"refuted {len(refuted)} ({', '.join(short(r['file']) for r in refuted)}; fixed as MINOR)")
        lines[0] += "; the gauge " + " and ".join(g) + (":" if upheld else ".")
        lines += [fail_line(r) for r in upheld]
    ap = ls.get("apply") or {}
    body = ["", f"The fix wave through fix.py accepted {ap.get('accepted', 0)} entries"
                f" ({ap.get('unchanged', 0)} sent back unchanged), {ap.get('rejected', 0)} rejected"]
    if ap.get("rejects"):
        body[-1] += " (" + "; ".join(f"{k}: {v}; left unchanged" for k, v in ap["rejects"]) + ")"
    body[-1] += "."
    if ap.get("english"):
        body.append(f"{len(ap['english'])} entr{'y' if len(ap['english']) == 1 else 'ies'} now equal"
                    f"{'s' if len(ap['english']) == 1 else ''} the English: "
                    + "; ".join(f"{k} ({_cut(v, 60)})" for k, v in ap["english"])
                    + (f". {ls['english_note']}" if ls.get("english_note") else
                       ". Each was checked against the review that asked for it."))
    if ls.get("accepted_findings"):
        body.append(f"{len(ls['accepted_findings'])} new completeness finding(s) were read and are sieve false "
                    f"positives ({ls.get('findings_note') or 'see the list'}); their keys are added to "
                    f"translation/eval/completeness-baseline/{locale}.txt.")
    if ls.get("verify"):
        v = ls["verify"]
        body.append(f"The fixes on the {v['pages']} FAIL page(s) were re-read before shipping: "
                    f"{v['summary']}.")
    for note in ls.get("notes", []):
        body.append(note)
    body += ["", "Gates clean on a fresh render: mdxcheck, lint, known mistranslations,",
             "wrong language, check.py audit; completeness ratchet no new findings.",
             f"Verdicts recorded in the {n} PO headers."]
    if claim:
        body += ["", f"Claim: #{claim}"]
    title = f"review({locale}): round {seed} — {n} pages, fix wave"
    commit = "\n".join([title, "", *lines, *body] + ([""] + trailers if trailers else [])) + "\n"
    pr = "\n".join([*lines, *body]) + "\n"
    return commit, pr


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------

def bake_review(st: dict, locale: str, wt: Path, sample_file: Path) -> list[str]:
    """Bake the sample into one or more opus-deep-review scripts, each under
    MAX_SCRIPT_BYTES (the Workflow limit is 512 KiB)."""
    d = state_dir(st["seed"])
    whole = d / f"review-{locale}-wf.js"
    run([PY, script(wt, "translation/scripts/make-opus-run.py"), "--sample", str(sample_file),
         "--out", str(whole)], wt)
    if whole.stat().st_size <= MAX_SCRIPT_BYTES:
        return [str(whole)]
    whole.unlink()
    sample = json.loads(sample_file.read_text(encoding="utf-8"))
    sizes = [len(json.dumps(f, ensure_ascii=False).encode()) for f in sample["files"]]
    out = []
    for i, part in enumerate(split_sample(sample, sizes, MAX_SCRIPT_BYTES)):
        pf = d / f"sample-{locale}-part{i}.json"
        pf.write_text(json.dumps(part, ensure_ascii=False, indent=1), encoding="utf-8")
        wf = d / f"review-{locale}-part{i}-wf.js"
        run([PY, script(wt, "translation/scripts/make-opus-run.py"), "--sample", str(pf), "--out", str(wf)], wt)
        if wf.stat().st_size > 512 * 1024:
            sys.exit(f"{wf} is still over 512 KiB; lower --per-locale")
        out.append(str(wf))
    return out


SEED_IN_RECORD = re.compile(r"opus-(\d{8,})-")


def used_seeds() -> set[str]:
    """Every seed a round has used: review records on origin/main and in
    this checkout, and local round state. The old default (today's date plus
    pid % 100) collided three times on 2026-09-30: 2026093024, 2026093027
    and 2026093035 each named an earlier round and a new one."""
    names = run(["git", "ls-tree", "-r", "--name-only", "-z", "origin/main", "translation/reviews"],
                REPO, check=False).stdout.split("\0")
    names += [p.name for p in (REPO / "translation" / "reviews").glob("opus-*.json")]
    seeds = {m.group(1) for n in names if (m := SEED_IN_RECORD.search(n))}
    if ROUNDS.is_dir():
        seeds |= {p.name for p in ROUNDS.iterdir() if p.is_dir()}
    return seeds


def new_seed(day: str, used: set[str], start: int) -> str:
    """`day` plus the first two-digit suffix from `start` (wrapping) that no
    round has used; three digits once all hundred are taken."""
    for width in (2, 3):
        n = 10 ** width
        for k in range(n):
            s = f"{day}{(start + k) % n:0{width}d}"
            if s not in used:
                return s
    sys.exit(f"no free seed for {day}; pass --seed")


def cmd_start(a) -> int:
    run(["git", "fetch", "-q", "origin", "main"], REPO)
    seed = a.seed or new_seed(date.today().strftime("%Y%m%d"), used_seeds(), os.getpid() % 100)
    if (state_dir(seed) / "state.json").exists():
        sys.exit(f"round {seed} exists; pick another --seed")
    wt_root = Path(a.worktrees or Path(tempfile.gettempdir()) / "doq-rounds")
    st = {"seed": str(seed), "handle": a.handle, "claim": a.claim, "trailers": a.trailer or [],
          "per_locale": a.per_locale, "order": a.order, "locales": {}}
    run(["git", "fetch", "-q", "origin", "main"], REPO)
    for loc in a.locales.split(","):
        wt = wt_root / f"{seed}-{loc}"
        branch = f"{a.branch_prefix}{seed}-{loc}"
        if wt.exists():
            sys.exit(f"{wt} exists; remove it or pick another --seed")
        run(["git", "worktree", "add", "-q", "-B", branch, str(wt), a.base], REPO)
        print(f"{loc}: worktree {wt} on {branch} ({a.base} {run(['git', 'rev-parse', '--short', 'HEAD'], wt).stdout.strip()})")
        run([PY, script(wt, "translation/v2/render.py"), "--locale", loc], wt)
        sample = state_dir(seed) / f"sample-{loc}.json"
        state_dir(seed).mkdir(parents=True, exist_ok=True)
        cmd = [PY, script(wt, "translation/scripts/sample-deep-review.py"), "--locale", loc,
               "--per-locale", str(a.per_locale), "--seed", str(seed), "--drift-focus",
               "--order", a.order, "--out", str(sample)]
        if a.exclude_reviewed:
            cmd.append("--exclude-reviewed")
        if a.pages:
            cmd += ["--pages", a.pages]
        r = run(cmd, wt)
        print("   " + " ".join(l.strip() for l in r.stdout.splitlines() if l.startswith("Wrote")))
        absolutize_file(sample, wt)
        wfs = bake_review(st, loc, wt, sample)
        st["locales"][loc] = {"stage": "review", "worktree": str(wt), "branch": branch,
                              "sample": str(sample), "review_workflows": wfs}
        save_state(st)
    print(f"\nround {seed}: run these, then `round.py collect --seed {seed} --locale <loc> --run <runId>...`")
    for loc, ls in st["locales"].items():
        for wf in ls["review_workflows"]:
            print(f"  {loc}: {workflow_call(Path(wf))}")
    return 0


def cmd_collect(a) -> int:
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "review")
    wt = Path(ls["worktree"])
    out = records_path(st, a.locale)
    cmd = [PY, script(wt, "translation/scripts/collect-opus-run.py"), "--sample", ls["sample"], "--out", str(out)]
    for r in a.run:
        cmd += ["--run", r]
    print(run(cmd, wt).stdout.strip().splitlines()[-1])
    recs = [r for r in json.loads(out.read_text(encoding="utf-8")) if r.get("locale", a.locale) == a.locale]
    out.write_text(json.dumps(recs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    want = json.loads(Path(ls["sample"]).read_text(encoding="utf-8"))["sample_size"]
    if len(recs) < want and not a.partial:
        sys.exit(f"{len(recs)} records for {want} sampled pages: a run is missing (pass every --run), "
                 f"or accept with --partial")
    c = collections.Counter(r["verdict"] for r in recs)
    print(f"{a.locale}: {len(recs)} records {dict(c)}")
    ls["records"] = str(out)
    if c["FAIL"]:
        wf = state_dir(st["seed"]) / f"gauge-{a.locale}-wf.js"
        run([PY, script(wt, "translation/scripts/make-gauge-run.py"), "--records", str(out),
             "--locale", a.locale, "--out", str(wf)], wt)
        absolutize_baked(wf, wt)
        ls.update(stage="gauge", gauge_workflow=str(wf))
        print(f"run {workflow_call(wf)}, save its result JSON, then `round.py gauge --result <file>`")
    else:
        ls["stage"] = "prepare"
        print("no FAIL: next `round.py prepare`")
    save_state(st)
    return 0


def cmd_gauge(a) -> int:
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "gauge")
    wt = Path(ls["worktree"])
    r = run([PY, script(wt, "translation/scripts/make-gauge-run.py"), "--records", ls["records"],
             "--locale", a.locale, "--record-result", a.result], wt)
    print(r.stdout.strip())
    ls["stage"] = "prepare"
    save_state(st)
    return 0


def bake_fill(st: dict, locale: str, wt: Path) -> Path:
    """The translate-locale workflow with this locale's fix manifest inlined."""
    src = (wt / ".claude" / "workflows" / "translate-locale.js").read_text(encoding="utf-8")
    manifest = json.loads((wt / "translation" / "v2" / "work" / locale / "manifest-fix.json").read_text(encoding="utf-8"))
    manifest = absolutize(manifest, wt)
    manifest["agentType"] = "translator"
    meta_end = src.index("\n", src.index("\n}\n", src.index("export const meta")) + 1)
    head, body = src[:meta_end + 1], src[meta_end + 1:]
    body = re.sub(r"(?<![\w.])args(?![\w])", "BAKED_ARGS", body)
    out = state_dir(st["seed"]) / f"fill-{locale}-wf.js"
    out.write_text(head + "\nconst BAKED_ARGS = " + json.dumps(manifest, ensure_ascii=False) + "\n" + body,
                   encoding="utf-8")
    return out


def cmd_prepare(a) -> int:
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "prepare")
    wt = Path(ls["worktree"])
    cmd = [PY, script(wt, "translation/v2/fix.py"), "--locale", a.locale, "--fixes", ls["records"], "--prepare"]
    if a.naturalness_min is not None:
        cmd += ["--naturalness-min", str(a.naturalness_min)]
    r = run(cmd, wt)
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(a.locale)))
    manifest = json.loads((wt / "translation" / "v2" / "work" / a.locale / "manifest-fix.json").read_text())
    if not manifest.get("batches"):
        ls.update(stage="triage", apply={"accepted": 0, "rejected": 0, "unfilled": 0, "unchanged": 0})
        print("nothing to fix: next `round.py finish` (gates only)")
    else:
        wf = bake_fill(st, a.locale, wt)
        ls.update(stage="fill", fill_workflow=str(wf))
        print(f"run {workflow_call(wf)}, then `round.py finish`")
    save_state(st)
    return 0


def ensure_node_modules(wt: Path) -> None:
    """mdxcheck.mjs imports the MDX compiler from node_modules, which a fresh
    worktree lacks; share the main checkout's (read-only use)."""
    link = wt / "node_modules"
    if link.exists():
        return
    common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], wt).stdout.strip()
    main_nm = Path(common).parent / "node_modules"
    if main_nm.is_dir():
        link.symlink_to(main_nm)
        # .gitignore's "node_modules/" does not match a symlink
        exclude = Path(common) / "info" / "exclude"
        if "/node_modules\n" not in (exclude.read_text() if exclude.exists() else ""):
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a") as fh:
                fh.write("/node_modules\n")


def gate(wt: Path, locale: str, baseline: Path) -> tuple[list[str], list[str], dict]:
    """Render and run every gate in the worktree. (failed gates, new ratchet
    findings, log). Restores tracked pages the render overwrites."""
    failed, log = [], {}
    r = run([PY, script(wt, "translation/v2/render.py"), "--locale", locale], wt, check=False)
    log["render"] = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode:
        failed.append("render")
    ensure_node_modules(wt)
    files = sorted(str(p) for p in (wt / "i18n" / locale / "docusaurus-plugin-content-docs" / "current").rglob("*.mdx"))
    rc, tails = 0, []
    for i in range(0, len(files), 150):
        r = run(["node", script(wt, "translation/v2/mdxcheck.mjs"), *files[i:i + 150]], wt, check=False)
        rc |= r.returncode
        tails += [l for l in (r.stdout + r.stderr).splitlines() if l.strip()][-3:] if r.returncode else []
    log["mdxcheck"] = " | ".join(tails)[-600:] or "ok"
    if rc:
        failed.append("mdxcheck")
    for name in ("lint-translation", "check-known-mistranslations", "check-wrong-language", "audit-check-py"):
        r = run([PY, script(wt, f"translation/scripts/{name}.py"), "--locale", locale], wt, check=False)
        log[name] = (r.stdout.strip().splitlines() or [""])[-1]
        if name == "lint-translation":
            m = re.search(r"Errors:\s+(\d+)", r.stdout)
            if not m or int(m.group(1)):
                failed.append(name)
        elif r.returncode:
            failed.append(name)
    r = run([PY, script(wt, "translation/scripts/check-completeness.py"), "--locale", locale, "--limit", "0",
             "--baseline", str(baseline)], wt, check=False)
    new = parse_ratchet(r.stdout, locale)
    log["ratchet"] = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr
    tracked = [p for p in run(["git", "ls-files", "-z", f"i18n/{locale}/docusaurus-plugin-content-docs"], wt).stdout.split("\0") if p]
    if tracked:
        run(["git", "checkout", "--", *tracked], wt)
    return failed, new, log


def cmd_finish(a) -> int:
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, ("fill", "triage"))
    wt = Path(ls["worktree"])
    if ls["stage"] == "fill":
        r = run([PY, script(wt, "translation/v2/fix.py"), "--locale", a.locale, "--apply"], wt, check=False)
        text = r.stdout + r.stderr
        (state_dir(st["seed"]) / f"apply-{a.locale}-{len(ls.get('applies', [])) + 1}.log").write_text(text)
        ap = parse_apply(text, a.locale)
        if not ap["ok"]:
            sys.exit(f"fix.py --apply did not report counts:\n{ap['log']}")
        if ap["unfilled"]:
            sys.exit(f"{ap['unfilled']} entries unfilled: re-run the fill (resume its run), then finish again")
        prev = ls.get("apply")
        if prev:  # a follow-up pass on top of an earlier one: keep both in the record
            ap = {**ap, "accepted": prev["accepted"] + ap["accepted"], "rejected": ap["rejected"],
                  "unchanged": prev["unchanged"] + ap["unchanged"],
                  "english": prev.get("english", []) + ap["english"]}
        ls.setdefault("applies", []).append(text[-4000:])
        ls["apply"] = ap
        print(f"{a.locale}: accepted {ap['accepted']}, rejected {ap['rejected']}, unchanged {ap['unchanged']}")
        for k, v in ap["english"]:
            print(f"  now equals English: {k}: {v[:80]}")
        for k, v in ap["rejects"]:
            print(f"  REJECT {k}: {v}")
    failed, new, log = gate(wt, a.locale, baseline_path(wt))
    ls["gates"] = {"failed": failed, "log": log, "new_findings": new}
    for n in new:
        print(f"  NEW {n}")
    if failed:
        ls["stage"] = "triage"
        save_state(st)
        print(f"gates FAILED: {', '.join(failed)} — repair through fix.py, then finish again")
        for name in failed:
            print(f"  {name}: {log.get(name, '')[:400]}")
        return 1
    if new:
        ls["stage"] = "triage"
        save_state(st)
        print("Read each NEW finding against its English. Real loss: repair through fix.py --mode flagged and "
              "finish again. Sieve false positive: `round.py accept --note \"<why>\"`.")
        return 1
    if ls["apply"].get("english") and not ls.get("english_note"):
        print("Entries now equal their English: check each against the review that asked for it, then "
              "`round.py accept --english-note \"<why>\"` (or repair them).")
        ls["stage"] = "triage"
        save_state(st)
        return 1
    ls["stage"] = "verify" if any(r.get("verdict") == "FAIL" and r.get("gauge") != "refuted"
                                  for r in json.loads(Path(ls["records"]).read_text())) else "ship"
    save_state(st)
    print(f"gates clean. next: `round.py {ls['stage']}`")
    return 0


def cmd_accept(a) -> int:
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "triage")
    wt = Path(ls["worktree"])
    if a.english_note:
        ls["english_note"] = a.english_note
    new = (ls.get("gates") or {}).get("new_findings") or []
    if new:
        if not a.note:
            sys.exit("say why the findings are false positives: --note \"<why>\"")
        base = baseline_path(wt)
        if not base.is_dir():
            sys.exit(f"{base} is the legacy single file: accept needs the per-locale directory")
        r = run([PY, script(wt, "translation/scripts/check-completeness.py"), "--locale", a.locale, "--limit", "0",
                 "--baseline", str(base), "--accept-new"], wt)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
        ls["accepted_findings"] = new
        ls["findings_note"] = a.note
        ls["gates"]["new_findings"] = []
    for n in a.add_note or []:
        ls.setdefault("notes", []).append(n)
    save_state(st)
    print("accepted; run `round.py finish` again: from triage it re-gates without re-applying")
    return 0


def cmd_repair(a) -> int:
    """A follow-up pass through fix.py for entries the gates, the English
    warnings or the verification flagged: a spec of those entries (the
    reviewer-record format, `entry` numbers pinned), fixed in flagged mode."""
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "triage")
    wt = Path(ls["worktree"])
    r = run([PY, script(wt, "translation/v2/fix.py"), "--locale", a.locale, "--fixes", a.spec, "--prepare",
             "--mode", "flagged", "--naturalness-min", "1"], wt)
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(a.locale)))
    wf = bake_fill(st, a.locale, wt)
    ls.setdefault("notes", []).extend(a.add_note or [])
    ls.update(stage="fill", fill_workflow=str(wf))
    save_state(st)
    print(f"run {workflow_call(wf)}, then `round.py finish` (its counts add to the first pass)")
    return 0


def cmd_verify(a) -> int:
    """Re-read the fixes on the upheld FAIL pages before shipping (a delta read
    of the entries this wave wrote), so a fix that introduced a new defect is
    caught before the PR, not by the next round."""
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "verify")
    if a.skip:
        ls["stage"] = "ship"
        ls.setdefault("notes", []).append("The fixes on the FAIL pages were not re-read before shipping.")
        save_state(st)
        print("skipped; next `round.py ship`")
        return 0
    wt = Path(ls["worktree"])
    recs = json.loads(Path(ls["records"]).read_text())
    pages = sorted(r["file"] for r in recs if r["verdict"] == "FAIL" and r.get("gauge") != "refuted")
    d = state_dir(st["seed"])
    if not a.run:
        pf = d / f"verify-{a.locale}-pages.txt"
        pf.write_text("".join(f"{a.locale} {p}\n" for p in pages))
        sample = d / f"verify-{a.locale}.json"
        tomorrow = (date.today() + timedelta(days=1)).isoformat()   # count today's fixes as unread
        run([PY, script(wt, "translation/scripts/sample-deep-review.py"), "--locale", a.locale,
             "--per-locale", str(len(pages)), "--seed", st["seed"], "--drift-focus", "--pages", str(pf),
             "--as-of", tomorrow, "--include-fixes", "--out", str(sample)], wt)
        absolutize_file(sample, wt)
        wf = d / f"verify-{a.locale}-wf.js"
        run([PY, script(wt, "translation/scripts/make-opus-run.py"), "--sample", str(sample), "--out", str(wf)], wt)
        ls["verify_sample"] = str(sample)
        save_state(st)
        print(f"run {workflow_call(wf)}, then `round.py verify --run <runId>` "
              f"(or `--skip` to ship without it)")
        return 0
    out = d / f"verify-{a.locale}-records.json"
    run([PY, script(wt, "translation/scripts/collect-opus-run.py"), "--sample", ls["verify_sample"],
         "--out", str(out), *sum((["--run", r] for r in a.run), [])], wt)
    vrecs = json.loads(out.read_text())
    c = collections.Counter(r["verdict"] for r in vrecs)
    ls["verify"] = {"pages": len(pages), "summary": ", ".join(f"{v} {k}" for k, v in sorted(c.items())),
                    "fails": [r["file"] for r in vrecs if r["verdict"] == "FAIL"]}
    if ls["verify"]["fails"]:
        ls["stage"] = "triage"
        save_state(st)
        print(f"re-read still FAILs: {ls['verify']['fails']} — repair through fix.py (spec from {out}), finish again")
        return 1
    ls["stage"] = "ship"
    save_state(st)
    print(f"verified ({ls['verify']['summary']}); next `round.py ship`")
    return 0


def cmd_ship(a) -> int:
    st = load_state(a.seed)
    ls = locale_state(st, a.locale, "ship")
    wt = Path(ls["worktree"])
    recs = json.loads(Path(ls["records"]).read_text())
    run([PY, script(wt, "translation/scripts/review-translations.py"), "--record-opus", "--from-json",
         ls["records"], "--locale", a.locale], wt)
    rel_records = str(Path(ls["records"]).relative_to(wt))
    base = baseline_path(wt)
    base_rel = (str((base / f"{a.locale}.txt").relative_to(wt)) if base.is_dir() else str(base.relative_to(wt)))
    run(["git", "add", "--", f"i18n/{a.locale}/po"], wt)
    run(["git", "add", "-f", "--", rel_records], wt)
    if ls.get("accepted_findings"):
        run(["git", "add", "--", base_rel], wt)
    # -z: a page name with a space ("… 101 Hands-on.po") split into two "stray"
    # paths under .split(), and git quotes non-ASCII names without it.
    staged = [p for p in run(["git", "diff", "--cached", "--name-only", "-z"], wt).stdout.split("\0") if p]
    stray = [p for p in staged if not (p.startswith(f"i18n/{a.locale}/po/") or p in (rel_records, base_rel))]
    if stray:
        run(["git", "reset", "-q"], wt)
        sys.exit(f"staged files outside the intended set, aborting: {stray[:5]}")
    commit, pr = build_message(a.locale, st["seed"], recs, ls, st.get("claim"), st.get("trailers") or [])
    subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=wt, input=commit, text=True, check=True)
    body = pr + (("\n" + "\n".join(a.pr_footer) + "\n") if a.pr_footer else "")
    (state_dir(st["seed"]) / f"pr-{a.locale}.md").write_text(body, encoding="utf-8")
    ls.update(stage="pr", files=len(staged), title=commit.splitlines()[0])
    if not a.no_push:
        r = run(["git", "push", "-q", "-u", "origin", ls["branch"]], wt, check=False)
        if r.returncode:
            save_state(st)
            sys.exit(f"push failed; retry with `git -C {wt} push -u origin {ls['branch']}`\n{r.stderr[-500:]}")
    save_state(st)
    print(f"{a.locale}: committed {len(staged)} file(s) on {ls['branch']}; PR title: {ls['title']}\n"
          f"PR body: {state_dir(st['seed']) / f'pr-{a.locale}.md'}")
    return 0


def cmd_status(a) -> int:
    st = load_state(a.seed)
    for loc, ls in st["locales"].items():
        extra = ""
        if ls.get("apply"):
            extra = f"  accepted {ls['apply'].get('accepted')}, unchanged {ls['apply'].get('unchanged')}"
        print(f"{loc:3s} {ls['stage']:8s} {ls['branch']}{extra}")
    return 0


def cmd_cleanup(a) -> int:
    st = load_state(a.seed)
    ls = st["locales"][a.locale]
    wt = Path(ls["worktree"])
    if wt.exists():
        run(["git", "worktree", "remove", "--force", str(wt)], REPO)
    ls["stage"] = "done"
    save_state(st)
    print(f"{a.locale}: worktree removed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--locales", required=True, help="comma-separated")
    p.add_argument("--per-locale", type=int, default=40)
    p.add_argument("--order", choices=("random", "risk"), default="risk")
    p.add_argument("--exclude-reviewed", action="store_true")
    p.add_argument("--pages", help="restrict the pool (sample-deep-review.py --pages)")
    p.add_argument("--seed")
    p.add_argument("--handle", required=True, help="GitHub handle in the records file name")
    p.add_argument("--claim", help="claim issue number, for the message")
    p.add_argument("--trailer", action="append", help="commit trailer line (repeatable)")
    p.add_argument("--branch-prefix", default="claude/review-")
    p.add_argument("--worktrees")
    p.add_argument("--base", default="origin/main", help="start point of every locale branch")
    for name in ("collect", "gauge", "prepare", "finish", "accept", "repair", "verify", "ship", "cleanup"):
        q = sub.add_parser(name)
        q.add_argument("--seed", required=True)
        q.add_argument("--locale", required=True)
        if name == "collect":
            q.add_argument("--run", action="append", required=True)
            q.add_argument("--partial", action="store_true")
        if name == "gauge":
            q.add_argument("--result", required=True, help="the gauge workflow's result JSON, saved to a file")
        if name == "prepare":
            q.add_argument("--naturalness-min", type=int)
        if name == "repair":
            q.add_argument("--spec", required=True, help="fix spec: records with the entries to repair")
            q.add_argument("--add-note", action="append", help="a line for the message saying what was repaired")
        if name == "accept":
            q.add_argument("--note", help="why the new completeness findings are false positives")
            q.add_argument("--english-note", help="why the entries that now equal English are right")
            q.add_argument("--add-note", action="append", help="an extra line for the message")
        if name == "verify":
            q.add_argument("--run", action="append")
            q.add_argument("--skip", action="store_true", help="ship without the re-read (said in the message)")
        if name == "ship":
            q.add_argument("--no-push", action="store_true")
            q.add_argument("--pr-footer", action="append", help="line appended to the PR body (repeatable)")
    s = sub.add_parser("status")
    s.add_argument("--seed", required=True)
    a = ap.parse_args()
    return {"start": cmd_start, "collect": cmd_collect, "gauge": cmd_gauge, "prepare": cmd_prepare,
            "finish": cmd_finish, "accept": cmd_accept, "repair": cmd_repair, "verify": cmd_verify,
            "ship": cmd_ship,
            "status": cmd_status, "cleanup": cmd_cleanup}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
