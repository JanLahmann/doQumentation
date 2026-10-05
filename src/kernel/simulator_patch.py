# Simulator Mode kernel patch (src/kernel/index.ts prepends the parameters):
#   _DQ_DEVICE             fake_provider class name, or None for the ideal AerSimulator
#   _DQ_SUPPRESS_WARNINGS  True to silence Python warnings
# QiskitRuntimeService is replaced by an offline stand-in whose backend(),
# least_busy() and backends() return that one simulator.
# scripts/check-simulator-mode.py runs doc pages against this exact file.
if _DQ_SUPPRESS_WARNINGS:
    import warnings
    warnings.filterwarnings("ignore")
    print("[doQumentation] Python warnings suppressed (can be changed in Settings)")

if _DQ_DEVICE:
    from qiskit_ibm_runtime import fake_provider as _dq_fp
    _dq_backend = getattr(_dq_fp, _DQ_DEVICE)()
else:
    try:
        from qiskit_aer import AerSimulator as _DQ_Sim
    except ImportError:
        from qiskit.providers.basic_provider import BasicSimulator as _DQ_Sim
    _dq_backend = _DQ_Sim()


class _DQ_MockService:
    def __init__(self, *a, **kw):
        print("[doQumentation] QiskitRuntimeService() intercepted by Simulator Mode")

    @staticmethod
    def save_account(*a, **kw):
        print("[doQumentation] Simulator mode active — save_account() skipped (no credentials needed)")

    def least_busy(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode — returning {_dq_backend}")
        return _dq_backend

    def backend(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode — returning {_dq_backend}")
        return _dq_backend

    def backends(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode — returning [{_dq_backend}]")
        return [_dq_backend]


# The ideal AerSimulator has no coupling map, so AerSimulator.from_backend()
# on it raises "'NoneType' object has no attribute 'get_edges'" (#965).
# Hand back a fresh ideal simulator instead.
try:
    from qiskit_aer import AerSimulator as _DQ_Aer
    if not getattr(_DQ_Aer.from_backend, "_dq_shim", False):
        _DQ_real_from_backend = _DQ_Aer.from_backend

        def _dq_from_backend(backend, **options):
            if isinstance(backend, _DQ_Aer) and backend.coupling_map is None:
                print("[doQumentation] Simulator Mode — from_backend() on the ideal AerSimulator returns an ideal AerSimulator")
                return _DQ_Aer(**options)
            return _DQ_real_from_backend(backend, **options)

        _dq_from_backend._dq_shim = True
        _DQ_Aer.from_backend = staticmethod(_dq_from_backend)
except ImportError:
    pass

import sys
import qiskit_ibm_runtime as _qir
_qir.QiskitRuntimeService = _DQ_MockService
_m = sys.modules.get("qiskit_ibm_runtime")
if _m:
    _m.QiskitRuntimeService = _DQ_MockService
print(f"[doQumentation] Simulator mode — using {type(_dq_backend).__name__}")
