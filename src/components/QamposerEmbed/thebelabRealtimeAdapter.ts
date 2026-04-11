/**
 * thebelabRealtimeAdapter
 *
 * A SimulationAdapter used for QAMPoser's automatic live preview on circuit
 * changes (via the `realtimeAdapter` prop on QamposerProvider).
 *
 * Design decisions:
 *   1. ALWAYS runs ideal simulation, regardless of doQumentation settings.
 *      Live previews must never touch real hardware — clicking a gate should
 *      never queue an IBM Quantum job.
 *   2. Does NOT auto-bootstrap the kernel. isAvailable() only returns true
 *      when a kernel is already connected, so live previews never surprise
 *      the user with a Binder cold start. (See QamposerEmbedClient.tsx for
 *      the prewarm-on-mount logic that gets the kernel ready in the
 *      background, and the kernelStatus dep on the useMemo that recreates
 *      this adapter once bootstrap completes — Qamposer otherwise caches
 *      isAvailable()'s initial `false` answer forever.)
 *   3. Disabled entirely when the user is in real-device mode, to avoid
 *      kernel contention with long-running hardware jobs queued via the
 *      main adapter.
 *   4. Uses the same base64 / function-scope / UUID-marker mitigations
 *      as the main thebelabAdapter.
 *   5. Counts + Q-sphere shapes match the main adapter (and upstream
 *      qamposer-backend) — see thebelabAdapter.ts for the `measure q -> c;`
 *      / qsphere port rationale.
 */

import {
  type SimulationAdapter,
  type CircuitRequest,
  type SimulationResult,
  type Circuit,
  circuitToQasm,
} from '@qamposer/react';
import { executeOnKernelWithOutput, getActiveKernel } from '../ExecutableCode';
import { getExecutionMode } from './executionMode';

function requestToQasm(request: CircuitRequest): string {
  const circuit: Circuit = {
    qubits: request.qubits,
    gates: request.gates.map((g, i) => ({ ...g, id: `g${i}` })),
  };
  // Append `measure q -> c;` so counts come from the single existing
  // classical register and avoid the space-delimited keys that
  // qc.measure_all() would produce. See thebelabAdapter.ts for the full
  // explanation; the realtime path needs the same fix.
  return circuitToQasm(circuit).trimEnd() + '\nmeasure q -> c;\n';
}

function makeRunId(): string {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * Always-ideal Python template. Bypasses `_dq_backend` entirely so the live
 * preview is never routed through a fake backend or real hardware.
 *
 * Counts come from the single `c` classical register that was declared by
 * circuitToQasm and measured into via the `measure q -> c;` line appended
 * in requestToQasm. Q-sphere is computed from the ideal statevector,
 * matching the main adapter and upstream qamposer-backend's qsphere.py.
 */
function buildRealtimeCode(qasm: string, shots: number, runId: string): string {
  const qasmB64 = typeof btoa === 'function'
    ? btoa(qasm)
    : Buffer.from(qasm, 'utf-8').toString('base64');

  const resultMarker = `__QAMPOSER_REALTIME_${runId}__`;
  const errorMarker = `__QAMPOSER_REALTIME_ERROR_${runId}__`;

  // Q-sphere computation — line-by-line port of upstream qamposer-backend's
  // src/backend/quantum/qsphere.py compute_qsphere_points(). Kept identical
  // to the main adapter's qsphereBlock so behaviour is consistent across the
  // realtime preview and the explicit Run path.
  const qsphereBlock = `        _qsphere_points = []
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
            _qsphere_points = []`;

  return `def __qamposer_realtime():
    import base64 as _b64, json as _json
    from qiskit import QuantumCircuit, transpile
    try:
        try:
            from qiskit_aer import AerSimulator as _QP_Sim
        except ImportError:
            from qiskit.providers.basic_provider import BasicSimulator as _QP_Sim
        _qasm = _b64.b64decode("${qasmB64}").decode("utf-8")
        qc = QuantumCircuit.from_qasm_str(_qasm)
        _sim = _QP_Sim()
        _tqc = transpile(qc, _sim)
        _res = _sim.run(_tqc, shots=${shots}).result()
        _counts = {str(k): int(v) for k, v in _res.get_counts().items()}
${qsphereBlock}
        print("${resultMarker}" + _json.dumps({"counts": _counts, "qsphere": _qsphere_points}))
    except Exception as _e:
        print("${errorMarker}" + _json.dumps({"type": type(_e).__name__, "message": str(_e)}))

try:
    __qamposer_realtime()
finally:
    try:
        del __qamposer_realtime
    except Exception:
        pass
`;
}

function extractMarker(buffer: string, marker: string): string | null {
  const idx = buffer.indexOf(marker);
  if (idx < 0) return null;
  const start = idx + marker.length;
  const newline = buffer.indexOf('\n', start);
  const end = newline < 0 ? buffer.length : newline;
  return buffer.slice(start, end);
}

export function createThebelabRealtimeAdapter(): SimulationAdapter {
  return {
    name: 'doQumentation live preview (ideal)',

    async isAvailable(): Promise<boolean> {
      // Only available when a kernel is already connected AND not in real-device mode.
      if (!getActiveKernel()) return false;
      if (getExecutionMode().kind === 'real') return false;
      return true;
    },

    async simulate(request: CircuitRequest): Promise<SimulationResult> {
      const kernel = getActiveKernel();
      if (!kernel) {
        throw new Error('Live preview requires an active kernel');
      }
      if (getExecutionMode().kind === 'real') {
        throw new Error('Live preview is disabled in real-device mode');
      }

      const qasm = requestToQasm(request);
      const runId = makeRunId();
      const code = buildRealtimeCode(qasm, request.shots || 1024, runId);

      const resultMarker = `__QAMPOSER_REALTIME_${runId}__`;
      const errorMarker = `__QAMPOSER_REALTIME_ERROR_${runId}__`;

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
        throw new Error('Failed to dispatch live preview to kernel');
      }
      if (kernelErrorRef.current) {
        throw new Error(`${kernelErrorRef.current.type}: ${kernelErrorRef.current.message}`);
      }

      const errorJson = extractMarker(buffer, errorMarker);
      if (errorJson) {
        try {
          const err = JSON.parse(errorJson);
          throw new Error(`${err.type}: ${err.message}`);
        } catch (parseErr) {
          throw parseErr instanceof Error
            ? parseErr
            : new Error('Live preview failed');
        }
      }

      const resultJson = extractMarker(buffer, resultMarker);
      if (!resultJson) {
        throw new Error('Live preview returned no result');
      }

      interface QSpherePointWire {
        state: string;
        x: number;
        y: number;
        z: number;
        probability: number;
        phase: number;
      }
      const data: {
        counts: Record<string, number>;
        qsphere?: QSpherePointWire[];
      } = JSON.parse(resultJson);
      return {
        counts: data.counts,
        execution_time: (performance.now() - startTime) / 1000,
        qsphere: Array.isArray(data.qsphere) && data.qsphere.length > 0
          ? data.qsphere
          : undefined,
      };
    },
  };
}
