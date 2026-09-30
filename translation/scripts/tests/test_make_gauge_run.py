"""make-gauge-run.py --record-result: the refutation gauge's outcome on the records."""

import importlib.util
import json
from pathlib import Path


def _mgr():
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("make_gauge_run", root / "make-gauge-run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_record_result_stamps_upheld_and_refuted(tmp_path):
    recs = tmp_path / "opus.json"
    recs.write_text(json.dumps([
        {"locale": "pl", "file": "a.mdx", "verdict": "FAIL"},
        {"locale": "pl", "file": "b.mdx", "verdict": "FAIL"},
        {"locale": "pl", "file": "c.mdx", "verdict": "MINOR_ISSUES"},
    ]))
    done = _mgr().record_result(recs, "pl", {"stands": ["a.mdx"], "refuted": ["b"]})
    assert done == {"a.mdx": "upheld", "b.mdx": "refuted"}
    out = {r["file"]: r.get("gauge") for r in json.loads(recs.read_text())}
    assert out == {"a.mdx": "upheld", "b.mdx": "refuted", "c.mdx": None}
