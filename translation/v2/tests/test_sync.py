"""sync.py's status check, bake, and the Haiku routing rule it relies on
(lessons of the 2026-09-30 sync)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import po4a_io as io  # noqa: E402
import sync  # noqa: E402
import translate  # noqa: E402


def test_display_math_never_goes_to_haiku():
    assert translate.has_display_math("$$\n\\begin{aligned}\nx &= 1\n\\end{aligned}\n$$")
    assert translate.has_display_math("Text then \\begin{equation}x\\end{equation}")
    assert not translate.has_display_math("Inline $x$ only, and a price of $5.")


def _batch(tmp_path, monkeypatch, items, out_text):
    monkeypatch.setattr(io, "REPO", tmp_path)
    (tmp_path / "b.json").write_text(json.dumps(items))
    (tmp_path / "b.out.json").write_text(out_text, encoding="utf-8")
    return {"batches": [{"file": "b.json", "out": "b.out.json", "items": len(items)}]}


def test_status_accepts_one_string_per_line(tmp_path, monkeypatch):
    # 9 of 34 Haiku batches were written like this; apply reads them, so status must too
    m = _batch(tmp_path, monkeypatch, [{"msgid": "a"}, {"msgid": "b"}], '"eins"\n"zwei"\n')
    assert sync.check_outputs(m) == []


def test_status_repairs_an_unescaped_quote_like_apply(tmp_path, monkeypatch):
    m = _batch(tmp_path, monkeypatch, [{"msgid": "a"}, {"msgid": "b"}],
               '"eins"\n"auf „ibm_aachen" laufen"\n')
    assert sync.check_outputs(m) == []


def test_status_still_rejects_a_wrong_count(tmp_path, monkeypatch):
    m = _batch(tmp_path, monkeypatch, [{"msgid": "a"}, {"msgid": "b"}], '["eins"]')
    assert "1 strings for 2 items" in sync.check_outputs(m)[0]


def test_bake_inlines_every_unfilled_batch_with_its_locale(tmp_path, monkeypatch):
    monkeypatch.setattr(io, "REPO", tmp_path)
    monkeypatch.setattr(io, "WORK_DIR", tmp_path / "work")
    wf = tmp_path / ".claude" / "workflows"
    wf.mkdir(parents=True)
    (wf / "translate-locale.js").write_text(
        "export const meta = {\n  name: 'x',\n}\nconst { batches } = args\nreturn batches.length\n")
    for loc, filled in (("de", False), ("ja", True)):
        d = tmp_path / "work" / loc
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"instructions_text": f"rules {loc}", "batches": [
            {"file": f"work/{loc}/batch-000-sonnet.json", "items": 3, "words": 10, "model": "sonnet"}]}))
        if filled:
            (d / "batch-000-sonnet.out.json").write_text('["a","b","c"]')
    out = tmp_path / "work" / "fill.js"
    args = type("A", (), {"locales": ["de", "ja"], "out": str(out), "all": False, "concurrency": 10})
    assert sync.cmd_bake(args) == 0
    js = out.read_text()
    baked = json.loads(js.split("const BAKED_ARGS = ", 1)[1].split("\n", 1)[0])
    assert [b["locale"] for b in baked["batches"]] == ["de"]          # ja already filled
    assert baked["instructions_by_locale"]["de"] == "rules de"
    assert "const { batches } = BAKED_ARGS" in js and baked["agentType"] == "translator"
