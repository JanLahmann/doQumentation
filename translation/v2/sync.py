#!/usr/bin/env python3
"""The English sync as one loop for every locale: prepare, fill, finish.

    python3 translation/v2/sync.py prepare --from sync/upstream-content   # branch, English, POTs, worklists, batches
    #   ... fill work/<locale>/batch-*.out.json (translate-locale.js per locale, or translator agents)
    python3 translation/v2/sync.py status                                 # every batch: filled? valid? right count?
    python3 translation/v2/sync.py finish                                 # apply, render, gate, commit

`prepare` starts a branch from origin/main, takes the bot's "sync: upstream
content" commit onto it (the PR that commit opened carries no CI checks —
the workflow token cannot trigger them — so the sync merges through the PR
this loop produces instead, English and every locale together), regenerates
the POTs, and for every locale runs `update.py` and `translate.py --prepare`.
It prints how much each locale needs from a model; what needs none (copy,
split-block, mechanical) is already written.

`finish` applies every locale through check.py (a locale with a rejected or
unfilled batch stops the run, nothing is committed), asserts every worklist
is empty, renders and gates every locale, restores the tracked index pages
the render overwrites, stages exactly the POT tree and the locale PO trees,
and commits with a generated message. Push and open the PR yourself; the
command is printed.

Everything is a subprocess call into the sibling scripts: only translate.py
--apply writes a msgstr, only fix.py repairs, and the gates are the same
ones CONTRIBUTING-REVIEWS.md lists.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import po4a_io as io  # noqa: E402

V2 = Path(__file__).resolve().parent
SCRIPTS = io.REPO / "translation" / "scripts"
PY = sys.executable


def sh(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=io.REPO, text=True, capture_output=capture, check=check)


def git(*args: str, check: bool = True) -> str:
    return sh(["git", *args], check=check).stdout.strip()


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------

def start_branch(from_branch: str | None) -> str:
    """A branch from origin/main carrying the bot's sync commit, if any."""
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("working tree has tracked changes; commit or discard them first")
    git("fetch", "-q", "origin", "main")
    if from_branch:
        git("fetch", "-q", "origin", from_branch)
        tip = git("rev-parse", f"origin/{from_branch}")
        subject = git("log", "-1", "--format=%s", tip)
        m = re.search(r"→\s*([0-9a-f]{7,})", subject)
        sha = (m.group(1) if m else tip)[:8]
        branch = f"sync/english-{sha}"
        if git("branch", "--list", branch):
            sys.exit(f"branch {branch} already exists; delete it or pick another")
        git("checkout", "-q", "-b", branch, "origin/main")
        git("cherry-pick", tip)
        git("submodule", "update", "-q", "upstream-docs")
        print(f"{branch}: cherry-picked {subject}")
    else:
        branch = git("branch", "--show-current")
        print(f"staying on {branch} (no --from): the English in docs/ is taken as it is")
    return branch


def prepare_locale(locale: str) -> dict:
    wl = io.WORK_DIR / f"worklist-{locale}.json"
    up = sh([PY, str(V2 / "update.py"), "--locale", locale, "--json", str(wl)], check=False)
    pr = sh([PY, str(V2 / "translate.py"), "--locale", locale, "--prepare"], check=False)
    out = {"locale": locale, "ok": up.returncode == 0 and pr.returncode == 0,
           "update": up.stdout + up.stderr, "prepare": pr.stdout + pr.stderr}
    m = re.search(r"worklist: (\d+) entries on (\d+) page", up.stdout)
    out["entries"], out["pages"] = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    m = re.search(r"copy (\d+), split-block (\d+), mechanical (\d+)", pr.stdout)
    out["direct"] = sum(int(x) for x in m.groups()) if m else 0
    m = re.search(r"haiku (\d+), sonnet (\d+) in (\d+) batch", pr.stdout)
    out["model"], out["batches"] = (int(m.group(1)) + int(m.group(2)), int(m.group(3))) if m else (0, 0)
    return out


