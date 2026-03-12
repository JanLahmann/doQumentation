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
import Translate, {translate} from '@docusaurus/Translate';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useLocation} from '@docusaurus/router';
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
  ensureBinderSession,
  touchBinderSession,
  clearBinderSession,
  cancelBinderBuild,
  type JupyterConfig,
  type BinderSession,
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
const RESTART_EVENT = 'executablecode:restart';
const INJECTION_EVENT = 'executablecode:injection';
const BINDER_PHASE_EVENT = 'executablecode:binderphase';

type ThebeStatus = 'idle' | 'connecting' | 'ready' | 'error';

type InjectionInfo = {
  mode: 'simulator' | 'credentials' | 'none';
  label: string;    // Badge text: "AerSimulator", "FakeSherbrooke", "IBM Quantum"
  message: string;  // Toast text for brief feedback
};

// Gate debug logging — only in development builds
const DEBUG = typeof process !== 'undefined' && process.env.NODE_ENV === 'development';

// ── Cell execution feedback ──
// Safety-net timeout (ms) — if kernel.statusChanged never fires idle after a cell
// execution, force-settle the cell feedback after this duration.
const FEEDBACK_SAFETY_NET_MS = 60000;
// Tracks which cell is currently executing so we can show "Done" for no-output cells.

let executingCell: Element | null = null;
let lastKernelBusy = false;
let feedbackFallbackTimer: ReturnType<typeof setTimeout> | null = null;
let feedbackIdleDebounceTimer: ReturnType<typeof setTimeout> | null = null;
let kernelDead = false;
let feedbackCleanupFns: (() => void)[] = [];
let activeKernel: unknown = null;

// ── Run All state ──
let runAllActive = false;
let runAllAbort = false;

/** Reset all module-level mutable state so next Run triggers a fresh bootstrap. */
function resetModuleState(): void {
  thebelabBootstrapped = false;
  kernelDead = false;
  activeKernel = null;
  executingCell = null;
  lastKernelBusy = false;
  runAllActive = false;
  runAllAbort = true;
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
}

/**
 * Wait for the kernel to go busy then idle (one execution cycle).
 * Used by Run All to sequence cell executions.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
function waitForKernelIdle(): Promise<void> {
  return new Promise(resolve => {
    if (!activeKernel) { resolve(); return; }
    const k = activeKernel as Record<string, any>;
    const realKernel = k?.statusChanged ? k : k?.kernel;
    if (!realKernel?.statusChanged?.connect) { resolve(); return; }

    let sawBusy = false;
    const handler = (_: unknown, status: string) => {
      if (status === 'busy') sawBusy = true;
      if (sawBusy && status === 'idle') {
        realKernel.statusChanged.disconnect(handler);
        clearTimeout(fallback);
        setTimeout(resolve, 200);
      }
    };
    realKernel.statusChanged.connect(handler);

    // Fallback: if kernel never goes busy (empty cell), resolve after 2s
    const fallback = setTimeout(() => {
      realKernel.statusChanged.disconnect(handler);
      resolve();
    }, 2000);
  });
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/** Validate a Python package name for pip install. */
function isValidPackageName(name: string): boolean {
  return /^[a-zA-Z0-9._-]+$/.test(name);
}

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
    if (!isValidPackageName(pkg)) return;
    const div = document.createElement('div');
    div.className = 'thebelab-cell__error-hint';

    const text = document.createElement('span');
    text.append(translate({id: 'executable.errorHint.packagePrefix', message: 'Package '}));
    const pkgCode = document.createElement('code');
    pkgCode.textContent = pkg;
    text.appendChild(pkgCode);
    text.append(translate({id: 'executable.errorHint.notInstalled', message: ' is not installed.'}));
    div.appendChild(text);

    if (activeKernel && !kernelDead) {
      const btn = document.createElement('button');
      btn.className = 'thebelab-cell__install-btn';
      btn.textContent = translate({id: 'executable.errorHint.installBtn', message: 'Install {pkg}'}).replace('{pkg}', pkg);
      btn.title = translate({id: 'executable.errorHint.installTitle', message: 'Run !pip install -q {pkg}'}).replace('{pkg}', pkg);
      btn.addEventListener('click', () => handlePipInstall(cell, pkg, btn));
      div.appendChild(btn);
    } else {
      const fallback = document.createElement('span');
      fallback.append(translate({id: 'executable.errorHint.runPrefix', message: ' Run '}));
      const fallbackCode = document.createElement('code');
      fallbackCode.textContent = `!pip install -q ${pkg}`;
      fallback.appendChild(fallbackCode);
      fallback.append(translate({id: 'executable.errorHint.inACell', message: ' in a cell.'}));
      div.appendChild(fallback);
    }

    cell.appendChild(div);
    return;
  }

  const div = document.createElement('div');
  div.className = 'thebelab-cell__error-hint';

  if (error.type === 'kernel') {
    div.append(translate({id: 'executable.errorHint.kernelDisconnected', message: 'Kernel disconnected. Click '}));
    const back = document.createElement('strong');
    back.textContent = translate({id: 'executable.errorHint.back', message: 'Back'});
    div.appendChild(back);
    div.append(translate({id: 'executable.errorHint.then', message: ' then '}));
    const run = document.createElement('strong');
    run.textContent = translate({id: 'executable.errorHint.run', message: 'Run'});
    div.appendChild(run);
    div.append(translate({id: 'executable.errorHint.toReconnect', message: ' to reconnect.'}));
    cell.appendChild(div);
  } else if (error.type === 'name' && error.name) {
    const nameCode = document.createElement('code');
    nameCode.textContent = error.name;
    div.appendChild(nameCode);
    div.append(translate({id: 'executable.errorHint.notDefined', message: ' is not defined. Run the cells above first \u2014 notebooks must be executed in order.'}));
    cell.appendChild(div);
  }
}

