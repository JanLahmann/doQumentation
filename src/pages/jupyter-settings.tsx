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
  getIBMQuantumToken,
  getIBMQuantumCRN,
  getCredentialDaysRemaining,
  saveIBMQuantumCredentials,
  clearIBMQuantumCredentials,
  getSimulatorMode,
  setSimulatorMode,
  getSimulatorBackend,
  setSimulatorBackend,
  getFakeDevice,
  setFakeDevice,
  getCachedFakeBackends,
  getActiveMode,
  setActiveMode,
  type JupyterConfig,
  type SimulatorBackend,
  type ActiveMode,
} from '../config/jupyter';
import {
  getProgressStats,
  clearVisitedByPrefix,
  clearExecutedByPrefix,
  clearAllVisited,
  clearAllExecuted,
  clearAllPreferences,
  type ProgressStats,
} from '../config/preferences';

const FALLBACK_BACKENDS = [
  { name: 'FakeManilaV2', qubits: 5 },
  { name: 'FakeBelemV2', qubits: 5 },
  { name: 'FakeMelbourneV2', qubits: 14 },
  { name: 'FakeTorontoV2', qubits: 27 },
  { name: 'FakeSherbrooke', qubits: 127 },
  { name: 'FakeBrisbane', qubits: 127 },
  { name: 'FakeKyoto', qubits: 127 },
  { name: 'FakeWashingtonV2', qubits: 127 },
];

