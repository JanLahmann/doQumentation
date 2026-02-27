/**
 * Jupyter Configuration
 * 
 * Handles runtime detection of the execution environment and provides
 * appropriate Jupyter server configuration for:
 * - GitHub Pages (static, optional Binder fallback)
 * - RasQberry Pi (local Jupyter server)
 * - Custom user-configured server
 */

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

/** Wrapper for localStorage.setItem that silently handles QuotaExceededError. */
function safeSave(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // QuotaExceededError or SecurityError — silently fail rather than crash
  }
}

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
  const customUrl = localStorage.getItem(STORAGE_KEY_URL);
  if (customUrl) {
    return {
      enabled: true,
      baseUrl: customUrl,
      wsUrl: customUrl.replace(/^http/, 'ws'),
      token: localStorage.getItem(STORAGE_KEY_TOKEN) || '',
      thebeEnabled: true,
      labEnabled: true,
      environment: 'custom',
    };
  }

  // GitHub Pages / custom domain detection
  if (
    hostname.includes('github.io') ||
    hostname.includes('githubusercontent.com') ||
    hostname === 'doqumentation.org' ||
    hostname === 'www.doqumentation.org'
  ) {
    return {
      enabled: true,
      baseUrl: '',
      wsUrl: '',
      token: '',
      thebeEnabled: true, // Can use Binder
      labEnabled: false,  // No direct Lab access
      binderUrl: 'https://2i2c.mybinder.org/v2/gh/JanLahmann/Qiskit-documentation/main',
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
    safeSave(STORAGE_KEY_URL, url);
    safeSave(STORAGE_KEY_TOKEN, token);
  } else {
    localStorage.removeItem(STORAGE_KEY_URL);
    localStorage.removeItem(STORAGE_KEY_TOKEN);
  }
}

/**
 * Clear custom Jupyter server configuration
 */
export function clearJupyterConfig(): void {
  if (typeof window === 'undefined') return;
  
  localStorage.removeItem(STORAGE_KEY_URL);
  localStorage.removeItem(STORAGE_KEY_TOKEN);
}

// ── IBM Quantum credential storage ──

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

export function getSuppressWarnings(): boolean {
  if (typeof window === 'undefined') return true;
  const stored = localStorage.getItem(STORAGE_KEY_SUPPRESS_WARNINGS);
  return stored === null ? true : stored === 'true';
}

export function setSuppressWarnings(suppress: boolean): void {
  if (typeof window === 'undefined') return;
  safeSave(STORAGE_KEY_SUPPRESS_WARNINGS, String(suppress));
}

export function getCredentialTTLDays(): number {
  if (typeof window === 'undefined') return DEFAULT_TTL_DAYS;
  const stored = localStorage.getItem(STORAGE_KEY_IBM_TTL_DAYS);
  return stored ? Number(stored) : DEFAULT_TTL_DAYS;
}

export function setCredentialTTLDays(days: number): void {
  if (typeof window === 'undefined') return;
  safeSave(STORAGE_KEY_IBM_TTL_DAYS, String(days));
}

function getCredentialTTLMs(): number {
  return getCredentialTTLDays() * 24 * 60 * 60 * 1000;
}

/** Check if credentials have expired. Auto-clears if expired. */
function checkCredentialExpiry(): boolean {
  const savedAt = localStorage.getItem(STORAGE_KEY_IBM_SAVED_AT);
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
  return localStorage.getItem(STORAGE_KEY_IBM_TOKEN) || '';
}

export function getIBMQuantumCRN(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(STORAGE_KEY_IBM_CRN) || '';
}

export function getCredentialDaysRemaining(): number {
  if (typeof window === 'undefined') return -1;
  const savedAt = localStorage.getItem(STORAGE_KEY_IBM_SAVED_AT);
  if (!savedAt) return -1;
  const remaining = getCredentialTTLMs() - (Date.now() - Number(savedAt));
  return Math.max(0, Math.ceil(remaining / (24 * 60 * 60 * 1000)));
}

