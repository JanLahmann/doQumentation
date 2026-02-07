/**
 * ExecutableCode Component
 *
 * A code block wrapper that provides three modes of interaction:
 * 1. Read - Static syntax-highlighted code (default)
 * 2. Run - Execute code via thebelab + Jupyter/Binder kernel
 * 3. Lab - Open the full notebook in JupyterLab
 *
 * Uses thebelab 0.4.x which manages its own DOM for the interactive cell.
 * The component keeps read-mode (React-managed) and run-mode (thebelab-managed)
 * in separate containers to avoid conflicts.
 */

import React, { useState, useEffect, useRef } from 'react';
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

// Track whether thebelab config has been injected globally
let thebelabConfigured = false;

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
        repo: 'JanLahmann/doQumentation',
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
  const hasBootstrapped = useRef(false);

  useEffect(() => {
    setJupyterConfig(detectJupyterConfig());
  }, []);

  const isExecutable = language === 'python' && jupyterConfig?.thebeEnabled;
  const canOpenLab = jupyterConfig?.labEnabled && notebookPath;

  const handleRun = () => {
    if (!jupyterConfig) return;

    // Switch to run mode — shows the thebelab container
    setMode('run');
    setThebeStatus('connecting');

    // Inject global config if needed
    injectThebelabConfig(jupyterConfig);

    // Wait for thebelab to be available and the DOM to render
    const tryBootstrap = () => {
      if (!window.thebelab) {
        // thebelab CDN hasn't loaded yet, retry
        setTimeout(tryBootstrap, 500);
        return;
      }

      if (hasBootstrapped.current) {
        setThebeStatus('ready');
        return;
      }

      try {
        // thebelab.bootstrap() finds all [data-executable] elements and activates them
        window.thebelab.bootstrap();
        hasBootstrapped.current = true;
        setThebeStatus('ready');
      } catch (err) {
        console.error('thebelab bootstrap error:', err);
        setThebeStatus('error');
      }
    };

    // Give React a tick to render the data-executable pre element
    setTimeout(tryBootstrap, 100);
  };

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
    connecting: 'Connecting to Binder...',
    ready: 'Ready',
    error: 'Connection error',
  };

  const code = children.replace(/\n$/, '');

  return (
    <div className="executable-code">
      {/* Toolbar */}
      {(isExecutable || canOpenLab) && (
        <div className="executable-code__toolbar">
          <button
            className={`executable-code__button ${mode === 'read' ? 'executable-code__button--active' : ''}`}
            onClick={handleReset}
            title="View code (read-only)"
          >
            Read
          </button>

          {isExecutable && (
            <button
              className={`executable-code__button ${mode === 'run' ? 'executable-code__button--active' : ''}`}
              onClick={handleRun}
              disabled={thebeStatus === 'connecting'}
              title={
                jupyterConfig?.environment === 'github-pages'
                  ? 'Execute via Binder (may take a moment to start)'
                  : 'Execute on local Jupyter server'
              }
            >
              {thebeStatus === 'connecting' ? 'Connecting...' : 'Run'}
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
