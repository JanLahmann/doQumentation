/**
 * ExecutableCode Component
 *
 * A code block wrapper that provides two modes of interaction:
 * 1. Read - Static syntax-highlighted code (default)
 * 2. Run - Execute code via thebelab + Jupyter/Binder kernel
 *
 * Uses thebelab 0.4.x which manages its own DOM for the interactive cell.
 * The component keeps read-mode (React-managed) and run-mode (thebelab-managed)
 * in separate containers to avoid conflicts.
 *
 * All cells on a page share a single kernel session so that variables
 * defined in earlier cells are available in later ones. The Run/Stop
 * toolbar appears only on the first cell; Run activates all cells, Back reverts to static view.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import CodeBlock from '@theme-original/CodeBlock';
import {
  detectJupyterConfig,
  getLabUrl,
  getIBMQuantumToken,
  getIBMQuantumCRN,
  getSimulatorMode,
  getSimulatorBackend,
  getFakeDevice,
  getActiveMode,
  setCachedFakeBackends,
  type JupyterConfig,
} from '../../config/jupyter';

// thebelab 0.4.x global — bootstrap() returns a Promise that resolves
// when the kernel is connected (after Binder launch + kernel start).
declare global {
  interface Window {
    thebelab?: {
      bootstrap: (options?: Record<string, unknown>) => Promise<unknown>;
      on: (event: string, callback: (...args: unknown[]) => void) => void;
    };
  }
}

// ── Global (module-level) state shared across all instances ──

let thebelabBootstrapped = false;
let thebelabEventsHooked = false;

// Custom event names used to coordinate all cells on the page
const ACTIVATE_EVENT = 'executablecode:activate';
const STATUS_EVENT = 'executablecode:status';
const RESET_EVENT = 'executablecode:reset';

type ThebeStatus = 'idle' | 'connecting' | 'ready' | 'error';

// ── Cell execution feedback ──
// Tracks which cell is currently executing so we can show "Done" for no-output cells.

let executingCell: Element | null = null;
let lastKernelBusy = false;
let feedbackFallbackTimer: ReturnType<typeof setTimeout> | null = null;

/** Detect execution errors in a cell's output. */
function detectCellError(cell: Element): { type: string; name?: string } | null {
  const output = cell.querySelector('.thebelab-output, .output_area');
  if (!output) return null;
  const text = output.textContent || '';

  const modMatch = text.match(/ModuleNotFoundError: No module named '([^']+)'/);
  if (modMatch) return { type: 'module', name: modMatch[1] };

  const nameMatch = text.match(/NameError: name '([^']+)' is not defined/);
  if (nameMatch) return { type: 'name', name: nameMatch[1] };

  if (output.querySelector('.output_error, .output_stderr') || text.includes('Traceback')) {
    return { type: 'generic' };
  }
  return null;
}

/** Show contextual hint for common errors. */
function showErrorHint(cell: Element, error: { type: string; name?: string }): void {
  cell.querySelector('.thebelab-cell__error-hint')?.remove();

  let hint = '';
  if (error.type === 'module' && error.name) {
    const pkg = error.name.split('.')[0];
    hint = `Package <code>${pkg}</code> is not installed. Run <code>!pip install -q ${pkg}</code> in a cell to install it.`;
  } else if (error.type === 'name' && error.name) {
    hint = `<code>${error.name}</code> is not defined. Run the cells above first &mdash; notebooks must be executed in order.`;
  }

  if (hint) {
    const div = document.createElement('div');
    div.className = 'thebelab-cell__error-hint';
    div.innerHTML = hint;
    cell.appendChild(div);
  }
}

/** Resolve execution feedback for a cell: transition from running → done or error. */
function settleCellFeedback(cell: Element): void {
  cell.querySelector('.exec-feedback')?.remove();
  cell.querySelector('.thebelab-cell__error-hint')?.remove();
  cell.classList.remove('thebelab-cell--running');

  const error = detectCellError(cell);
  if (error) {
    cell.classList.remove('thebelab-cell--done');
    cell.classList.add('thebelab-cell--error');
    showErrorHint(cell, error);
  } else {
    cell.classList.remove('thebelab-cell--error');
    cell.classList.add('thebelab-cell--done');
  }
}

/** Handle kernel busy/idle transitions to detect execution completion. */
function handleKernelStatusForFeedback(status: string): void {
  if (status === 'busy') {
    lastKernelBusy = true;
  }
  if (status === 'idle' && lastKernelBusy && executingCell) {
    lastKernelBusy = false;
    const cell = executingCell;
    executingCell = null;
    if (feedbackFallbackTimer) {
      clearTimeout(feedbackFallbackTimer);
      feedbackFallbackTimer = null;
    }
    setTimeout(() => settleCellFeedback(cell), 300);
  }
}

