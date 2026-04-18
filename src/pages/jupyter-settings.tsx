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
import InfoIcon from '@site/src/components/InfoIcon';
import {
  detectJupyterConfig,
  saveJupyterConfig,
  clearJupyterConfig,
  clearBinderSession,
  cancelBinderBuild,
  testJupyterConnection,
  getIBMQuantumToken,
  getIBMQuantumCRN,
  getCredentialDaysRemaining,
  saveIBMQuantumCredentials,
  clearIBMQuantumCredentials,
  getExecutionMode,
  setExecutionMode,
  getFakeDevice,
  setFakeDevice,
  getCachedFakeBackends,
  getCredentialTTLDays,
  setCredentialTTLDays,
  getSuppressWarnings,
  setSuppressWarnings,
  getCodeEngineUrl,
  getCodeEngineToken,
  getCEDaysRemaining,
  saveCodeEngineCredentials,
  clearCodeEngineCredentials,
  getAvailableBackends,
  getBackendOverride,
  setBackendOverride,
  getWorkshopPool,
  saveWorkshopPool,
  clearWorkshopPool,
  getWorkshopAssignment,
  getWorkshopInstanceStats,
  type WorkshopPool,
  type InstanceStats,
  type JupyterConfig,
  type ExecutionMode,
  type AvailableBackend,
  getIBMQuantumPlan,
  setIBMQuantumPlan,
  type IBMQuantumPlan,
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
  clearRecentAndLastPage,
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
  const [ibmSaveResult, setIbmSaveResult] = useState<string | null>(null);
  const [ibmPlan, setIbmPlanState] = useState<IBMQuantumPlan>('open');

  // Learning progress state
  const [progressStats, setProgressStats] = useState<ProgressStats | null>(null);

  // Display preferences state
  const [fontSize, setFontSize] = useState(14);
  const [hideOutputs, setHideOutputs] = useState(false);
  const [suppressWarnings, setSuppressWarningsState] = useState(true);
  const [bookmarkCount, setBookmarkCount] = useState(0);

  // Execution mode state
  const [executionMode, setExecutionModeState] = useState<ExecutionMode>('aer');
  const [fakeDevice, setFakeDeviceState] = useState('FakeSherbrooke');
  const [fakeBackends, setFakeBackends] = useState(FALLBACK_BACKENDS);
  const [ttlDays, setTtlDaysState] = useState(1);

  // Code Engine state
  const [ceUrl, setCeUrl] = useState('');
  const [ceToken, setCeToken] = useState('');
  const [ceDaysRemaining, setCeDaysRemaining] = useState(-1);
  const [ceSaveResult, setCeSaveResult] = useState<string | null>(null);
  const [ceSaveResultType, setCeSaveResultType] = useState<'success' | 'warning' | 'info'>('success');

  // Workshop pool state
  const [workshopPool, setWorkshopPoolState] = useState<WorkshopPool | null>(null);
  const [workshopAssigned, setWorkshopAssignedState] = useState<string | null>(null);
  const [workshopStats, setWorkshopStats] = useState<InstanceStats[] | null>(null);
  const [workshopResult, setWorkshopResult] = useState<string | null>(null);
  const [workshopResultType, setWorkshopResultType] = useState<'success' | 'warning' | 'info'>('success');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Backend selection state
  const [availableBackends, setAvailableBackends] = useState<AvailableBackend[]>([]);
  const [backendOverride, setBackendOverrideState] = useState<JupyterConfig['environment'] | null>(null);

  // Load current config on mount
  useEffect(() => {
    const currentConfig = detectJupyterConfig();
    setConfig(currentConfig);

    if (currentConfig.environment === 'custom') {
      setCustomUrl(currentConfig.baseUrl);
      setCustomToken(currentConfig.token);
    }

    // Load IBM credentials state
    // getIBMQuantumToken() calls checkCredentialExpiry() internally,
    // which auto-clears expired credentials before returning ''.
    const savedToken = getIBMQuantumToken();
    const days = getCredentialDaysRemaining();
    setIbmDaysRemaining(days);
    if (savedToken) {
      setIbmToken(savedToken);
      setIbmCrn(getIBMQuantumCRN());
    }

    // Load execution mode state
    setExecutionModeState(getExecutionMode());
    setFakeDeviceState(getFakeDevice());
    setTtlDaysState(getCredentialTTLDays());
    setIbmPlanState(getIBMQuantumPlan());

    // Load cached fake backends
    const cached = getCachedFakeBackends();
    if (cached && cached.length > 0) {
      setFakeBackends(cached);
    }

    // Load Code Engine credentials
    const savedCeUrl = getCodeEngineUrl();
    if (savedCeUrl) {
      setCeUrl(savedCeUrl);
      setCeToken(getCodeEngineToken());
      setCeDaysRemaining(getCEDaysRemaining());
    }

    // Load workshop pool state
    const savedPool = getWorkshopPool();
    if (savedPool) {
      setWorkshopPoolState(savedPool);
      setWorkshopAssignedState(getWorkshopAssignment());
    }

    // Load backend selection state
    setAvailableBackends(getAvailableBackends());
    setBackendOverrideState(getBackendOverride());

    // Load learning progress
    setProgressStats(getProgressStats());

    // Load display preferences
    setFontSize(getCodeFontSize());
    setHideOutputs(getHideStaticOutputs());
    setSuppressWarningsState(getSuppressWarnings());
    setBookmarkCount(getBookmarks().length);
  }, []);

  // Auto-open <details> when URL has a hash anchor (e.g., #code-engine)
  useEffect(() => {
    const hash = window.location.hash?.slice(1);
    if (!hash) return;

    const target = document.getElementById(hash);
    if (!target) return;
    // Walk up to find enclosing <details> and open it
    let el: HTMLElement | null = target;
    while (el) {
      if (el.tagName === 'DETAILS') {
        (el as HTMLDetailsElement).open = true;
        break;
      }
      el = el.parentElement;
    }
    setTimeout(() => target.scrollIntoView({ behavior: 'smooth' }), 100);
  }, []);

  // Auto-refresh workshop stats every 30s when enabled
  useEffect(() => {
    if (!autoRefresh || !workshopPool) return;
    handleWorkshopRefreshStats();
    const interval = setInterval(handleWorkshopRefreshStats, 30_000);
    return () => clearInterval(interval);
  }, [autoRefresh, workshopPool]);

  const handleTest = async () => {
    if (!customUrl) return;

    setIsTesting(true);
    setTestResult(null);

    const result = await testJupyterConnection(customUrl, customToken);
    setTestResult(result);
    setIsTesting(false);
  };

  /** Refresh available backends list and re-detect config after credential changes. */
  const refreshBackends = (clearedEnv?: JupyterConfig['environment']) => {
    if (clearedEnv && backendOverride === clearedEnv) {
      setBackendOverrideState(null);
      setBackendOverride(null);
    }
    setAvailableBackends(getAvailableBackends());
    setConfig(detectJupyterConfig());
  };

  const handleBackendChange = (env: JupyterConfig['environment'] | null) => {
    setBackendOverrideState(env);
    setBackendOverride(env);
    // Clear any active session so next Run uses the new backend
    cancelBinderBuild();
    clearBinderSession();
    setConfig(detectJupyterConfig());
    setAvailableBackends(getAvailableBackends());
  };

  const handleSave = () => {
    saveJupyterConfig(customUrl, customToken);
    refreshBackends();
    setTestResult({
      success: true,
      message: translate({id: 'settings.advanced.saveSuccess', message: 'Settings saved! Refresh the page to apply.'}),
    });
  };

  const handleClear = () => {
    clearJupyterConfig();
    setCustomUrl('');
    setCustomToken('');
    refreshBackends('custom');
    setTestResult({
      success: true,
      message: translate({id: 'settings.advanced.clearSuccess', message: 'Custom settings cleared. Using auto-detected configuration.'}),
    });
  };

  // IBM Quantum credential handlers
  const handleIbmSave = () => {
    if (!ibmToken) return;
    if (ibmCrn && !ibmCrn.startsWith('crn:')) {
      setIbmSaveResult(translate({id: 'settings.ibm.invalidCrn', message: 'CRN must start with "crn:" (e.g. crn:v1:bluemix:...). Leave blank if unsure.'}));
      return;
    }
    saveIBMQuantumCredentials(ibmToken, ibmCrn);
    setIbmDaysRemaining(ttlDays);
    setIbmSaveResult(translate({id: 'settings.ibm.saveSuccess', message: 'Credentials saved! They will be auto-injected when the kernel starts.'}));
  };

  const handleIbmDelete = () => {
    clearIBMQuantumCredentials();
    setIbmToken('');
    setIbmCrn('');
    setIbmDaysRemaining(-1);
    setIbmSaveResult(translate({id: 'settings.ibm.deleteSuccess', message: 'Credentials deleted.'}));
    if (executionMode === 'credentials') {
      setExecutionModeState('aer');
      setExecutionMode('aer');
    }
  };

  // Code Engine handlers
  // Smart save: detects single URL, comma-separated URLs, or base64 pool config.
  // Single URL → saves as CE credentials. Multiple URLs / pool → saves as workshop pool.
  const handleCeSave = () => {
    const raw = ceUrl.trim();
    if (!raw) return;
    if (!ceToken || ceToken.length < 8) {
      setCeSaveResult(translate({id: 'settings.ce.tokenRequired', message: 'Token is required (min 8 characters).'}));
      setCeSaveResultType('warning');
      return;
    }

    // Detect format: try base64 pool config first, then comma-separated, then single URL
    let urls: string[] = [];
    if (!raw.startsWith('http')) {
      try {
        const decoded = JSON.parse(atob(raw));
        if (Array.isArray(decoded.pool) && decoded.pool.length > 0) {
          urls = decoded.pool.map((u: string) => String(u).trim().replace(/\/+$/, ''));
        }
      } catch { /* not base64 */ }
    }
    if (urls.length === 0 && raw.includes(',')) {
      urls = raw.split(',').map(u => u.trim().replace(/\/+$/, '')).filter(u => /^https?:\/\//i.test(u));
    }

    if (urls.length > 1) {
      // Multi-URL → save as workshop pool
      saveWorkshopPool(urls, ceToken);
      const pool = getWorkshopPool();
      setWorkshopPoolState(pool);
      setWorkshopAssignedState(getWorkshopAssignment());
      refreshBackends();
      setCeSaveResult(translate({id: 'settings.ce.workshopJoined', message: 'Joined workshop pool with {n} instance(s).'}).replace('{n}', String(urls.length)));
      setCeSaveResultType('success');
      return;
    }

    // Single URL path
    if (!/^https:\/\//i.test(raw)) {
      setCeSaveResult(translate({id: 'settings.ce.httpsRequired', message: 'URL must start with https:// (or paste comma-separated URLs / base64 pool config for workshops).'}));
      setCeSaveResultType('warning');
      return;
    }
    saveCodeEngineCredentials(raw, ceToken);
    setCeDaysRemaining(ttlDays);
    refreshBackends();
    setCeSaveResult(translate({id: 'settings.ce.saveSuccess', message: 'Code Engine settings saved! Code will now execute via your CE instance.'}));
    setCeSaveResultType('success');
  };

  const handleCeDelete = () => {
    clearCodeEngineCredentials();
    setCeUrl('');
    setCeToken('');
    setCeDaysRemaining(-1);
    refreshBackends('code-engine');
    setCeSaveResult(translate({id: 'settings.ce.deleteSuccess', message: 'Code Engine settings cleared. Falling back to Binder.'}));
    setCeSaveResultType('success');
  };

  const handleCeTest = async () => {
    if (!ceUrl) return;
    if (!/^https:\/\//i.test(ceUrl)) {
      setCeSaveResult(translate({id: 'settings.ce.httpsRequired', message: 'URL must start with https://'}));
      setCeSaveResultType('warning');
      return;
    }
    setCeSaveResult(null);
    setCeSaveResultType('info');
    const result = await testJupyterConnection(
      ceUrl.replace(/\/+$/, ''),
      ceToken,
      (status) => {
        setCeSaveResult(status);
        setCeSaveResultType('info');
      },
    );
    setCeSaveResult(result.message);
    setCeSaveResultType(result.success ? 'success' : 'warning');
  };

  // Workshop handlers
  // Workshop join is now handled in handleCeSave() — single URL field accepts
  // CE URL, comma-separated workshop URLs, or base64 pool config.

  const handleWorkshopLeave = () => {
    clearWorkshopPool();
    setWorkshopPoolState(null);
    setWorkshopAssignedState(null);
    setWorkshopStats(null);
    setAutoRefresh(false);
    setLastUpdated(null);
    refreshBackends('code-engine');
    setWorkshopResult('Left workshop. Falling back to single CE instance or Binder.');
    setWorkshopResultType('success');
  };

  const handleWorkshopRefreshStats = async () => {
    const pool = getWorkshopPool();
    if (!pool) return;
    setWorkshopResult('Checking instances...');
    setWorkshopResultType('info');
    const stats = await getWorkshopInstanceStats(pool.pool);
    setWorkshopStats(stats);
    setLastUpdated(new Date());
    const online = stats.filter(s => s.status === 'online').length;
    const totalKernels = stats.reduce((sum, s) => sum + s.kernels, 0);
    const totalBusy = stats.reduce((sum, s) => sum + s.kernelsBusy, 0);
    const totalConn = stats.reduce((sum, s) => sum + s.connections, 0);
    setWorkshopResult(
      `${online}/${stats.length} online, ${totalKernels} kernels (${totalBusy} busy), ${totalConn} connections`
    );
    setWorkshopResultType(online === stats.length ? 'success' : 'warning');
  };

  // Execution mode handler
  const handleExecutionModeChange = (mode: ExecutionMode) => {
    setExecutionModeState(mode);
    setExecutionMode(mode);
  };

  const handleFakeDeviceChange = (name: string) => {
    setFakeDeviceState(name);
    setFakeDevice(name);
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


          {/* Current backend status — always visible */}
          <div className="alert alert--info margin-bottom--md" id="compute-backend">
            <strong><Translate id="settings.env.label">Current:</Translate></strong>{' '}
            {config?.environment === 'code-engine' && (
              <Translate id="settings.computeBackend.envCE" values={{url: config.baseUrl}}>{'Code Engine — {url}'}</Translate>
            )}
            {config?.environment === 'github-pages' && (
              <Translate id="settings.computeBackend.envBinder">Binder (mybinder.org)</Translate>
            )}
            {config?.environment === 'rasqberry' && (
              <Translate id="settings.computeBackend.envLocal" values={{url: config.baseUrl}}>{'Local — {url}'}</Translate>
            )}
            {config?.environment === 'custom' && (
              <Translate id="settings.computeBackend.envCustom" values={{url: config.baseUrl}}>{'Custom — {url}'}</Translate>
            )}
            {(!config?.environment || config?.environment === 'unknown') && (
              <Translate id="settings.computeBackend.envUnknown">Not detected</Translate>
            )}
          </div>

          {/* Backend Selection — always visible so users can discover CE */}
          {(() => {
            // Build display list: detected backends + CE and Custom if not already present
            const displayBackends = [...availableBackends];
            if (!displayBackends.some(b => b.environment === 'code-engine')) {
              displayBackends.push({
                environment: 'code-engine',
                label: translate({id: 'settings.backend.ce.label', message: 'Code Engine'}),
                detail: translate({id: 'settings.backend.ce.notConfigured', message: 'not configured — set up below'}),
              });
            }
            if (!displayBackends.some(b => b.environment === 'custom')) {
              displayBackends.push({
                environment: 'custom',
                label: translate({id: 'settings.backend.custom.label', message: 'Custom Server'}),
                detail: translate({id: 'settings.backend.custom.notConfigured', message: 'not configured — enter URL below'}),
              });
            }
            return (
            <>
              <h3 id="backend-selection" style={{ marginTop: '1.5rem' }}>
                <Translate id="settings.backend.heading">Server Backend</Translate>
              </h3>
              <p style={{ fontSize: '0.9rem' }}>
                <Translate id="settings.backend.description">
                  Choose which backend to use for code execution:
                </Translate>
              </p>
              <div className="jupyter-settings__radio-group">
                <label className="jupyter-settings__radio-label">
                  <input
                    type="radio"
                    name="backend-override"
                    checked={backendOverride === null}
                    onChange={() => handleBackendChange(null)}
                  />
                  <span>
                    <Translate id="settings.backend.auto">Auto-detect (recommended)</Translate>
                  </span>
                </label>
                {displayBackends.map((b) => (
                  <label key={b.environment} className="jupyter-settings__radio-label">
                    <input
                      type="radio"
                      name="backend-override"
                      checked={backendOverride === b.environment}
                      onChange={() => handleBackendChange(b.environment)}
                    />
                    <span>
                      {b.label}
                      {b.detail && (
                        <span style={{ color: 'var(--ifm-color-content-secondary)', fontSize: '0.85rem' }}>
                          {' — '}{b.detail}
                        </span>
                      )}
                    </span>
                  </label>
                ))}
              </div>

              {/* Inline Custom Server fields — shown when custom is selected or configured */}
              {(backendOverride === 'custom' || config?.environment === 'custom') && (
                <div style={{ marginTop: '1rem', padding: '1rem', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '8px' }}>
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
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                    <button className="jupyter-settings__button jupyter-settings__button--primary" onClick={handleTest} disabled={!customUrl || isTesting}>
                      {isTesting ? translate({id: 'settings.advanced.testing', message: 'Testing...'}) : translate({id: 'settings.advanced.testBtn', message: 'Test Connection'})}
                    </button>
                    <button className="jupyter-settings__button jupyter-settings__button--primary" onClick={handleSave} disabled={!customUrl}>
                      <Translate id="settings.advanced.saveBtn">Save Settings</Translate>
                    </button>
                    <button className="jupyter-settings__button jupyter-settings__button--secondary" onClick={handleClear}>
                      <Translate id="settings.advanced.clearBtn">Clear</Translate>
                    </button>
                  </div>
                  {testResult && (
                    <div className={`alert margin-top--md ${testResult.success ? 'alert--success' : 'alert--danger'}`}>
                      {testResult.message}
                    </div>
                  )}
                </div>
              )}
            </>
            );
          })()}

          {/* ═══════════════════════════════════════════════════════════════
              ESSENTIALS — always visible
              ═══════════════════════════════════════════════════════════════ */}


          {/* CE Quick Config — always visible so users can configure CE */}
          <div style={{ marginTop: '1rem', padding: '1rem', border: '1px solid var(--ifm-color-emphasis-200)', borderRadius: '8px' }}>
              <h3 id="code-engine-config" style={{ marginTop: 0 }}>
                <Translate id="settings.ce.quickHeading">Code Engine</Translate>
              </h3>
              {ceDaysRemaining >= 0 && (
                <div className="alert alert--info margin-bottom--md">
                  <Translate id="settings.ce.daysRemaining" values={{days: ceDaysRemaining}}>
                    {'Code Engine settings will auto-delete in {days} day(s).'}
                  </Translate>
                </div>
              )}
              <div className="margin-bottom--sm">
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600 }}>
                  <Translate id="settings.ce.urlLabel">Code Engine URL</Translate><InfoIcon tooltip={translate({id: 'settings.info.ceUrl', message: 'Your Code Engine app URL, OR comma-separated URLs / base64 pool config from a workshop instructor.'})} />
                </label>
                <input type="text" value={ceUrl}
                  onChange={e => { setCeUrl(e.target.value); setCeSaveResult(null); }}
                  placeholder="https://your-app.region.codeengine.appdomain.cloud"
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--ifm-color-emphasis-300)' }} />
                <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
                  <Translate id="settings.ce.urlHint">For workshops: paste comma-separated URLs or the base64 pool config from your instructor.</Translate>
                </small>
              </div>
              <div className="margin-bottom--md">
                <label style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600 }}>
                  <Translate id="settings.ce.tokenLabel">Jupyter Token</Translate><InfoIcon tooltip={translate({id: 'settings.info.ceToken', message: 'The JUPYTER_TOKEN value you set when creating the Code Engine app.'})} />
                </label>
                <input type="password" value={ceToken}
                  onChange={e => { setCeToken(e.target.value); setCeSaveResult(null); }}
                  placeholder={translate({id: 'settings.ce.tokenPlaceholder', message: 'Your JUPYTER_TOKEN value'})}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--ifm-color-emphasis-300)' }} />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <button className="button button--primary button--sm" onClick={handleCeSave} disabled={!ceUrl}>
                  <Translate id="settings.ce.save">Save</Translate>
                </button>
                <button className="button button--secondary button--sm" onClick={handleCeTest} disabled={!ceUrl}>
                  <Translate id="settings.ce.test">Test Connection</Translate>
                </button>
                <button className="button button--outline button--danger button--sm" onClick={handleCeDelete} disabled={ceDaysRemaining < 0 && !ceUrl}>
                  <Translate id="settings.ce.clear">Clear</Translate>
                </button>
              </div>
              {ceSaveResult && (
                <div className={`alert alert--${ceSaveResultType} margin-bottom--md`}>
                  {ceSaveResult}
                </div>
              )}
              <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
                <Translate id="settings.ce.setupLink" values={{link: <a href="#code-engine"><Translate id="settings.ce.setupLinkText">setup instructions</Translate></a>}}>
                  {'Need help? See {link} below.'}
                </Translate>
              </small>
            </div>

          {/* Execution Mode */}
          <hr style={{ margin: '2rem 0', borderColor: 'var(--ifm-color-emphasis-200)' }} />

          <h2 id="execution-mode" style={{ marginTop: '2rem' }}>
            <Translate id="settings.executionMode.heading">Execution Mode</Translate>
            <InfoIcon tooltip={translate({id: 'settings.info.executionMode', message: 'Choose how quantum circuits are executed when you click Run on tutorial pages.'})} />
          </h2>

          <p>
            <Translate id="settings.executionMode.desc">
              Choose what happens when you click Run on tutorial pages. This applies to embedded code execution on this site only — opening a notebook in JupyterLab uses the standard Qiskit runtime.
            </Translate>
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
              <input type="radio" name="execution-mode" value="aer"
                checked={executionMode === 'aer'}
                onChange={() => handleExecutionModeChange('aer')}
                style={{ marginTop: '0.25rem' }} />
              <span>
                <strong>AerSimulator</strong> — <Translate id="settings.executionMode.aerDesc">Ideal simulation, no noise. Fast, works for all circuits.</Translate>
              </span>
            </label>

            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
              <input type="radio" name="execution-mode" value="fake"
                checked={executionMode === 'fake'}
                onChange={() => handleExecutionModeChange('fake')}
                style={{ marginTop: '0.25rem' }} />
              <span>
                <strong>FakeBackend</strong> — <Translate id="settings.executionMode.fakeDesc">Simulates real IBM device noise. More realistic but slower.</Translate>
              </span>
            </label>

            {executionMode === 'fake' && (
              <div className="jupyter-settings__field" style={{ marginLeft: '1.5rem' }}>
                <label className="jupyter-settings__label" htmlFor="fake-device">
                  <Translate id="settings.executionMode.deviceLabel">Device</Translate>
                </label>
                <select id="fake-device" className="jupyter-settings__input"
                  value={fakeDevice}
                  onChange={(e) => handleFakeDeviceChange(e.target.value)}>
                  {sortedQubitGroups.map(([qubits, backends]) => (
                    <optgroup key={qubits} label={`${qubits} qubits`}>
                      {backends.map((b) => (
                        <option key={b.name} value={b.name}>{b.name}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
                  <Translate id="settings.executionMode.deviceHint">Device list is updated automatically when you run code.</Translate>
                </small>
              </div>
            )}

            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
              <input type="radio" name="execution-mode" value="credentials"
                checked={executionMode === 'credentials'}
                onChange={() => handleExecutionModeChange('credentials')}
                style={{ marginTop: '0.25rem' }} />
              <span>
                <strong><Translate id="settings.executionMode.ibm">IBM Quantum (real hardware)</Translate></strong> — <Translate id="settings.executionMode.ibmDesc">Connect to real quantum hardware via IBM Quantum credentials.</Translate>
              </span>
            </label>

            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
              <input type="radio" name="execution-mode" value="none"
                checked={executionMode === 'none'}
                onChange={() => handleExecutionModeChange('none')}
                style={{ marginTop: '0.25rem' }} />
              <span>
                <strong><Translate id="settings.executionMode.none">No automatic injection</Translate></strong> — <Translate id="settings.executionMode.noneDesc">Manage credentials and backend in code cells yourself.</Translate>
              </span>
            </label>
          </div>

          {executionMode === 'credentials' && ibmDaysRemaining < 0 && (
            <div className="alert alert--warning margin-top--md">
              <Translate id="settings.executionMode.noCredentials">
                IBM Quantum mode selected but no credentials saved. Enter your token and CRN below.
              </Translate>
            </div>
          )}

          <div className="alert alert--info margin-top--md">
            <Translate id="settings.executionMode.applyHint">
              Changes take effect on the next kernel session. If code is running, click Back then Run to apply.
            </Translate>
          </div>

          {/* IBM Quantum Account */}
          <details className="jupyter-settings__details" open={executionMode === 'credentials' || ibmDaysRemaining >= 0}>
            <summary>
              <h3 id="ibm-quantum" className="jupyter-settings__details-heading">
                <Translate id="settings.ibm.heading">IBM Quantum Account</Translate>
              </h3>
            </summary>
            <div className="jupyter-settings__details-content">

              <details style={{ marginBottom: '1rem' }}>
                <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                  <Translate id="settings.ibm.setupInstructions">Setup instructions &amp; security notes</Translate>
                </summary>
                <div style={{ marginTop: '0.5rem' }}>
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
                        {'{strong} at {link} (free, no credit card required)'}
                      </Translate>
                    </li>
                    <li>
                      <Translate
                        id="settings.ibm.step2"
                        values={{
                          strong: <strong><Translate id="settings.ibm.step2.label">Create an instance</Translate></strong>,
                          link: <a href="https://quantum.cloud.ibm.com/instances" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.step2.instances">Instances</Translate></a>,
                        }}
                      >
                        {'{strong} — go to {link}, click "Create instance +", select the Open (free) plan, and follow the wizard'}
                      </Translate>
                    </li>
                    <li>
                      <Translate
                        id="settings.ibm.step3"
                        values={{
                          strong: <strong><Translate id="settings.ibm.step3.label">Copy CRN</Translate></strong>,
                          link: <a href="https://quantum.cloud.ibm.com" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.step3.home">home page</Translate></a>,
                        }}
                      >
                        {'{strong} — back on the {link}, find your instance under "Instances" and click the copy icon next to "CRN"'}
                      </Translate>
                    </li>
                    <li>
                      <Translate
                        id="settings.ibm.step4"
                        values={{
                          strong: <strong><Translate id="settings.ibm.step4.label">Create API key</Translate></strong>,
                          link: <a href="https://quantum.cloud.ibm.com" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.step4.home">home page</Translate></a>,
                        }}
                      >
                        {'{strong} — on the {link}, find "API key" and click "Create +"'}
                      </Translate>
                    </li>
                  </ol>

                  <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
                    <Translate
                      id="settings.ibm.guideLink"
                      values={{
                        link: <a href="https://quantum.cloud.ibm.com/docs/en/guides/hello-world#install-and-authenticate" target="_blank" rel="noopener noreferrer"><Translate id="settings.ibm.guideLink.text">IBM's authentication guide</Translate></a>,
                      }}
                    >
                      {'Need more help? See {link} for screenshots and detailed steps.'}
                    </Translate>
                  </p>
                </div>
              </details>

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
                  <Translate id="settings.ibm.tokenLabel">API Token</Translate><InfoIcon tooltip={translate({id: 'settings.info.apiToken', message: 'Find your API token at quantum.cloud.ibm.com under your profile.'})} />
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
                  <Translate id="settings.ibm.crnLabel">Cloud Resource Name (CRN) / Instance</Translate><InfoIcon tooltip={translate({id: 'settings.info.crn', message: 'Cloud Resource Name — copy from the Instances page on IBM Quantum Platform.'})} />
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

              <div className="jupyter-settings__field">
                <label className="jupyter-settings__label" htmlFor="ibm-plan">
                  <Translate id="settings.ibm.planLabel">Plan type</Translate><InfoIcon tooltip={translate({id: 'settings.info.ibmPlan', message: 'Open Plan does not support Sessions. When set to Open, Session calls are automatically converted to job mode so tutorials run without errors.'})} />
                </label>
                <select
                  id="ibm-plan"
                  value={ibmPlan}
                  onChange={(e) => {
                    const plan = e.target.value as IBMQuantumPlan;
                    setIbmPlanState(plan);
                    setIBMQuantumPlan(plan);
                  }}
                  style={{
                    padding: '0.35rem 0.5rem',
                    borderRadius: '4px',
                    border: '1px solid var(--ifm-color-emphasis-300)',
                    background: 'var(--ifm-background-color)',
                    fontSize: '0.85rem',
                    maxWidth: '200px',
                  }}
                >
                  <option value="open">{translate({id: 'settings.ibm.plan.open', message: 'Open (free)'})}</option>
                  <option value="payg">{translate({id: 'settings.ibm.plan.payg', message: 'Pay-as-you-go'})}</option>
                  <option value="premium">{translate({id: 'settings.ibm.plan.premium', message: 'Premium'})}</option>
                </select>
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
            </div>
          </details>


          {/* Display Preferences */}
          <hr style={{ margin: '2rem 0', borderColor: 'var(--ifm-color-emphasis-200)' }} />

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

          {/* Learning Progress */}
          <hr style={{ margin: '2rem 0', borderColor: 'var(--ifm-color-emphasis-200)' }} />

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
                  <Translate id="settings.progress.clearPrefs">Clear Learning Data</Translate>
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
                clearRecentAndLastPage();
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
            <button
              className="jupyter-settings__button jupyter-settings__button--secondary"
              onClick={() => {
                clearBinderSession();
              }}
            >
              <Translate id="settings.other.clearBinderSession">Clear Binder Session</Translate>
            </button>
          </div>

          {/* Reset Everything */}
          <h3 style={{ marginTop: '2rem' }}><Translate id="settings.resetAll.heading">Reset Everything</Translate></h3>
          <p style={{ fontSize: '0.9rem', color: 'var(--ifm-color-emphasis-600)' }}>
            <Translate id="settings.resetAll.description">
              Remove all saved data including progress, bookmarks, preferences, and credentials.
            </Translate>
          </p>
          <button
            className="jupyter-settings__button jupyter-settings__button--danger"
            onClick={() => {
              if (window.confirm(translate({
                id: 'settings.resetAll.confirm',
                message: 'This will remove all your progress, bookmarks, preferences, and saved credentials. This cannot be undone. Continue?',
              }))) {
                clearAllVisited();
                clearAllExecuted();
                clearAllPreferences();
                clearAllBookmarks();
                resetOnboarding();
                clearRecentAndLastPage();
                clearSidebarCollapseStates();
                clearBinderSession();
                clearIBMQuantumCredentials();
                clearCodeEngineCredentials();
                clearWorkshopPool();
                clearJupyterConfig();
                setProgressStats(getProgressStats());
                setBookmarkCount(0);
              }
            }}
          >
            <Translate id="settings.resetAll.button">Reset Everything</Translate>
          </button>

          {/* ═══════════════════════════════════════════════════════════════
              ADVANCED — collapsed by default
              ═══════════════════════════════════════════════════════════════ */}

          <hr style={{ margin: '2rem 0', borderColor: 'var(--ifm-color-emphasis-200)' }} />

          <h2 id="advanced-settings" style={{ marginTop: '2.5rem' }}>
            <Translate id="settings.advancedSettings.heading">Advanced Settings</Translate>
          </h2>

          {/* Code Engine */}
          <details className="jupyter-settings__details" open={config?.environment === 'code-engine' || ceDaysRemaining >= 0}>
            <summary>
              <h3 id="code-engine" className="jupyter-settings__details-heading">
                <Translate id="settings.ce.heading">IBM Cloud Code Engine</Translate>
              </h3>
            </summary>
            <div className="jupyter-settings__details-content">
              <p>
                <Translate id="settings.ce.description">
                  Code Engine provides a fast, serverless Jupyter kernel powered by your own IBM Cloud account.
                  Startup takes seconds instead of minutes. Free tier covers ~14 hours/month.
                </Translate>
              </p>

              {/* ── Workshop Mode Panel ── */}
              {workshopPool && workshopPool.pool.length > 0 ? (
                <>
                  <div className="alert alert--success margin-bottom--md">
                    <strong>Workshop Mode</strong> — {workshopPool.pool.length} instance(s)
                    {workshopAssigned && (
                      <span style={{ display: 'block', fontSize: '0.85rem', marginTop: '0.25rem', opacity: 0.85 }}>
                        This tab assigned to: {workshopAssigned.replace(/^https:\/\//, '').split('.')[0]}...
                      </span>
                    )}
                  </div>

                  {/* Instance Status Dashboard */}
                  <details className="margin-bottom--md">
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                      Instance Status
                    </summary>
                    <div style={{ marginTop: '0.5rem' }}>
                      {workshopStats ? (
                        <>
                          <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse', minWidth: '500px' }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid var(--ifm-color-emphasis-300)' }}>
                                  <th style={{ textAlign: 'left', padding: '0.25rem 0.5rem' }}>#</th>
                                  <th style={{ textAlign: 'left', padding: '0.25rem 0.5rem' }}>Instance</th>
                                  <th style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>Kernels</th>
                                  <th style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>Busy</th>
                                  <th style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>Conn</th>
                                  <th style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>Memory</th>
                                  <th style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>Uptime</th>
                                  <th style={{ textAlign: 'center', padding: '0.25rem 0.5rem' }}>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {workshopStats.map((s, i) => (
                                  <tr key={s.url} style={{ borderBottom: '1px solid var(--ifm-color-emphasis-200)' }}>
                                    <td style={{ padding: '0.25rem 0.5rem' }}>{i + 1}</td>
                                    <td style={{ padding: '0.25rem 0.5rem', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                                      {s.url.replace(/^https:\/\//, '').split('.')[0]}
                                    </td>
                                    <td style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>{s.kernels}</td>
                                    <td style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>{s.kernelsBusy}</td>
                                    <td style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>{s.connections}</td>
                                    <td style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>
                                      {s.memoryMb != null && s.memoryTotalMb != null
                                        ? `${s.memoryMb}/${s.memoryTotalMb} MB`
                                        : '\u2014'}
                                    </td>
                                    <td style={{ textAlign: 'right', padding: '0.25rem 0.5rem' }}>
                                      {s.uptimeSeconds > 0
                                        ? s.uptimeSeconds >= 3600
                                          ? `${Math.floor(s.uptimeSeconds / 3600)}h ${Math.floor((s.uptimeSeconds % 3600) / 60)}m`
                                          : `${Math.floor(s.uptimeSeconds / 60)}m`
                                        : '\u2014'}
                                    </td>
                                    <td style={{ textAlign: 'center', padding: '0.25rem 0.5rem' }}>
                                      {s.status === 'online' ? '\u25CF Online' : s.status === 'starting' ? '\u25CB Starting...' : '\u25CB Offline'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          {/* Peak stats summary */}
                          {workshopStats.some(s => s.status === 'online') && (
                            <p style={{ fontSize: '0.8rem', color: 'var(--ifm-color-emphasis-600)', marginTop: '0.25rem', marginBottom: '0.5rem' }}>
                              Peak: {Math.max(...workshopStats.map(s => s.peakKernels))} kernels, {Math.max(...workshopStats.map(s => s.peakConnections))} connections | Total sessions: {workshopStats.reduce((sum, s) => sum + s.totalSseConnections, 0)}
                            </p>
                          )}
                        </>
                      ) : (
                        <p style={{ color: 'var(--ifm-color-emphasis-600)', fontSize: '0.85rem' }}>
                          Click Refresh to check instance status.
                        </p>
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                        <button
                          className="button button--secondary button--sm"
                          onClick={handleWorkshopRefreshStats}
                        >
                          Refresh
                        </button>
                        <label style={{ fontSize: '0.85rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <input
                            type="checkbox"
                            checked={autoRefresh}
                            onChange={e => setAutoRefresh(e.target.checked)}
                          />
                          Auto-refresh (30s)
                        </label>
                        {lastUpdated && (
                          <span style={{ fontSize: '0.8rem', color: 'var(--ifm-color-emphasis-500)' }}>
                            Last updated: {lastUpdated.toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </details>

                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <button
                      className="button button--outline button--danger button--sm"
                      onClick={handleWorkshopLeave}
                    >
                      Leave Workshop
                    </button>
                  </div>
                </>
              ) : (
                <>
                  {/* ── Single CE Instance Form ── */}
                  <details className="margin-bottom--md">
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                      <Translate id="settings.ce.setupTitle">Setup Instructions</Translate>
                    </summary>
                    <ol style={{ marginTop: '0.5rem' }}>
                      <li>
                        <Translate
                          id="settings.ce.step1"
                          values={{link: <a href="https://cloud.ibm.com/registration" target="_blank" rel="noopener noreferrer">cloud.ibm.com</a>}}
                        >
                          {'Create an IBM Cloud account at {link} (free tier available)'}
                        </Translate>
                      </li>
                      <li>
                        <Translate
                          id="settings.ce.step2"
                          values={{link: <a href="https://cloud.ibm.com/codeengine/projects" target="_blank" rel="noopener noreferrer">Code Engine console</a>}}
                        >
                          {'Go to the {link} and create a new project in your preferred region'}
                        </Translate>
                      </li>
                      <li>
                        <Translate
                          id="settings.ce.step3"
                          values={{image: <code>ghcr.io/janlahmann/doqumentation-codeengine:latest</code>}}
                        >
                          {'Create a new application with image {image}, listening port 8080'}
                        </Translate>
                        <br />
                        <small style={{ color: 'var(--ifm-color-content-secondary)' }}>
                          <Translate id="settings.ce.step3sizing">
                            Sizing: 2 vCPU / 4 GB for single user, 8 vCPU / 16 GB for workshops (up to 80 users)
                          </Translate>
                        </small>
                      </li>
                      <li>
                        <Translate
                          id="settings.ce.step4"
                          values={{
                            token: <code>JUPYTER_TOKEN</code>,
                            cors: <code>CORS_ORIGIN</code>,
                            domain: <code>https://doqumentation.org</code>,
                          }}
                        >
                          {'Set environment variables: {token} to a secure token (min 32 characters) and {cors} to your domain (e.g. {domain})'}
                        </Translate>
                      </li>
                    </ol>
                    <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
                      <Translate
                        id="settings.ce.adminLink"
                        values={{link: <a href="/admin">admin page</a>}}
                      >
                        {'For workshop sizing details and stress testing, see the {link}.'}
                      </Translate>
                    </p>
                  </details>

                </>
              )}

              {workshopResult && (
                <div className={`alert alert--${workshopResultType} margin-bottom--md`}>
                  {workshopResult}
                </div>
              )}
            </div>
          </details>

          {/* Binder Packages */}
          <details className="jupyter-settings__details">
            <summary>
              <h3 id="binder-packages" className="jupyter-settings__details-heading">
                <Translate id="settings.binder.heading">Binder Packages</Translate>
              </h3>
            </summary>
            <div className="jupyter-settings__details-content">
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
            </div>
          </details>

          {/* Custom Jupyter Server — merged into backend selector above */}

          {/* Setup Help */}
          <details className="jupyter-settings__details">
            <summary>
              <h3 id="setup-help" className="jupyter-settings__details-heading">
                <Translate id="settings.help.heading">Setup Help</Translate>
              </h3>
            </summary>
            <div className="jupyter-settings__details-content">
              <h4><Translate id="settings.help.rasqberry.heading">RasQberry Setup</Translate></h4>
              <p>
                <Translate id="settings.help.rasqberry.desc">
                  If you're running on a RasQberry Pi, the Jupyter server should be
                  automatically detected. If not, ensure the jupyter-tutorials service is running:
                </Translate>
              </p>
              <pre>
                <code>sudo systemctl status jupyter-tutorials</code>
              </pre>

              <h4><Translate id="settings.help.local.heading">Local Jupyter Setup</Translate></h4>
              <p><Translate id="settings.help.local.desc">Start a Jupyter server with CORS enabled:</Translate></p>
              <pre>
                <code>{`jupyter server --ServerApp.token='rasqberry' \\
  --ServerApp.allow_origin='*' \\
  --ServerApp.disable_check_xsrf=True`}</code>
              </pre>

              <h4><Translate id="settings.help.docker.heading">Docker Setup</Translate></h4>
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

              <h4><Translate id="settings.help.remote.heading">Remote Server</Translate></h4>
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
          </details>
        </div>
      </main>
    </Layout>
  );
}
