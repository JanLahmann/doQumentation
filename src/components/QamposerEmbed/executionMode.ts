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
  getExecutionMode as getConfigMode,
  getFakeDevice,
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
  const mode = getConfigMode();
  switch (mode) {
    case 'aer':
      return { kind: 'ideal', label: 'AerSimulator' };
    case 'fake': {
      const device = getFakeDevice();
      return { kind: 'noisy_fake', label: device, device };
    }
    case 'credentials':
      return { kind: 'real', label: 'IBM Quantum' };
    case 'none':
      return { kind: 'none', label: 'AerSimulator (fallback)' };
  }
}
