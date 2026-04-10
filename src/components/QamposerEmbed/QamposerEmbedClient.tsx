/**
 * QamposerEmbedClient
 *
 * Client-only inner component holding all @qamposer/react imports. This file
 * must never be imported at module load from server-rendered code — the
 * @qamposer/react package touches `document` at import time, which would
 * crash Docusaurus static site generation. Load it via dynamic `import()`
 * from inside a `<BrowserOnly>` callback (see `./index.tsx`).
 *
 * Renders the full `Qamposer` component from `@qamposer/react/visualization`
 * — the same layout as qamposer.org/demo — with Operations panel, circuit
 * editor, results histogram, Q-sphere viewer, and QASM code editor. This
 * replaces the earlier editor-only `QamposerMicro` preset.
 *
 * `Qamposer` internally wraps its children in its own `QamposerProvider`,
 * so we pass provider props (adapter, realtimeAdapter, config, etc.) DIRECTLY
 * to `<Qamposer>`. Do NOT nest it inside our own `<QamposerProvider>` — that
 * would hide our adapter behind the inner default `noopAdapter` and the
 * Run button would never actually execute anything.
 */

import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  type SimulationAdapter,
  type CircuitRequest,
  type SimulationResult,
  type SimulationCompleteEvent,
} from '@qamposer/react';
import { Qamposer } from '@qamposer/react/visualization';
import { useColorMode } from '@docusaurus/theme-common';
import { createThebelabAdapter } from './thebelabAdapter';
import { createThebelabRealtimeAdapter } from './thebelabRealtimeAdapter';
import { getExecutionMode, type ExecutionMode } from './executionMode';

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

export interface QamposerEmbedClientProps {
  defaultQubits?: number;
  showHeader?: boolean;
}

export default function QamposerEmbedClient({
  defaultQubits = 3,
  showHeader = true,
}: QamposerEmbedClientProps): JSX.Element {
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
      {/*
        Provider props go DIRECTLY on <Qamposer>, not on an outer
        <QamposerProvider>. Qamposer wraps its content in its own provider
        using these spread props; an outer wrapper would be ignored and our
        adapter would silently fall back to noopAdapter.
      */}
      <Qamposer
        showHeader={showHeader}
        defaultTheme={colorMode === 'dark' ? 'dark' : 'light'}
        adapter={adapter}
        realtimeAdapter={realtimeAdapter}
        onSimulationComplete={handleSimulationComplete}
        config={{ maxQubits: 5, maxShots: 10000 }}
        defaultCircuit={{ qubits: defaultQubits, gates: [] }}
      />
    </div>
  );
}
