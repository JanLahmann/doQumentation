/**
 * thebelabAdapter
 *
 * A QAMPoser SimulationAdapter implementation that executes circuits on
 * doQumentation's existing thebelab Jupyter kernel. The kernel has already
 * been configured by ExecutableCode's injectKernelSetup() based on the user's
 * settings (ideal / noisy fake / real device), so this adapter inherits that
 * routing automatically — no duplicate backend selection logic.
 *
 * ─── Upstream compatibility ─────────────────────────────────────────────────
 * The Python code we ship to the kernel is a PORT of QAMP-62's qamposer-backend
 * Python service that powers https://qamposer.org/demo. Specifically:
 *
 *   - `measure q -> c;` is appended to the QASM string before sending
 *     (mirrors QAMP-62/qamposer-backend/src/backend/quantum/converter.py's
 *     `json_to_qasm()` which always appends `measure q -> c;`).
 *   - `get_counts()` reads from the single `c` classical register — matching
 *     upstream's ResultsPanel expectation that count keys are pure binary
 *     strings with no space separator.
 *   - The Q-sphere point computation in `qsphereBlock` below is a line-by-line
 *     port of QAMP-62/qamposer-backend/src/backend/quantum/qsphere.py
 *     (`compute_qsphere_points()`). Same Hamming-weight grouping, same
 *     theta/phi formulas, same 5-qubit cap, same probability normalization.
 *
 * IMPORTANT: If upstream's simulator.py or qsphere.py change, this file
 * must be updated to match. See PROJECT_HANDOFF.md → Open Items → TODO →
 * "Qamposer Python backend reuse" for the long-term plan to package
 * upstream's code so it can be installed via pip instead of inline-ported.
 *
 * Upstream source (Apache 2.0): https://github.com/QAMP-62/qamposer-backend
 * ────────────────────────────────────────────────────────────────────────────
 *
 * Mitigations baked in:
 *   1. QASM is base64-encoded in JS and decoded in Python (no string injection)
 *   2. Python code runs in a function scope to avoid kernel-global pollution
 *   3. stdout markers include a per-request UUID to prevent collisions
 *   4. Try/except at the Python level converts exceptions into ERROR markers
 *   5. The function is del'd after execution to keep the namespace clean
 */

import {
  type SimulationAdapter,
  type CircuitRequest,
  type SimulationResult,
  type Circuit,
  circuitToQasm,
} from '@qamposer/react';
import { executeOnKernelWithOutput, getActiveKernel } from '../ExecutableCode';
import { getExecutionMode, type ExecutionMode } from './executionMode';
import { waitForKernelReady } from './kernelReady';

/**
 * Convert a QAMPoser CircuitRequest into an OpenQASM 2.0 string with a
 * trailing `measure q -> c;` line.
 *
 * `circuitToQasm` from @qamposer/react only emits `qreg q[N]; creg c[N];`
 * plus gate instructions — it never adds measurements. If we relied on
 * `qc.measure_all()` in Python, Qiskit would add a SECOND classical
 * register (`meas`) alongside the existing `c`, and get_counts() would
 * return space-delimited keys like "000 000". Those keys break Qamposer's
 * ResultsPanel which assumes single-register binary strings. Instead we
 * emulate upstream qamposer-backend's converter: measure into the single
 * `c` register that's already declared by circuitToQasm.
 */
function requestToQasm(request: CircuitRequest): string {
  // QAMPoser's Circuit type requires an id on each gate; reconstruct.
  const circuit: Circuit = {
    qubits: request.qubits,
    gates: request.gates.map((g, i) => ({ ...g, id: `g${i}` })),
  };
  const qasm = circuitToQasm(circuit);
  return qasm.trimEnd() + '\nmeasure q -> c;\n';
}

