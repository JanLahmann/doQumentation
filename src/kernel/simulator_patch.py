# Simulator Mode kernel patch (src/kernel/index.ts prepends the parameters):
#   _DQ_DEVICE             qiskit_ibm_runtime.fake_provider class name
#   _DQ_PINNED             True when the page pins its device (pages.json): every
#                          request gets it; otherwise named/sized requests are honoured
#   _DQ_NOISE              False in "aer" mode: the device's shape, ideal simulation
#   _DQ_SUPPRESS_WARNINGS  True to silence Python warnings
# QiskitRuntimeService is replaced by an offline stand-in that hands out fake
# devices. Even the ideal mode hands out a device rather than a bare
# AerSimulator: notebooks read its coupling map, gate durations, basis_gates
# and processor_type, which a bare AerSimulator lacks.
# scripts/check-simulator-mode.py and the notebook sweep's Pass S run this file.
if _DQ_SUPPRESS_WARNINGS:
    import warnings
    warnings.filterwarnings("ignore")
    print("[doQumentation] Python warnings suppressed (can be changed in Settings)")

from qiskit_ibm_runtime import fake_provider as _dq_fp

# A request the default device cannot serve (more qubits, or a filter it
# fails, e.g. "measure_2" in b.supported_instructions) gets the first of these.
_DQ_LARGEST = "FakeFez"
_DQ_HERONS = ("FakeFez", "FakeKingston", "FakeBoston", "FakePittsburgh",
              "FakeMarrakesh", "FakeAachen", "FakeTorino")
_dq_devices = {}


def _dq_active_qubits(circuit):
    used = set()
    for inst in circuit.data:
        if inst.operation.name not in ("barrier", "delay"):
            used.update(circuit.find_bit(q).index for q in inst.qubits)
    return len(used)


def _dq_add_fractional_gates(dev):
    """Heron devices offer rx and rzz to jobs that ask for fractional gates;
    the fake devices' targets lack them, so add them (rzz on the cz edges)."""
    from qiskit.circuit import Parameter
    from qiskit.circuit.library import RXGate, RZZGate
    target = dev.target
    if "rx" not in target.operation_names:
        target.add_instruction(RXGate(Parameter("theta")),
                               {(q,): None for q in range(dev.num_qubits)})
    two_q = next((g for g in ("cz", "ecr", "cx") if g in target.operation_names), None)
    if two_q and "rzz" not in target.operation_names:
        target.add_instruction(RZZGate(Parameter("theta")),
                               {qargs: None for qargs in target.qargs_for_operation_name(two_q)})


def _dq_device(cls_name, fractional=False):
    """The fake device for a fake_provider class name, built once per kernel."""
    if (cls_name, fractional) in _dq_devices:
        return _dq_devices[(cls_name, fractional)]
    dev = getattr(_dq_fp, cls_name)()
    if fractional:
        _dq_add_fractional_gates(dev)
    try:
        from qiskit_aer import AerSimulator as _DQ_Aer
        # A fake device builds its noisy simulator on first run(); one set
        # beforehand is used as is.
        if _DQ_NOISE:
            dev._setup_sim()
        else:
            dev.sim = _DQ_Aer()
        sim_run = dev.sim.run

        def plain_measures(circuit):
            # Mid-circuit measurement variants (measure_2, MidCircuitMeasure)
            # are ordinary measurements logically; Aer only knows "measure".
            if not any(i.operation.name.startswith("measure_") for i in circuit.data):
                return circuit
            from qiskit.circuit import Measure
            out = circuit.copy_empty_like()
            for inst in circuit.data:
                if inst.operation.name.startswith("measure_"):
                    inst = inst.replace(operation=Measure())
                out.append(inst)
            return out

        def run(circuits, **options):
            # Statevector needs 2^n memory in the qubits a circuit touches. A
            # circuit laid out on the whole device and measured on every qubit
            # (measure_all on an ISA circuit) touches all of them; switch to
            # matrix_product_state, which handles mostly idle qubits cheaply.
            # Only where statevector would run out of memory anyway.
            single = not isinstance(circuits, (list, tuple))
            batch = [plain_measures(c) for c in ([circuits] if single else circuits)]
            circuits = batch[0] if single else batch
            if "method" not in options and any(_dq_active_qubits(c) > 28 for c in batch):
                options["method"] = "matrix_product_state"
            return sim_run(circuits, **options)

        dev.sim.run = run
    except ImportError:
        pass  # without Aer, fake devices simulate ideally anyway
    # IBMBackend.target_history(datetime) has no offline history: the
    # device's current target stands in for every date.
    dev.target_history = lambda *a, **kw: dev.target
    _dq_devices[(cls_name, fractional)] = dev
    return dev


