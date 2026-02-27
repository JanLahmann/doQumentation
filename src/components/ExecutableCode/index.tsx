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
  getColabUrl,
  getIBMQuantumToken,
  getIBMQuantumCRN,
  getSimulatorMode,
  getSimulatorBackend,
  getFakeDevice,
  getActiveMode,
  setCachedFakeBackends,
  getSuppressWarnings,
  type JupyterConfig,
} from '../../config/jupyter';
import { markPageExecuted, isBinderHintDismissed, dismissBinderHint, getHideStaticOutputs } from '../../config/preferences';

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
const INJECTION_EVENT = 'executablecode:injection';

type ThebeStatus = 'idle' | 'connecting' | 'ready' | 'error';

type InjectionInfo = {
  mode: 'simulator' | 'credentials' | 'none';
  label: string;    // Badge text: "AerSimulator", "FakeSherbrooke", "IBM Quantum"
  message: string;  // Toast text for brief feedback
};

// Gate debug logging — only in development builds
const DEBUG = typeof process !== 'undefined' && process.env.NODE_ENV === 'development';

// ── Cell execution feedback ──
// Tracks which cell is currently executing so we can show "Done" for no-output cells.

let executingCell: Element | null = null;
let lastKernelBusy = false;
let feedbackFallbackTimer: ReturnType<typeof setTimeout> | null = null;
let feedbackIdleDebounceTimer: ReturnType<typeof setTimeout> | null = null;
let kernelDead = false;
let feedbackCleanupFns: (() => void)[] = [];
let activeKernel: unknown = null;

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

  // Module errors get a clickable Install button when kernel is available
  if (error.type === 'module' && error.name) {
    const pkg = error.name.split('.')[0];
    if (!/^[a-zA-Z0-9._-]+$/.test(pkg)) return; // validate package name
    const div = document.createElement('div');
    div.className = 'thebelab-cell__error-hint';

    const text = document.createElement('span');
    text.append('Package ');
    const pkgCode = document.createElement('code');
    pkgCode.textContent = pkg;
    text.appendChild(pkgCode);
    text.append(' is not installed.');
    div.appendChild(text);

    if (activeKernel && !kernelDead) {
      const btn = document.createElement('button');
      btn.className = 'thebelab-cell__install-btn';
      btn.textContent = `Install ${pkg}`;
      btn.title = `Run !pip install -q ${pkg}`;
      btn.addEventListener('click', () => handlePipInstall(cell, pkg, btn));
      div.appendChild(btn);
    } else {
      const fallback = document.createElement('span');
      fallback.append(' Run ');
      const fallbackCode = document.createElement('code');
      fallbackCode.textContent = `!pip install -q ${pkg}`;
      fallback.appendChild(fallbackCode);
      fallback.append(' in a cell.');
      div.appendChild(fallback);
    }

    cell.appendChild(div);
    return;
  }

  const div = document.createElement('div');
  div.className = 'thebelab-cell__error-hint';

  if (error.type === 'kernel') {
    div.append('Kernel disconnected. Click ');
    const back = document.createElement('strong');
    back.textContent = 'Back';
    div.appendChild(back);
    div.append(' then ');
    const run = document.createElement('strong');
    run.textContent = 'Run';
    div.appendChild(run);
    div.append(' to reconnect.');
    cell.appendChild(div);
  } else if (error.type === 'name' && error.name) {
    const nameCode = document.createElement('code');
    nameCode.textContent = error.name;
    div.appendChild(nameCode);
    div.append(' is not defined. Run the cells above first \u2014 notebooks must be executed in order.');
    cell.appendChild(div);
  }
}