export default function JupyterSettings(): JSX.Element {
  const [config, setConfig] = useState<JupyterConfig | null>(null);
  const [customUrl, setCustomUrl] = useState('');
  const [customToken, setCustomToken] = useState('');
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // IBM Quantum credentials state
  const [ibmToken, setIbmToken] = useState('');
  const [ibmCrn, setIbmCrn] = useState('');
  const [ibmDaysRemaining, setIbmDaysRemaining] = useState(-1);
  const [ibmExpiredNotice, setIbmExpiredNotice] = useState(false);
  const [ibmSaveResult, setIbmSaveResult] = useState<string | null>(null);

  // Learning progress state
  const [progressStats, setProgressStats] = useState<ProgressStats | null>(null);

  // Simulator mode state
  const [simEnabled, setSimEnabled] = useState(false);
  const [simBackend, setSimBackend] = useState<SimulatorBackend>('aer');
  const [fakeDevice, setFakeDeviceState] = useState('FakeSherbrooke');
  const [fakeBackends, setFakeBackends] = useState(FALLBACK_BACKENDS);
  const [activeMode, setActiveModeState] = useState<ActiveMode | null>(null);

  // Load current config on mount
  useEffect(() => {
    const currentConfig = detectJupyterConfig();
    setConfig(currentConfig);

    if (currentConfig.environment === 'custom') {
      setCustomUrl(currentConfig.baseUrl);
      setCustomToken(currentConfig.token);
    }

    // Load IBM credentials state
    const days = getCredentialDaysRemaining();
    if (days === -1 && getIBMQuantumToken() === '') {
      // Check if credentials were just expired (token gone but we had them)
      // We detect this by checking if days is -1 but there was a saved_at that got cleared
      // Actually: if token is empty AND days is -1, it could be expired or never set.
      // We'll show expired notice only if localStorage still has a stale saved_at
    }
    setIbmDaysRemaining(days);
    const savedToken = getIBMQuantumToken();
    if (savedToken) {
      setIbmToken(savedToken);
      setIbmCrn(getIBMQuantumCRN());
    }

    // Load simulator mode state
    setSimEnabled(getSimulatorMode());
    setSimBackend(getSimulatorBackend());
    setFakeDeviceState(getFakeDevice());
    setActiveModeState(getActiveMode());

    // Load cached fake backends
    const cached = getCachedFakeBackends();
    if (cached && cached.length > 0) {
      setFakeBackends(cached);
    }

    // Load learning progress
    setProgressStats(getProgressStats());
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

  // IBM Quantum credential handlers
  const handleIbmSave = () => {
    if (!ibmToken) return;
    saveIBMQuantumCredentials(ibmToken, ibmCrn);
    setIbmDaysRemaining(7);
    setIbmSaveResult('Credentials saved! They will be auto-injected when the kernel starts.');
    setIbmExpiredNotice(false);
  };

  const handleIbmDelete = () => {
    clearIBMQuantumCredentials();
    setIbmToken('');
    setIbmCrn('');
    setIbmDaysRemaining(-1);
    setIbmSaveResult('Credentials deleted.');
    setActiveModeState(null);
    setActiveMode(null);
  };

  // Simulator mode handlers
  const handleSimToggle = () => {
    const newVal = !simEnabled;
    setSimEnabled(newVal);
    setSimulatorMode(newVal);
  };

  const handleSimBackendChange = (value: SimulatorBackend) => {
    setSimBackend(value);
    setSimulatorBackend(value);
  };

  const handleFakeDeviceChange = (name: string) => {
    setFakeDeviceState(name);
    setFakeDevice(name);
  };

  const handleActiveModeChange = (mode: ActiveMode) => {
    setActiveModeState(mode);
    setActiveMode(mode);
  };

  // Group fake backends by qubit count for <optgroup>
  const backendsByQubits = new Map<number, Array<{name: string; qubits: number}>>();
  for (const b of fakeBackends) {
    if (!backendsByQubits.has(b.qubits)) {
      backendsByQubits.set(b.qubits, []);
    }
    backendsByQubits.get(b.qubits)!.push(b);
  }
  const sortedQubitGroups = Array.from(backendsByQubits.entries()).sort((a, b) => a[0] - b[0]);

  const hasBothConfigured = simEnabled && ibmDaysRemaining >= 0;

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

          {/* IBM Quantum Account */}
          <h2 id="ibm-quantum">IBM Quantum Account</h2>

          <p>
            Enter your IBM Quantum credentials once here. They will be
            auto-injected via <code>save_account()</code> when the kernel starts,
            so you don't need to enter them in every notebook.
          </p>

          <ol>
            <li><strong>Register</strong> at{' '}
              <a href="https://quantum.cloud.ibm.com/registration" target="_blank" rel="noopener noreferrer">
                quantum.cloud.ibm.com/registration
              </a>
              {' '}— no credit card required for the first 30 days
            </li>
            <li><strong>Sign in</strong> at{' '}
              <a href="https://quantum.cloud.ibm.com" target="_blank" rel="noopener noreferrer">
                quantum.cloud.ibm.com
              </a>
            </li>
            <li><strong>Instance</strong> — Create a free Open Plan instance at{' '}
              <a href="https://quantum.cloud.ibm.com/instances" target="_blank" rel="noopener noreferrer">
                Instances
              </a>
              {' '}if you don't have one yet
            </li>
            <li><strong>API Token</strong> — Click your profile icon (top right), then "API token". Copy the key.</li>
            <li><strong>CRN</strong> — Copy the CRN string from your{' '}
              <a href="https://quantum.cloud.ibm.com/instances" target="_blank" rel="noopener noreferrer">
                Instances
              </a>
              {' '}page
            </li>
          </ol>

          <p>
            For detailed steps, see IBM's{' '}
            <a href="https://quantum.cloud.ibm.com/docs/en/guides/hello-world#install-and-authenticate" target="_blank" rel="noopener noreferrer">
              Set up authentication
            </a>{' '}
            guide (step 2).
          </p>

          {ibmExpiredNotice && (
            <div className="alert alert--warning margin-bottom--md">
              Your IBM Quantum credentials have expired and were deleted.
              Please re-enter them below.
            </div>
          )}

          {ibmDaysRemaining >= 0 && (
            <div className="alert alert--info margin-bottom--md">
              Credentials expire in <strong>{ibmDaysRemaining} day{ibmDaysRemaining !== 1 ? 's' : ''}</strong>.
              They are stored in your browser only and auto-deleted after 7 days.
            </div>
          )}

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="ibm-token">
              API Token
            </label>
            <input
              id="ibm-token"
              type="password"
              className="jupyter-settings__input"
              placeholder="44-character API key"
              value={ibmToken}
              onChange={(e) => setIbmToken(e.target.value)}
            />
          </div>

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="ibm-crn">
              Cloud Resource Name (CRN) / Instance
            </label>
            <input
              id="ibm-crn"
              type="text"
              className="jupyter-settings__input"
              placeholder="crn:v1:bluemix:public:quantum-computing:..."
              value={ibmCrn}
              onChange={(e) => setIbmCrn(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleIbmSave}
              disabled={!ibmToken}
            >
              Save Credentials
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleIbmDelete}
            >
              Delete Credentials
            </button>
          </div>

          {ibmSaveResult && (
            <div className="alert alert--success margin-top--md">
              {ibmSaveResult}
            </div>
          )}

          {/* Simulator Mode */}
          <h2 id="simulator-mode" style={{ marginTop: '2rem' }}>Simulator Mode</h2>

          <p>
            Enable to run notebooks without an IBM Quantum account.
            All <code>QiskitRuntimeService</code> calls are redirected to a local
            simulator. No cell modifications needed.
          </p>

          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
            Transpiled circuits and backend-specific results will differ from real hardware
            when using simulator mode. Static expected outputs shown on pages reflect real IBM backends.
          </p>

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__toggle">
              <input
                type="checkbox"
                checked={simEnabled}
                onChange={handleSimToggle}
              />
              <span className="jupyter-settings__toggle-track">
                <span className="jupyter-settings__toggle-thumb" />
              </span>
              <span style={{ marginLeft: '0.5rem' }}>
                {simEnabled ? 'Simulator mode enabled' : 'Simulator mode disabled'}
              </span>
            </label>
          </div>

          {simEnabled && (
            <>
              <div className="jupyter-settings__field">
                <label className="jupyter-settings__label">Backend</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="radio"
                      name="sim-backend"
                      value="aer"
                      checked={simBackend === 'aer'}
                      onChange={() => handleSimBackendChange('aer')}
                    />
                    <span>
                      <strong>AerSimulator</strong> — Ideal simulation, no noise. Fast, works for all circuits.
                    </span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="radio"
                      name="sim-backend"
                      value="fake"
                      checked={simBackend === 'fake'}
                      onChange={() => handleSimBackendChange('fake')}
                    />
                    <span>
                      <strong>FakeBackend</strong> — Simulates real IBM device noise. More realistic but slower.
                    </span>
                  </label>
                </div>
              </div>

              {simBackend === 'fake' && (
                <div className="jupyter-settings__field">
                  <label className="jupyter-settings__label" htmlFor="fake-device">
                    Device
                  </label>
                  <select
                    id="fake-device"
                    className="jupyter-settings__input"
                    value={fakeDevice}
                    onChange={(e) => handleFakeDeviceChange(e.target.value)}
                  >
                    {sortedQubitGroups.map(([qubits, backends]) => (
                      <optgroup key={qubits} label={`${qubits} qubits`}>
                        {backends.map((b) => (
                          <option key={b.name} value={b.name}>
                            {b.name}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
                    Device list is updated automatically when you run code.
                  </small>
                </div>
              )}

              <div className="alert alert--info margin-top--md">
                Changes take effect on the next kernel session. If code is running,
                click Back then Run to apply.
              </div>
            </>
          )}

          {/* Active mode selector when both are configured */}
          {hasBothConfigured && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}>Active Mode</h3>
              <p>
                You have both IBM credentials and simulator mode configured.
                Choose which to use when the kernel starts:
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="radio"
                    name="active-mode"
                    value="credentials"
                    checked={activeMode === 'credentials'}
                    onChange={() => handleActiveModeChange('credentials')}
                  />
                  <span>Use IBM credentials (connect to real hardware)</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="radio"
                    name="active-mode"
                    value="simulator"
                    checked={activeMode === 'simulator'}
                    onChange={() => handleActiveModeChange('simulator')}
                  />
                  <span>Use simulator (no real hardware access)</span>
                </label>
              </div>
              {!activeMode && (
                <div className="alert alert--warning margin-top--md">
                  Please select an active mode. Without a selection, simulator
                  mode will be used by default and a reminder banner will appear.
                </div>
              )}
            </>
          )}

          {/* Learning Progress */}
          <h2 id="learning-progress" style={{ marginTop: '2rem' }}>Learning Progress</h2>

          <p>
            Your reading and execution progress is tracked locally in your browser.
            Visited pages show a <strong>&#10003;</strong> in the sidebar; executed notebooks show a <strong>&#9654;</strong>.
          </p>

          {progressStats && (progressStats.visitedCount > 0 || progressStats.executedCount > 0) ? (
            <>
              <div className="dq-progress-stats">
                <div className="dq-progress-stat">
                  <span className="dq-progress-stat__number">{progressStats.visitedCount}</span>
                  <span className="dq-progress-stat__label">Pages visited</span>
                </div>
                <div className="dq-progress-stat">
                  <span className="dq-progress-stat__number">{progressStats.executedCount}</span>
                  <span className="dq-progress-stat__label">Notebooks executed</span>
                </div>
                {Object.entries(progressStats.visitedByCategory).map(([cat, count]) => (
                  <div className="dq-progress-stat" key={cat}>
                    <span className="dq-progress-stat__number">{count}</span>
                    <span className="dq-progress-stat__label">{cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
                  </div>
                ))}
              </div>

              <h3>Clear Progress</h3>
              <div className="dq-clear-buttons">
                {Object.keys(progressStats.visitedByCategory).map((cat) => (
                  <button
                    key={cat}
                    className="jupyter-settings__button jupyter-settings__button--secondary"
                    onClick={() => {
                      const prefix = cat === 'courses' ? '/learning/courses'
                        : cat === 'modules' ? '/learning/modules'
                        : `/${cat}`;
                      clearVisitedByPrefix(prefix);
                      clearExecutedByPrefix(prefix);
                      setProgressStats(getProgressStats());
                    }}
                  >
                    Clear {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </button>
                ))}
                <button
                  className="jupyter-settings__button jupyter-settings__button--secondary"
                  onClick={() => {
                    clearAllVisited();
                    clearAllExecuted();
                    setProgressStats(getProgressStats());
                  }}
                >
                  Clear All Progress
                </button>
                <button
                  className="jupyter-settings__button jupyter-settings__button--secondary"
                  onClick={() => {
                    clearAllPreferences();
                    setProgressStats(getProgressStats());
                  }}
                >
                  Clear All Preferences
                </button>
              </div>
            </>
          ) : (
            <div className="alert alert--info margin-bottom--md">
              No progress tracked yet. Visit tutorials and guides to start tracking.
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

          {/* Advanced: Custom Jupyter Server */}
          <h2 id="advanced" style={{ marginTop: '2rem' }}>Advanced</h2>

          <h3>Custom Jupyter Server</h3>

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

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleTest}
              disabled={!customUrl || isTesting}
            >
              {isTesting ? 'Testing...' : 'Test Connection'}
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleSave}
              disabled={!customUrl}
            >
              Save Settings
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleUseDefault}
            >
              Use Default
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleClear}
            >
              Clear Custom
            </button>
          </div>

          {testResult && (
            <div
              className={`alert margin-top--md ${
                testResult.success ? 'alert--success' : 'alert--danger'
              }`}
            >
              {testResult.message}
            </div>
          )}

          {/* Setup Help */}
          <h3 style={{ marginTop: '2rem' }}>Setup Help</h3>
          
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