def cmd_prepare(args) -> int:
    start_branch(args.from_branch)
    ex = sh([PY, str(V2 / "extract.py"), "--check"], check=False)
    print(ex.stdout.strip().splitlines()[-1] if ex.stdout.strip() else ex.stderr)
    if ex.returncode:
        return 1
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(prepare_locale, args.locales))
    print(f"\n{'locale':7} {'entries':>8} {'pages':>6} {'no model':>9} {'to model':>9} {'batches':>8}")
    for r in rows:
        flag = "" if r["ok"] else "   FAILED — see below"
        print(f"{r['locale']:7} {r['entries']:8} {r['pages']:6} {r['direct']:9} {r['model']:9} {r['batches']:8}{flag}")
    for r in rows:
        if not r["ok"]:
            print(f"\n== {r['locale']}\n{r['update']}\n{r['prepare']}")
    todo = [r["locale"] for r in rows if r["batches"]]
    print(f"\ntotal: {sum(r['entries'] for r in rows)} entries, {sum(r['direct'] for r in rows)} written without a model, "
          f"{sum(r['model'] for r in rows)} to a model in {sum(r['batches'] for r in rows)} batch(es)")
    if todo:
        print("\nNext: fill each locale's work/<locale>/batch-*.out.json — one translate-locale.js run per locale\n"
              "(args = work/<locale>/manifest.json, plus \"agentType\": \"translator\"), or one translator agent per batch —\n"
              "then `sync.py status`, then `sync.py finish`.")
    else:
        print("\nNothing needs a model: run `sync.py finish`.")
    return 0 if all(r["ok"] for r in rows) else 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def check_outputs(manifest: dict) -> list[str]:
    """Problems with a locale's filled batches, one line each; [] when every
    batch has an output that is a JSON list of the right length."""
    problems = []
    for b in manifest.get("batches", []):
        out = io.REPO / (b.get("out") or b["file"].replace(".json", ".out.json"))
        if not out.exists():
            problems.append(f"{out.name}: not filled")
            continue
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f"{out.name}: not valid JSON ({str(e)[:60]}) — the agent wrote text instead of a list; redo it")
            continue
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            problems.append(f"{out.name}: not a list of strings")
        elif len(data) != b["items"]:
            problems.append(f"{out.name}: {len(data)} strings for {b['items']} items — apply would reject the batch; redo it")
    return problems


def cmd_status(args) -> int:
    bad = 0
    for loc in args.locales:
        mf = io.WORK_DIR / loc / "manifest.json"
        if not mf.exists():
            print(f"{loc}: no manifest (run prepare)")
            continue
        manifest = json.loads(mf.read_text(encoding="utf-8"))
        problems = check_outputs(manifest)
        n = len(manifest.get("batches", []))
        if problems:
            bad += 1
            print(f"{loc}: {n - len(problems)}/{n} batches ready")
            for p in problems:
                print(f"    {p}")
        else:
            print(f"{loc}: {n}/{n} batches ready")
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# finish
# ---------------------------------------------------------------------------

GATES = [
    ("mdxcheck", None),  # special-cased: needs the rendered file list
    ("lint", [PY, str(SCRIPTS / "lint-translation.py"), "--locale", "{loc}"]),
    ("known-mistranslations", [PY, str(SCRIPTS / "check-known-mistranslations.py"), "--locale", "{loc}"]),
    ("wrong-language", [PY, str(SCRIPTS / "check-wrong-language.py"), "--locale", "{loc}"]),
    ("check.py audit", [PY, str(SCRIPTS / "audit-check-py.py"), "--locale", "{loc}"]),
    ("completeness ratchet", [PY, str(SCRIPTS / "check-completeness.py"), "--locale", "{loc}", "--limit", "0",
                              "--baseline", str(io.REPO / "translation" / "eval" / "completeness-baseline.json")]),
]


def apply_locale(locale: str) -> dict:
    ap = sh([PY, str(V2 / "translate.py"), "--locale", locale, "--apply"], check=False)
    text = ap.stdout + ap.stderr
    m = re.search(r"accepted (\d+), rejected (\d+), unfilled (\d+)", text)
    acc, rej, unf = (int(x) for x in m.groups()) if m else (0, 1, 0)
    warnings = [l for l in text.splitlines() if l.startswith("WARNING")]
    withdrawn = re.search(r"review verdicts withdrawn (\d+)", text)
    up = sh([PY, str(V2 / "update.py"), "--locale", locale], check=False)
    m = re.search(rf"^{locale}: \d+ translated, (\d+) fuzzy, (\d+) untranslated", up.stdout, re.M)
    left = (int(m.group(1)) + int(m.group(2))) if m else -1
    return {"locale": locale, "accepted": acc, "rejected": rej, "unfilled": unf, "left": left,
            "withdrawn": int(withdrawn.group(1)) if withdrawn else 0, "warnings": warnings, "log": text}


def gate_locale(locale: str) -> dict:
    res = {"locale": locale, "failed": [], "log": {}}
    r = sh([PY, str(V2 / "render.py"), "--locale", locale], check=False)
    res["log"]["render"] = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr
    if r.returncode or " failed 0" not in res["log"]["render"]:
        res["failed"].append("render")
    for name, cmd in GATES:
        if name == "mdxcheck":
            files = sorted(str(p) for p in (io.I18N / locale / io.DOC_SUB).rglob("*.mdx"))
            out_lines, rc = [], 0
            for i in range(0, len(files), 150):
                r = sh(["node", str(V2 / "mdxcheck.mjs"), *files[i:i + 150]], check=False)
                out_lines += [l for l in r.stdout.splitlines() if l.startswith("mdxcheck:")]
                rc |= r.returncode
            res["log"][name] = "; ".join(out_lines)
            if rc:
                res["failed"].append(name)
            continue
        r = sh([c.format(loc=locale) for c in cmd], check=False)
        tail = (r.stdout.strip() or r.stderr.strip()).splitlines()[-1:] or [""]
        res["log"][name] = tail[0]
        if name == "lint":
            m = re.search(r"Errors:\s+(\d+)", r.stdout)
            if not m or int(m.group(1)):
                res["failed"].append(name)
        elif r.returncode:
            res["failed"].append(name)
    return res


