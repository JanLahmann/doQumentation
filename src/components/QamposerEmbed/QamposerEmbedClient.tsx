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
import { ensureKernel, getActiveKernel } from '../ExecutableCode';

// Global event names emitted by ExecutableCode's bootstrap / kernel machinery.
// Kept as string literals because ExecutableCode does not export them; see
// src/components/ExecutableCode/index.tsx for the source of truth.
const INJECTION_EVENT = 'executablecode:injection';
const STATUS_EVENT = 'executablecode:status';
const BINDER_PHASE_EVENT = 'executablecode:binderphase';

type KernelStatus = 'idle' | 'connecting' | 'ready' | 'error';

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

/**
 * Small status pill above the composer that reflects the kernel's
 * bootstrap/connected/error lifecycle. Helps users understand why
 * the composer may not respond immediately when they first load the
 * page — bootstrap is proactive (see prewarm effect below) but can
 * take 30s–2min on a Binder cold start.
 */
interface KernelStatusStripProps {
  status: KernelStatus;
  phase: string | null;
  modeKind: ExecutionMode['kind'];
}

function KernelStatusStrip({ status, phase, modeKind }: KernelStatusStripProps): JSX.Element | null {
  // In real-hardware mode we don't prewarm a local kernel — the dialog's
  // Run button goes straight to qiskit_ibm_runtime — so no status strip.
  if (modeKind === 'real') return null;

  // Human-readable labels for the Binder bootstrap phases
  const phaseLabels: Record<string, string> = {
    connecting: 'Connecting to Binder…',
    waiting: 'Waiting for a free server…',
    fetching: 'Fetching repository (2–5 min)…',
    building: 'Building container image (5–10 min)…',
    pushing: 'Pushing image…',
    launching: 'Launching kernel…',
    built: 'Finalizing…',
    ready: 'Kernel ready',
  };

  let variant: 'info' | 'success' | 'danger' = 'info';
  let label: string;
  let detail: string | null = null;

  if (status === 'ready') {
    variant = 'success';
    label = 'Simulator ready';
    detail = 'Live preview is enabled — circuit edits will re-simulate automatically.';
  } else if (status === 'error') {
    variant = 'danger';
    label = 'Simulator unavailable';
    detail = 'The Jupyter kernel could not be reached. Check your connection or try again.';
  } else if (status === 'connecting' || phase) {
    variant = 'info';
    label = (phase && phaseLabels[phase]) || 'Preparing simulator…';
    detail = 'First visit can take 1–2 minutes on a cold Binder build.';
  } else {
    // status === 'idle' — we will trigger bootstrap momentarily
    variant = 'info';
    label = 'Preparing simulator…';
  }

  return (
    <div
      className={`qamposer-embed__kernel-strip qamposer-embed__kernel-strip--${variant}`}
      role="status"
      aria-live="polite"
    >
      <span className="qamposer-embed__kernel-strip-dot" aria-hidden="true" />
      <strong>{label}</strong>
      {detail && <span className="qamposer-embed__kernel-strip-sep">·</span>}
      {detail && <span>{detail}</span>}
    </div>
  );
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
  const [kernelStatus, setKernelStatus] = useState<KernelStatus>(() =>
    getActiveKernel() ? 'ready' : 'idle',
  );
  const [binderPhase, setBinderPhase] = useState<string | null>(null);

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

  // Track the kernel's bootstrap/idle/ready lifecycle so we can show a small
  // status strip above the composer. Source of truth is ExecutableCode, which
  // broadcasts these global events whenever bootstrap progresses.
  useEffect(() => {
    const onStatus = (e: Event) => {
      const s = (e as CustomEvent<KernelStatus>).detail;
      setKernelStatus(s);
      if (s === 'ready' || s === 'error') setBinderPhase(null);
    };
    const onPhase = (e: Event) => {
      const phase = (e as CustomEvent<string>).detail;
      if (phase === 'ready' || phase === 'failed') {
        setBinderPhase(null);
      } else {
        setBinderPhase(phase);
      }
    };
    window.addEventListener(STATUS_EVENT, onStatus);
    window.addEventListener(BINDER_PHASE_EVENT, onPhase);
    return () => {
      window.removeEventListener(STATUS_EVENT, onStatus);
      window.removeEventListener(BINDER_PHASE_EVENT, onPhase);
    };
  }, []);

  // Pre-warm the kernel on mount so by the time the user has dragged their
  // first gate, simulation and the QAMPoser live-preview adapter are ready.
  // Without this, the first click on "Run circuit" triggers a ~30s Binder
  // cold start — and the real-time auto-simulation on circuit changes never
  // fires at all, because thebelabRealtimeAdapter intentionally does not
  // bootstrap. ensureKernel() is idempotent (bootstrapOnce() guards against
  // repeat bootstraps) and safe to call unconditionally.
  //
  // We skip prewarm in real-hardware mode: there is no local kernel to warm
  // up in that path — execution goes straight to qiskit_ibm_runtime, and
  // burning a Binder slot would be wasteful.
  useEffect(() => {
    if (mode.kind === 'real') return;
    // Defer one tick so the BrowserOnly loading fallback has painted first
    // and the page feels responsive even if bootstrap is slow.
    const id = window.setTimeout(() => {
      try {
        setKernelStatus((prev) => (prev === 'ready' ? prev : 'connecting'));
        ensureKernel();
      } catch (err) {
        console.warn('[Qamposer] Kernel pre-warm failed:', err);
        setKernelStatus('error');
      }
    }, 0);
    return () => window.clearTimeout(id);
  }, [mode.kind]);

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
      <KernelStatusStrip
        status={kernelStatus}
        phase={binderPhase}
        modeKind={mode.kind}
      />
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
