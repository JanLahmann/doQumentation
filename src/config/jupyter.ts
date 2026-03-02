/**
 * Jupyter Configuration
 *
 * Handles runtime detection of the execution environment and provides
 * appropriate Jupyter server configuration for:
 * - GitHub Pages (static, optional Binder fallback)
 * - RasQberry Pi (local Jupyter server)
 * - Custom user-configured server
 *
 * Storage is backed by cookies (cross-subdomain) + localStorage via storage.ts.
 */

import { getItem, setItem, removeItem } from './storage';

export interface JupyterConfig {
  enabled: boolean;
  baseUrl: string;
  wsUrl: string;
  token: string;
  thebeEnabled: boolean;
  labEnabled: boolean;
  binderUrl?: string;
  environment: 'github-pages' | 'rasqberry' | 'custom' | 'unknown';
}

const STORAGE_KEY_URL = 'rasqberry_jupyter_url';
const STORAGE_KEY_TOKEN = 'rasqberry_jupyter_token';

const STORAGE_KEY_IBM_TOKEN = 'doqumentation_ibm_token';
const STORAGE_KEY_IBM_CRN = 'doqumentation_ibm_crn';
const STORAGE_KEY_IBM_SAVED_AT = 'doqumentation_ibm_saved_at';
const STORAGE_KEY_SIM_MODE = 'doqumentation_simulator_mode';
const STORAGE_KEY_SIM_BACKEND = 'doqumentation_simulator_backend';
const STORAGE_KEY_FAKE_DEVICE = 'doqumentation_fake_device';
const STORAGE_KEY_FAKE_BACKENDS_CACHE = 'doqumentation_fake_backends';
const STORAGE_KEY_ACTIVE_MODE = 'doqumentation_active_mode';

const STORAGE_KEY_IBM_TTL_DAYS = 'doqumentation_ibm_ttl_days';
const STORAGE_KEY_SUPPRESS_WARNINGS = 'doqumentation_suppress_warnings';
const DEFAULT_TTL_DAYS = 7;

/** All Jupyter storage keys, exported for migration. */
export const ALL_JUPYTER_KEYS = [
  STORAGE_KEY_URL, STORAGE_KEY_TOKEN,
  STORAGE_KEY_IBM_TOKEN, STORAGE_KEY_IBM_CRN, STORAGE_KEY_IBM_SAVED_AT,
  STORAGE_KEY_IBM_TTL_DAYS, STORAGE_KEY_SIM_MODE, STORAGE_KEY_SIM_BACKEND,
  STORAGE_KEY_FAKE_DEVICE, STORAGE_KEY_FAKE_BACKENDS_CACHE,
  STORAGE_KEY_ACTIVE_MODE, STORAGE_KEY_SUPPRESS_WARNINGS,
];

/**
 * Detect the current environment and return appropriate Jupyter config
 */
export function detectJupyterConfig(): JupyterConfig {
  // Server-side rendering check
  if (typeof window === 'undefined') {
    return getDisabledConfig('unknown');
  }

  const hostname = window.location.hostname;

  // Check for user-configured custom Jupyter server
  const customUrl = getItem(STORAGE_KEY_URL);
  if (customUrl) {
    return {
      enabled: true,
      baseUrl: customUrl,
      wsUrl: customUrl.replace(/^http/, 'ws'),
      token: getItem(STORAGE_KEY_TOKEN) || '',
      thebeEnabled: true,
      labEnabled: true,
      environment: 'custom',
    };
  }

  // GitHub Pages / custom domain detection
  if (
    hostname.includes('github.io') ||
    hostname.includes('githubusercontent.com') ||
    hostname.endsWith('doqumentation.org')
  ) {
    return {
      enabled: true,
      baseUrl: '',
      wsUrl: '',
      token: '',
      thebeEnabled: true, // Can use Binder
      labEnabled: false,  // No direct Lab access
      binderUrl: 'https://mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks',
      environment: 'github-pages',
    };
  }

  // RasQberry / Local Pi / Docker detection
  if (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.includes('rasqberry') ||
    hostname.endsWith('.local') ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    hostname.startsWith('172.')
  ) {
    const port = window.location.port;
    // Docker container: nginx proxies /api/ to Jupyter on same origin
    // (site served on a mapped port like 8080, not the default 80/443)
    const isDocker = port && port !== '80' && port !== '443' && port !== '8888';
    const origin = window.location.origin;

    return {
      enabled: true,
      baseUrl: isDocker ? origin : `http://${hostname}:8888`,
      wsUrl: isDocker ? origin.replace(/^http/, 'ws') : `ws://${hostname}:8888`,
      token: isDocker ? '' : 'rasqberry',
      thebeEnabled: true,
      labEnabled: true,
      environment: 'rasqberry',
    };
  }

  // Unknown environment - read only
  return getDisabledConfig('unknown');
}

