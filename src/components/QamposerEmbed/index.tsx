/**
 * QamposerEmbed
 *
 * SSR-safe wrapper around QAMPoser's QamposerMicro component, wired into
 * doQumentation's thebelab kernel via thebelabAdapter and thebelabRealtimeAdapter.
 *
 * Shows the currently-active execution mode as a prominent badge so users
 * can see at a glance whether their simulation will run on an ideal
 * simulator, a noisy fake backend, or real IBM Quantum hardware.
 *
 * For real-device mode, wraps the adapter's simulate() with an explicit
 * confirmation dialog to prevent accidental hardware job submissions from
 * a visual UI.
 */

import React, { useEffect, useMemo, useState, useCallback } from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import {
  QamposerProvider,
  QamposerMicro,
  type SimulationAdapter,
  type CircuitRequest,
  type SimulationResult,
  type SimulationCompleteEvent,
} from '@qamposer/react';
import { useColorMode } from '@docusaurus/theme-common';
import { createThebelabAdapter } from './thebelabAdapter';
import { createThebelabRealtimeAdapter } from './thebelabRealtimeAdapter';
import { getExecutionMode, type ExecutionMode } from './executionMode';
import './styles.css';

const INJECTION_EVENT = 'executablecode:injection';

interface BackendBadgeProps {
  mode: ExecutionMode;
}

/** Colored dot + label showing the currently-active execution target. */
function BackendBadge({ mode }: BackendBadgeProps): JSX.Element {
  const variant =
    mode.kind === 'real'
      ? 'danger'
      : mode.kind === 'noisy_fake'
        ? 'warning'
        : 'success';
  const prefix =
    mode.kind === 'real'
      ? 'Real hardware'
      : mode.kind === 'noisy_fake'
        ? 'Noisy simulator'
        : mode.kind === 'ideal'
          ? 'Ideal simulator'
          : 'Ideal (fallback)';
  return (
    <div className={`qamposer-embed__badge qamposer-embed__badge--${variant}`}>
      <span className="qamposer-embed__badge-dot" aria-hidden="true" />
      <strong>{prefix}</strong>
      <span className="qamposer-embed__badge-sep">·</span>
      <span>{mode.label}</span>
    </div>
  );
}

/**
 * Wrap an adapter with a real-device confirmation prompt.
 * When the user is in real-device mode, calling simulate() first pops a
 * native confirm dialog — cancelling throws a user-facing error.
 */
function withRealDeviceGuard(inner: SimulationAdapter): SimulationAdapter {
  return {
    ...inner,
    name: inner.name,
    async simulate(request: CircuitRequest): Promise<SimulationResult> {
      const mode = getExecutionMode();
      if (mode.kind === 'real') {
        const ok = window.confirm(
          'This will submit a job to real IBM Quantum hardware (' +
            mode.label +
            ').\n\n' +
            'Real-device runs may queue for minutes or hours and consume ' +
            'credits or time on your IBM Quantum account.\n\n' +
            'Continue?',
        );
        if (!ok) {
          throw new Error('Simulation cancelled by user');
        }
      }
      return inner.simulate(request);
    },
  };
}

interface QamposerEmbedInnerProps {
  defaultQubits?: number;
  showHeader?: boolean;
}

function QamposerEmbedInner({
  defaultQubits = 3,
  showHeader = true,
}: QamposerEmbedInnerProps): JSX.Element {
  const { colorMode } = useColorMode();
  const [mode, setMode] = useState<ExecutionMode>(() => getExecutionMode());

  // Re-read the mode whenever the kernel broadcasts an injection event,
  // or when the window regains focus (user may have changed Settings in
  // another tab).
  useEffect(() => {
    const refresh = () => setMode(getExecutionMode());
    window.addEventListener(INJECTION_EVENT, refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener(INJECTION_EVENT, refresh);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('storage', refresh);
    };
  }, []);

  const adapter = useMemo(
    () => withRealDeviceGuard(createThebelabAdapter()),
    [],
  );
  const realtimeAdapter = useMemo(() => createThebelabRealtimeAdapter(), []);

  const handleSimulationComplete = useCallback(
    (event: SimulationCompleteEvent) => {
      if (typeof console !== 'undefined') {
        console.info(
          '[Qamposer] Simulation complete:',
          event.result.counts,
          'backend:',
          mode.label,
        );
      }
    },
    [mode.label],
  );

  return (
    <div className="qamposer-embed">
      <BackendBadge mode={mode} />
      {mode.kind === 'real' && (
        <div className="qamposer-embed__warning">
          <strong>⚠ Real hardware mode is active.</strong>{' '}
          Clicking <em>Run Simulation</em> will submit a job to IBM Quantum.
          Live preview on circuit changes is disabled.
        </div>
      )}
      {mode.kind === 'none' && (
        <div className="qamposer-embed__hint">
          No execution mode selected. Simulations will run on a local ideal
          simulator. Configure a simulator or IBM Quantum credentials in{' '}
          <a href="/jupyter-settings">Settings</a> to change this.
        </div>
      )}
      <QamposerProvider
        adapter={adapter}
        realtimeAdapter={realtimeAdapter}
        onSimulationComplete={handleSimulationComplete}
        config={{ maxQubits: 5, maxShots: 10000 }}
        defaultCircuit={{ qubits: defaultQubits, gates: [] }}
      >
        <QamposerMicro
          showHeader={showHeader}
          defaultTheme={colorMode === 'dark' ? 'dark' : 'light'}
        />
      </QamposerProvider>
    </div>
  );
}

export interface QamposerEmbedProps {
  /** Initial qubit count (default: 3) */
  defaultQubits?: number;
  /** Show the QamposerMicro header (default: true) */
  showHeader?: boolean;
}

/**
 * SSR-safe entry point. QAMPoser touches window/document at module load,
 * so it must only render in the browser.
 */
export default function QamposerEmbed(props: QamposerEmbedProps): JSX.Element {
  return (
    <BrowserOnly fallback={<div className="qamposer-embed qamposer-embed--loading">Loading circuit composer…</div>}>
      {() => <QamposerEmbedInner {...props} />}
    </BrowserOnly>
  );
}
