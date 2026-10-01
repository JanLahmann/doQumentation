"""round.py: the pure pieces — sample splitting, log parsing, the message."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def rnd():
    p = Path(__file__).resolve().parent.parent / "round.py"
    spec = importlib.util.spec_from_file_location("round_driver", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_split_sample_keeps_every_file_in_order_under_the_limit(rnd):
    sample = {"seed": 1, "sample_size": 5, "files": [{"rel": f"p{i}"} for i in range(5)]}
    sizes = [100_000, 100_000, 300_000, 50_000, 50_000]
    parts = rnd.split_sample(sample, sizes, 450_000)
    assert [f["rel"] for p in parts for f in p["files"]] == ["p0", "p1", "p2", "p3", "p4"]
    assert all(p["sample_size"] == len(p["files"]) for p in parts) and parts[0]["seed"] == 1
    size = dict(zip((f["rel"] for f in sample["files"]), sizes))
    assert all(sum(size[f["rel"]] for f in p["files"]) + 60_000 <= 450_000 for p in parts)
    assert len(parts) == 3


def test_parse_apply_reads_counts_rejects_and_english(rnd):
    text = ("WARNING guides/a.mdx#3: translation replaced by the English source — check this is intended: 'Job mode'\n"
            "REJECT guides/b.mdx#9: inline code mismatch: added '`pip`'\n"
            "uk: accepted 159, rejected 1, unfilled 0, unchanged 172, REPLACED BY ENGLISH 1\n")
    ap = rnd.parse_apply(text, "uk")
    assert (ap["accepted"], ap["rejected"], ap["unfilled"], ap["unchanged"]) == (159, 1, 0, 172)
    assert ap["rejects"] == [("guides/b.mdx#9", "inline code mismatch: added '`pip`'")]
    assert ap["english"] == [("guides/a.mdx#3", "'Job mode'")]
    assert not rnd.parse_apply("nothing here", "uk")["ok"]


def test_parse_ratchet_returns_only_the_new_findings(rnd):
    text = ("uk: 3 finding(s) over 450 file(s)\n\nratchet: 1 NEW finding(s) not in the baseline:\n"
            "  uk numbers              guides/x.po#34: missing 5\n      EN 'x'\n")
    assert rnd.parse_ratchet(text, "uk") == ["uk numbers              guides/x.po#34: missing 5"]
    assert rnd.parse_ratchet("ratchet: no new findings (1 known, baseline 2)", "uk") == []


def test_message_counts_the_gauge_from_the_records_not_a_side_file(rnd):
    recs = [{"file": "guides/a.mdx", "verdict": "FAIL", "gauge": "upheld",
             "examples": [{"type": "Drift", "source": "up to order", "translation": "bis einschließlich",
                           "why": "'up to' means disregarding"}]},
            {"file": "guides/b.mdx", "verdict": "FAIL", "gauge": "refuted", "examples": []},
            {"file": "guides/c.mdx", "verdict": "MINOR_ISSUES", "examples": []}]
    ls = {"apply": {"accepted": 12, "rejected": 0, "unchanged": 3, "rejects": [], "english": []}}
    commit, pr = rnd.build_message("de", "42", recs, ls, "725", ["Co-Authored-By: X <x@y>"])
    assert commit.splitlines()[0] == "review(de): round 42 — 3 pages, fix wave"
    assert "the gauge upheld 1 and refuted 1 (guides/b; fixed as MINOR):" in commit
    assert "- guides/a: \"up to order\" was «bis einschließlich». 'up to' means disregarding" in commit
    assert "accepted 12 entries (3 sent back unchanged), 0 rejected." in commit
    assert commit.rstrip().endswith("Co-Authored-By: X <x@y>") and "Co-Authored-By" not in pr
    assert "Claim: #725" in pr


def test_message_says_no_gauge_without_fails(rnd):
    commit, _ = rnd.build_message("de", "1", [{"file": "a.mdx", "verdict": "PASS", "examples": []}],
                                  {"apply": {}}, None, [])
    assert "1 PASS, so no gauge run." in commit


def test_absolutize_points_every_agent_path_into_the_worktree(rnd, tmp_path):
    wt = tmp_path / "wt"
    obj = {"files": [{"pair": "translation/v2/work/review/de/a.md", "rel": "guides/a.mdx"}],
           "batches": [{"file": "translation/v2/work/de/fix-000.json", "out": "/abs/x.out.json"}],
           "instructions": "translation/v2/work/de/instructions-fix.md"}
    out = rnd.absolutize(obj, wt)
    assert out["files"][0]["pair"] == str(wt / "translation/v2/work/review/de/a.md")
    assert out["files"][0]["rel"] == "guides/a.mdx"                 # not a path an agent opens
    assert out["batches"][0]["file"] == str(wt / "translation/v2/work/de/fix-000.json")
    assert out["batches"][0]["out"] == "/abs/x.out.json"            # already absolute
    assert out["instructions"] == str(wt / "translation/v2/work/de/instructions-fix.md")


def test_absolutize_baked_rewrites_the_inlined_payload(rnd, tmp_path):
    js = tmp_path / "g.js"
    js.write_text('const BAKED = {"fails": [{"file": "guides/a.mdx", "pair": "translation/v2/work/review/de/a.md"}]}\n')
    rnd.absolutize_baked(js, tmp_path / "wt")
    text = js.read_text()
    assert f'"pair": "{tmp_path / "wt"}/translation/v2/work/review/de/a.md"' in text
    assert '"file": "guides/a.mdx"' in text                          # the page name stays


def test_new_seed_skips_every_used_seed(rnd):
    used = {"2026093024", "2026093025"}
    assert rnd.new_seed("20260930", used, 24) == "2026093026"
    assert rnd.new_seed("20260930", set(), 99) == "2026093099"
    assert rnd.new_seed("20260930", {"2026093099"}, 99) == "2026093000"          # wraps
    full = {f"20260930{n:02d}" for n in range(100)}
    assert rnd.new_seed("20260930", full, 7) == "20260930007"                    # three digits


def test_sample_seed_differs_per_locale_and_is_stable(rnd):
    # 2026100104 drew the same 3 pages in all 17 locales from one shared seed.
    seeds = {loc: rnd.sample_seed("2026100104", loc) for loc in ("de", "es", "fr", "ja", "ar")}
    assert len(set(seeds.values())) == len(seeds)
    assert rnd.sample_seed("2026100104", "de") == seeds["de"]
    assert rnd.sample_seed("2026100105", "de") != seeds["de"]
