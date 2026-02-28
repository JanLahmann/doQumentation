/**
 * doQumentation Settings Page
 *
 * Allows users to configure a custom Jupyter server for code execution.
 * Useful for:
 * - Connecting to a remote Jupyter server
 * - Using a different port
 * - Providing authentication tokens
 */

import React, { useState, useEffect } from 'react';
import Layout from '@theme/Layout';
import Translate, {translate} from '@docusaurus/Translate';
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
  getCredentialTTLDays,
  setCredentialTTLDays,
  getSuppressWarnings,
  setSuppressWarnings,
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
  getCodeFontSize,
  setCodeFontSize,
  getHideStaticOutputs,
  setHideStaticOutputs,
  getBookmarks,
  clearAllBookmarks,
  resetOnboarding,
  clearRecentPages,
  clearSidebarCollapseStates,
  type ProgressStats,
} from '../config/preferences';
import { DISPLAY_PREFS_EVENT } from '../clientModules/displayPrefs';

const FALLBACK_BACKENDS = [
  // 1 qubit
  { name: 'FakeArmonkV2', qubits: 1 },
  // 5 qubits
  { name: 'FakeAthensV2', qubits: 5 },
  { name: 'FakeBelemV2', qubits: 5 },
  { name: 'FakeBogotaV2', qubits: 5 },
  { name: 'FakeBurlingtonV2', qubits: 5 },
  { name: 'FakeEssexV2', qubits: 5 },
  { name: 'FakeFractionalBackend', qubits: 5 },
  { name: 'FakeLimaV2', qubits: 5 },
  { name: 'FakeLondonV2', qubits: 5 },
  { name: 'FakeManilaV2', qubits: 5 },
  { name: 'FakeOurenseV2', qubits: 5 },
  { name: 'FakeQuitoV2', qubits: 5 },
  { name: 'FakeRomeV2', qubits: 5 },
  { name: 'FakeSantiagoV2', qubits: 5 },
  { name: 'FakeValenciaV2', qubits: 5 },
  { name: 'FakeVigoV2', qubits: 5 },
  { name: 'FakeYorktownV2', qubits: 5 },
  // 7 qubits
  { name: 'FakeCasablancaV2', qubits: 7 },
  { name: 'FakeJakartaV2', qubits: 7 },
  { name: 'FakeLagosV2', qubits: 7 },
  { name: 'FakeNairobiV2', qubits: 7 },
  { name: 'FakeOslo', qubits: 7 },
  { name: 'FakePerth', qubits: 7 },
  // 14–16 qubits
  { name: 'FakeMelbourneV2', qubits: 14 },
  { name: 'FakeGuadalupeV2', qubits: 16 },
  // 20 qubits
  { name: 'FakeAlmadenV2', qubits: 20 },
  { name: 'FakeBoeblingenV2', qubits: 20 },
  { name: 'FakeJohannesburgV2', qubits: 20 },
  { name: 'FakePoughkeepsieV2', qubits: 20 },
  { name: 'FakeSingaporeV2', qubits: 20 },
  // 27 qubits
  { name: 'FakeAlgiers', qubits: 27 },
  { name: 'FakeAuckland', qubits: 27 },
  { name: 'FakeCairoV2', qubits: 27 },
  { name: 'FakeGeneva', qubits: 27 },
  { name: 'FakeHanoiV2', qubits: 27 },
  { name: 'FakeKolkataV2', qubits: 27 },
  { name: 'FakeMontrealV2', qubits: 27 },
  { name: 'FakeMumbaiV2', qubits: 27 },
  { name: 'FakeParisV2', qubits: 27 },
  { name: 'FakePeekskill', qubits: 27 },
  { name: 'FakeSydneyV2', qubits: 27 },
  { name: 'FakeTorontoV2', qubits: 27 },
  // 28 qubits
  { name: 'FakeCambridgeV2', qubits: 28 },
  // 33 qubits
  { name: 'FakePrague', qubits: 33 },
  // 53–65 qubits
  { name: 'FakeRochesterV2', qubits: 53 },
  { name: 'FakeBrooklynV2', qubits: 65 },
  { name: 'FakeManhattanV2', qubits: 65 },
  // 127 qubits
  { name: 'FakeBrisbane', qubits: 127 },
  { name: 'FakeCusco', qubits: 127 },
  { name: 'FakeKawasaki', qubits: 127 },
  { name: 'FakeKyiv', qubits: 127 },
  { name: 'FakeKyoto', qubits: 127 },
  { name: 'FakeQuebec', qubits: 127 },
  { name: 'FakeSherbrooke', qubits: 127 },
  { name: 'FakeWashingtonV2', qubits: 127 },
  // 133–156 qubits
  { name: 'FakeTorino', qubits: 133 },
  { name: 'FakeFez', qubits: 156 },
  { name: 'FakeMarrakesh', qubits: 156 },
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

  // Display preferences state
  const [fontSize, setFontSize] = useState(14);
  const [hideOutputs, setHideOutputs] = useState(false);
  const [suppressWarnings, setSuppressWarningsState] = useState(true);
  const [bookmarkCount, setBookmarkCount] = useState(0);

  // Simulator mode state
  const [simEnabled, setSimEnabled] = useState(false);
  const [simBackend, setSimBackend] = useState<SimulatorBackend>('aer');
  const [fakeDevice, setFakeDeviceState] = useState('FakeSherbrooke');
  const [fakeBackends, setFakeBackends] = useState(FALLBACK_BACKENDS);
  const [activeMode, setActiveModeState] = useState<ActiveMode | null>(null);
  const [ttlDays, setTtlDaysState] = useState(7);

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
    setTtlDaysState(getCredentialTTLDays());

    // Load cached fake backends
    const cached = getCachedFakeBackends();
    if (cached && cached.length > 0) {
      setFakeBackends(cached);
    }

    // Load learning progress
    setProgressStats(getProgressStats());

    // Load display preferences
    setFontSize(getCodeFontSize());
    setHideOutputs(getHideStaticOutputs());
    setSuppressWarningsState(getSuppressWarnings());
    setBookmarkCount(getBookmarks().length);
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
      message: translate({id: 'settings.advanced.saveSuccess', message: 'Settings saved! Refresh the page to apply.'}),
    });
  };

  const handleClear = () => {
    clearJupyterConfig();
    setCustomUrl('');
    setCustomToken('');
    setConfig(detectJupyterConfig());
    setTestResult({
      success: true,
      message: translate({id: 'settings.advanced.clearSuccess', message: 'Custom settings cleared. Using auto-detected configuration.'}),
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
    setIbmDaysRemaining(ttlDays);
    setIbmSaveResult(translate({id: 'settings.ibm.saveSuccess', message: 'Credentials saved! They will be auto-injected when the kernel starts.'}));
    setIbmExpiredNotice(false);
  };

  const handleIbmDelete = () => {
    clearIBMQuantumCredentials();
    setIbmToken('');
    setIbmCrn('');
    setIbmDaysRemaining(-1);
    setIbmSaveResult(translate({id: 'settings.ibm.deleteSuccess', message: 'Credentials deleted.'}));
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
      title={translate({id: 'settings.title', message: 'doQumentation Settings'})}
      description={translate({id: 'settings.description', message: 'Configure Jupyter server for code execution'})}
    >
      <main className="container margin-vert--lg">
        <div className="jupyter-settings">
          <h1><Translate id="settings.heading">⚙️ doQumentation Settings</Translate></h1>

          <p>
            <Translate id="settings.intro">
              Configure the Jupyter server used for executing Python code in tutorials.
            </Translate>
          </p>

          {/* Current Environment Status */}
          <div className="alert alert--info margin-bottom--md">
            <strong><Translate id="settings.env.label">Current Environment:</Translate></strong>{' '}
            {config?.environment === 'github-pages' && (
              <Translate
                id="settings.env.githubPages"
                values={{binder: <a href="https://mybinder.org" target="_blank" rel="noopener noreferrer">Binder</a>}}
              >
                {'GitHub Pages - Code execution uses {binder} (may take a moment to start)'}
              </Translate>
            )}
            {config?.environment === 'rasqberry' && (
              <Translate
                id="settings.env.rasqberry"
                values={{url: config.baseUrl}}
              >
                {'RasQberry / Local - Connected to {url}'}
              </Translate>
            )}
            {config?.environment === 'custom' && (
              <Translate
                id="settings.env.custom"
                values={{url: config.baseUrl}}
              >
                {'Custom Server - {url}'}
              </Translate>
            )}
            {config?.environment === 'unknown' && (
              <Translate id="settings.env.unknown">
                Unknown - Code execution disabled
              </Translate>
            )}
          </div>

          {/* IBM Quantum Account */}
          <h2 id="ibm-quantum"><Translate id="settings.ibm.heading">IBM Quantum Account</Translate></h2>

          <div className="alert alert--warning margin-bottom--md">
            <Translate
              id="settings.ibm.securityNote"
              values={{
                strong: <strong>{translate({id: 'settings.ibm.securityNoteLabel', message: 'Security note:'})}</strong>,
                saveAccount: <code>save_account()</code>,
              }}
            >
              {'{strong} Credentials are stored in your browser\'s localStorage in plain text. They are not encrypted and can be read by browser extensions or anyone with access to this device. Use the expiry setting below to limit exposure, and delete credentials when you\'re done. For shared or public computers, prefer the manual {saveAccount} method described below instead.'}
            </Translate>
          </div>

          <p>
            <Translate
              id="settings.ibm.autoInjectDesc"
              values={{
                saveAccount: <code>save_account()</code>,
              }}
            >
              {'Enter your IBM Quantum credentials once here. They will be auto-injected via {saveAccount} when the kernel starts, so you don\'t need to enter them in every notebook. This applies to embedded code execution on this site only — opening a notebook in JupyterLab requires calling {saveAccount} manually.'}
            </Translate>
          </p>

          <ol>
            <li>
              <Translate
                id="settings.ibm.step1"
                values={{
                  strong: <strong><Translate id="settings.ibm.step1.label">Register</Translate></strong>,
                  link: <a href="https://quantum.cloud.ibm.com/registration" target="_blank" rel="noopener noreferrer">quantum.cloud.ibm.com/registration</a>,
                }}
              >
                {'{strong} at {link} — no credit card required for the first 30 days'}
              </Translate>
            </li>
            <li>
              <Translate
                id="settings.ibm.step2"
                values={{
                  strong: <strong><Translate id="settings.ibm.step2.label">Sign in</Translate></strong>,
                  link: <a href="https://quantum.cloud.ibm.com" target="_blank" rel="noopener noreferrer">quantum.cloud.ibm.com</a>,
                }}
              >
                {'{strong} at {link}'}
              </Translate>
            </li>
            <li>
              <Translate
                id="settings.ibm.step3"
                values={{
                  strong: <strong><Translate id="settings.ibm.step3.label">Instance</Translate></strong>,
                  link: <a href="https://quantum.cloud.ibm.com/instances" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.step3.instances">Instances</Translate></a>,
                }}
              >
                {'{strong} — Create a free Open Plan instance at {link} if you don\'t have one yet'}
              </Translate>
            </li>
            <li>
              <Translate
                id="settings.ibm.step4"
                values={{
                  strong: <strong><Translate id="settings.ibm.step4.label">API Token</Translate></strong>,
                }}
              >
                {'{strong} — Click your profile icon (top right), then "API token". Copy the key.'}
              </Translate>
            </li>
            <li>
              <Translate
                id="settings.ibm.step5"
                values={{
                  strong: <strong>CRN</strong>,
                  link: <a href="https://quantum.cloud.ibm.com/instances" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.step5.instances">Instances</Translate></a>,
                }}
              >
                {'{strong} — Copy the CRN string from your {link} page'}
              </Translate>
            </li>
          </ol>

          <p>
            <Translate
              id="settings.ibm.guideLink"
              values={{
                link: <a href="https://quantum.cloud.ibm.com/docs/en/guides/hello-world#install-and-authenticate" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.guideLink.text">Set up authentication</Translate></a>,
              }}
            >
              {'For detailed steps, see IBM\'s {link} guide (step 2).'}
            </Translate>
          </p>

          {ibmExpiredNotice && (
            <div className="alert alert--warning margin-bottom--md">
              <Translate id="settings.ibm.expiredNotice">
                Your IBM Quantum credentials have expired and were deleted.
                Please re-enter them below.
              </Translate>
            </div>
          )}

          {ibmDaysRemaining >= 0 && (
            <div className="alert alert--info margin-bottom--md" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
              <span>
                <Translate
                  id="settings.ibm.expiryNotice"
                  values={{days: <strong>{ibmDaysRemaining} {ibmDaysRemaining !== 1 ? translate({id: 'settings.ibm.days', message: 'days'}) : translate({id: 'settings.ibm.day', message: 'day'})}</strong>}}
                >
                  {'Credentials expire in {days}.'}
                </Translate>
              </span>
              <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Translate id="settings.ibm.autoDelete">Auto-delete after:</Translate>{' '}
                <select
                  value={ttlDays}
                  onChange={(e) => {
                    const days = Number(e.target.value);
                    setTtlDaysState(days);
                    setCredentialTTLDays(days);
                    setIbmDaysRemaining(getCredentialDaysRemaining());
                  }}
                  style={{
                    padding: '0.15rem 0.3rem',
                    borderRadius: '4px',
                    border: '1px solid var(--ifm-color-emphasis-300)',
                    background: 'var(--ifm-background-color)',
                    fontSize: '0.85rem',
                  }}
                >
                  <option value={1}>{translate({id: 'settings.ibm.ttl.1day', message: '1 day'})}</option>
                  <option value={3}>{translate({id: 'settings.ibm.ttl.3days', message: '3 days'})}</option>
                  <option value={7}>{translate({id: 'settings.ibm.ttl.7days', message: '7 days'})}</option>
                </select>
              </span>
            </div>
          )}

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="ibm-token">
              <Translate id="settings.ibm.tokenLabel">API Token</Translate>
            </label>
            <input
              id="ibm-token"
              type="password"
              className="jupyter-settings__input"
              placeholder={translate({id: 'settings.ibm.tokenPlaceholder', message: '44-character API key'})}
              value={ibmToken}
              onChange={(e) => setIbmToken(e.target.value)}
            />
          </div>

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="ibm-crn">
              <Translate id="settings.ibm.crnLabel">Cloud Resource Name (CRN) / Instance</Translate>
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
              <Translate id="settings.ibm.saveBtn">Save Credentials</Translate>
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleIbmDelete}
            >
              <Translate id="settings.ibm.deleteBtn">Delete Credentials</Translate>
            </button>
          </div>

          {ibmSaveResult && (
            <div className="alert alert--success margin-top--md">
              {ibmSaveResult}
            </div>
          )}

          <details style={{ marginTop: '1rem' }}>
            <summary><strong><Translate id="settings.ibm.manualSummary">Alternative: Run save_account() manually in a notebook cell</Translate></strong></summary>
            <p style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
              <Translate id="settings.ibm.manualDesc">
                If you prefer not to store credentials in this browser, paste this into any
                code cell and run it. Credentials are saved in the Binder kernel's temporary
                storage and lost when the session ends.
              </Translate>
            </p>
            <pre><code>{`from qiskit_ibm_runtime import QiskitRuntimeService
QiskitRuntimeService.save_account(
    token="YOUR_API_TOKEN",
    instance="YOUR_CRN",
    overwrite=True
)`}</code></pre>
          </details>

          {/* Simulator Mode */}
          <h2 id="simulator-mode" style={{ marginTop: '2rem' }}><Translate id="settings.simulator.heading">Simulator Mode</Translate></h2>

          <p>
            <Translate
              id="settings.simulator.desc"
              values={{service: <code>QiskitRuntimeService</code>}}
            >
              {'Enable to run notebooks without an IBM Quantum account. All {service} calls are redirected to a local simulator. No cell modifications needed. This applies to embedded code execution on this site only — opening a notebook in JupyterLab uses the standard Qiskit runtime.'}
            </Translate>
          </p>

          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
            <Translate id="settings.simulator.caveat">
              Transpiled circuits and backend-specific results will differ from real hardware
              when using simulator mode. Static expected outputs shown on pages reflect real IBM backends.
            </Translate>
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
                {simEnabled
                  ? translate({id: 'settings.simulator.toggleOn', message: 'Simulator mode enabled'})
                  : translate({id: 'settings.simulator.toggleOff', message: 'Simulator mode disabled'})}
              </span>
            </label>
          </div>

          {simEnabled && (
            <>
              <div className="jupyter-settings__field">
                <label className="jupyter-settings__label"><Translate id="settings.simulator.backendLabel">Backend</Translate></label>
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
                      <strong>AerSimulator</strong> — <Translate id="settings.simulator.aerDesc">Ideal simulation, no noise. Fast, works for all circuits.</Translate>
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
                      <strong>FakeBackend</strong> — <Translate id="settings.simulator.fakeDesc">Simulates real IBM device noise. More realistic but slower.</Translate>
                    </span>
                  </label>
                </div>
              </div>

              {simBackend === 'fake' && (
                <div className="jupyter-settings__field">
                  <label className="jupyter-settings__label" htmlFor="fake-device">
                    <Translate id="settings.simulator.deviceLabel">Device</Translate>
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
                    <Translate id="settings.simulator.deviceHint">Device list is updated automatically when you run code.</Translate>
                  </small>
                </div>
              )}

              <div className="alert alert--info margin-top--md">
                <Translate id="settings.simulator.applyHint">
                  Changes take effect on the next kernel session. If code is running,
                  click Back then Run to apply.
                </Translate>
              </div>
            </>
          )}

          {/* Active mode selector when both are configured */}
          {hasBothConfigured && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}><Translate id="settings.activeMode.heading">Active Mode</Translate></h3>
              <p>
                <Translate id="settings.activeMode.desc">
                  You have both IBM credentials and simulator mode configured.
                  Choose which to use when the kernel starts:
                </Translate>
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
                  <span><Translate id="settings.activeMode.credentials">Use IBM credentials (connect to real hardware)</Translate></span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="radio"
                    name="active-mode"
                    value="simulator"
                    checked={activeMode === 'simulator'}
                    onChange={() => handleActiveModeChange('simulator')}
                  />
                  <span><Translate id="settings.activeMode.simulator">Use simulator (no real hardware access)</Translate></span>
                </label>
              </div>
              {!activeMode && (
                <div className="alert alert--warning margin-top--md">
                  <Translate id="settings.activeMode.warning">
                    Please select an active mode. Without a selection, simulator
                    mode will be used by default and a reminder banner will appear.
                  </Translate>
                </div>
              )}
            </>
          )}

          {/* Learning Progress */}
          <h2 id="learning-progress" style={{ marginTop: '2rem' }}><Translate id="settings.progress.heading">Learning Progress</Translate></h2>

          <p>
            <Translate
              id="settings.progress.desc"
              values={{
                check: <strong>&#10003;</strong>,
                play: <strong>&#9654;</strong>,
              }}
            >
              {'Your reading and execution progress is tracked locally in your browser. Visited pages show a {check} in the sidebar; executed notebooks show a {play}.'}
            </Translate>
          </p>

          {progressStats && (progressStats.visitedCount > 0 || progressStats.executedCount > 0) ? (
            <>
              <div className="dq-progress-stats">
                <div className="dq-progress-stat">
                  <span className="dq-progress-stat__number">{progressStats.visitedCount}</span>
                  <span className="dq-progress-stat__label"><Translate id="settings.progress.pagesVisited">Pages visited</Translate></span>
                </div>
                <div className="dq-progress-stat">
                  <span className="dq-progress-stat__number">{progressStats.executedCount}</span>
                  <span className="dq-progress-stat__label"><Translate id="settings.progress.notebooksExecuted">Notebooks executed</Translate></span>
                </div>
                {Object.entries(progressStats.visitedByCategory).map(([cat, count]) => (
                  <div className="dq-progress-stat" key={cat}>
                    <span className="dq-progress-stat__number">{count}</span>
                    <span className="dq-progress-stat__label">{cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
                  </div>
                ))}
              </div>

              <h3><Translate id="settings.progress.clearHeading">Clear Progress</Translate></h3>
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
                    {translate({id: 'settings.progress.clearCategory', message: 'Clear {category}'}, {category: cat.charAt(0).toUpperCase() + cat.slice(1)})}
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
                  <Translate id="settings.progress.clearAll">Clear All Progress</Translate>
                </button>
                <button
                  className="jupyter-settings__button jupyter-settings__button--secondary"
                  onClick={() => {
                    clearAllPreferences();
                    setProgressStats(getProgressStats());
                  }}
                >
                  <Translate id="settings.progress.clearPrefs">Clear All Preferences</Translate>
                </button>
              </div>
            </>
          ) : (
            <div className="alert alert--info margin-bottom--md">
              <Translate id="settings.progress.empty">
                No progress tracked yet. Visit tutorials and guides to start tracking.
              </Translate>
            </div>
          )}

          {/* Display Preferences */}
          <h2 id="display" style={{ marginTop: '2rem' }}><Translate id="settings.display.heading">Display Preferences</Translate></h2>

          <h3><Translate id="settings.display.fontSize.heading">Code Font Size</Translate></h3>
          <div className="dq-font-size-control">
            <button
              onClick={() => {
                const next = fontSize - 1;
                if (next >= 10) {
                  setFontSize(next);
                  setCodeFontSize(next);
                  window.dispatchEvent(new CustomEvent(DISPLAY_PREFS_EVENT));
                }
              }}
              disabled={fontSize <= 10}
              aria-label={translate({id: 'settings.display.fontSize.decrease', message: 'Decrease font size'})}
            >
              &minus;
            </button>
            <span className="dq-font-size-control__value">{fontSize}px</span>
            <button
              onClick={() => {
                const next = fontSize + 1;
                if (next <= 22) {
                  setFontSize(next);
                  setCodeFontSize(next);
                  window.dispatchEvent(new CustomEvent(DISPLAY_PREFS_EVENT));
                }
              }}
              disabled={fontSize >= 22}
              aria-label={translate({id: 'settings.display.fontSize.increase', message: 'Increase font size'})}
            >
              +
            </button>
          </div>
          <div className="dq-font-size-preview">
            <code>from qiskit import QuantumCircuit</code>
          </div>

          <h3><Translate id="settings.display.outputs.heading">Pre-computed Outputs</Translate></h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
            <Translate
              id="settings.display.outputs.desc"
              values={{run: <strong>Run</strong>}}
            >
              {'Each notebook page shows pre-computed outputs (images, tables, text) from IBM\'s original runs. When you click {run} to execute code live, both the original outputs and your new live results are shown side by side. Enable this toggle to hide the original outputs during live execution, keeping only your results visible.'}
            </Translate>
          </p>
          <div className="jupyter-settings__field">
            <label className="jupyter-settings__toggle">
              <input
                type="checkbox"
                checked={!hideOutputs}
                onChange={() => {
                  const next = !hideOutputs;
                  setHideOutputs(next);
                  setHideStaticOutputs(next);
                }}
              />
              <span className="jupyter-settings__toggle-track">
                <span className="jupyter-settings__toggle-thumb" />
              </span>
              <span style={{ marginLeft: '0.5rem' }}>
                {hideOutputs
                  ? translate({id: 'settings.display.outputs.hidden', message: 'Pre-computed outputs hidden during live execution'})
                  : translate({id: 'settings.display.outputs.shown', message: 'Show both pre-computed and live outputs'})}
              </span>
            </label>
          </div>

          <h3><Translate id="settings.display.warnings.heading">Python Warnings</Translate></h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
            <Translate id="settings.display.warnings.desc">
              By default, Python warnings (deprecation notices, runtime hints) are
              suppressed for cleaner notebook output. Disable this to see all warnings
              — useful for debugging or learning about API changes.
            </Translate>
          </p>
          <div className="jupyter-settings__field">
            <label className="jupyter-settings__toggle">
              <input
                type="checkbox"
                checked={suppressWarnings}
                onChange={() => {
                  const next = !suppressWarnings;
                  setSuppressWarningsState(next);
                  setSuppressWarnings(next);
                }}
              />
              <span className="jupyter-settings__toggle-track">
                <span className="jupyter-settings__toggle-thumb" />
              </span>
              <span style={{ marginLeft: '0.5rem' }}>
                {suppressWarnings
                  ? translate({id: 'settings.display.warnings.suppressed', message: 'Warnings suppressed for cleaner output'})
                  : translate({id: 'settings.display.warnings.shown', message: 'All Python warnings shown'})}
              </span>
            </label>
          </div>

          {/* Bookmarks */}
          {bookmarkCount > 0 && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}><Translate id="settings.bookmarks.heading">Bookmarks</Translate></h3>
              <p>{translate({id: 'settings.bookmarks.count', message: '{count} bookmarked page(s)'}, {count: String(bookmarkCount)})}</p>
              <button
                className="jupyter-settings__button jupyter-settings__button--secondary"
                onClick={() => {
                  clearAllBookmarks();
                  setBookmarkCount(0);
                }}
              >
                <Translate id="settings.bookmarks.clearBtn">Clear All Bookmarks</Translate>
              </button>
            </>
          )}

          {/* Other preferences */}
          <h3 style={{ marginTop: '1.5rem' }}><Translate id="settings.other.heading">Other</Translate></h3>
          <div className="dq-clear-buttons">
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={() => {
                resetOnboarding();
              }}
            >
              <Translate id="settings.other.resetOnboarding">Reset Onboarding Tips</Translate>
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={() => {
                clearRecentPages();
              }}
            >
              <Translate id="settings.other.clearRecent">Clear Recent History</Translate>
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={() => {
                clearSidebarCollapseStates();
              }}
            >
              <Translate id="settings.other.resetSidebar">Reset Sidebar Layout</Translate>
            </button>
          </div>

          {/* Binder Packages */}
          <h2 id="binder-packages" style={{ marginTop: '2rem' }}><Translate id="settings.binder.heading">Binder Packages</Translate></h2>

          <p>
            <Translate
              id="settings.binder.desc"
              values={{
                mybinder: <a href="https://mybinder.org" target="_blank" rel="noopener noreferrer">MyBinder</a>,
              }}
            >
              {'When running on GitHub Pages, code executes via {mybinder}. The Binder environment includes core Qiskit packages pre-installed:'}
            </Translate>
          </p>
          <pre>
            <code>{`qiskit[visualization], qiskit-aer,
qiskit-ibm-runtime, pylatexenc,
qiskit-ibm-catalog, qiskit-addon-utils, pyscf`}</code>
          </pre>

          <p>
            <Translate id="settings.binder.installHint">
              Some notebooks require additional packages. You can install them
              on demand by running this in a code cell:
            </Translate>
          </p>
          <pre>
            <code>{`!pip install -q <package>`}</code>
          </pre>

          <p><Translate id="settings.binder.installAll">Or install all optional packages at once:</Translate></p>
          <pre>
            <code>{`!pip install -q scipy scikit-learn qiskit-ibm-transpiler \\
  qiskit-experiments plotly sympy qiskit-serverless \\
  qiskit-addon-sqd qiskit-addon-mpf \\
  qiskit-addon-aqc-tensor[aer,quimb-jax] \\
  qiskit-addon-obp qiskit-addon-cutting ffsim \\
  gem-suite python-sat`}</code>
          </pre>

          {/* Advanced: Custom Jupyter Server */}
          <h2 id="advanced" style={{ marginTop: '2rem' }}><Translate id="settings.advanced.heading">Advanced</Translate></h2>

          <h3><Translate id="settings.advanced.serverHeading">Custom Jupyter Server</Translate></h3>

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="jupyter-url">
              <Translate id="settings.advanced.urlLabel">Jupyter Server URL</Translate>
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
              <Translate id="settings.advanced.urlHint">The base URL of your Jupyter server (e.g., http://localhost:8888)</Translate>
            </small>
          </div>

          <div className="jupyter-settings__field">
            <label className="jupyter-settings__label" htmlFor="jupyter-token">
              <Translate id="settings.advanced.tokenLabel">Authentication Token</Translate>
            </label>
            <input
              id="jupyter-token"
              type="password"
              className="jupyter-settings__input"
              placeholder={translate({id: 'settings.advanced.tokenPlaceholder', message: '(optional)'})}
              value={customToken}
              onChange={(e) => setCustomToken(e.target.value)}
            />
            <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
              <Translate id="settings.advanced.tokenHint">Token from jupyter server --generate-config or displayed at startup</Translate>
            </small>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1rem' }}>
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleTest}
              disabled={!customUrl || isTesting}
            >
              {isTesting
                ? translate({id: 'settings.advanced.testing', message: 'Testing...'})
                : translate({id: 'settings.advanced.testBtn', message: 'Test Connection'})}
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--primary"
              onClick={handleSave}
              disabled={!customUrl}
            >
              <Translate id="settings.advanced.saveBtn">Save Settings</Translate>
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleUseDefault}
            >
              <Translate id="settings.advanced.defaultBtn">Use Default</Translate>
            </button>
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={handleClear}
            >
              <Translate id="settings.advanced.clearBtn">Clear Custom</Translate>
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
          <h3 style={{ marginTop: '2rem' }}><Translate id="settings.help.heading">Setup Help</Translate></h3>

          <h3><Translate id="settings.help.rasqberry.heading">RasQberry Setup</Translate></h3>
          <p>
            <Translate id="settings.help.rasqberry.desc">
              If you're running on a RasQberry Pi, the Jupyter server should be
              automatically detected. If not, ensure the jupyter-tutorials service is running:
            </Translate>
          </p>
          <pre>
            <code>sudo systemctl status jupyter-tutorials</code>
          </pre>

          <h3><Translate id="settings.help.local.heading">Local Jupyter Setup</Translate></h3>
          <p><Translate id="settings.help.local.desc">Start a Jupyter server with CORS enabled:</Translate></p>
          <pre>
            <code>{`jupyter server --ServerApp.token='rasqberry' \\
  --ServerApp.allow_origin='*' \\
  --ServerApp.disable_check_xsrf=True`}</code>
          </pre>

          <h3><Translate id="settings.help.docker.heading">Docker Setup</Translate></h3>
          <p>
            <Translate id="settings.help.docker.desc">
              The Docker container generates a random Jupyter token at startup.
              Code execution through the website (port 8080) works automatically
              — no token needed. The token is only required for direct
              JupyterLab access on port 8888.
            </Translate>
          </p>
          <p><Translate id="settings.help.docker.retrieveToken">To retrieve the token from container logs:</Translate></p>
          <pre>
            <code>docker compose --profile jupyter logs | grep &quot;Jupyter token&quot;</code>
          </pre>
          <p><Translate id="settings.help.docker.fixedToken">To set a fixed token:</Translate></p>
          <pre>
            <code>JUPYTER_TOKEN=mytoken docker compose --profile jupyter up</code>
          </pre>

          <h3><Translate id="settings.help.remote.heading">Remote Server</Translate></h3>
          <p>
            <Translate
              id="settings.help.remote.desc"
              values={{config: <code>jupyter_server_config.py</code>}}
            >
              {'For remote servers, ensure CORS is configured to allow connections from this site. Add the following to your {config}:'}
            </Translate>
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