/** Mark a cell as executing via left border state. */
function markCellExecuting(cell: Element): void {
  cell.querySelector('.exec-feedback')?.remove();
  cell.querySelector('.thebelab-cell__error-hint')?.remove();
  executingCell = cell;
  cell.classList.remove('thebelab-cell--done', 'thebelab-cell--error');
  cell.classList.add('thebelab-cell--running');

  if (feedbackFallbackTimer) clearTimeout(feedbackFallbackTimer);
  feedbackFallbackTimer = setTimeout(() => {
    if (executingCell === cell) {
      executingCell = null;
      settleCellFeedback(cell);
    }
  }, 15000);
}

/** After thebelab cells are rendered, attach listeners for execution feedback. */
function setupCellFeedback(): void {
  setTimeout(() => {
    const cells = document.querySelectorAll('.thebelab-cell');
    console.log(`[ExecutableCode] Setting up feedback for ${cells.length} cell(s)`);

    cells.forEach((cell) => {
      const buttons = cell.querySelectorAll('button');
      const runBtn = Array.from(buttons).find(
        b => b.textContent?.trim().toLowerCase() === 'run'
      );
      if (runBtn) {
        runBtn.addEventListener('click', () => markCellExecuting(cell));
      }
      // Also handle Shift+Enter (thebelab's CodeMirror keybinding)
      const cm = cell.querySelector('.CodeMirror');
      if (cm) {
        cm.addEventListener('keydown', (e: Event) => {
          const ke = e as KeyboardEvent;
          if (ke.shiftKey && ke.key === 'Enter') {
            markCellExecuting(cell);
          }
        });
      }
    });
  }, 1000);
}

// ── Kernel injection for IBM credentials / simulator mode ──

const CONFLICT_EVENT = 'executablecode:conflict';

