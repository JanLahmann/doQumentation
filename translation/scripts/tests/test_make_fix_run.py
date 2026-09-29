"""make-fix-run.py bakes batch manifests into runnable translate-locale copies."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "make-fix-run.py"


def _manifest(tmp_path, loc, n, filled=0):
    batches = []
    for i in range(n):
        out = tmp_path / f"{loc}-fix-{i:03d}.out.json"
        if i < filled:
            out.write_text(json.dumps(["x"] * 3))
        batches.append({"file": str(tmp_path / f"{loc}-fix-{i:03d}.json"), "out": str(out),
                        "model": "sonnet", "items": 3, "words": 10})
    m = tmp_path / f"manifest-fix-{loc}.json"
    m.write_text(json.dumps({"locale": loc, "task": "fix", "instructions": "i.md",
                             "instructions_text": f"Rules for {loc}. Register: informal.", "batches": batches}))
    return m


def _run(*argv):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, argv)], capture_output=True, text=True)


def _baked(path):
    text = path.read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("const BAKED_ARGS = "))
    return text, json.loads(line[len("const BAKED_ARGS = "):])


def test_bakes_several_locales_with_their_own_rules(tmp_path):
    out = tmp_path / "wave.js"
    r = _run("--manifest", _manifest(tmp_path, "de", 2), "--manifest", _manifest(tmp_path, "ro", 1), "--out", out)
    assert r.returncode == 0, r.stderr
    text, args = _baked(out)
    assert args["task"] == "fix" and args["agentType"] == "translator"
    assert [b["locale"] for b in args["batches"]] == ["de", "de", "ro"]
    # each locale's rules once, so a multi-locale wave keeps every register line
    assert args["instructions_by_locale"] == {"de": "Rules for de. Register: informal.",
                                              "ro": "Rules for ro. Register: informal."}
    assert "name: 'fix-wave'" in text
    assert "= args" not in text and "(args" not in text      # the template's global is fully replaced
    if shutil.which("node"):
        assert subprocess.run(["node", "--check", str(out)]).returncode == 0


def test_splits_per_workflow_and_skips_filled_batches(tmp_path):
    out = tmp_path / "wave.js"
    r = _run("--manifest", _manifest(tmp_path, "th", 5, filled=2), "--out", out, "--per-workflow", 2)
    assert r.returncode == 0, r.stderr
    assert "2 batch(es) already filled" in r.stdout
    parts = sorted(tmp_path.glob("wave-*.js"))
    assert [p.name for p in parts] == ["wave-0.js", "wave-1.js"]
    assert [len(_baked(p)[1]["batches"]) for p in parts] == [2, 1]
    # --all keeps the filled ones
    r = _run("--manifest", _manifest(tmp_path, "th", 5, filled=2), "--out", tmp_path / "all.js", "--all")
    assert len(_baked(tmp_path / "all.js")[1]["batches"]) == 5


def test_refuses_to_mix_a_fix_wave_and_a_translation_fill(tmp_path):
    fix = _manifest(tmp_path, "de", 1)
    tr = tmp_path / "manifest.json"
    tr.write_text(json.dumps({"locale": "fr", "instructions": "i.md", "batches": [
        {"file": "a.json", "out": str(tmp_path / "a.out.json"), "items": 1}]}))
    r = _run("--manifest", fix, "--manifest", tr, "--out", tmp_path / "x.js")
    assert r.returncode != 0 and "mix tasks" in r.stderr