function getDisabledConfig(environment: JupyterConfig['environment']): JupyterConfig {
  return {
    enabled: false,
    baseUrl: '',
    wsUrl: '',
    token: '',
    thebeEnabled: false,
    labEnabled: false,
    environment,
  };
}

/**
 * Save custom Jupyter server configuration
 */
export function saveJupyterConfig(url: string, token: string): void {
  if (typeof window === 'undefined') return;

  if (url) {
    setItem(STORAGE_KEY_URL, url);
    setItem(STORAGE_KEY_TOKEN, token);
  } else {
    removeItem(STORAGE_KEY_URL);
    removeItem(STORAGE_KEY_TOKEN);
  }
}

/**
 * Clear custom Jupyter server configuration
 */
export function clearJupyterConfig(): void {
  if (typeof window === 'undefined') return;

  removeItem(STORAGE_KEY_URL);
  removeItem(STORAGE_KEY_TOKEN);
}

// ── IBM Quantum credential storage ──

export function getSuppressWarnings(): boolean {
  if (typeof window === 'undefined') return true;
  const stored = getItem(STORAGE_KEY_SUPPRESS_WARNINGS);
  return stored === null ? true : stored === 'true';
}

export function setSuppressWarnings(suppress: boolean): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_SUPPRESS_WARNINGS, String(suppress));
}

export function getCredentialTTLDays(): number {
  if (typeof window === 'undefined') return DEFAULT_TTL_DAYS;
  const stored = getItem(STORAGE_KEY_IBM_TTL_DAYS);
  return stored ? Number(stored) : DEFAULT_TTL_DAYS;
}

export function setCredentialTTLDays(days: number): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_IBM_TTL_DAYS, String(days));
}

function getCredentialTTLMs(): number {
  return getCredentialTTLDays() * 24 * 60 * 60 * 1000;
}

/** Check if credentials have expired. Auto-clears if expired. */
function checkCredentialExpiry(): boolean {
  const savedAt = getItem(STORAGE_KEY_IBM_SAVED_AT);
  if (!savedAt) return false;
  if (Date.now() - Number(savedAt) > getCredentialTTLMs()) {
    clearIBMQuantumCredentials();
    return true;
  }
  return false;
}

export function getIBMQuantumToken(): string {
  if (typeof window === 'undefined') return '';
  checkCredentialExpiry();
  return getItem(STORAGE_KEY_IBM_TOKEN) || '';
}

export function getIBMQuantumCRN(): string {
  if (typeof window === 'undefined') return '';
  return getItem(STORAGE_KEY_IBM_CRN) || '';
}

export function getCredentialDaysRemaining(): number {
  if (typeof window === 'undefined') return -1;
  const savedAt = getItem(STORAGE_KEY_IBM_SAVED_AT);
  if (!savedAt) return -1;
  const remaining = getCredentialTTLMs() - (Date.now() - Number(savedAt));
  return Math.max(0, Math.ceil(remaining / (24 * 60 * 60 * 1000)));
}

export function saveIBMQuantumCredentials(token: string, crn: string): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_IBM_TOKEN, token);
  setItem(STORAGE_KEY_IBM_CRN, crn);
  setItem(STORAGE_KEY_IBM_SAVED_AT, String(Date.now()));
}

export function clearIBMQuantumCredentials(): void {
  if (typeof window === 'undefined') return;
  removeItem(STORAGE_KEY_IBM_TOKEN);
  removeItem(STORAGE_KEY_IBM_CRN);
  removeItem(STORAGE_KEY_IBM_SAVED_AT);
}

// ── Simulator mode ──

export type SimulatorBackend = 'aer' | 'fake';

export function getSimulatorMode(): boolean {
  if (typeof window === 'undefined') return false;
  return getItem(STORAGE_KEY_SIM_MODE) === 'true';
}