/** Run !pip install on the kernel, update button state, and re-run the failed cell. */
async function handlePipInstall(
  cell: Element,
  pkg: string,
  btn: HTMLButtonElement
): Promise<void> {
  if (!/^[a-zA-Z0-9._-]+$/.test(pkg)) return;
  btn.disabled = true;
  btn.textContent = `Installing ${pkg}...`;
  btn.classList.add('thebelab-cell__install-btn--installing');
  cell.classList.remove('thebelab-cell--error');
  cell.classList.add('thebelab-cell--running');

  const ok = await executeOnKernel(activeKernel, `!pip install -q ${pkg}`);

  if (ok) {
    btn.textContent = 'Installed \u2713';
    btn.classList.remove('thebelab-cell__install-btn--installing');
    btn.classList.add('thebelab-cell__install-btn--done');

    // Re-run the failed cell by clicking its thebelab run button
    setTimeout(() => {
      const runBtn = Array.from(cell.querySelectorAll('button')).find(
        b => b.textContent?.trim().toLowerCase() === 'run'
      );
      if (runBtn) {
        runBtn.click();
      } else {
        cell.classList.remove('thebelab-cell--running');
        cell.classList.add('thebelab-cell--done');
        cell.querySelector('.thebelab-cell__error-hint')?.remove();
      }
    }, 500);
  } else {
    btn.textContent = 'Install failed';
    btn.classList.remove('thebelab-cell__install-btn--installing');
    btn.classList.add('thebelab-cell__install-btn--failed');
    cell.classList.remove('thebelab-cell--running');
    cell.classList.add('thebelab-cell--error');
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

  // #28: Fix generic/missing alt text on live-rendered output images
  cell.querySelectorAll('.thebelab-output img, .output_area img').forEach((img) => {
    const htmlImg = img as HTMLImageElement;
    if (!htmlImg.alt || htmlImg.alt === 'output') {
      htmlImg.alt = 'Code execution output';
    }
  });
}

/** Debounce window for idle detection (ms).
 *  Must survive brief idle blips between execute_input → execute_result → idle
 *  transitions during multi-phase executions (e.g., matplotlib, SamplerV2.run).
 *  1500ms bridges gaps from overlapping thebelab/kernel status signals. */
const IDLE_DEBOUNCE_MS = 1500;

/** Handle kernel busy/idle transitions to detect execution completion.
 *  Called from BOTH:
 *  - thebelab's on('status') for lifecycle events (dead/failed/ready)
 *  - kernel.statusChanged signal for actual busy/idle protocol events */
function handleKernelStatusForFeedback(status: string): void {
  // Detect kernel death — mark current cell as error and flag for future checks
  if (status === 'dead' || status === 'failed') {
    kernelDead = true;
    thebelabBootstrapped = false; // Allow re-bootstrap on next Run
    if (feedbackIdleDebounceTimer) {
      clearTimeout(feedbackIdleDebounceTimer);
      feedbackIdleDebounceTimer = null;
    }
    if (executingCell) {
      const cell = executingCell;
      executingCell = null;
      if (feedbackFallbackTimer) {
        clearTimeout(feedbackFallbackTimer);
        feedbackFallbackTimer = null;
      }
      cell.classList.remove('thebelab-cell--running');
      cell.classList.add('thebelab-cell--error');
      showErrorHint(cell, { type: 'kernel' });
    }
    broadcastStatus('error');
    return;
  }

  // busy: cancel any pending idle debounce — the kernel is still working
  if (status === 'busy') {
    lastKernelBusy = true;
    if (feedbackIdleDebounceTimer) {
      clearTimeout(feedbackIdleDebounceTimer);
      feedbackIdleDebounceTimer = null;
    }
    return;
  }

  // idle: start debounce timer — only settle if we stay idle for IDLE_DEBOUNCE_MS
  if (status === 'idle' && lastKernelBusy && executingCell) {
    if (feedbackIdleDebounceTimer) {
      clearTimeout(feedbackIdleDebounceTimer);
    }
    feedbackIdleDebounceTimer = setTimeout(() => {
      feedbackIdleDebounceTimer = null;
      if (executingCell) {
        lastKernelBusy = false;
        const cell = executingCell;
        executingCell = null;
        if (feedbackFallbackTimer) {
          clearTimeout(feedbackFallbackTimer);
          feedbackFallbackTimer = null;
        }
        settleCellFeedback(cell);
      }
    }, IDLE_DEBOUNCE_MS);
  }
}

/** Mark a cell as executing via left border state. */
function markCellExecuting(cell: Element): void {
  cell.querySelector('.exec-feedback')?.remove();
  cell.querySelector('.thebelab-cell__error-hint')?.remove();

  // If kernel is dead, show error immediately instead of misleading "running" state
  if (kernelDead) {
    cell.classList.remove('thebelab-cell--done', 'thebelab-cell--running');
    cell.classList.add('thebelab-cell--error');
    showErrorHint(cell, { type: 'kernel' });
    return;
  }

  executingCell = cell;
  cell.classList.remove('thebelab-cell--done', 'thebelab-cell--error');
  cell.classList.add('thebelab-cell--running');

  if (feedbackFallbackTimer) clearTimeout(feedbackFallbackTimer);
  feedbackFallbackTimer = setTimeout(() => {
    if (executingCell === cell) {
      executingCell = null;
      console.warn('[ExecutableCode] Safety-net timer fired — kernel.statusChanged may not be working');
      settleCellFeedback(cell);
    }
  }, 60000);
}

/** After thebelab cells are rendered, attach listeners for execution feedback. */
function setupCellFeedback(): void {
  // Clean up listeners from any previous bootstrap
  feedbackCleanupFns.forEach(fn => fn());
  feedbackCleanupFns = [];

  setTimeout(() => {
    const cells = document.querySelectorAll('.thebelab-cell');
    if (DEBUG) console.log(`[ExecutableCode] Setting up feedback for ${cells.length} cell(s)`);

    cells.forEach((cell) => {
      const buttons = cell.querySelectorAll('button');

      // Hide thebelab's restart buttons — they don't integrate with our feedback system
      Array.from(buttons).forEach(b => {
        const text = b.textContent?.trim().toLowerCase() || '';
        if (text.includes('restart')) {
          (b as HTMLElement).style.display = 'none';
        }
      });

      const runBtn = Array.from(buttons).find(
        b => b.textContent?.trim().toLowerCase() === 'run'
      );
      if (runBtn) {
        const handler = () => markCellExecuting(cell);
        runBtn.addEventListener('click', handler);
        feedbackCleanupFns.push(() => runBtn.removeEventListener('click', handler));
      }
      // Also handle Shift+Enter (thebelab's CodeMirror keybinding)
      const cm = cell.querySelector('.CodeMirror');
      if (cm) {
        const handler = (e: Event) => {
          const ke = e as KeyboardEvent;
          if (ke.shiftKey && ke.key === 'Enter') {
            markCellExecuting(cell);
          }
        };
        cm.addEventListener('keydown', handler);
        feedbackCleanupFns.push(() => cm.removeEventListener('keydown', handler));
      }
    });
  }, 1000);
}

/** After injection, show a skip-hint on cells that contain save_account().
 *  Prevents users from overwriting injected credentials with placeholder values. */
function annotateSaveAccountCells(): void {
  const simMode = getSimulatorMode();
  const hasCredentials = !!getIBMQuantumToken();
  if (!simMode && !hasCredentials) return;

  // Wait for thebelab to render cells (same delay as setupCellFeedback)
  setTimeout(() => {
    const cells = document.querySelectorAll('.thebelab-cell');
    cells.forEach((cell) => {
      const code = cell.querySelector('.CodeMirror')?.textContent ||
                   cell.querySelector('pre')?.textContent || '';
      if (!code.includes('save_account(')) return;
      if (cell.querySelector('.thebelab-cell__skip-hint')) return;

      const div = document.createElement('div');
      div.className = 'thebelab-cell__skip-hint';
      if (simMode) {
        div.innerHTML =
          '<strong>Skip this cell</strong> \u2014 Simulator Mode is active. Running it has no effect.';
      } else {
        div.innerHTML =
          '<strong>Skip this cell</strong> \u2014 your credentials are already configured via ' +
          '<a href="/jupyter-settings#ibm-quantum">Settings</a>. ' +
          'Running it with placeholder values will overwrite them.';
      }
      cell.insertBefore(div, cell.firstChild);
    });
  }, 1200);
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
  const t = token.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
  const c = crn.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
  const suppressWarnings = getSuppressWarnings();
  const warningLine = suppressWarnings
    ? `import warnings; warnings.filterwarnings('ignore')
print("[doQumentation] Python warnings suppressed (can be changed in Settings)")`
    : '';
  return `${warningLine}
from qiskit_ibm_runtime import QiskitRuntimeService
try:
    QiskitRuntimeService.save_account(
        token="${t}",
        instance="${c}",
        overwrite=True, set_as_default=True
    )
    print("[doQumentation] IBM Quantum credentials injected from Settings")
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

  const suppressWarnings = getSuppressWarnings();
  const warningLine = suppressWarnings
    ? `import warnings; warnings.filterwarnings('ignore')
print("[doQumentation] Python warnings suppressed (can be changed in Settings)")
`
    : '';

  return `${warningLine}${backendSetup}

class _DQ_MockService:
    def __init__(self, *a, **kw):
        print("[doQumentation] QiskitRuntimeService() intercepted by Simulator Mode")
    @staticmethod
    def save_account(*a, **kw):
        print("[doQumentation] Simulator mode active \\u2014 save_account() skipped (no credentials needed)")
    def least_busy(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode \\u2014 returning {_dq_backend}")
        return _dq_backend
    def backend(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode \\u2014 returning {_dq_backend}")
        return _dq_backend
    def backends(self, *a, **kw):
        print(f"[doQumentation] Intercepted by Simulator Mode \\u2014 returning [{_dq_backend}]")
        return [_dq_backend]

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

function broadcastInjection(info: InjectionInfo): void {
  window.dispatchEvent(new CustomEvent(INJECTION_EVENT, { detail: info }));
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
    if (ok) {
      const backend = getSimulatorBackend();
      const device = backend === 'fake' ? getFakeDevice() : 'AerSimulator';
      broadcastInjection({
        mode: 'simulator',
        label: device,
        message: `Simulator active \u2014 using ${device}`,
      });
    }
  } else if (useCredentials) {
    const crn = getIBMQuantumCRN();
    const ok = await executeOnKernel(kernelObj, getSaveAccountCode(token, crn));
    if (ok) {
      broadcastInjection({
        mode: 'credentials',
        label: 'IBM Quantum',
        message: 'IBM Quantum credentials applied',
      });
    }
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
            if (DEBUG) console.log(`[ExecutableCode] Discovered ${backends.length} fake backends`);
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
      if (DEBUG) console.log('[ExecutableCode] waiting for thebelab CDN...');
      setTimeout(tryBootstrap, 500);
      return;
    }

    // Hook into thebelab's internal jQuery events (once)
    if (!thebelabEventsHooked && window.thebelab.on) {
      thebelabEventsHooked = true;
      window.thebelab.on('status', function (...args: unknown[]) {
        const data = args[1] as { status: string; message: string };
        if (data) {
          if (DEBUG) console.log(`[thebelab] status: ${data.status} — ${data.message}`);
          // Skip busy/idle — these are handled reliably via kernel.statusChanged.
          // thebelab lifecycle events (e.g. "ready") can overlap with cell execution
          // and cause premature green borders if routed through the debounce logic.
          if (data.status === 'busy' || data.status === 'idle') return;
          handleKernelStatusForFeedback(data.status);
        }
      });
    }

    const cells = document.querySelectorAll('[data-executable]');
    if (DEBUG) console.log(`[ExecutableCode] bootstrap: ${cells.length} cell(s), options:`, thebelabOptions);

    try {
      // Pass options directly to bootstrap() — bypasses the config script
      // cache which can be empty if getPageConfig() ran before injection.
      const kernelPromise = window.thebelab.bootstrap(thebelabOptions);
      thebelabBootstrapped = true;
      if (DEBUG) console.log('[ExecutableCode] bootstrap() called, waiting for kernel promise...');

      // Stay in 'connecting' state until the kernel is ready
      if (kernelPromise && typeof kernelPromise.then === 'function') {
        kernelPromise.then(
          (kernel) => {
            if (DEBUG) console.log('[ExecutableCode] kernel ready:', kernel);
            kernelDead = false;
            activeKernel = kernel;

            // Subscribe to kernel busy/idle for cell execution feedback.
            // thebelab 0.4.0 only emits lifecycle events (starting/ready/failed),
            // not busy/idle. The real IKernel from @jupyterlab/services has
            // a statusChanged signal we can subscribe to directly.
            /* eslint-disable @typescript-eslint/no-explicit-any */
            const k = kernel as Record<string, any>;
            const realKernel = k?.statusChanged ? k : k?.kernel;
            if (realKernel?.statusChanged?.connect) {
              realKernel.statusChanged.connect(
                (_sender: unknown, kernelStatus: string) => {
                  if (DEBUG) console.log(`[ExecutableCode] kernel.statusChanged: ${kernelStatus}`);
                  handleKernelStatusForFeedback(kernelStatus);
                }
              );
              if (DEBUG) console.log('[ExecutableCode] Subscribed to kernel.statusChanged');
            } else {
              console.warn(
                '[ExecutableCode] kernel.statusChanged not available — ' +
                'falling back to safety-net timer only'
              );
            }
            /* eslint-enable @typescript-eslint/no-explicit-any */

            injectKernelSetup(kernel).then(() => {
              broadcastStatus('ready');
              setupCellFeedback();
              annotateSaveAccountCells();
            });
          },
          (err) => {
            console.error('[ExecutableCode] kernel error:', err);
            broadcastStatus('error');
          }
        );
      } else {
        if (DEBUG) console.log('[ExecutableCode] bootstrap returned non-promise, assuming ready');
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
  const [injectionInfo, setInjectionInfo] = useState<InjectionInfo | null>(null);
  const [injectionToast, setInjectionToast] = useState<string | null>(null);
  const [binderHintDismissed, setBinderHintDismissed] = useState(false);
  const [hideStaticOutputs, setHideStaticOutputs] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const thebeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setJupyterConfig(detectJupyterConfig());
    setBinderHintDismissed(isBinderHintDismissed());
    setHideStaticOutputs(getHideStaticOutputs());
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
      setInjectionInfo(null);
      setInjectionToast(null);
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

  // Listen for injection feedback (simulator or credentials applied)
  useEffect(() => {
    const onInjection = (e: Event) => {
      const info = (e as CustomEvent<InjectionInfo>).detail;
      setInjectionInfo(info);
      if (info.message) {
        setInjectionToast(info.message);
        setTimeout(() => setInjectionToast(null), 4000);
      }
    };
    window.addEventListener(INJECTION_EVENT, onInjection);
    return () => window.removeEventListener(INJECTION_EVENT, onInjection);
  }, []);

  const isExecutable = language === 'python' && jupyterConfig?.thebeEnabled;
  const canOpenLab = jupyterConfig?.labEnabled && notebookPath;

  const handleRun = useCallback(() => {
    if (!jupyterConfig) return;

    // Track this page as executed in learning progress
    markPageExecuted(window.location.pathname);

    // Hide static outputs if user preference is set
    if (hideStaticOutputs) {
      document.body.classList.add('dq-hide-static-outputs');
    }

    // Tell ALL cells on the page to switch to run mode
    window.dispatchEvent(new CustomEvent(ACTIVATE_EVENT));

    // After all cells have rendered their <pre data-executable>, bootstrap once
    bootstrapOnce(jupyterConfig);
  }, [jupyterConfig, hideStaticOutputs]);

  const handleReset = () => {
    // Check if any cells have been executed (have done/error state)
    const executedCells = document.querySelectorAll('.thebelab-cell--done, .thebelab-cell--error');
    if (executedCells.length > 0) {
      if (!window.confirm('This will clear all execution results and return to static view. Continue?')) {
        return;
      }
    }
    // Reset module-level state so next Run triggers a fresh bootstrap
    thebelabBootstrapped = false;
    kernelDead = false;
    activeKernel = null;
    executingCell = null;
    lastKernelBusy = false;
    if (feedbackFallbackTimer) {
      clearTimeout(feedbackFallbackTimer);
      feedbackFallbackTimer = null;
    }
    if (feedbackIdleDebounceTimer) {
      clearTimeout(feedbackIdleDebounceTimer);
      feedbackIdleDebounceTimer = null;
    }
    feedbackCleanupFns.forEach(fn => fn());
    feedbackCleanupFns = [];
    // Restore static outputs
    document.body.classList.remove('dq-hide-static-outputs');
    // Tell ALL cells on the page to switch back to read mode
    window.dispatchEvent(new CustomEvent(RESET_EVENT));
  };

  const handleOpenLab = () => {
    if (!jupyterConfig || !notebookPath) return;
    const labUrl = getLabUrl(jupyterConfig, notebookPath);
    if (labUrl) {
      window.open(labUrl, 'binder-lab', 'noopener,noreferrer');
    }
  };

  const statusText: Record<ThebeStatus, string> = {
    idle: '',
    connecting: jupyterConfig?.environment === 'github-pages'
      ? 'Starting Binder (this may take 1\u20132 minutes on first run)...'
      : 'Connecting...',
    ready: '',
    error: 'Disconnected \u2014 click Back, then Run to retry',
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

          {notebookPath && (
            <a
              className="executable-code__button"
              href={getColabUrl(notebookPath)}
              target="_blank"
              rel="noopener noreferrer"
              title="Open notebook in Google Colab"
            >
              Open in Colab
            </a>
          )}

          {(thebeStatus === 'connecting' || thebeStatus === 'error') && (
            <span className={`thebe-status thebe-status--${thebeStatus}`} aria-live="polite">
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

          {thebeStatus === 'ready' && injectionInfo && injectionInfo.mode !== 'none' && (
            <span className={`executable-code__mode-badge executable-code__mode-badge--${injectionInfo.mode}`}>
              {injectionInfo.label}
            </span>
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

      {isFirstCell && injectionToast && (
        <div className="executable-code__injection-toast">
          {injectionToast}
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
              dismissBinderHint();
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