/** Generate a short random id suitable for a stdout marker. */
function makeRunId(): string {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * Build the Python template sent to the kernel.
 * Branches on execution mode so we pick the correct Qiskit API
 * (Backend.run() for local simulators, SamplerV2 for real hardware).
 */
function buildSimulateCode(
  qasm: string,
  shots: number,
  runId: string,
  mode: ExecutionMode,
): string {
  // Base64 encode to avoid Python string-injection when QASM contains triple quotes.
  const qasmB64 = typeof btoa === 'function'
    ? btoa(qasm)
    : Buffer.from(qasm, 'utf-8').toString('base64');

  const resultMarker = `__QAMPOSER_RESULT_${runId}__`;
  const errorMarker = `__QAMPOSER_ERROR_${runId}__`;

  // Execution block differs for real hardware vs. local backends.
  // The QASM already contains `measure q -> c;` (added by requestToQasm),
  // so counts come from the single `c` register — no extra measure_all().
  let executionBlock: string;
  if (mode.kind === 'real') {
    executionBlock = `        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        from qiskit import transpile
        service = QiskitRuntimeService()
        backend = service.least_busy(simulator=False, operational=True)
        tqc = transpile(qc, backend)
        sampler = SamplerV2(backend)
        job = sampler.run([tqc], shots=${shots})
        result = job.result()
        raw_counts = result[0].data.c.get_counts()
        backend_name = getattr(backend, "name", str(backend))`;
  } else {
    executionBlock = `        from qiskit import transpile
        try:
            backend = _dq_backend  # injected by Simulator Mode, if active
        except NameError:
            try:
                from qiskit_aer import AerSimulator as _QP_Sim
            except ImportError:
                from qiskit.providers.basic_provider import BasicSimulator as _QP_Sim
            backend = _QP_Sim()
        tqc = transpile(qc, backend)
        _res = backend.run(tqc, shots=${shots}).result()
        raw_counts = _res.get_counts()
        backend_name = type(backend).__name__`;
  }

  // Q-sphere computation — ported from QAMP-62/qamposer-backend's qsphere.py.
  // Produces the same shape QSphereView expects: list of
  //   {state, x, y, z, probability, phase}
  // computed from the ideal statevector (noise-free, regardless of backend).
  // Skipped for >5 qubits because the view is only meaningful up to there.
  const qsphereBlock = `        # --- Q-sphere points (upstream-compatible) ---
        _qsphere_points = []
        try:
            import numpy as _np
            from qiskit.quantum_info import Statevector as _QP_Statevector
            _qc_nomeas = qc.remove_final_measurements(inplace=False)
            _nq = _qc_nomeas.num_qubits
            if 1 <= _nq <= 5:
                _state = _QP_Statevector.from_instruction(_qc_nomeas)
                _amps = _np.asarray(_state.data)
                _by_weight = {}
                for _idx in range(_amps.shape[0]):
                    _bs = format(_idx, "0" + str(_nq) + "b")
                    _w = _bs.count("1")
                    _by_weight.setdefault(_w, []).append(_idx)
                for _w, _indices in _by_weight.items():
                    if not _indices:
                        continue
                    if _nq <= 1:
                        _theta = 0.0 if _w == 0 else float(_np.pi)
                    else:
                        _theta = float(_np.pi * _w / _nq)
                    _ring = len(_indices)
                    for _pos, _idx in enumerate(_indices):
                        _amp = _amps[_idx]
                        _prob = float(_np.real(_amp * _np.conj(_amp)))
                        if _prob < 1e-12:
                            continue
                        _phase = float(_np.angle(_amp))
                        _phi = 2.0 * float(_np.pi) * _pos / _ring
                        _qsphere_points.append({
                            "state": format(_idx, "0" + str(_nq) + "b"),
                            "x": float(_np.sin(_theta) * _np.cos(_phi)),
                            "y": float(_np.sin(_theta) * _np.sin(_phi)),
                            "z": float(_np.cos(_theta)),
                            "probability": _prob,
                            "phase": _phase,
                        })
                _total = sum(_p["probability"] for _p in _qsphere_points) or 1.0
                for _p in _qsphere_points:
                    _p["probability"] = _p["probability"] / _total
        except Exception:
            # Q-sphere is optional — never block the simulation on its failure.
            _qsphere_points = []`;

  return `def __qamposer_run():
    import base64 as _b64, json as _json
    from qiskit import QuantumCircuit
    try:
        _qasm = _b64.b64decode("${qasmB64}").decode("utf-8")
        qc = QuantumCircuit.from_qasm_str(_qasm)
${executionBlock}
        _counts = {str(k): int(v) for k, v in raw_counts.items()}
${qsphereBlock}
        _payload = {
            "counts": _counts,
            "backend": str(backend_name),
            "qsphere": _qsphere_points,
        }
        print("${resultMarker}" + _json.dumps(_payload))
    except Exception as _e:
        print("${errorMarker}" + _json.dumps({"type": type(_e).__name__, "message": str(_e)}))

try:
    __qamposer_run()
finally:
    try:
        del __qamposer_run
    except Exception:
        pass
`;
}

/** Extract JSON payload following a marker in the buffered stdout. */
function extractMarker(buffer: string, marker: string): string | null {
  const idx = buffer.indexOf(marker);
  if (idx < 0) return null;
  const start = idx + marker.length;
  // The payload runs until the next newline
  const newline = buffer.indexOf('\n', start);
  const end = newline < 0 ? buffer.length : newline;
  return buffer.slice(start, end);
}

/**
 * Create a SimulationAdapter that routes through doQumentation's thebelab kernel.
 * All three execution modes (ideal / noisy fake / real device) are supported
 * and selected automatically from the user's doQumentation settings.
 */
export function createThebelabAdapter(): SimulationAdapter {
  return {
    name: 'doQumentation kernel',

    async isAvailable(): Promise<boolean> {
      // Always report available — simulate() will bootstrap on demand if needed.
      return true;
    },

    async simulate(request: CircuitRequest): Promise<SimulationResult> {
      // Ensure a kernel is running before we try to execute.
      if (!getActiveKernel()) {
        await waitForKernelReady();
      }
      const kernel = getActiveKernel();
      if (!kernel) {
        throw new Error('No kernel available to execute simulation');
      }

      const mode = getExecutionMode();
      const qasm = requestToQasm(request);
      const runId = makeRunId();
      const code = buildSimulateCode(qasm, request.shots, runId, mode);

      const resultMarker = `__QAMPOSER_RESULT_${runId}__`;
      const errorMarker = `__QAMPOSER_ERROR_${runId}__`;

      const startTime = performance.now();
      let buffer = '';
      const kernelErrorRef: { current: { type: string; message: string } | null } = { current: null };

      const dispatched = await executeOnKernelWithOutput(
        kernel,
        code,
        (text: string) => {
          buffer += text;
        },
        (ename: string, evalue: string) => {
          kernelErrorRef.current = { type: ename, message: evalue };
        },
      );

      if (!dispatched) {
        throw new Error('Failed to dispatch simulation code to kernel');
      }

      // Surface unhandled kernel errors first
      if (kernelErrorRef.current) {
        throw new Error(`${kernelErrorRef.current.type}: ${kernelErrorRef.current.message}`);
      }

      // Handle Python-level errors captured via our __QAMPOSER_ERROR__ marker
      const errorJson = extractMarker(buffer, errorMarker);
      if (errorJson) {
        try {
          const err = JSON.parse(errorJson);
          throw new Error(`${err.type}: ${err.message}`);
        } catch (parseErr) {
          if (parseErr instanceof Error && parseErr.message.startsWith('SyntaxError')) {
            throw new Error('Simulation failed (could not parse error payload)');
          }
          throw parseErr;
        }
      }

      // Success path — parse counts from result marker
      const resultJson = extractMarker(buffer, resultMarker);
      if (!resultJson) {
        throw new Error(
          'Simulation completed without a result marker. The kernel may be in an unexpected state.',
        );
      }

      interface QSpherePointWire {
        state: string;
        x: number;
        y: number;
        z: number;
        probability: number;
        phase: number;
      }
      let data: {
        counts: Record<string, number>;
        backend?: string;
        qsphere?: QSpherePointWire[];
      };
      try {
        data = JSON.parse(resultJson);
      } catch {
        throw new Error('Failed to parse simulation result from kernel output');
      }

      const result: SimulationResult = {
        counts: data.counts,
        execution_time: (performance.now() - startTime) / 1000,
        qsphere: Array.isArray(data.qsphere) && data.qsphere.length > 0
          ? data.qsphere
          : undefined,
      };
      // TEMPORARY DEBUG: stash the full result on window so we can inspect it
      // from a puppeteer probe even if Qamposer's render crashes synchronously.
      // Remove once the React #130 bug is identified and fixed.
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).__qamp_lastResult = result;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).__qamp_lastResultJSON = JSON.stringify(result, null, 2);
        console.info('[Qamposer DEBUG] Full result:', result);
      } catch {
        // ignore
      }
      return result;
    },

    async getBackends() {
      // QAMPoser's SimulationControls dialog only lists entries where
      // backend_type === "noisy_fake" — everything else is silently
      // filtered out (and a disabled "Real Hardware — Coming soon" is
      // appended unconditionally). If we report our actual mode (ideal
      // or real), the dialog shows an empty Step 2 and the Run button
      // does nothing useful.
      //
      // Our simulate() ignores the `profile` argument the dialog passes
      // back anyway — execution is routed via doQumentation Settings
      // at the Python layer (ideal AerSimulator / noisy FakeBackend /
      // real IBM Quantum). So we always report backend_type="noisy_fake"
      // here purely to satisfy the dialog's filter. The displayed name
      // still reflects the user's actual active mode so they can see
      // what will run.
      const mode = getExecutionMode();
      const labelPrefix =
        mode.kind === 'real'
          ? 'IBM Quantum (real hardware)'
          : mode.kind === 'noisy_fake'
            ? 'Noisy fake backend'
            : mode.kind === 'ideal'
              ? 'Ideal simulator'
              : 'Ideal simulator (fallback)';
      return [
        {
          id: `doqumentation-${mode.kind}`,
          name: `${labelPrefix} · ${mode.label}`,
          num_qubits: 32,
          backend_type: 'noisy_fake' as const,
          description: `Routed via doQumentation Settings (${mode.kind})`,
        },
      ];
    },
  };
}