export function setSimulatorMode(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  if (enabled) {
    setItem(STORAGE_KEY_SIM_MODE, 'true');
  } else {
    removeItem(STORAGE_KEY_SIM_MODE);
  }
}

export function getSimulatorBackend(): SimulatorBackend {
  if (typeof window === 'undefined') return 'aer';
  return (getItem(STORAGE_KEY_SIM_BACKEND) as SimulatorBackend) || 'aer';
}

export function setSimulatorBackend(backend: SimulatorBackend): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_SIM_BACKEND, backend);
}

export function getFakeDevice(): string {
  if (typeof window === 'undefined') return 'FakeSherbrooke';
  return getItem(STORAGE_KEY_FAKE_DEVICE) || 'FakeSherbrooke';
}

export function setFakeDevice(name: string): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_FAKE_DEVICE, name);
}

export function getCachedFakeBackends(): Array<{name: string; qubits: number}> | null {
  if (typeof window === 'undefined') return null;
  const cached = getItem(STORAGE_KEY_FAKE_BACKENDS_CACHE);
  return cached ? JSON.parse(cached) : null;
}

export function setCachedFakeBackends(backends: Array<{name: string; qubits: number}>): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_FAKE_BACKENDS_CACHE, JSON.stringify(backends));
}

// ── Active mode (conflict resolution when both credentials + simulator set) ──

export type ActiveMode = 'credentials' | 'simulator';

export function getActiveMode(): ActiveMode | null {
  if (typeof window === 'undefined') return null;
  return getItem(STORAGE_KEY_ACTIVE_MODE) as ActiveMode | null;
}

export function setActiveMode(mode: ActiveMode | null): void {
  if (typeof window === 'undefined') return;
  if (mode) {
    setItem(STORAGE_KEY_ACTIVE_MODE, mode);
  } else {
    removeItem(STORAGE_KEY_ACTIVE_MODE);
  }
}

/**
 * Test connection to a Jupyter server
 */
export async function testJupyterConnection(url: string, token: string): Promise<{
  success: boolean;
  message: string;
}> {
  try {
    const apiUrl = `${url}/api/status`;
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = `token ${token}`;
    }

    const response = await fetch(apiUrl, {
      method: 'GET',
      headers,
      mode: 'cors',
    });

    if (response.ok) {
      const data = await response.json();
      return {
        success: true,
        message: `Connected! Jupyter version: ${data.version || 'unknown'}`,
      };
    } else {
      return {
        success: false,
        message: `Connection failed: ${response.status} ${response.statusText}`,
      };
    }
  } catch (error) {
    return {
      success: false,
      message: `Connection error: ${error instanceof Error ? error.message : 'Unknown error'}`,
    };
  }
}

/**
 * Get the JupyterLab URL for a specific notebook
 */
export function getLabUrl(config: JupyterConfig, notebookPath: string): string | null {
  if (!config.labEnabled || !config.baseUrl) {
    return null;
  }

  const encodedPath = notebookPath.split('/').map(encodeURIComponent).join('/');
  const tokenParam = config.token ? `?token=${encodeURIComponent(config.token)}` : '';
  return `${config.baseUrl}/lab/tree/${encodedPath}${tokenParam}`;
}

/**
 * Get the Binder JupyterLab URL for a specific notebook.
 * Opens enhanced notebooks from the doQumentation notebooks branch.
 * Locale-aware: translated notebooks live under {locale}/ prefix.
 */
export function getBinderLabUrl(config: JupyterConfig, notebookPath: string, locale?: string): string | null {
  if (!config.binderUrl) return null;
  const fullPath = mapBinderNotebookPath(notebookPath, locale);
  return `${config.binderUrl}?labpath=${encodeURIComponent(fullPath)}`;
}

// ── Binder session reuse ──

export interface BinderSession {
  url: string;      // e.g. "https://hub.2i2c.mybinder.org/user/janlahmann-doqumentation-HASH/"
  token: string;
  lastUsed: number; // Date.now()
}

const BINDER_SESSION_KEY = 'dq-binder-session';
const BINDER_IDLE_LIMIT = 8 * 60 * 1000; // 8 min (safety margin before 10 min Binder timeout)

