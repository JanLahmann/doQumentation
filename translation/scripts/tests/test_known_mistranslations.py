"""check-known-mistranslations.py: the rule table itself."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "check-known-mistranslations.py"


def test_known_has_no_duplicate_locale_keys():
    """A dict literal keeps only the LAST of two equal keys, silently: a
    second "ar" block once disabled every rule in the first."""
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "KNOWN":
            keys = [k.value for k in node.value.keys]
            assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)
            return
    raise AssertionError("KNOWN not found")


def test_miner_takes_term_swaps_not_rewrites():
    import importlib.util
    spec = importlib.util.spec_from_file_location("miner", SRC.parent / "mine-known-mistranslations.py")
    miner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(miner)
    swap = {"source": "the CHSH inequality", "translation": "ketidaksetaraan CHSH",
            "suggested": "pertidaksamaan CHSH"}
    assert miner.swaps(swap) == [("ketidaksetaraan", "pertidaksamaan")]
    kept_name = {"source": "the Sampler primitive", "translation": "Sampler asli", "suggested": "Sampler primitif"}
    assert miner.swaps(kept_name) == [("asli", "primitif")]