/** Run !pip install on the kernel, update button state, and re-run the failed cell. */
async function handlePipInstall(
  cell: Element,
  pkg: string,
  btn: HTMLButtonElement
): Promise<void> {
  if (!isValidPackageName(pkg)) return;
  btn.disabled = true;
  btn.textContent = translate({id: 'executable.pip.installing', message: 'Installing {pkg}...'}).replace('{pkg}', pkg);
  btn.classList.add('thebelab-cell__install-btn--installing');
  cell.classList.remove('thebelab-cell--error');
  cell.classList.add('thebelab-cell--running');

  const ok = await executeOnKernel(activeKernel, `!pip install -q ${pkg}`);

  if (ok) {
    btn.textContent = translate({id: 'executable.pip.installed', message: 'Installed \u2713'});
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
    btn.textContent = translate({id: 'executable.pip.failed', message: 'Install failed'});
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
  }, FEEDBACK_SAFETY_NET_MS);
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

      const skipLabel = translate({
        id: 'executable.skipCell',
        message: 'Skip this cell',
        description: 'Bold label on save_account() cells when simulator/credentials active',
      });
      const div = document.createElement('div');
      div.className = 'thebelab-cell__skip-hint';
      const strong = document.createElement('strong');
      strong.textContent = skipLabel;
      div.appendChild(strong);
      if (simMode) {
        const simText = translate({
          id: 'executable.skipCell.simulatorActive',
          message: 'Simulator Mode is active. Running it has no effect.',
          description: 'Explanation shown on save_account() cells when simulator mode is on',
        });
        div.appendChild(document.createTextNode(` \u2014 ${simText}`));
      } else {
        const credsBefore = translate({
          id: 'executable.skipCell.credentialsBefore',
          message: 'your credentials are already configured via ',
          description: 'Text before the Settings link on save_account() cells (include trailing space if needed)',
        });
        const settingsLabel = translate({
          id: 'executable.skipCell.settingsLink',
          message: 'Settings',
          description: 'Link text pointing to the Settings page',
        });
        const credsAfter = translate({
          id: 'executable.skipCell.credentialsAfter',
          message: '. Running it with placeholder values will overwrite them.',
          description: 'Text after the Settings link on save_account() cells (include leading punctuation)',
        });
        div.appendChild(document.createTextNode(` \u2014 `));
        div.appendChild(document.createTextNode(credsBefore));
        const a = document.createElement('a');
        a.href = '/jupyter-settings#ibm-quantum';
        a.textContent = settingsLabel;
        div.appendChild(a);
        div.appendChild(document.createTextNode(credsAfter));
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
          } catch (e) {
            if (DEBUG) console.debug('[ExecutableCode] Failed to parse fake backends response', e);
          }
        }
      };
    }
  } catch (e) {
    if (DEBUG) console.debug('[ExecutableCode] Failed to discover fake backends', e);
  }
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
function getThebelabOptions(config: JupyterConfig, session?: BinderSession | null): Record<string, unknown> {
  if (config.environment === 'github-pages' || config.environment === 'code-engine') {
    if (session) {
      // Reuse existing Binder/CE server — connect via serverSettings (same as local/Docker)
      return {
        requestKernel: true,
        kernelOptions: {
          name: 'python3',
          serverSettings: {
            baseUrl: session.url,
            wsUrl: session.url.replace(/^http(s?):\/\//, 'ws$1://'),
            token: session.token,
          },
        },
      };
    }
    // Fallback: let thebelab start its own Binder build (same repo as "Open in Binder")
    return {
      requestKernel: true,
      binderOptions: {
        repo: 'JanLahmann/doQumentation',
        ref: 'notebooks',
        binderUrl: 'https://mybinder.org',
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
 * Wait for thebelab CDN to load, then call bootstrap() with the given options.
 * Handles kernel promise, status events, and credential injection.
 */
const BOOTSTRAP_MAX_RETRIES = 60; // 60 × 500ms = 30s total timeout

function doBootstrap(thebelabOptions: Record<string, unknown>): void {
  let retryCount = 0;
  const tryBootstrap = () => {
    if (!window.thebelab) {
      retryCount++;
      if (retryCount > BOOTSTRAP_MAX_RETRIES) {
        console.error('[ExecutableCode] thebelab CDN failed to load after 30s');
        broadcastStatus('error');
        return;
      }
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
                  // Keep Binder session alive during active code execution
                  if (kernelStatus === 'busy' || kernelStatus === 'idle') {
                    touchBinderSession();
                  }
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

/**
 * Bootstrap thebelab with Binder session reuse.
 * Called once — subsequent activations are no-ops.
 *
 * For GitHub Pages: ensures a Binder session exists (reuses or starts build),
 * then connects thebelab via serverSettings. This shares the Binder server
 * with "Open in Binder JupyterLab" — one build serves both.
 */
function bootstrapOnce(config: JupyterConfig): void {
  if (thebelabBootstrapped) {
    broadcastStatus('ready');
    return;
  }

  // Set guard synchronously to prevent duplicate bootstrap from rapid clicks
  thebelabBootstrapped = true;

  if ((config.environment === 'github-pages' || config.environment === 'code-engine') && config.binderUrl) {
    // Build (or reuse) Binder/CE session, then connect thebelab via serverSettings
    ensureBinderSession(config, (phase) => {
      if (DEBUG) console.log(`[ExecutableCode] ${config.environment === 'code-engine' ? 'CE' : 'Binder'} phase: ${phase}`);
      window.dispatchEvent(new CustomEvent(BINDER_PHASE_EVENT, { detail: phase }));
    }).then((session) => {
      const options = getThebelabOptions(config, session);
      doBootstrap(options);
    }).catch(() => {
      thebelabBootstrapped = false; // allow retry on failure
      broadcastStatus('error');
    });
    return;
  }

  const options = getThebelabOptions(config);
  doBootstrap(options);
}

/**
 * Restart the active kernel — clears all cell outputs, resets feedback state,
 * and re-injects credentials/simulator setup. The kernel stays connected
 * to the same Binder session (no rebuild).
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
async function restartKernel(): Promise<boolean> {
  if (!activeKernel) return false;

  const k = activeKernel as Record<string, any>;
  const realKernel = k?.restart ? k : k?.kernel;
  if (!realKernel?.restart) {
    console.warn('[ExecutableCode] kernel.restart() not available');
    return false;
  }

  try {
    broadcastStatus('connecting');
    await realKernel.restart();
    if (DEBUG) console.log('[ExecutableCode] kernel restarted');

    // Clear cell outputs and feedback classes
    document.querySelectorAll('.thebelab-cell').forEach(cell => {
      cell.classList.remove('thebelab-cell--running', 'thebelab-cell--done', 'thebelab-cell--error');
      const output = cell.querySelector('.thebelab-output, .output_area');
      if (output) output.textContent = '';
    });

    // Reset feedback state
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

    // Re-inject credentials/simulator setup
    await injectKernelSetup(activeKernel);
    broadcastStatus('ready');
    // Notify cells to clear their UI state
    window.dispatchEvent(new CustomEvent(RESTART_EVENT));
    return true;
  } catch (err) {
    console.error('[ExecutableCode] kernel restart failed:', err);
    broadcastStatus('error');
    return false;
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export default function ExecutableCode({
  children,
  language = 'python',
  notebookPath,
  title,
  showLineNumbers = true,
}: ExecutableCodeProps): JSX.Element {
  const { i18n: { currentLocale } } = useDocusaurusContext();
  const location = useLocation();

  // Reset module-level state on SPA page navigation so stale kernel/bootstrap
  // state from the previous page doesn't leak into the new page.
  const prevPathRef = useRef(location.pathname);
  useEffect(() => {
    if (location.pathname !== prevPathRef.current) {
      prevPathRef.current = location.pathname;
      resetModuleState();
    }
  }, [location.pathname]);

  const [mode, setMode] = useState<'read' | 'run'>('read');
  const [thebeStatus, setThebeStatus] = useState<ThebeStatus>('idle');
  const [jupyterConfig, setJupyterConfig] = useState<JupyterConfig | null>(null);
  const [isFirstCell, setIsFirstCell] = useState(false);
  const [conflictBanner, setConflictBanner] = useState<string | null>(null);
  const [injectionInfo, setInjectionInfo] = useState<InjectionInfo | null>(null);
  const [injectionToast, setInjectionToast] = useState<string | null>(null);
  const [binderHintDismissed, setBinderHintDismissed] = useState(false);
  const [hideStaticOutputs, setHideStaticOutputs] = useState(false);
  const [binderPhase, setBinderPhase] = useState<string | null>(null);
  const [binderElapsed, setBinderElapsed] = useState(0);
  const [binderCacheMiss, setBinderCacheMiss] = useState(false);
  const [binderSlowStartup, setBinderSlowStartup] = useState(false);
  const [runAllProgress, setRunAllProgress] = useState<{ current: number; total: number } | null>(null);
  const binderStartRef = useRef<number | null>(null);
  const phaseStartRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setJupyterConfig(detectJupyterConfig());
    setBinderHintDismissed(isBinderHintDismissed());
    setHideStaticOutputs(getHideStaticOutputs());
  }, []);

  // Determine if this is the first executable cell on the page (toolbar owner).
  // Re-evaluate when cells mount/unmount dynamically via MutationObserver.
  useEffect(() => {
    if (!containerRef.current) return;
    const check = () => {
      const allCells = document.querySelectorAll('.executable-code');
      setIsFirstCell(allCells.length > 0 && allCells[0] === containerRef.current);
    };
    check();
    const observer = new MutationObserver(check);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
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
      setBinderPhase(null);
      setBinderElapsed(0);
      setBinderCacheMiss(false);
      setBinderSlowStartup(false);
      binderStartRef.current = null;
      phaseStartRef.current = null;
      setInjectionInfo(null);
      setInjectionToast(null);
      runAllActive = false;
      runAllAbort = true;
      setRunAllProgress(null);
    };
    window.addEventListener(RESET_EVENT, onReset);
    return () => window.removeEventListener(RESET_EVENT, onReset);
  }, []);

  // Listen for global status updates from the bootstrap process
  useEffect(() => {
    const onStatus = (e: Event) => {
      const status = (e as CustomEvent<ThebeStatus>).detail;
      setThebeStatus(status);
      if (status === 'ready' || status === 'error') setBinderPhase(null);
    };
    window.addEventListener(STATUS_EVENT, onStatus);
    return () => window.removeEventListener(STATUS_EVENT, onStatus);
  }, []);

  // Listen for Binder build phase updates (GitHub Pages only)
  useEffect(() => {
    const onPhase = (e: Event) => {
      const phase = (e as CustomEvent<string>).detail;
      if (phase === 'connecting' && binderStartRef.current === null) {
        binderStartRef.current = Date.now();
      }
      if (phase === 'building') {
        setBinderCacheMiss(true);
      }
      if (phase === 'ready' || phase === 'failed') {
        setBinderPhase(null);
        binderStartRef.current = null;
        phaseStartRef.current = null;
        setBinderElapsed(0);
        setBinderSlowStartup(false);
        if (phase === 'ready') setBinderCacheMiss(false);
      } else {
        setBinderPhase(phase);
        phaseStartRef.current = Date.now();
        setBinderSlowStartup(false);
      }
    };
    window.addEventListener(BINDER_PHASE_EVENT, onPhase);
    return () => window.removeEventListener(BINDER_PHASE_EVENT, onPhase);
  }, []);

  // Per-phase timeout thresholds (seconds) — exceeding triggers slow startup warning
  const PHASE_TIMEOUTS: Record<string, number> = {
    connecting: 60,      // 1 min — should connect quickly
    waiting: 3 * 60,     // 3 min — queue can be slow
    fetching: 5 * 60,    // 5 min — "Fetching repo (2–5 min)"
    building: 12 * 60,   // 12 min — "Building image (5–10 min)" + buffer
    pushing: 5 * 60,     // 5 min — "Pushing image (2–5 min)"
    built: 2 * 60,       // 2 min — should be fast
    launching: 5 * 60,   // 5 min — "Launching server (2–5 min)"
  };

  // Elapsed timer for Binder build + per-phase slow startup detection
  useEffect(() => {
    if (!binderPhase) return;
    const interval = setInterval(() => {
      if (binderStartRef.current !== null) {
        setBinderElapsed(Math.floor((Date.now() - binderStartRef.current) / 1000));
      }
      if (phaseStartRef.current !== null && binderPhase) {
        const phaseElapsed = Math.floor((Date.now() - phaseStartRef.current) / 1000);
        const threshold = PHASE_TIMEOUTS[binderPhase] ?? 5 * 60;
        if (phaseElapsed >= threshold) {
          setBinderSlowStartup(true);
        }
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [binderPhase]);

  // Listen for conflict banner (both credentials + simulator configured, no explicit choice)
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onConflict = (e: Event) => {
      const usingMode = (e as CustomEvent<string>).detail;
      setConflictBanner(usingMode);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setConflictBanner(null), 5000);
    };
    window.addEventListener(CONFLICT_EVENT, onConflict);
    return () => {
      window.removeEventListener(CONFLICT_EVENT, onConflict);
      if (timer) clearTimeout(timer);
    };
  }, []);

  // Listen for injection feedback (simulator or credentials applied)
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onInjection = (e: Event) => {
      const info = (e as CustomEvent<InjectionInfo>).detail;
      setInjectionInfo(info);
      if (info.message) {
        setInjectionToast(info.message);
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => setInjectionToast(null), 4000);
      }
    };
    window.addEventListener(INJECTION_EVENT, onInjection);
    return () => {
      window.removeEventListener(INJECTION_EVENT, onInjection);
      if (timer) clearTimeout(timer);
    };
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

    // Defer bootstrap to next frame so React can render <pre data-executable> first
    requestAnimationFrame(() => {
      bootstrapOnce(jupyterConfig);
    });
  }, [jupyterConfig, hideStaticOutputs]);

  const handleReset = useCallback(() => {
    // If still connecting, cancel the Binder build without confirmation
    if (thebeStatus === 'connecting') {
      cancelBinderBuild();
      resetModuleState();
      document.body.classList.remove('dq-hide-static-outputs');
      window.dispatchEvent(new CustomEvent(RESET_EVENT));
      return;
    }
    // Check if any cells have been executed (have done/error state)
    const executedCells = document.querySelectorAll('.thebelab-cell--done, .thebelab-cell--error');
    if (executedCells.length > 0) {
      if (!window.confirm(translate({id: 'executable.reset.confirm', message: 'This will clear all execution results and return to static view. Continue?'}))) {
        return;
      }
    }
    resetModuleState();
    document.body.classList.remove('dq-hide-static-outputs');
    window.dispatchEvent(new CustomEvent(RESET_EVENT));
  }, [thebeStatus]);

  const handleRestart = useCallback(() => {
    if (!window.confirm(translate({
      id: 'executable.restart.confirm',
      message: 'Restart kernel? All variables and outputs will be cleared.',
    }))) return;
    runAllActive = false;
    runAllAbort = true;
    setRunAllProgress(null);
    restartKernel();
  }, []);

  const handleRunAll = useCallback(async () => {
    if (runAllActive) return;
    runAllActive = true;
    runAllAbort = false;

    // Collect all thebelab cells and find their run buttons
    const cells = document.querySelectorAll('.thebelab-cell');
    const runBtns: HTMLButtonElement[] = [];
    cells.forEach(cell => {
      const btn = Array.from(cell.querySelectorAll('button'))
        .find(b => b.textContent?.trim().toLowerCase() === 'run');
      if (btn) runBtns.push(btn as HTMLButtonElement);
    });

    if (runBtns.length === 0) {
      runAllActive = false;
      return;
    }

    setRunAllProgress({ current: 0, total: runBtns.length });

    for (let i = 0; i < runBtns.length; i++) {
      if (runAllAbort) break;
      setRunAllProgress({ current: i + 1, total: runBtns.length });
      const cell = runBtns[i].closest('.thebelab-cell');
      if (cell) markCellExecuting(cell);
      runBtns[i].click();
      await waitForKernelIdle();
    }

    runAllActive = false;
    runAllAbort = false;
    setRunAllProgress(null);
  }, []);

  const handleStopRunAll = useCallback(() => {
    runAllAbort = true;
  }, []);

  const handleClearSession = useCallback(() => {
    if (!window.confirm(translate({
      id: 'executable.clearSession.confirm',
      message: 'Clear session? You will need to wait for a new server on next Run.',
    }))) return;
    clearBinderSession();
    resetModuleState();
    document.body.classList.remove('dq-hide-static-outputs');
    window.dispatchEvent(new CustomEvent(RESET_EVENT));
  }, []);

  const handleOpenLab = () => {
    if (!jupyterConfig || !notebookPath) return;
    const labUrl = getLabUrl(jupyterConfig, notebookPath);
    if (labUrl) {
      window.open(labUrl, 'binder-lab');
    }
  };

  // Binder phase labels for the toolbar status text
  const binderPhaseLabels: Record<string, string> = {
    connecting: translate({id: 'executable.status.binderConnecting', message: 'Connecting...'}),
    waiting: translate({id: 'executable.status.binderWaiting', message: 'In queue...'}),
    fetching: translate({id: 'executable.status.binderFetching', message: 'Fetching repo (2\u20135 min)...'}),
    building: translate({id: 'executable.status.binderBuilding', message: 'Building image (5\u201310 min)...'}),
    pushing: translate({id: 'executable.status.binderPushing', message: 'Pushing image (2\u20135 min)...'}),
    built: translate({id: 'executable.status.binderBuilt', message: 'Launching...'}),
    launching: translate({id: 'executable.status.binderLaunching', message: 'Launching server (2\u20135 min)...'}),
  };

  // CE phase labels — faster startup, fewer phases
  const cePhaseLabels: Record<string, string> = {
    connecting: translate({id: 'executable.status.ceConnecting', message: 'Connecting to Code Engine...'}),
    launching: translate({id: 'executable.status.ceLaunching', message: 'Starting server...'}),
    ready: translate({id: 'executable.status.ceReady', message: 'Connected!'}),
    failed: translate({id: 'executable.status.ceFailed', message: 'Code Engine connection failed'}),
  };

  const isCodeEngine = jupyterConfig?.environment === 'code-engine';
  const usesRemoteSession = jupyterConfig?.environment === 'github-pages' || isCodeEngine;
  const activePhaseLabels = isCodeEngine ? cePhaseLabels : binderPhaseLabels;

  const formatElapsed = (s: number) => s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
  const phaseLabel = usesRemoteSession
    ? (binderPhase && activePhaseLabels[binderPhase]) || activePhaseLabels.connecting
    : null;
  const connectingText = usesRemoteSession
    ? (phaseLabel || '') + (binderElapsed > 0 ? ` ${formatElapsed(binderElapsed)}` : '')
    : translate({id: 'executable.status.connecting', message: 'Connecting...'});

  const statusText: Record<ThebeStatus, string> = {
    idle: '',
    connecting: connectingText,
    ready: '',
    error: translate({id: 'executable.status.error', message: 'Disconnected \u2014 click Back, then Run to retry'}),
  };

  const code = children.replace(/\n$/, '');

  // Hide injected pip install cell on Binder/CE (packages pre-installed)
  const isPipInstallCell = children.includes('Added by doQumentation') && children.includes('!pip install');
  const packagesPreinstalled = jupyterConfig?.environment === 'github-pages' || jupyterConfig?.environment === 'code-engine';
  if (isPipInstallCell && packagesPreinstalled) {
    return null;
  }

  return (
    <div className="executable-code" ref={containerRef}>
      {/* Toolbar — only rendered on the first executable cell */}
      {isFirstCell && (isExecutable || canOpenLab) && (
        <div className="executable-code__toolbar">
          {isExecutable && (
            <button
              className={`executable-code__button ${mode === 'run' ? 'executable-code__button--active' : ''}`}
              onClick={mode === 'run' ? handleReset : handleRun}
              title={
                thebeStatus === 'connecting'
                  ? translate({id: 'executable.button.cancelTitle', message: 'Cancel Binder startup and return to static view'})
                  : mode === 'run'
                    ? translate({id: 'executable.button.backTitle', message: 'Back to static view'})
                    : isCodeEngine
                      ? translate({id: 'executable.button.runCeTitle', message: 'Execute via Code Engine'})
                      : jupyterConfig?.environment === 'github-pages'
                        ? translate({id: 'executable.button.runBinderTitle', message: 'Execute via Binder (may take a moment to start)'})
                        : translate({id: 'executable.button.runLocalTitle', message: 'Execute on local Jupyter server'})
              }
            >
              {thebeStatus === 'connecting'
                ? translate({id: 'executable.button.cancel', message: 'Cancel'})
                : mode === 'run'
                  ? translate({id: 'executable.button.back', message: 'Back'})
                  : translate({id: 'executable.button.run', message: 'Run'})}
            </button>
          )}

          {isExecutable && mode === 'run' && thebeStatus === 'ready' && (
            <button
              className="executable-code__button"
              onClick={handleRestart}
              title={translate({id: 'executable.button.restartTitle', message: 'Restart kernel (clears all variables and outputs)'})}
            >
              {translate({id: 'executable.button.restart', message: 'Restart Kernel'})}
            </button>
          )}

          {isExecutable && mode === 'run' && thebeStatus === 'ready' && (
            <button
              className="executable-code__button"
              onClick={runAllProgress ? handleStopRunAll : handleRunAll}
              title={runAllProgress
                ? translate({id: 'executable.button.stopRunAllTitle', message: 'Stop after current cell finishes'})
                : translate({id: 'executable.button.runAllTitle', message: 'Run all cells on this page in order'})}
            >
              {runAllProgress
                ? translate(
                    {id: 'executable.button.stopRunAll', message: 'Stop ({current}/{total})'},
                    {current: String(runAllProgress.current), total: String(runAllProgress.total)}
                  )
                : translate({id: 'executable.button.runAll', message: 'Run All'})}
            </button>
          )}

          {isExecutable && mode === 'run' && thebeStatus === 'ready' && usesRemoteSession && (
            <button
              className="executable-code__button"
              onClick={handleClearSession}
              title={translate({id: 'executable.button.clearSessionTitle', message: 'Clear session and return to static view (next Run starts a new server)'})}
            >
              {translate({id: 'executable.button.clearSession', message: 'Clear Session'})}
            </button>
          )}

          {canOpenLab && (
            <button
              className="executable-code__button"
              onClick={handleOpenLab}
              title={translate({id: 'executable.button.labTitle', message: 'Open full notebook in JupyterLab'})}
            >
              {translate({id: 'executable.button.lab', message: 'Open in Lab'})}
            </button>
          )}

          {notebookPath && (
            <a
              className="executable-code__button"
              href={getColabUrl(notebookPath, currentLocale)}
              target="_blank"
              rel="noopener noreferrer"
              title={translate({id: 'executable.button.colabTitle', message: 'Open notebook in Google Colab'})}
            >
              {translate({id: 'executable.button.colab', message: 'Open in Colab'})}
            </a>
          )}

          {(thebeStatus === 'connecting' || thebeStatus === 'error') && (
            <span className={`thebe-status thebe-status--${thebeStatus}`} aria-live="polite">
              {statusText[thebeStatus]}
            </span>
          )}

          {thebeStatus === 'ready' && (
            <span className="executable-code__legend">
              <span className="executable-code__legend-item executable-code__legend-item--running">{translate({id: 'executable.legend.running', message: 'running'})}</span>
              <span className="executable-code__legend-item executable-code__legend-item--done">{translate({id: 'executable.legend.done', message: 'done'})}</span>
              <span className="executable-code__legend-item executable-code__legend-item--error">{translate({id: 'executable.legend.error', message: 'error'})}</span>
            </span>
          )}

          {thebeStatus === 'ready' && injectionInfo && injectionInfo.mode !== 'none' && (
            <a
              href="/jupyter-settings#simulator-mode"
              className={`executable-code__mode-badge executable-code__mode-badge--${injectionInfo.mode}`}
              style={{ textDecoration: 'none', color: 'inherit' }}
              title={translate({id: 'executable.badge.settingsTitle', message: 'Go to Settings to change execution mode'})}
            >
              {injectionInfo.label}
            </a>
          )}

          <a
            className="executable-code__settings-link"
            href="/jupyter-settings#ibm-quantum"
            title={translate({id: 'executable.settingsLink.title', message: 'Jupyter & IBM Quantum settings'})}
          >
            {translate({id: 'executable.settingsLink', message: 'Settings'})}
          </a>
        </div>
      )}

      {isFirstCell && binderCacheMiss && binderPhase && (
        <div className="executable-code__conflict-banner" style={{ borderColor: 'var(--ifm-color-warning-dark, #b45309)', color: 'var(--ifm-color-warning-dark, #b45309)' }}>
          {translate({id: 'executable.status.binderCacheMiss', message: '\u26a0 Cache not warmed \u2014 total build time 10\u201325 min. Use Colab (above) or come back later.'})}
        </div>
      )}

      {isFirstCell && binderSlowStartup && binderPhase && (
        <div className="executable-code__conflict-banner" style={{ borderColor: 'var(--ifm-color-danger-dark, #dc3545)', color: 'var(--ifm-color-danger-dark, #dc3545)' }}>
          {translate({id: 'executable.status.binderSlowStartup', message: 'Binder startup is taking longer than expected. You can cancel and try again later, or use one of the other backends (Colab, Docker, or Code Engine).'})}
        </div>
      )}

      {isFirstCell && conflictBanner && (
        <div className="executable-code__conflict-banner" role="alert">
          <Translate
            id="executable.conflict"
            values={{
              mode: <strong>{conflictBanner}</strong>,
              settingsLink: (
                <a href="/jupyter-settings#ibm-quantum">
                  <Translate id="executable.conflict.settingsLink">Change in Settings</Translate>
                </a>
              ),
            }}
          >
            {'Both IBM credentials and simulator mode are configured. Using {mode}. {settingsLink}.'}
          </Translate>
        </div>
      )}

      {isFirstCell && injectionToast && (
        <div className="executable-code__injection-toast" role="status" aria-live="polite">
          {injectionToast}
        </div>
      )}

      {isFirstCell && thebeStatus === 'ready' && usesRemoteSession &&
        !binderHintDismissed && (
        <div className="executable-code__binder-hint">
          <Translate
            id="executable.binderHint"
            values={{
              pipCode: <code>!pip install -q &lt;package&gt;</code>,
              packagesLink: (
                <a href="/jupyter-settings#binder-packages">
                  <Translate id="executable.binderHint.packagesLink">available packages</Translate>
                </a>
              ),
            }}
          >
            {'Need extra packages? Run {pipCode} in a cell, or see {packagesLink}.'}
          </Translate>
          <button
            className="executable-code__binder-hint-dismiss"
            onClick={() => {
              dismissBinderHint();
              setBinderHintDismissed(true);
            }}
            title={translate({id: 'executable.dismissHint', message: 'Dismiss'})}
            aria-label={translate({id: 'executable.dismissHint', message: 'Dismiss'})}
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
        <div className="executable-code__thebe">
          <pre data-executable="true" data-language="python">
            {code}
          </pre>
        </div>
      )}
    </div>
  );
}
