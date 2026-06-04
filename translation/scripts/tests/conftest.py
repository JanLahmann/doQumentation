"""pytest fixtures for the translation-pipeline unit tests.

The pipeline scripts have hyphens in their filenames (validate-translation.py,
lint-translation.py), so they can't be imported with a normal `import`. This
loads them by path and exposes them as fixtures. All target functions are PURE
(string in → value out), so no network / git / filesystem is touched.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def common():
    return _load("_common", "_common.py")


@pytest.fixture(scope="session")
def validate():
    return _load("validate_translation", "validate-translation.py")


@pytest.fixture(scope="session")
def lint():
    return _load("lint_translation", "lint-translation.py")


@pytest.fixture(scope="session")
def passage_units():
    return _load("passage_units", "passage_units.py")