def _dq_label(dev):
    return f"{dev.name}{'' if _DQ_NOISE else ' (ideal)'}"


def _dq_twin(name):
    """fake_provider class for an IBM device name: "ibm_fez" -> "FakeFez"."""
    base = str(name or "").lower().replace("ibmq_", "").replace("ibm_", "").replace("fake_", "")
    for cand in (f"Fake{base.capitalize()}", f"Fake{base.capitalize()}V2"):
        if base and isinstance(getattr(_dq_fp, cand, None), type):
            return cand
    return None


def _dq_fits(dev, min_num_qubits, filters):
    if min_num_qubits and dev.num_qubits < int(min_num_qubits):
        return False
    try:
        return not callable(filters) or bool(filters(dev))
    except Exception:
        return False


def _dq_pick(name=None, min_num_qubits=None, filters=None, fractional=False):
    cls = _DQ_DEVICE
    if not _DQ_PINNED:
        cls = _dq_twin(name) or cls
        if not _dq_fits(_dq_device(cls, fractional), min_num_qubits, filters):
            cls = next((c for c in _DQ_HERONS
                        if _dq_fits(_dq_device(c, fractional), min_num_qubits, filters)), cls)
    dev = _dq_device(cls, fractional)
    print(f"[doQumentation] Intercepted by Simulator Mode — returning {_dq_label(dev)}")
    return dev


_dq_backend = _dq_device(_DQ_DEVICE)


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
        return _dq_pick(min_num_qubits=kw.get("min_num_qubits"), filters=kw.get("filters"),
                        fractional=bool(kw.get("use_fractional_gates")))

    def backend(self, name=None, *a, **kw):
        return _dq_pick(name=name, fractional=bool(kw.get("use_fractional_gates")))

    def backends(self, *a, **kw):
        return [_dq_pick(name=kw.get("name"), min_num_qubits=kw.get("min_num_qubits"),
                         filters=kw.get("filters"),
                         fractional=bool(kw.get("use_fractional_gates")))]

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


import importlib
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

# Executor has an experimental local mode: switch it on, so executor
# notebooks run on the stand-in device instead of failing.
try:
    from qiskit_ibm_runtime.executor import executor as _dq_exm
    if not getattr(_dq_exm.Executor.__init__, "_dq_local", False):
        _DQ_exec_init = _dq_exm.Executor.__init__

        def _dq_exec_init_local(self, mode=None, options=None):
            if options is None or isinstance(options, dict):
                options = dict(options or {})
                options["experimental"] = {"local_mode": True, **options.get("experimental", {})}
            else:
                options.experimental["local_mode"] = True
            _DQ_exec_init(self, mode=mode, options=options)

        _dq_exec_init_local._dq_local = True
        _dq_exm.Executor.__init__ = _dq_exec_init_local
except (ImportError, AttributeError):
    pass

# IBM's local simulation rejects these in __init__ with a bare ValueError;
# say why and what to do. Patched on the class, so every import path sees it.
for _dq_mod, _dq_cls in (("noise_learner", "NoiseLearner"), ("noise_learner_v3", "NoiseLearnerV3"),
                         ("calibrator", "Calibrator")):
    try:
        _dq_c = getattr(importlib.import_module(f"qiskit_ibm_runtime.{_dq_mod}"), _dq_cls)

        def _dq_hardware_only(self, *a, _what=_dq_cls, **kw):
            raise _DQ_NeedsIBMCloud(f"{_what} (IBM Quantum hardware only, "
                                    "not in local simulation)")

        _dq_c.__init__ = _dq_hardware_only
    except (ImportError, AttributeError):
        pass
print(f"[doQumentation] Simulator mode — using {_dq_label(_dq_backend)}")
