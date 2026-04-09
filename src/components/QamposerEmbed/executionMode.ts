/**
 * Execution Mode
 *
 * Reads doQumentation's existing settings to determine which of the three
 * quantum execution modes the Qamposer adapter should route through.
 *
 * The kernel has already been configured by ExecutableCode's injectKernelSetup()
 * based on the same settings — see src/components/ExecutableCode/index.tsx.
 * This helper mirrors that decision so the adapter can build the right Python
 * template (simulator vs. real device) without duplicating the selection logic.
 */

import {
  getSimulatorMode,
  getSimulatorBackend,
  getFakeDevice,
  getIBMQuantumToken,
  getActiveMode,
} from '../../config/jupyter';

export type ExecutionMode =
  | { kind: 'ideal'; label: string }
  | { kind: 'noisy_fake'; label: string; device: string }
  | { kind: 'real'; label: string }
  | { kind: 'none'; label: string };

/**
 * Determine the active execution mode from the user's settings.
 * Mirrors the decision logic in injectKernelSetup() in ExecutableCode.
 */
export function getExecutionMode(): ExecutionMode {
  const simMode = getSimulatorMode();
  const token = getIBMQuantumToken();
  const activeMode = getActiveMode();

  const hasBoth = simMode && !!token;
  const useSimulator = simMode && (!hasBoth || activeMode === 'simulator');
  const useCredentials = !!token && (!simMode || activeMode === 'credentials');

  // If both are configured but no choice made, default to simulator (matches ExecutableCode)
  if (useSimulator || (hasBoth && !activeMode)) {
    const backend = getSimulatorBackend();
    if (backend === 'fake') {
      const device = getFakeDevice();
      return { kind: 'noisy_fake', label: device, device };
    }
    return { kind: 'ideal', label: 'AerSimulator' };
  }

  if (useCredentials) {
    return { kind: 'real', label: 'IBM Quantum' };
  }

  // No mode configured — adapter will fall back to local AerSimulator
  return { kind: 'none', label: 'AerSimulator (fallback)' };
}
