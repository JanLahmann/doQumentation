#!/usr/bin/env python3
"""Regenerate src/theme/NotFound/Content/retiredPages.json.

IBM retires and moves pages, and the redirects it sets up for them live in
its private site config, not in Qiskit/documentation. So this finds them
empirically, and the 404 page (src/theme/NotFound/Content) uses the result to
send an old link on to where the page went instead of showing "not found".

1. Candidates: every page file deleted in the history of Qiskit/documentation
   (the `upstream-docs` submodule) that is not in its tree at --ref, plus
   every page deleted from this repo's own docs/ that is not in docs/ now.
   File paths map to our routes as in scripts/sync-content.py:
   docs/guides/X → /guides/X, docs/tutorials/X → /tutorials/X,
   learning/(courses|modules)/… → /learning/(courses|modules)/…, …/index → its folder.
2. Each candidate's IBM address is requested, following redirects.
3. Where IBM ends up decides the entry:
   - a page we mirror (its route has a file in docs/) → that route;
   - another live IBM page → that absolute URL (language segment dropped,
     IBM adds the visitor's own), or the archived notebook on
     github.com/Qiskit/ where IBM itself sends the old address;
   - 404 or an error → no redirect, listed under "unresolved".
   MANUAL entries (retired pages IBM did not redirect) override the probe.

A redirect target that is one of our routes is only followed at runtime when
that route is a real page, so a stale entry can never loop back to the 404.
An entry for a route that still has a page here does nothing until the page
goes (e.g. a page IBM retired that the next sync will remove).

Run after an upstream sync (needs network; ~1 request per candidate):
    git submodule update --init --filter=blob:none upstream-docs
    git -C upstream-docs fetch origin main
    python3 scripts/generate-retired-pages.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/theme/NotFound/Content/retiredPages.json"
IBM = "https://quantum.cloud.ibm.com"

# Retired pages IBM does not redirect (its old URL answers 404), with the
# page that replaced them. Overrides the probe.
MANUAL = {
    # Removed upstream in 5b24bb708 "Post selection changes" (#5737).
    "/guides/post-selection": f"{IBM}/docs/addons/qiskit-mitigation/guides/postselection-with-non-markovian-error-checks",
}

PAGE_EXT = (".mdx", ".md", ".ipynb")
UPSTREAM_DIRS = ["docs/guides", "docs/tutorials", "learning/courses", "learning/modules"]
LOCAL_DIRS = ["docs/guides", "docs/tutorials", "docs/learning/courses", "docs/learning/modules"]
LANG = r"[a-z]{2}(?:[-_][a-zA-Z]{2,4})?"


def git(cwd: Path, *args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def is_page(path: str) -> bool:
    if not path.endswith(PAGE_EXT):
        return False
    return not any(part.startswith(("_", ".")) or part == "extracted-outputs" for part in path.split("/"))


def route_of(path: str, prefix: str) -> str:
    """docs/guides/x.ipynb → /guides/x (prefix "docs/" stripped for both trees)."""
    p = re.sub(r"\.(mdx|md|ipynb)$", "", path)
    p = p[len(prefix):] if p.startswith(prefix) else p
    p = re.sub(r"/index$", "", "/" + p)
    return p


def upstream_route(path: str) -> str:
    return route_of(path, "docs/")  # learning/… keeps its path


def ibm_url(route: str) -> str:
    return f"{IBM}{route}" if route.startswith("/learning/") else f"{IBM}/docs{route}"


# IBM sends some retired notebooks to their last version on GitHub.
ARCHIVE = "https://github.com/Qiskit/"


def ibm_to_route(url: str) -> tuple[str, str] | None:
    """IBM URL → (our route, IBM URL without language segment); None if not IBM."""
    if url.startswith(ARCHIVE):
        return "", url
    m = re.match(rf"^{re.escape(IBM)}(/[^?#]*)", url)
    if not m:
        return None
    path = m.group(1).rstrip("/") or "/"
    path = re.sub(rf"^/docs/{LANG}(?=/)", "/docs", path)
    path = re.sub(rf"^/learning/{LANG}(?=/)", "/learning", path)
    route = re.sub(r"^/docs(?=/(guides|tutorials)(/|$))", "", path)
    return route, f"{IBM}{path}"


def probe_once(url: str) -> tuple[int, str]:
    """(final status, final URL) following redirects; HEAD, GET on 405."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "doQumentation-retired-pages/1.0 (+https://doqumentation.org)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            if e.code == 405 and method == "HEAD":
                continue
            return e.code, e.geturl() or url
        except Exception as e:  # network trouble: report, do not guess
            return 0, f"error: {e}"
    return 0, url


def probe(url: str, sleep: float) -> tuple[int, str]:
    """probe_once, retried with backoff on 429, 5xx and network errors."""
    for attempt in range(4):
        time.sleep(sleep * (4 ** attempt))
        status, final = probe_once(url)
        if status not in (0, 429) and status < 500:
            break
    return status, final


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--upstream", default=str(ROOT / "upstream-docs"), help="Qiskit/documentation checkout")
    ap.add_argument("--ref", default=None, help="upstream ref for 'exists now' (default origin/main, else HEAD)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=0.3, help="pause before each request (s)")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args()

    up = Path(args.upstream)
    ref = args.ref
    if ref is None:
        try:
            git(up, "rev-parse", "--verify", "-q", "origin/main")
            ref = "origin/main"
        except subprocess.CalledProcessError:
            ref = "HEAD"
    up_sha = git(up, "rev-parse", "--short=9", ref)[0]

    up_deleted = {upstream_route(p) for p in git(up, "log", ref, "--no-renames", "--diff-filter=D", "--name-only", "--format=", "--", *UPSTREAM_DIRS) if is_page(p)}
    up_now = {upstream_route(p) for p in git(up, "ls-tree", "-r", "--name-only", ref, "--", *UPSTREAM_DIRS) if is_page(p)}
    local_deleted = {route_of(p, "docs/") for p in git(ROOT, "log", "--no-renames", "--diff-filter=D", "--name-only", "--format=", "--", *LOCAL_DIRS) if is_page(p)}
    local_now = {route_of(str(p.relative_to(ROOT)), "docs/") for d in LOCAL_DIRS for p in (ROOT / d).rglob("*") if p.is_file() and is_page(str(p.relative_to(ROOT)))}

    # Pages of the pinned upstream (submodule HEAD) that --ref no longer has:
    # still here, gone at the next sync. Every other page here is no candidate
    # (e.g. our own docs/tutorials/hello-world.mdx, which upstream removed).
    pinned = {upstream_route(p) for p in git(up, "ls-tree", "-r", "--name-only", "HEAD", "--", *UPSTREAM_DIRS) if is_page(p)}
    keep_here = (pinned - up_now) | set(MANUAL)
    candidates = sorted(((up_deleted - up_now) | (local_deleted - local_now) | set(MANUAL)) - (local_now - keep_here))
    print(f"{len(candidates)} candidates ({len(up_deleted - up_now)} retired upstream, {len(local_deleted - local_now)} removed here)", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = dict(zip(candidates, pool.map(lambda r: probe(ibm_url(r), args.sleep), candidates)))

    redirects: dict[str, str] = {}
    unresolved: dict[str, str] = {}
    for route in candidates:
        status, final = results[route]
        if route in MANUAL:
            redirects[route] = MANUAL[route]
            continue
        mapped = ibm_to_route(final) if status == 200 else None
        if mapped is None:
            unresolved[route] = str(status) if status else final
            continue
        target, ibm_target = mapped
        if target in local_now and target != route:
            redirects[route] = target
        else:
            redirects[route] = ibm_target
    for route in candidates:
        print(f"{results[route][0]:>3}  {route}  →  {redirects.get(route, '-')}", file=sys.stderr)

    data = {
        "_generated": (
            f"By scripts/generate-retired-pages.py on {dt.date.today().isoformat()}: pages deleted from "
            f"Qiskit/documentation (history up to {up_sha}) or from this repo's docs/, probed at {IBM}. "
            "Old route → our route or IBM URL; 'unresolved' = no live page at IBM (status). "
            "Do not edit by hand: rerun the script, or add to its MANUAL map."
        ),
        "redirects": dict(sorted(redirects.items())),
        "unresolved": dict(sorted(unresolved.items())),
    }
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    internal = sum(1 for t in redirects.values() if t.startswith("/"))
    print(f"redirects: {len(redirects)} ({internal} internal, {len(redirects) - internal} IBM); unresolved: {len(unresolved)}", file=sys.stderr)
    if args.dry_run:
        print(text)
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
