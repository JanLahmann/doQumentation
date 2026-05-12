"""Patch qiskit_ibm_runtime so notebooks run against local fake backends in CI.

Loaded automatically by IPython at kernel startup when IPYTHONDIR points at the
parent of profile_default/. The patch must run before any user cell so that
``from qiskit_ibm_runtime import QiskitRuntimeService`` in a notebook resolves
to our fake (the import reads the module attribute at execution time).
"""
import os
import contextlib

import qiskit_ibm_runtime as _qir
from qiskit_ibm_runtime.fake_provider import FakeBrisbane, FakeFez, FakeMarrakesh

_BACKEND_MAP = {
    "ibm_brisbane": FakeBrisbane,
    "ibm_fez": FakeFez,
    "ibm_pittsburgh": FakeMarrakesh,
    "ibm_marrakesh": FakeMarrakesh,
}


def _pick_fake(min_num_qubits=None, name=None, **_):
    if name and name in _BACKEND_MAP:
        return _BACKEND_MAP[name]()
    if min_num_qubits and min_num_qubits >= 128:
        return FakeFez()
    return FakeBrisbane()


class _FakeJob:
    """Minimal stub returned by _FakeService.job() so notebooks that look up
    a submitted job's metadata (tags, status, metrics) don't fail. Real
    results are not reproducible without the cloud; notebooks that need them
    should tag the cell with 'nbmake-skip-cell'."""

    def __init__(self, job_id):
        self._job_id = job_id

    def job_id(self):
        return self._job_id

    @property
    def tags(self):
        return []

    def status(self):
        return "DONE"

    def metrics(self):
        return {}

    def usage(self):
        return {}

    def creation_date(self):
        return None

    def backend(self):
        return FakeBrisbane()

    def result(self):
        raise RuntimeError(
            f"CI: job({self._job_id!r}).result() is unsupported under fake "
            "backends. Tag this cell with 'nbmake-skip-cell' to skip it."
        )


class _FakeService:
    def __init__(self, *_, **__):
        pass

    @staticmethod
    def save_account(*_, **__):
        return None

    @staticmethod
    def delete_account(*_, **__):
        return None

    @staticmethod
    def saved_accounts(*_, **__):
        return {}

    def least_busy(self, *_, **kw):
        return _pick_fake(**kw)

    def backend(self, name=None, **_):
        return _pick_fake(name=name)

    def backends(self, *_, **__):
        return [FakeBrisbane(), FakeFez(), FakeMarrakesh()]

    def job(self, job_id, *_, **__):
        return _FakeJob(job_id)

    def jobs(self, *_, **__):
        return []


_qir.QiskitRuntimeService = _FakeService

_MAX_SHOTS = int(os.environ.get("CI_MAX_SHOTS", "1024"))
_OrigSampler = _qir.SamplerV2
_OrigEstimator = _qir.EstimatorV2


def _wrap_primitive(orig):
    class _Wrapped(orig):
        def __init__(self, mode=None, *a, **kw):
            from qiskit.providers.backend import BackendV2
            if not isinstance(mode, BackendV2):
                mode = FakeBrisbane()
            super().__init__(mode=mode, *a, **kw)
            try:
                if getattr(self.options, "default_shots", None) and self.options.default_shots > _MAX_SHOTS:
                    self.options.default_shots = _MAX_SHOTS
            except Exception:
                pass

    _Wrapped.__name__ = orig.__name__
    _Wrapped.__qualname__ = orig.__qualname__
    return _Wrapped


_qir.SamplerV2 = _wrap_primitive(_OrigSampler)
_qir.EstimatorV2 = _wrap_primitive(_OrigEstimator)


@contextlib.contextmanager
def _fake_session(backend=None, **_):
    yield backend if backend is not None else FakeBrisbane()


_qir.Session = _fake_session
_qir.Batch = _fake_session

print(f"[ci] qiskit_ibm_runtime patched: fake backends, shots<={_MAX_SHOTS}")
