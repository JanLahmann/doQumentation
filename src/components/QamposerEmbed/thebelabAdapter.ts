/**
 * thebelabAdapter
 *
 * A QAMPoser SimulationAdapter implementation that executes circuits on
 * doQumentation's existing thebelab Jupyter kernel. The kernel has already
 * been configured by ExecutableCode's injectKernelSetup() based on the user's
 * settings (ideal / noisy fake / real device), so this adapter inherits that
 * routing automatically — no duplicate backend selection logic.
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

/** Convert a QAMPoser CircuitRequest into an OpenQASM 2.0 string. */
function requestToQasm(request: CircuitRequest): string {
  // QAMPoser's Circuit type requires an id on each gate; reconstruct.
  const circuit: Circuit = {
    qubits: request.qubits,
    gates: request.gates.map((g, i) => ({ ...g, id: `g${i}` })),
  };
  return circuitToQasm(circuit);
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

  // Execution block differs for real hardware vs. local backends
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
        raw_counts = result[0].data.meas.get_counts()
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

  return `def __qamposer_run():
    import base64 as _b64, json as _json
    from qiskit import QuantumCircuit
    try:
        _qasm = _b64.b64decode("${qasmB64}").decode("utf-8")
        qc = QuantumCircuit.from_qasm_str(_qasm)
        qc.measure_all()
${executionBlock}
        _counts = {str(k): int(v) for k, v in raw_counts.items()}
        print("${resultMarker}" + _json.dumps({"counts": _counts, "backend": str(backend_name)}))
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

      let data: { counts: Record<string, number>; backend?: string };
      try {
        data = JSON.parse(resultJson);
      } catch {
        throw new Error('Failed to parse simulation result from kernel output');
      }

      return {
        counts: data.counts,
        execution_time: (performance.now() - startTime) / 1000,
      };
    },

    async getBackends() {
      const mode = getExecutionMode();
      const backendType =
        mode.kind === 'noisy_fake'
          ? 'noisy_fake'
          : mode.kind === 'real'
            ? 'real'
            : 'ideal';
      return [
        {
          id: mode.kind,
          name: mode.label,
          num_qubits: 0,
          backend_type: backendType,
          description: `Routed via doQumentation settings (${mode.kind})`,
        },
      ];
    },
  };
}
