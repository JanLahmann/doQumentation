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
 * defined in earlier cells are available in later ones. Clicking "Run"
 * on any cell activates all cells on the page.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import CodeBlock from '@theme-original/CodeBlock';
import {
  detectJupyterConfig,
  getLabUrl,
  type JupyterConfig,
} from '../../config/jupyter';

// thebelab 0.4.x global
declare global {
  interface Window {
    thebelab?: {
      bootstrap: (options?: Record<string, unknown>) => void;
    };
  }
}

// ── Global (module-level) state shared across all instances ──

let thebelabConfigured = false;
let thebelabBootstrapped = false;

// Custom event name used to coordinate all cells on the page
const ACTIVATE_EVENT = 'executablecode:activate';
const STATUS_EVENT = 'executablecode:status';

type ThebeStatus = 'idle' | 'connecting' | 'ready' | 'error';

interface ExecutableCodeProps {
  children: string;
  language?: string;
  notebookPath?: string;
  title?: string;
  showLineNumbers?: boolean;
}

function injectThebelabConfig(config: JupyterConfig): void {
  if (thebelabConfigured) return;

  // Remove any existing config script
  const existing = document.querySelector('script[type="text/x-thebe-config"]');
  if (existing) existing.remove();

  const script = document.createElement('script');
  script.type = 'text/x-thebe-config';

  if (config.environment === 'github-pages') {
    script.textContent = JSON.stringify({
      requestKernel: true,
      binderOptions: {
        repo: 'JanLahmann/Qiskit-documentation',
        ref: 'main',
        binderUrl: 'https://mybinder.org',
      },
      kernelOptions: {
        name: 'python3',
      },
    });
  } else if (config.baseUrl) {
    script.textContent = JSON.stringify({
      requestKernel: true,
      kernelOptions: {
        name: 'python3',
        serverSettings: {
          baseUrl: config.baseUrl,
          wsUrl: config.wsUrl,
          token: config.token,
        },
      },
    });
  }

  document.head.appendChild(script);
  thebelabConfigured = true;
}

/** Broadcast a status change to all cells on the page. */
function broadcastStatus(status: ThebeStatus): void {
  window.dispatchEvent(new CustomEvent(STATUS_EVENT, { detail: status }));
}

/**
 * Wait for thebelab to load, then bootstrap all [data-executable] cells.
 * Called once — subsequent activations are no-ops.
 */
function bootstrapOnce(): void {
  if (thebelabBootstrapped) {
    broadcastStatus('ready');
    return;
  }

  const tryBootstrap = () => {
    if (!window.thebelab) {
      setTimeout(tryBootstrap, 500);
      return;
    }
    try {
      window.thebelab.bootstrap();
      thebelabBootstrapped = true;
      broadcastStatus('ready');
    } catch (err) {
      console.error('thebelab bootstrap error:', err);
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
  const thebeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setJupyterConfig(detectJupyterConfig());
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

  // Listen for global status updates from the bootstrap process
  useEffect(() => {
    const onStatus = (e: Event) => {
      const status = (e as CustomEvent<ThebeStatus>).detail;
      setThebeStatus(status);
    };
    window.addEventListener(STATUS_EVENT, onStatus);
    return () => window.removeEventListener(STATUS_EVENT, onStatus);
  }, []);

  const isExecutable = language === 'python' && jupyterConfig?.thebeEnabled;
  const canOpenLab = jupyterConfig?.labEnabled && notebookPath;

  const handleRun = useCallback(() => {
    if (!jupyterConfig) return;

    // Inject global config if needed
    injectThebelabConfig(jupyterConfig);

    // Tell ALL cells on the page to switch to run mode
    window.dispatchEvent(new CustomEvent(ACTIVATE_EVENT));

    // After all cells have rendered their <pre data-executable>, bootstrap once
    bootstrapOnce();
  }, [jupyterConfig]);

  const handleReset = () => {
    setMode('read');
    setThebeStatus('idle');
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
    <div className="executable-code">
      {/* Toolbar */}
      {(isExecutable || canOpenLab) && (
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
              {thebeStatus === 'connecting' ? 'Connecting...' : mode === 'run' ? 'Stop' : 'Run'}
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
        </div>
      )}

      {thebeStatus === 'ready' && jupyterConfig?.environment === 'github-pages' && (
        <div className="executable-code__binder-hint">
          Some notebooks need extra packages. Run{' '}
          <code>!pip install -q &lt;package&gt;</code>{' '}
          in a cell, or see{' '}
          <a href="/jupyter-settings#binder-packages">all available packages</a>.
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
