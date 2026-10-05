# Simulator Mode kernel patch (src/kernel/index.ts prepends the parameters):
#   _DQ_DEVICE             qiskit_ibm_runtime.fake_provider class name
#   _DQ_NOISE              False in "aer" mode: the device's shape, ideal simulation
#   _DQ_SUPPRESS_WARNINGS  True to silence Python warnings
# QiskitRuntimeService is replaced by an offline stand-in whose backend(),
# least_busy() and backends() return that one device. Even the ideal mode
# hands out a device rather than a bare AerSimulator: notebooks read its
# coupling map, gate durations, basis_gates and processor_type, which a bare
# AerSimulator lacks (12 notebooks failed on it in the 2026-10-05 sweep).
# scripts/check-simulator-mode.py and the notebook sweep's Pass S run this file.
if _DQ_SUPPRESS_WARNINGS:
    import warnings
    warnings.filterwarnings("ignore")
    print("[doQumentation] Python warnings suppressed (can be changed in Settings)")

from qiskit_ibm_runtime import fake_provider as _dq_fp

_dq_backend = getattr(_dq_fp, _DQ_DEVICE)()
if not _DQ_NOISE:
    try:
        from qiskit_aer import AerSimulator as _DQ_Aer
        # A fake device builds its noisy simulator on first run(); one set
        # beforehand is used as is.
        _dq_backend.sim = _DQ_Aer()
    except ImportError:
        pass  # without Aer, fake devices simulate ideally anyway
_dq_label = f"{_dq_backend.name}{'' if _DQ_NOISE else ' (ideal)'}"


class _DQ_NeedsIBMCloud(RuntimeError):
    """Raised for calls that need a real IBM Quantum account."""

    def __init__(self, what):
        super().__init__(
            f"[doQumentation] Simulator Mode: {what} needs IBM Quantum and has no offline "
            "equivalent. To run this cell, add your IBM Quantum credentials in Settings "
            "and switch Simulator Mode off.")


class _DQ_MockService:
    def __init__(self, *a, **kw):
        print("[doQumentation] QiskitRuntimeService() intercepted by Simulator Mode")

    @staticmethod
    def save_account(*a, **kw):
        print("[doQumentation] Simulator mode active — save_account() skipped (no credentials needed)")

    def least_busy(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode — returning {_dq_label}")
        return _dq_backend

    def backend(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode — returning {_dq_label}")
        return _dq_backend

    def backends(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode — returning [{_dq_label}]")
        return [_dq_backend]

    def job(self, *a, **kw):
        raise _DQ_NeedsIBMCloud("service.job() (fetching a job that ran on IBM Quantum)")

    def jobs(self, *a, **kw):
        raise _DQ_NeedsIBMCloud("service.jobs() (listing jobs that ran on IBM Quantum)")

    def __getattr__(self, name):
        # Anything else (active_account, usage, _account for Qiskit Functions,
        # ...). An AttributeError, so hasattr() and IPython's display probes
        # still work, carrying the same explanation.
        raise AttributeError(str(_DQ_NeedsIBMCloud(f"service.{name}")))


def _dq_needs_cloud(what):
    class _DQ_CloudOnly:
        def __init__(self, *a, **kw):
            raise _DQ_NeedsIBMCloud(what)
    return _DQ_CloudOnly


import sys
import qiskit_ibm_runtime as _qir
_qir.QiskitRuntimeService = _DQ_MockService
_m = sys.modules.get("qiskit_ibm_runtime")
if _m:
    _m.QiskitRuntimeService = _DQ_MockService
try:
    import qiskit_ibm_catalog as _qic
    _qic.QiskitFunctionsCatalog = _dq_needs_cloud("Qiskit Functions (QiskitFunctionsCatalog)")
    _qic.QiskitServerless = _dq_needs_cloud("Qiskit Serverless (QiskitServerless)")
except ImportError:
    pass
print(f"[doQumentation] Simulator mode — using {_dq_label}")
