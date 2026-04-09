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
 *      the user with a Binder cold start.
 *   3. Disabled entirely when the user is in real-device mode, to avoid
 *      kernel contention with long-running hardware jobs queued via the
 *      main adapter.
 *   4. Uses the same base64 / function-scope / UUID-marker mitigations
 *      as the main thebelabAdapter.
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
  return circuitToQasm(circuit);
}

function makeRunId(): string {
  return Math.random().toString(36).slice(2, 10);
}

/**
 * Always-ideal Python template. Bypasses `_dq_backend` entirely so the live
 * preview is never routed through a fake backend or real hardware.
 */
function buildRealtimeCode(qasm: string, shots: number, runId: string): string {
  const qasmB64 = typeof btoa === 'function'
    ? btoa(qasm)
    : Buffer.from(qasm, 'utf-8').toString('base64');

  const resultMarker = `__QAMPOSER_REALTIME_${runId}__`;
  const errorMarker = `__QAMPOSER_REALTIME_ERROR_${runId}__`;

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
        qc.measure_all()
        _sim = _QP_Sim()
        _tqc = transpile(qc, _sim)
        _res = _sim.run(_tqc, shots=${shots}).result()
        _counts = {str(k): int(v) for k, v in _res.get_counts().items()}
        print("${resultMarker}" + _json.dumps({"counts": _counts}))
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

      const data: { counts: Record<string, number> } = JSON.parse(resultJson);
      return {
        counts: data.counts,
        execution_time: (performance.now() - startTime) / 1000,
      };
    },
  };
}