export function saveIBMQuantumCredentials(token: string, crn: string): void {
  if (typeof window === 'undefined') return;
  safeSave(STORAGE_KEY_IBM_TOKEN, token);
  safeSave(STORAGE_KEY_IBM_CRN, crn);
  safeSave(STORAGE_KEY_IBM_SAVED_AT, String(Date.now()));
}

export function clearIBMQuantumCredentials(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY_IBM_TOKEN);
  localStorage.removeItem(STORAGE_KEY_IBM_CRN);
  localStorage.removeItem(STORAGE_KEY_IBM_SAVED_AT);
}

// ── Simulator mode ──

export type SimulatorBackend = 'aer' | 'fake';

export function getSimulatorMode(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEY_SIM_MODE) === 'true';
}

export function setSimulatorMode(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  if (enabled) {
    safeSave(STORAGE_KEY_SIM_MODE, 'true');
  } else {
    localStorage.removeItem(STORAGE_KEY_SIM_MODE);
  }
}

export function getSimulatorBackend(): SimulatorBackend {
  if (typeof window === 'undefined') return 'aer';
  return (localStorage.getItem(STORAGE_KEY_SIM_BACKEND) as SimulatorBackend) || 'aer';
}

export function setSimulatorBackend(backend: SimulatorBackend): void {
  if (typeof window === 'undefined') return;
  safeSave(STORAGE_KEY_SIM_BACKEND, backend);
}

export function getFakeDevice(): string {
  if (typeof window === 'undefined') return 'FakeSherbrooke';
  return localStorage.getItem(STORAGE_KEY_FAKE_DEVICE) || 'FakeSherbrooke';
}

export function setFakeDevice(name: string): void {
  if (typeof window === 'undefined') return;
  safeSave(STORAGE_KEY_FAKE_DEVICE, name);
}

export function getCachedFakeBackends(): Array<{name: string; qubits: number}> | null {
  if (typeof window === 'undefined') return null;
  const cached = localStorage.getItem(STORAGE_KEY_FAKE_BACKENDS_CACHE);
  return cached ? JSON.parse(cached) : null;
}

export function setCachedFakeBackends(backends: Array<{name: string; qubits: number}>): void {
  if (typeof window === 'undefined') return;
  safeSave(STORAGE_KEY_FAKE_BACKENDS_CACHE, JSON.stringify(backends));
}

// ── Active mode (conflict resolution when both credentials + simulator set) ──

export type ActiveMode = 'credentials' | 'simulator';

export function getActiveMode(): ActiveMode | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(STORAGE_KEY_ACTIVE_MODE) as ActiveMode | null;
}

export function setActiveMode(mode: ActiveMode | null): void {
  if (typeof window === 'undefined') return;
  if (mode) {
    safeSave(STORAGE_KEY_ACTIVE_MODE, mode);
  } else {
    localStorage.removeItem(STORAGE_KEY_ACTIVE_MODE);
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
 * Get the Binder JupyterLab URL for a specific notebook (GitHub Pages).
 * Points to the dependency-ready copy on gh-pages (has install cells).
 */
export function getBinderLabUrl(config: JupyterConfig, notebookPath: string): string | null {
  if (!config.binderUrl) {
    return null;
  }

  // notebookPath is upstream-relative, e.g. "docs/tutorials/hello-world.ipynb"
  // Strip "docs/" prefix to match the notebooks/ directory structure on gh-pages.
  const nbPath = notebookPath.replace(/^docs\//, '');
  const fullPath = `notebooks/${nbPath}`;
  return `${config.binderUrl}?labpath=${encodeURIComponent(fullPath)}`;
}

/**
 * Get the Google Colab URL for a notebook.
 * Points to the dependency-ready copy on gh-pages (has install cells + Colab metadata).
 */
export function getColabUrl(notebookPath: string): string {
  const nbPath = notebookPath.replace(/^docs\//, '');
  return `https://colab.research.google.com/github/JanLahmann/doQumentation/blob/gh-pages/notebooks/${nbPath}`;
}
