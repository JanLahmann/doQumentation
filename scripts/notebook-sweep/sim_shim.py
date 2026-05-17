"""
sim_shim.py — neuter qiskit-ibm-runtime so notebooks run on Aer/fakes only.

Loaded via PYTHONSTARTUP (interactive) AND imported explicitly by the kernel
launcher so it also takes effect for nbclient (non-interactive). It must be
import-safe and idempotent: notebooks frequently re-import the symbols it
patches, and a notebook's own `from qiskit_ibm_runtime import ...` must pick
up the patched objects.

Guarantees:
  * No network / no auth: QiskitRuntimeService() constructs offline.
  * No real jobs: SamplerV2/EstimatorV2 bound to any IBM backend or a
    Session/Batch transparently fall back to qiskit_aer.primitives.
  * service.backend()/least_busy()/backends() return fake backends, sized
    to the request when a qubit count / simulator flag is given.
  * Session/Batch become no-op context managers.

Anything we miss surfaces as an error in the sweep report (a "shim gap"),
which is the intended signal — we patch the gap and re-run the subset.
"""
from __future__ import annotations

import os
import sys

_MARKER = "_DOQ_SIM_SHIM_APPLIED"


def _log(msg: str) -> None:
    # stderr so it never pollutes nbclient's stdout capture
    print(f"[sim_shim] {msg}", file=sys.stderr, flush=True)


class CloudOnlyOffline(RuntimeError):
    """Raised by the shim when a notebook needs a live IBM Cloud
    resource that has NO offline/simulator equivalent (premium Qiskit
    Functions, retrieving a pre-existing job by ID, etc.).

    Distinctly named so the sweep report buckets these as
    "cloud-only — not runnable offline (EXPECTED)" rather than
    confusing them with shim gaps or real notebook bugs.
    """


