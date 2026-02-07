/**
 * Jupyter Settings Page
 * 
 * Allows users to configure a custom Jupyter server for code execution.
 * Useful for:
 * - Connecting to a remote Jupyter server
 * - Using a different port
 * - Providing authentication tokens
 */

import React, { useState, useEffect } from 'react';
import Layout from '@theme/Layout';
import {
  detectJupyterConfig,
  saveJupyterConfig,
  clearJupyterConfig,
  testJupyterConnection,
  type JupyterConfig,
} from '../config/jupyter';

export default function JupyterSettings(): JSX.Element {
  const [config, setConfig] = useState<JupyterConfig | null>(null);
  const [customUrl, setCustomUrl] = useState('');
  const [customToken, setCustomToken] = useState('');
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Load current config on mount
  useEffect(() => {
    const currentConfig = detectJupyterConfig();
    setConfig(currentConfig);
    
    if (currentConfig.environment === 'custom') {
      setCustomUrl(currentConfig.baseUrl);
      setCustomToken(currentConfig.token);
    }
  }, []);

  const handleTest = async () => {
    if (!customUrl) return;
    
    setIsTesting(true);
    setTestResult(null);
    
    const result = await testJupyterConnection(customUrl, customToken);
    setTestResult(result);
    setIsTesting(false);
  };

  const handleSave = () => {
    saveJupyterConfig(customUrl, customToken);
    setConfig(detectJupyterConfig());
    setTestResult({
      success: true,
      message: 'Settings saved! Refresh the page to apply.',
    });
  };

  const handleClear = () => {
    clearJupyterConfig();
    setCustomUrl('');
    setCustomToken('');
    setConfig(detectJupyterConfig());
    setTestResult({
      success: true,
      message: 'Custom settings cleared. Using auto-detected configuration.',
    });
  };

  const handleUseDefault = () => {
    if (config?.environment === 'rasqberry') {
      setCustomUrl(config.baseUrl);
      setCustomToken(config.token);
    } else {
      setCustomUrl('http://localhost:8888');
      setCustomToken('rasqberry');
    }
  };

  return (
    <Layout
      title="Jupyter Settings"
      description="Configure Jupyter server for code execution"
    >
      <main className="container margin-vert--lg">
        <div className="jupyter-settings">
          <h1>⚙️ Jupyter Settings</h1>
          
          <p>
            Configure the Jupyter server used for executing Python code in tutorials.
          </p>

          {/* Current Environment Status */}
          <div className="alert alert--info margin-bottom--md">
            <strong>Current Environment:</strong>{' '}
            {config?.environment === 'github-pages' && (
              <>
                GitHub Pages - Code execution uses{' '}
                <a href="https://mybinder.org" target="_blank" rel="noopener noreferrer">
                  Binder
                </a>{' '}
                (may take a moment to start)
              </>
            )}
            {config?.environment === 'rasqberry' && (
              <>
                RasQberry / Local - Connected to {config.baseUrl}
              </>
            )}
            {config?.environment === 'custom' && (
              <>
                Custom Server - {config.baseUrl}
              </>
            )}
            {config?.environment === 'unknown' && (
              <>
                Unknown - Code execution disabled
              </>
            )}
          </div>

          {/* Custom Server Configuration */}
          <h2>Custom Jupyter Server</h2>
          
          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="jupyter-url">
              Jupyter Server URL
            </label>
            <input
              id="jupyter-url"
              type="url"
              className="jupyter-settings__input"
              placeholder="http://localhost:8888"
              value={customUrl}
              onChange={(e) => setCustomUrl(e.target.value)}
            />
            <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
              The base URL of your Jupyter server (e.g., http://localhost:8888)
            </small>
          </div>

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="jupyter-token">
              Authentication Token
            </label>
            <input
              id="jupyter-token"
              type="password"
              className="jupyter-settings__input"
              placeholder="(optional)"
              value={customToken}
              onChange={(e) => setCustomToken(e.target.value)}
            />
            <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
              Token from jupyter server --generate-config or displayed at startup
            </small>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleTest}
              disabled={!customUrl || isTesting}
            >
              {isTesting ? 'Testing...' : '🔌 Test Connection'}
            </button>
            
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleSave}
              disabled={!customUrl}
            >
              💾 Save Settings
            </button>
            
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleUseDefault}
            >
              📍 Use Default
            </button>
            
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleClear}
            >
              🗑️ Clear Custom
            </button>
          </div>

          {/* Test Result */}
          {testResult && (
            <div
              className={`alert margin-top--md ${
                testResult.success ? 'alert--success' : 'alert--danger'
              }`}
            >
              {testResult.message}
            </div>
          )}

          {/* Binder Packages */}
          <h2 id="binder-packages" style={{ marginTop: '2rem' }}>Binder Packages</h2>

          <p>
            When running on GitHub Pages, code executes via{' '}
            <a href="https://mybinder.org" target="_blank" rel="noopener noreferrer">MyBinder</a>.
            The Binder environment includes core Qiskit packages pre-installed:
          </p>
          <pre>
            <code>{`qiskit[visualization], qiskit-aer,
qiskit-ibm-runtime, pylatexenc`}</code>
          </pre>

          <p>
            Most notebooks require additional packages. You can install them
            on demand by running this in a code cell:
          </p>
          <pre>
            <code>{`!pip install -q <package>`}</code>
          </pre>

          <p>Or install all optional packages at once:</p>
          <pre>
            <code>{`!pip install -q scipy scikit-learn qiskit-ibm-transpiler \\
  qiskit-experiments plotly sympy qiskit-serverless \\
  qiskit-ibm-catalog qiskit-addon-sqd qiskit-addon-utils \\
  qiskit-addon-mpf qiskit-addon-aqc-tensor[aer,quimb-jax] \\
  qiskit-addon-obp qiskit-addon-cutting pyscf ffsim \\
  gem-suite python-sat`}</code>
          </pre>

          {/* Help Section */}
          <h2 style={{ marginTop: '2rem' }}>Setup Help</h2>
          
          <h3>RasQberry Setup</h3>
          <p>
            If you're running on a RasQberry Pi, the Jupyter server should be
            automatically detected. If not, ensure the jupyter-tutorials service is running:
          </p>
          <pre>
            <code>sudo systemctl status jupyter-tutorials</code>
          </pre>

          <h3>Local Jupyter Setup</h3>
          <p>Start a Jupyter server with CORS enabled:</p>
          <pre>
            <code>{`jupyter server --ServerApp.token='rasqberry' \\
  --ServerApp.allow_origin='*' \\
  --ServerApp.disable_check_xsrf=True`}</code>
          </pre>

          <h3>Remote Server</h3>
          <p>
            For remote servers, ensure CORS is configured to allow connections from this site.
            Add the following to your <code>jupyter_server_config.py</code>:
          </p>
          <pre>
            <code>{`c.ServerApp.allow_origin = '*'
c.ServerApp.allow_credentials = True`}</code>
          </pre>
        </div>
      </main>
    </Layout>
  );
}
