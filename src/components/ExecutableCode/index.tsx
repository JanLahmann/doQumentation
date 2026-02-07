/**
 * ExecutableCode Component
 * 
 * A code block wrapper that provides three modes of interaction:
 * 1. Read - Static syntax-highlighted code (default)
 * 2. Run - Execute code via Thebe + Jupyter kernel
 * 3. Lab - Open the full notebook in JupyterLab
 * 
 * This component automatically detects the environment and enables
 * appropriate features for GitHub Pages vs RasQberry.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import CodeBlock from '@theme-original/CodeBlock';
import { 
  detectJupyterConfig, 
  getLabUrl, 
  type JupyterConfig 
} from '../../config/jupyter';

// Extend Window interface for Thebe
declare global {
  interface Window {
    thebe?: {
      bootstrap: () => Promise<void>;
      renderAllElements: () => Promise<void>;
      events?: {
        on: (event: string, callback: () => void) => void;
      };
    };
    thebeConfig?: {
      bootstrap: boolean;
      requestKernel: boolean;
      kernelOptions: {
        name: string;
        serverSettings: {
          baseUrl: string;
          wsUrl: string;
          token: string;
        };
      };
      binderOptions?: {
        repo: string;
      };
    };
  }
}

type ExecutionMode = 'read' | 'thebe';
type ThebeStatus = 'idle' | 'connecting' | 'ready' | 'error';

interface ExecutableCodeProps {
  children: string;
  language?: string;
  notebookPath?: string;
  title?: string;
  showLineNumbers?: boolean;
}

export default function ExecutableCode({
  children,
  language = 'python',
  notebookPath,
  title,
  showLineNumbers = true,
}: ExecutableCodeProps): JSX.Element {
  const [mode, setMode] = useState<ExecutionMode>('read');
  const [thebeStatus, setThebeStatus] = useState<ThebeStatus>('idle');
  const [output, setOutput] = useState<string | null>(null);
  const [jupyterConfig, setJupyterConfig] = useState<JupyterConfig | null>(null);
  const codeRef = useRef<HTMLDivElement>(null);
  const thebeInitialized = useRef(false);

  // Detect Jupyter configuration on mount
  useEffect(() => {
    setJupyterConfig(detectJupyterConfig());
  }, []);

  // Only show execution options for Python code
  const isExecutable = language === 'python' && jupyterConfig?.thebeEnabled;
  const canOpenLab = jupyterConfig?.labEnabled && notebookPath;

  // Initialize Thebe configuration
  const initializeThebe = useCallback(async () => {
    if (!jupyterConfig || thebeInitialized.current) return;
    
    // Configure Thebe based on environment
    if (jupyterConfig.environment === 'github-pages' && jupyterConfig.binderUrl) {
      // Use Binder for GitHub Pages
      window.thebeConfig = {
        bootstrap: true,
        requestKernel: true,
        kernelOptions: {
          name: 'python3',
          serverSettings: {
            baseUrl: '',
            wsUrl: '',
            token: '',
          },
        },
        binderOptions: {
          repo: 'Qiskit/qiskit',
        },
      };
    } else if (jupyterConfig.baseUrl) {
      // Use local Jupyter server
      window.thebeConfig = {
        bootstrap: true,
        requestKernel: true,
        kernelOptions: {
          name: 'python3',
          serverSettings: {
            baseUrl: jupyterConfig.baseUrl,
            wsUrl: jupyterConfig.wsUrl,
            token: jupyterConfig.token,
          },
        },
      };
    }

    thebeInitialized.current = true;
  }, [jupyterConfig]);

  // Handle Run button click
  const handleRun = async () => {
    if (!window.thebe) {
      console.error('Thebe not loaded');
      setThebeStatus('error');
      return;
    }

    setMode('thebe');
    setThebeStatus('connecting');
    setOutput(null);

    try {
      await initializeThebe();
      
      // Bootstrap Thebe if needed
      await window.thebe.bootstrap();
      
      // Mark code cell as executable
      if (codeRef.current) {
        const preElement = codeRef.current.querySelector('pre');
        if (preElement) {
          preElement.setAttribute('data-executable', 'true');
          preElement.setAttribute('data-language', 'python');
        }
      }

      // Render and execute
      await window.thebe.renderAllElements();
      
      setThebeStatus('ready');
      
      // Capture output (Thebe will update the DOM)
      setTimeout(() => {
        if (codeRef.current) {
          const outputArea = codeRef.current.querySelector('.jp-OutputArea-output');
          if (outputArea) {
            setOutput(outputArea.innerHTML);
          }
        }
      }, 100);
      
    } catch (error) {
      console.error('Thebe execution error:', error);
      setThebeStatus('error');
      setOutput(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle Open in Lab button click
  const handleOpenLab = () => {
    if (!jupyterConfig || !notebookPath) return;
    
    const labUrl = getLabUrl(jupyterConfig, notebookPath);
    if (labUrl) {
      window.open(labUrl, '_blank', 'noopener,noreferrer');
    }
  };

  // Reset to read mode
  const handleReset = () => {
    setMode('read');
    setThebeStatus('idle');
    setOutput(null);
  };

  // Render status badge
  const renderStatusBadge = () => {
    if (thebeStatus === 'idle') return null;
    
    const statusClasses: Record<ThebeStatus, string> = {
      idle: '',
      connecting: 'thebe-status thebe-status--connecting',
      ready: 'thebe-status thebe-status--ready',
      error: 'thebe-status thebe-status--error',
    };
    
    const statusText: Record<ThebeStatus, string> = {
      idle: '',
      connecting: '⏳ Connecting...',
      ready: '✓ Ready',
      error: '✗ Error',
    };

    return (
      <span className={statusClasses[thebeStatus]}>
        {statusText[thebeStatus]}
      </span>
    );
  };

  return (
    <div className="executable-code">
      {/* Toolbar */}
      {(isExecutable || canOpenLab) && (
        <div className="executable-code__toolbar">
          <button
            className={`executable-code__button executable-code__button--read ${
              mode === 'read' ? 'executable-code__button--active' : ''
            }`}
            onClick={handleReset}
            title="View code (read-only)"
          >
            📖 Read
          </button>

          {isExecutable && (
            <button
              className={`executable-code__button executable-code__button--run ${
                mode === 'thebe' ? 'executable-code__button--active' : ''
              }`}
              onClick={handleRun}
              disabled={thebeStatus === 'connecting'}
              title={
                jupyterConfig?.environment === 'github-pages'
                  ? 'Execute via Binder (may take a moment to start)'
                  : 'Execute on local Jupyter server'
              }
            >
              {thebeStatus === 'connecting' ? '⏳ Running...' : '▶️ Run'}
            </button>
          )}

          {canOpenLab && (
            <button
              className="executable-code__button executable-code__button--lab"
              onClick={handleOpenLab}
              title="Open full notebook in JupyterLab"
            >
              🔬 Open in Lab
            </button>
          )}

          {renderStatusBadge()}
        </div>
      )}

      {/* Title (optional) */}
      {title && (
        <div className="executable-code__title">
          {title}
        </div>
      )}

      {/* Code block */}
      <div
        ref={codeRef}
        className="executable-code__code"
        data-mode={mode}
      >
        <CodeBlock
          language={language}
          showLineNumbers={showLineNumbers}
        >
          {children}
        </CodeBlock>
      </div>

      {/* Output area */}
      {output && (
        <div className="executable-code__output">
          <div className="executable-code__output-header">
            Output
          </div>
          <pre 
            className="executable-code__output-content"
            dangerouslySetInnerHTML={{ __html: output }}
          />
        </div>
      )}
    </div>
  );
}