export function getBinderSession(): BinderSession | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(BINDER_SESSION_KEY);
    if (!raw) return null;
    const session: BinderSession = JSON.parse(raw);
    if (Date.now() - session.lastUsed > BINDER_IDLE_LIMIT) {
      sessionStorage.removeItem(BINDER_SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

function saveBinderSession(url: string, token: string): void {
  sessionStorage.setItem(BINDER_SESSION_KEY, JSON.stringify({
    url, token, lastUsed: Date.now(),
  }));
}

export function touchBinderSession(): void {
  const session = getBinderSession();
  if (session) {
    session.lastUsed = Date.now();
    sessionStorage.setItem(BINDER_SESSION_KEY, JSON.stringify(session));
  }
}

/** Map notebookPath to the notebooks branch layout (shared with getBinderLabUrl). */
export function mapBinderNotebookPath(notebookPath: string, locale?: string): string {
  let nbPath = notebookPath.replace(/^docs\//, '');
  if (!nbPath.includes('/')) {
    nbPath = `tutorials/${nbPath}`;
  }
  return locale && locale !== 'en' ? `${locale}/${nbPath}` : nbPath;
}

/**
 * Ensure a Binder session exists — return existing or start a new build.
 * Shared by both "Open in Binder JupyterLab" and thebelab code execution.
 */
export function ensureBinderSession(
  config: JupyterConfig,
  onProgress?: (phase: string) => void,
): Promise<BinderSession> {
  const existing = getBinderSession();
  if (existing) {
    touchBinderSession();
    onProgress?.('ready');
    return Promise.resolve(existing);
  }

  if (!config.binderUrl) return Promise.reject(new Error('No Binder URL'));

  return new Promise((resolve, reject) => {
    const buildUrl = config.binderUrl!.replace('/v2/', '/build/');
    onProgress?.('connecting');
    const es = new EventSource(buildUrl);
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.phase) onProgress?.(data.phase);
        if (data.phase === 'ready' && data.url && data.token) {
          saveBinderSession(data.url, data.token);
          es.close();
          resolve({ url: data.url, token: data.token, lastUsed: Date.now() });
        }
        if (data.phase === 'failed') {
          es.close();
          reject(new Error('Binder build failed'));
        }
      } catch { /* ignore parse errors from heartbeat comments */ }
    };
    es.onerror = () => {
      onProgress?.('failed');
      es.close();
      reject(new Error('Binder connection error'));
    };
  });
}

/**
 * Open a notebook in Binder JupyterLab, reusing an existing session if available.
 *
 * First call: starts a Binder build via SSE, stores the session URL + token,
 * and opens JupyterLab in a new tab when ready.
 * Subsequent calls (within 8 min): opens directly in a new tab on the same server.
 */
export function openBinderLab(
  config: JupyterConfig,
  notebookPath: string,
  locale?: string,
  onProgress?: (phase: string) => void,
): void {
  const nbPath = mapBinderNotebookPath(notebookPath, locale);

  ensureBinderSession(config, onProgress).then((session) => {
    const labUrl = `${session.url}lab/tree/${nbPath}?token=${session.token}`;
    window.open(labUrl, '_blank');
    onProgress?.('ready');
  }).catch(() => { /* onProgress('failed') already called by ensureBinderSession */ });
}

/**
 * Get the Google Colab URL for a notebook.
 * Uses the /github/ scheme (Colab's /url/ scheme blocks non-GitHub domains).
 * Points to processed notebooks with pip install cells injected.
 * EN: main repo notebooks branch. Translated: satellite repo gh-pages branch.
 */
export function getColabUrl(notebookPath: string, locale?: string): string {
  // Map Binder-repo path → site notebooks/ path:
  //   "docs/tutorials/foo.ipynb" → "tutorials/foo.ipynb"
  //   "hello-world.ipynb" → "tutorials/hello-world.ipynb"
  //   "learning/courses/bar.ipynb" → "learning/courses/bar.ipynb"
  let nbPath = notebookPath.replace(/^docs\//, '');
  if (!nbPath.includes('/')) {
    nbPath = `tutorials/${nbPath}`;
  }
  if (locale && locale !== 'en') {
    return `https://colab.research.google.com/github/JanLahmann/doqumentation-${locale}/blob/gh-pages/notebooks/${nbPath}`;
  }
  return `https://colab.research.google.com/github/JanLahmann/doQumentation/blob/notebooks/${nbPath}`;
}