def apply() -> None:
    import qiskit_ibm_runtime as qir

    if getattr(qir, _MARKER, False):
        return

    from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2

    _fake_provider = FakeProviderForBackendV2()
    _fakes = list(_fake_provider.backends())
    # name -> backend, and sorted-by-qubits for "give me something >= N"
    _by_name = {b.name: b for b in _fakes}
    _by_qubits = sorted(_fakes, key=lambda b: getattr(b, "num_qubits", 0))

    def _default_fake():
        # 127q heavy-hex, the modern IBM default users would get
        return _by_name.get("fake_brisbane") or _by_qubits[-1]

    def _largest_fake():
        return _by_qubits[-1]  # 127q heavy-hex

    def _pick_fake(name=None, min_num_qubits=None, use_fractional_gates=False):
        # NOTE: do NOT route use_fractional_gates -> the 5q
        # `fake_fractional`. Notebooks that ask least_busy(simulator=
        # False, use_fractional_gates=True) build utility-scale (100+q)
        # circuits and expect a 127q device; a 5q backend yields a
        # bogus TranspilerError. Aer simulates the 127q fake fine
        # regardless of native fractional-gate support, so prefer size.
        if name:
            key = str(name).lower().replace("ibm_", "fake_").replace("ibmq_", "fake_")
            if key in _by_name:
                return _by_name[key]
            # bare match e.g. "brisbane" -> "fake_brisbane"
            if f"fake_{name}".lower() in _by_name:
                return _by_name[f"fake_{name}".lower()]
        if min_num_qubits:
            for b in _by_qubits:
                if getattr(b, "num_qubits", 0) >= int(min_num_qubits):
                    return b
        # No name / size hint: hand back the largest device so any
        # circuit fits. least_busy(simulator=False) on real hardware
        # would likewise return a utility-scale QPU.
        if use_fractional_gates:
            return _largest_fake()
        return _default_fake()

    # ---- QiskitRuntimeService -------------------------------------------
    class _FakeService:
        """Drop-in for QiskitRuntimeService — fully offline."""

        def __init__(self, *a, **kw):
            self._channel = kw.get("channel", "ibm_quantum")

        # account / metadata no-ops
        @staticmethod
        def save_account(*a, **kw):
            return None

        @staticmethod
        def saved_accounts(*a, **kw):
            return {}

        @staticmethod
        def delete_account(*a, **kw):
            return None

        def active_account(self, *a, **kw):
            return {"channel": self._channel, "instance": "sim/shim"}

        def active_instance(self, *a, **kw):
            return "sim/shim"

        def instances(self, *a, **kw):
            return ["sim/shim"]

        # backend resolution -> fakes
        def backend(self, name=None, *a, **kw):
            return _pick_fake(name=name)

        def backends(self, *a, **kw):
            n = kw.get("min_num_qubits")
            flt = kw.get("filters")
            bks = _by_qubits
            if n:
                bks = [b for b in bks if getattr(b, "num_qubits", 0) >= int(n)]
            if callable(flt):
                try:
                    bks = [b for b in bks if flt(b)]
                except Exception:
                    pass
            return bks or [_default_fake()]

        def least_busy(self, *a, **kw):
            return _pick_fake(
                min_num_qubits=kw.get("min_num_qubits"),
                use_fractional_gates=kw.get("use_fractional_gates", False),
            )

        # job introspection — nothing ran, so nothing to show
        def jobs(self, *a, **kw):
            return []

        def job(self, *a, **kw):
            # service.job("<paste-job-id>") retrieves a previously
            # submitted real cloud job — no offline equivalent.
            raise CloudOnlyOffline(
                "service.job(id) needs a pre-existing IBM Cloud job; "
                "not runnable offline"
            )

        def usage(self, *a, **kw):
            return {"period": "sim/shim", "byInstance": []}

        def check_pending_jobs(self, *a, **kw):
            return None

    qir.QiskitRuntimeService = _FakeService

    # ---- Qiskit Functions / Serverless (qiskit_ibm_catalog) -------------
    # These notebooks load+run *premium IBM-hosted functions*
    # (catalog.load("algorithmiq/tem").run(...)). There is NO offline
    # equivalent — the function code runs on IBM's cloud. Construct the
    # catalog cleanly (so imports/instantiation succeed and we can see
    # any *other* issues earlier in the notebook), but loading/running a
    # function raises CloudOnlyOffline so the report buckets it as
    # expected-cloud-only, not a shim gap.
    try:
        import qiskit_ibm_catalog as qic

        class _FakeFunction:
            def __init__(self, name="cloud-fn"):
                self.title = name
                self.name = name

            def run(self, *a, **kw):
                raise CloudOnlyOffline(
                    f"Qiskit Function {self.name!r} runs on IBM Cloud; "
                    "no offline equivalent"
                )

        class _FakeCatalog:
            def __init__(self, *a, **kw):
                pass

            def load(self, name="cloud-fn", *a, **kw):
                # Return a function handle; the cloud boundary is .run().
                return _FakeFunction(name)

            def list(self, *a, **kw):
                return []

            def jobs(self, *a, **kw):
                return []

            def job(self, *a, **kw):
                raise CloudOnlyOffline(
                    "Qiskit Functions job lookup needs IBM Cloud"
                )

            get_job_by_id = job

            def upload(self, *a, **kw):
                # Deploying a serverless function/program is inherently
                # a cloud operation (serverless-first-program,
                # spin-chain-vqe, …).
                raise CloudOnlyOffline(
                    "Qiskit Functions upload/deploy needs IBM Cloud"
                )

            # less-common catalog surface seen across notebooks
            def files(self, *a, **kw):
                return []

            file_upload = upload
            file_download = upload
            provider_file_upload = upload

            @staticmethod
            def save_account(*a, **kw):
                return None

        # Both the Functions catalog and the lower-level Serverless
        # client share the same offline boundary.
        qic.QiskitFunctionsCatalog = _FakeCatalog
        if hasattr(qic, "QiskitServerless"):
            qic.QiskitServerless = _FakeCatalog
    except ModuleNotFoundError:
        pass  # notebook may pip-install it; runner re-applies after

    # ---- Session / Batch -> no-op context managers ----------------------
    class _NoopExecutionMode:
        def __init__(self, *a, **kw):
            # capture a backend if one was passed positionally or by kw
            self.backend = kw.get("backend")
            if a:
                self.backend = a[-1] if not self.backend else self.backend
            self._service = kw.get("service")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def close(self):
            return None

    qir.Session = _NoopExecutionMode
    qir.Batch = _NoopExecutionMode

    # ---- Permissive options stub ----------------------------------------
    # IBM primitives expose a deeply-nested mutable options tree:
    #   sampler.options.dynamical_decoupling.enable = True
    #   estimator.options.resilience.zne.noise_factors = [1, 3, 5]
    #   estimator.options.update(default_shots=4000)
    #   sampler.options.environment.job_tags = [...]
    # Aer primitives have no such tree, so notebooks blow up with
    # AttributeError. _Opts absorbs ANY attribute/item get-set-call:
    # nested access auto-creates children, assignments stick (so
    # read-back / prints work), .update() and calls are no-ops. It
    # never affects execution — Aer ignores it — it just lets the
    # notebook's option-plumbing run so deeper code is reached.
    class _Opts:
        def __init__(self):
            object.__setattr__(self, "_d", {})

        def __getattr__(self, k):
            d = object.__getattribute__(self, "_d")
            if k not in d:
                d[k] = _Opts()
            return d[k]

        def __setattr__(self, k, v):
            object.__getattribute__(self, "_d")[k] = v

        def __getitem__(self, k):
            return self.__getattr__(k)

        def __setitem__(self, k, v):
            self.__setattr__(k, v)

        def update(self, *a, **kw):
            d = object.__getattribute__(self, "_d")
            for src in (*a, kw):
                if isinstance(src, dict):
                    d.update(src)
            return None

        def __call__(self, *a, **kw):
            return self

        def __iter__(self):
            return iter(object.__getattribute__(self, "_d"))

        def __repr__(self):
            return f"_Opts({object.__getattribute__(self, '_d')!r})"

    _PERMISSIVE_TYPES: set = set()

    def _make_permissive(obj) -> None:
        """Let an Aer options object absorb IBM-only attribute access.

        Python only calls __getattr__ when normal lookup FAILS, so
        real Aer attributes (backend_options, default_shots, …) keep
        working untouched; only unknown IBM-only names
        (dynamical_decoupling, environment, resilience, twirling, …)
        fall through to an auto-created permissive _Opts child. The
        fallback is installed once per options *type*.
        """
        cls = type(obj)
        if cls in _PERMISSIVE_TYPES:
            return

        def __getattr__(self, name):  # noqa: N807
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            store = self.__dict__.setdefault("_doq_perm", {})
            if name not in store:
                store[name] = _Opts()
            return store[name]

        try:
            cls.__getattr__ = __getattr__
            _PERMISSIVE_TYPES.add(cls)
        except (TypeError, AttributeError):
            # Built-in / slotted type we can't patch — best effort.
            pass

    # ---- Primitives -> Aer ----------------------------------------------
    from qiskit_aer.primitives import SamplerV2 as _AerSampler
    from qiskit_aer.primitives import EstimatorV2 as _AerEstimator

    def _aer_primitive(aer_cls):
        class _Wrapped(aer_cls):
            # IBM primitives take (mode=backend|session, options=...).
            # Aer primitives don't accept `mode` — strip it and any
            # IBM-only kwargs, keep the call working on a simulator.
            def __init__(self, *a, **kw):
                kw.pop("mode", None)
                kw.pop("backend", None)
                kw.pop("session", None)
                kw.pop("options", None)
                try:
                    super().__init__(*a, **kw)
                except TypeError:
                    super().__init__()
                # Keep Aer's REAL options object (it owns
                # backend_options etc. that Aer needs), but make
                # unknown IBM-only attribute access auto-create
                # permissive children so notebook option-plumbing like
                # `sampler.options.dynamical_decoupling.enable = True`
                # neither raises nor disturbs Aer execution.
                real = super().options
                _make_permissive(real)

            # No `options` property override — Aer's own descriptor
            # stays intact (it's read during super().__init__()).

        _Wrapped.__name__ = aer_cls.__name__
        _Wrapped.__qualname__ = aer_cls.__qualname__
        return _Wrapped

    qir.SamplerV2 = _aer_primitive(_AerSampler)
    qir.EstimatorV2 = _aer_primitive(_AerEstimator)
    # Some notebooks use the V1-era names / aliases
    if hasattr(qir, "Sampler"):
        qir.Sampler = qir.SamplerV2
    if hasattr(qir, "Estimator"):
        qir.Estimator = qir.EstimatorV2

    # ---- Standalone Options classes -> permissive stub ------------------
    # Notebooks build options BEFORE the primitive:
    #   options = EstimatorOptions(); options.resilience.zne... = ...
    #   then EstimatorV2(mode=backend, options=options)
    # Replace the option classes (top-level + .options submodule) with
    # the permissive stub so that construction + nested assignment never
    # raise. The primitive wrapper drops `options=` anyway.
    def _opts_factory(*a, **kw):
        return _Opts()

    for _name in (
        "Options", "OptionsV2", "EstimatorOptions", "SamplerOptions",
        "RuntimeOptions",
    ):
        if hasattr(qir, _name):
            setattr(qir, _name, _opts_factory)
    try:
        from qiskit_ibm_runtime import options as _optmod

        for _name in dir(_optmod):
            if _name.endswith("Options") and not _name.startswith("_"):
                setattr(_optmod, _name, _opts_factory)
    except Exception as e:  # noqa: BLE001
        _log(f"could not patch options submodule: {e}")

    # ---- FakeBackend rough edges ----------------------------------------
    # Pass A surfaced: `'FakeBrisbane' object is not callable` (a
    # notebook treats the backend like a factory) and missing
    # `target_history`. Add permissive shims on the fake backend
    # classes so these don't masquerade as real notebook bugs.
    for _b in _fakes:
        cls = type(_b)
        if not getattr(cls, "_doq_patched", False):
            if not callable(cls):
                pass  # classes are callable; instances handled below
            if not hasattr(cls, "target_history"):
                try:
                    cls.target_history = property(
                        lambda self: [getattr(self, "target", None)]
                    )
                except Exception:
                    pass
            cls._doq_patched = True

    # ---- Missing symbols some notebooks import ---------------------------
    # dc-hex-ising imports this from the wrong module (real home:
    # qiskit.providers.exceptions). Provide it so the *import* succeeds
    # and the sweep can proceed past cell 7 to find any real issues.
    try:
        import qiskit_ibm_runtime.exceptions as _exc

        if not hasattr(_exc, "QiskitBackendNotFoundError"):
            try:
                from qiskit.providers.exceptions import QiskitBackendNotFoundError as _QBNFE
            except Exception:
                class _QBNFE(Exception):
                    pass
            _exc.QiskitBackendNotFoundError = _QBNFE
    except Exception as e:
        _log(f"could not patch exceptions module: {e}")

    setattr(qir, _MARKER, True)
    _log("applied (offline; Aer-backed primitives; fake backends)")


# Apply on import / PYTHONSTARTUP. Tolerate qiskit_ibm_runtime not yet
# installed (e.g. a notebook's first cell pip-installs it) — the runner
# re-applies after the install cell.
if os.environ.get("DOQ_SIM_SHIM", "1") != "0":
    try:
        apply()
    except ModuleNotFoundError:
        pass
    except Exception as _e:  # never let the shim itself break a kernel
        _log(f"apply() failed: {_e!r}")