def cmd_finish(args) -> int:
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        applied = list(pool.map(apply_locale, args.locales))
    stop = False
    for a in applied:
        flag = ""
        if a["rejected"] or a["unfilled"] or a["left"]:
            flag = "   STOP: " + ", ".join(x for x, n in (("rejected batches", a["rejected"]),
                                                          ("unfilled", a["unfilled"]),
                                                          ("entries still pending", a["left"])) if n)
            stop = True
        print(f"{a['locale']}: accepted {a['accepted']}, verdicts withdrawn {a['withdrawn']}{flag}")
        for w in a["warnings"]:
            print(f"    {w[:160]}")
    if stop:
        print("\nFix the locales marked STOP (redo the batch, or repair through fix.py) and run finish again. Nothing committed.")
        return 1
    if any(a["warnings"] for a in applied):
        print("\nRead every WARNING above: an entry that now equals its English source is right for code and names,"
              " and a lost translation for anything else — repair those through fix.py --flagged-only before committing.")
        if not args.accept_warnings:
            print("Re-run with --accept-warnings once they are checked. Nothing committed.")
            return 1

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        gated = list(pool.map(gate_locale, args.locales))
    bad = False
    for g in gated:
        status = "ok" if not g["failed"] else "FAILED " + ", ".join(g["failed"])
        print(f"{g['locale']}: {status}")
        for name, line in g["log"].items():
            if name in g["failed"] or args.verbose:
                print(f"    {name}: {line[:160]}")
        bad |= bool(g["failed"])
    # render.py overwrites the few tracked pages under current/ (index.mdx and
    # friends); they are derived and must not ride along.
    tracked = git("ls-files", *[f"i18n/{l}/{io.DOC_SUB}" for l in args.locales]).split()
    if tracked:
        git("checkout", "--", *tracked)
    if bad:
        print("\nGates failed; nothing committed.")
        return 1
    if args.no_commit:
        return 0

    paths = ["translation/v2/pot"] + [f"i18n/{l}/po" for l in args.locales]
    git("add", "--", *paths)
    staged = git("diff", "--cached", "--name-only").split()
    stray = [p for p in staged if not (p.startswith("translation/v2/pot/") or
                                       any(p.startswith(f"i18n/{l}/po/") for l in args.locales))]
    if stray:
        git("reset", "-q")
        sys.exit(f"staged files outside the intended set, aborting: {stray[:5]}")
    if not staged:
        print("nothing to commit")
        return 0
    diff = git("diff", "--cached", "-U0", "--", "i18n")
    carried = len(re.findall(r"^\+# doq: carried over from the paragraph", diff, re.M))
    sha = io.en_hash("index.mdx")
    en = git("log", "-1", "--format=%s", "--", "upstream-docs") or "the current English"
    msg = (f"i18n: sync {len(args.locales)} locale(s) to the English of {en}\n\n"
           f"translation/v2/sync.py: {sum(a['accepted'] for a in applied)} entries accepted from a model, "
           f"{carried} carried over from split paragraphs, {sum(a['withdrawn'] for a in applied)} page verdicts withdrawn; "
           f"every worklist empty; render, mdxcheck, lint, known-mistranslations, wrong-language, check.py audit and "
           f"the completeness ratchet clean on every locale.\n")
    subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=io.REPO, input=msg, text=True, check=True)
    print(f"\ncommitted {len(staged)} file(s) on {git('branch', '--show-current')} (EN hash {sha})")
    print("Next: git push -u origin HEAD && gh pr create --repo JanLahmann/doQumentation --base main\n"
          "      (then close the bot's sync PR as superseded).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "status", "finish"):
        p = sub.add_parser(name)
        p.add_argument("--locales", nargs="*", default=io.MAIN_LOCALES, help="default: every locale")
        p.add_argument("-j", "--jobs", type=int, default=4)
    sub.choices["prepare"].add_argument("--from", dest="from_branch", metavar="BRANCH",
                                        help="the bot's sync branch (sync/upstream-content); omit to sync against docs/ as it is")
    sub.choices["finish"].add_argument("--accept-warnings", action="store_true",
                                       help="commit although apply printed REPLACED-BY-ENGLISH warnings (after checking them)")
    sub.choices["finish"].add_argument("--no-commit", action="store_true")
    sub.choices["finish"].add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    return {"prepare": cmd_prepare, "status": cmd_status, "finish": cmd_finish}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