/* eslint-disable @typescript-eslint/no-explicit-any */
async function executeOnKernel(kernelObj: unknown, code: string): Promise<boolean> {
  const k = kernelObj as Record<string, any>;
  const kernel = k?.requestExecute ? k : k?.kernel;
  if (!kernel?.requestExecute) {
    console.warn('[ExecutableCode] kernel.requestExecute not available');
    return false;
  }
  try {
    const future = kernel.requestExecute({ code, silent: true, store_history: false });
    if (future?.done) await future.done;
    return true;
  } catch (err) {
    console.error('[ExecutableCode] kernel exec error:', err);
    return false;
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function getSaveAccountCode(token: string, crn: string): string {
  const t = token.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const c = crn.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  return `import warnings; warnings.filterwarnings('ignore')
from qiskit_ibm_runtime import QiskitRuntimeService
try:
    QiskitRuntimeService.save_account(
        token="${t}",
        instance="${c}",
        overwrite=True, set_as_default=True
    )
except Exception as e:
    print(f"[doQumentation] Credential setup: {e}")`;
}

function getSimulatorPatchCode(): string {
  const backend = getSimulatorBackend();
  let backendSetup: string;

  if (backend === 'fake') {
    const device = getFakeDevice();
    const safeName = device.replace(/[^a-zA-Z0-9_]/g, '');
    backendSetup = `from qiskit_ibm_runtime.fake_provider import ${safeName} as _DQ_Cls
_dq_backend = _DQ_Cls()`;
  } else {
    backendSetup = `try:
    from qiskit_aer import AerSimulator as _DQ_Sim
except ImportError:
    from qiskit.providers.basic_provider import BasicSimulator as _DQ_Sim
_dq_backend = _DQ_Sim()`;
  }

  return `${backendSetup}

class _DQ_MockService:
    def __init__(self, *a, **kw): pass
    @staticmethod
    def save_account(*a, **kw): pass
    def least_busy(self, *a, **kw): return _dq_backend
    def backend(self, *a, **kw): return _dq_backend
    def backends(self, *a, **kw): return [_dq_backend]

import qiskit_ibm_runtime as _qir
_qir.QiskitRuntimeService = _DQ_MockService
import sys
_m = sys.modules.get('qiskit_ibm_runtime')
if _m: _m.QiskitRuntimeService = _DQ_MockService
print(f"[doQumentation] Simulator mode — using {type(_dq_backend).__name__}")`;
}

function broadcastConflictBanner(usingMode: string): void {
  window.dispatchEvent(new CustomEvent(CONFLICT_EVENT, { detail: usingMode }));
}

async function injectKernelSetup(kernelObj: unknown): Promise<void> {
  const simMode = getSimulatorMode();
  const token = getIBMQuantumToken();
  const activeMode = getActiveMode();

  const hasBoth = simMode && !!token;
  const useSimulator = simMode && (!hasBoth || activeMode === 'simulator');
  const useCredentials = !!token && (!simMode || activeMode === 'credentials');

  if (hasBoth && !activeMode) {
    broadcastConflictBanner('simulator');
  }

  if (useSimulator || (hasBoth && !activeMode)) {
    const ok = await executeOnKernel(kernelObj, getSimulatorPatchCode());
    if (ok) console.log('[ExecutableCode] Simulator mode injected');
  } else if (useCredentials) {
    const crn = getIBMQuantumCRN();
    const ok = await executeOnKernel(kernelObj, getSaveAccountCode(token, crn));
    if (ok) console.log('[ExecutableCode] IBM Quantum credentials injected');
  }

  discoverFakeBackends(kernelObj);
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function discoverFakeBackends(kernelObj: unknown): void {
  const k = kernelObj as Record<string, any>;
  const kernel = k?.requestExecute ? k : k?.kernel;
  if (!kernel?.requestExecute) return;

  const code = `import json as _j
from qiskit_ibm_runtime import fake_provider as _fp
_bs = []
for _n in sorted(dir(_fp)):
    _c = getattr(_fp, _n)
    if isinstance(_c, type) and hasattr(_c, 'num_qubits'):
        try: _bs.append({"name": _n, "qubits": _c().num_qubits})
        except: pass
print("__DQ_BACKENDS__" + _j.dumps(_bs))`;

  try {
    const future = kernel.requestExecute({ code, silent: false, store_history: false });
    if (future?.onIOPub) {
      future.onIOPub = (msg: any) => {
        const text = msg?.content?.text;
        if (typeof text === 'string' && text.includes('__DQ_BACKENDS__')) {
          try {
            const json = text.substring(text.indexOf('__DQ_BACKENDS__') + 15);
            const backends = JSON.parse(json);
            setCachedFakeBackends(backends);
            console.log(`[ExecutableCode] Discovered ${backends.length} fake backends`);
          } catch { /* ignore parse errors */ }
        }
      };
    }
  } catch { /* ignore discovery errors */ }
}
/* eslint-enable @typescript-eslint/no-explicit-any */

interface ExecutableCodeProps {
  children: string;
  language?: string;
  notebookPath?: string;
  title?: string;
  showLineNumbers?: boolean;
}

/** Build thebelab bootstrap options for the current environment. */
function getThebelabOptions(config: JupyterConfig): Record<string, unknown> {
  if (config.environment === 'github-pages') {
    return {
      requestKernel: true,
      binderOptions: {
        repo: 'JanLahmann/Qiskit-documentation',
        ref: 'main',
        binderUrl: 'https://2i2c.mybinder.org',
      },
      kernelOptions: {
        name: 'python3',
      },
    };
  }
  // Local / Docker / custom — direct Jupyter connection
  return {
    requestKernel: true,
    kernelOptions: {
      name: 'python3',
      serverSettings: {
        baseUrl: config.baseUrl,
        wsUrl: config.wsUrl,
        token: config.token,
      },
    },
  };
}

/** Broadcast a status change to all cells on the page. */
function broadcastStatus(status: ThebeStatus): void {
  window.dispatchEvent(new CustomEvent(STATUS_EVENT, { detail: status }));
}

/**
 * Wait for thebelab to load, then bootstrap all [data-executable] cells.
 * Called once — subsequent activations are no-ops.
 * The kernel Promise from bootstrap() drives the status updates:
 *   connecting → (Binder launches, kernel starts) → ready | error
 */
function bootstrapOnce(config: JupyterConfig): void {
  if (thebelabBootstrapped) {
    broadcastStatus('ready');
    return;
  }

  const thebelabOptions = getThebelabOptions(config);

  const tryBootstrap = () => {
    if (!window.thebelab) {
      console.log('[ExecutableCode] waiting for thebelab CDN...');
      setTimeout(tryBootstrap, 500);
      return;
    }

    // Hook into thebelab's internal jQuery events (once)
    if (!thebelabEventsHooked && window.thebelab.on) {
      thebelabEventsHooked = true;
      window.thebelab.on('status', function (...args: unknown[]) {
        const data = args[1] as { status: string; message: string };
        if (data) {
          console.log(`[thebelab] status: ${data.status} — ${data.message}`);
          handleKernelStatusForFeedback(data.status);
        }
      });
    }

    const cells = document.querySelectorAll('[data-executable]');
    console.log(`[ExecutableCode] bootstrap: ${cells.length} cell(s), options:`, thebelabOptions);

    try {
      // Pass options directly to bootstrap() — bypasses the config script
      // cache which can be empty if getPageConfig() ran before injection.
      const kernelPromise = window.thebelab.bootstrap(thebelabOptions);
      thebelabBootstrapped = true;
      console.log('[ExecutableCode] bootstrap() called, waiting for kernel promise...');

      // Stay in 'connecting' state until the kernel is ready
      if (kernelPromise && typeof kernelPromise.then === 'function') {
        kernelPromise.then(
          (kernel) => {
            console.log('[ExecutableCode] kernel ready:', kernel);
            injectKernelSetup(kernel).then(() => {
              broadcastStatus('ready');
              setupCellFeedback();
            });
          },
          (err) => {
            console.error('[ExecutableCode] kernel error:', err);
            broadcastStatus('error');
          }
        );
      } else {
        console.log('[ExecutableCode] bootstrap returned non-promise, assuming ready');
        broadcastStatus('ready');
      }
    } catch (err) {
      console.error('[ExecutableCode] bootstrap error:', err);
      broadcastStatus('error');
    }
  };

  // Give React a tick to render all the <pre data-executable> elements
  setTimeout(tryBootstrap, 100);
}

export default function ExecutableCode({
  children,
  language = 'python',
  notebookPath,
  title,
  showLineNumbers = true,
}: ExecutableCodeProps): JSX.Element {
  const [mode, setMode] = useState<'read' | 'run'>('read');
  const [thebeStatus, setThebeStatus] = useState<ThebeStatus>('idle');
  const [jupyterConfig, setJupyterConfig] = useState<JupyterConfig | null>(null);
  const [isFirstCell, setIsFirstCell] = useState(false);
  const [conflictBanner, setConflictBanner] = useState<string | null>(null);
  const [binderHintDismissed, setBinderHintDismissed] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const thebeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setJupyterConfig(detectJupyterConfig());
    setBinderHintDismissed(!!localStorage.getItem('dq-binder-hint-dismissed'));
  }, []);

  // Determine if this is the first executable cell on the page (toolbar owner)
  useEffect(() => {
    if (!containerRef.current) return;
    const allCells = document.querySelectorAll('.executable-code');
    setIsFirstCell(allCells[0] === containerRef.current);
  }, []);

  // Listen for the global activate event (fired when ANY cell's Run is clicked)
  useEffect(() => {
    const onActivate = () => {
      setMode('run');
      setThebeStatus('connecting');
    };
    window.addEventListener(ACTIVATE_EVENT, onActivate);
    return () => window.removeEventListener(ACTIVATE_EVENT, onActivate);
  }, []);

  // Listen for global reset event (Stop clicked on toolbar)
  useEffect(() => {
    const onReset = () => {
      setMode('read');
      setThebeStatus('idle');
    };
    window.addEventListener(RESET_EVENT, onReset);
    return () => window.removeEventListener(RESET_EVENT, onReset);
  }, []);

  // Listen for global status updates from the bootstrap process
  useEffect(() => {
    const onStatus = (e: Event) => {
      const status = (e as CustomEvent<ThebeStatus>).detail;
      setThebeStatus(status);
    };
    window.addEventListener(STATUS_EVENT, onStatus);
    return () => window.removeEventListener(STATUS_EVENT, onStatus);
  }, []);

  // Listen for conflict banner (both credentials + simulator configured, no explicit choice)
  useEffect(() => {
    const onConflict = (e: Event) => {
      const usingMode = (e as CustomEvent<string>).detail;
      setConflictBanner(usingMode);
      setTimeout(() => setConflictBanner(null), 5000);
    };
    window.addEventListener(CONFLICT_EVENT, onConflict);
    return () => window.removeEventListener(CONFLICT_EVENT, onConflict);
  }, []);

  const isExecutable = language === 'python' && jupyterConfig?.thebeEnabled;
  const canOpenLab = jupyterConfig?.labEnabled && notebookPath;
  const simActive = typeof window !== 'undefined' && getSimulatorMode();

  const handleRun = useCallback(() => {
    if (!jupyterConfig) return;

    // Tell ALL cells on the page to switch to run mode
    window.dispatchEvent(new CustomEvent(ACTIVATE_EVENT));

    // After all cells have rendered their <pre data-executable>, bootstrap once
    bootstrapOnce(jupyterConfig);
  }, [jupyterConfig]);

  const handleReset = () => {
    // Check if any cells have been executed (have done/error state)
    const executedCells = document.querySelectorAll('.thebelab-cell--done, .thebelab-cell--error');
    if (executedCells.length > 0) {
      if (!window.confirm('This will clear all execution results and return to static view. Continue?')) {
        return;
      }
    }
    // Tell ALL cells on the page to switch back to read mode
    window.dispatchEvent(new CustomEvent(RESET_EVENT));
  };

  const handleOpenLab = () => {
    if (!jupyterConfig || !notebookPath) return;
    const labUrl = getLabUrl(jupyterConfig, notebookPath);
    if (labUrl) {
      window.open(labUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const statusText: Record<ThebeStatus, string> = {
    idle: '',
    connecting: jupyterConfig?.environment === 'github-pages'
      ? 'Starting Binder (this may take 1\u20132 minutes on first run)...'
      : 'Connecting...',
    ready: 'Ready',
    error: 'Connection error',
  };

  const code = children.replace(/\n$/, '');

  return (
    <div className="executable-code" ref={containerRef}>
      {/* Toolbar — only rendered on the first executable cell */}
      {isFirstCell && (isExecutable || canOpenLab) && (
        <div className="executable-code__toolbar">
          {isExecutable && (
            <button
              className={`executable-code__button ${mode === 'run' ? 'executable-code__button--active' : ''}`}
              onClick={mode === 'run' ? handleReset : handleRun}
              disabled={thebeStatus === 'connecting'}
              title={
                mode === 'run'
                  ? 'Back to static view'
                  : jupyterConfig?.environment === 'github-pages'
                    ? 'Execute via Binder (may take a moment to start)'
                    : 'Execute on local Jupyter server'
              }
            >
              {thebeStatus === 'connecting' ? 'Connecting...' : mode === 'run' ? 'Back' : 'Run'}
            </button>
          )}

          {canOpenLab && (
            <button
              className="executable-code__button"
              onClick={handleOpenLab}
              title="Open full notebook in JupyterLab"
            >
              Open in Lab
            </button>
          )}

          {thebeStatus !== 'idle' && (
            <span className={`thebe-status thebe-status--${thebeStatus}`}>
              {statusText[thebeStatus]}
            </span>
          )}

          {thebeStatus === 'ready' && (
            <span className="executable-code__legend">
              <span className="executable-code__legend-item executable-code__legend-item--running">running</span>
              <span className="executable-code__legend-item executable-code__legend-item--done">done</span>
              <span className="executable-code__legend-item executable-code__legend-item--error">error</span>
            </span>
          )}

          {simActive && (
            <span className="executable-code__sim-badge">Simulator</span>
          )}

          <a
            className="executable-code__settings-link"
            href="/jupyter-settings#ibm-quantum"
            title="Jupyter & IBM Quantum settings"
          >
            Settings
          </a>
        </div>
      )}

      {isFirstCell && conflictBanner && (
        <div className="executable-code__conflict-banner">
          Both IBM credentials and simulator mode are configured.
          Using <strong>{conflictBanner}</strong>.{' '}
          <a href="/jupyter-settings#ibm-quantum">Change in Settings</a>.
        </div>
      )}

      {isFirstCell && thebeStatus === 'ready' && jupyterConfig?.environment === 'github-pages' &&
        !binderHintDismissed && (
        <div className="executable-code__binder-hint">
          Need extra packages? Run{' '}
          <code>!pip install -q &lt;package&gt;</code>{' '}
          in a cell, or see{' '}
          <a href="/jupyter-settings#binder-packages">available packages</a>.
          <button
            className="executable-code__binder-hint-dismiss"
            onClick={() => {
              localStorage.setItem('dq-binder-hint-dismissed', 'true');
              setBinderHintDismissed(true);
            }}
            title="Dismiss"
            aria-label="Dismiss hint"
          >
            &times;
          </button>
        </div>
      )}

      {title && <div className="executable-code__title">{title}</div>}

      {/* Read mode: React-managed syntax-highlighted code */}
      <div
        className="executable-code__code"
        style={{ display: mode === 'read' ? 'block' : 'none' }}
      >
        <CodeBlock language={language} showLineNumbers={showLineNumbers}>
          {children}
        </CodeBlock>
      </div>

      {/* Run mode: thebelab-managed interactive cell */}
      {mode === 'run' && (
        <div ref={thebeContainerRef} className="executable-code__thebe">
          <pre data-executable="true" data-language="python">
            {code}
          </pre>
        </div>
      )}
    </div>
  );
}
