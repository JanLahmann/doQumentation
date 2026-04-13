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
  environment: 'github-pages' | 'code-engine' | 'rasqberry' | 'custom' | 'unknown';
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

// Code Engine credential storage
const STORAGE_KEY_CE_URL = 'doqumentation_ce_url';
const STORAGE_KEY_CE_TOKEN = 'doqumentation_ce_token';
const STORAGE_KEY_CE_SAVED_AT = 'doqumentation_ce_saved_at';

// Backend override (user-selected execution backend)
const STORAGE_KEY_BACKEND_OVERRIDE = 'doqumentation_backend_override';

// Workshop pool (multiple CE instances for classroom use)
const STORAGE_KEY_WORKSHOP_POOL = 'doqumentation_workshop_pool';
const SESSION_KEY_WORKSHOP_ASSIGNED = 'dq-workshop-assigned';
const SESSION_KEY_WORKSHOP_POOL_VERSION = 'dq-workshop-pool-version';

// IBM Quantum plan type
const STORAGE_KEY_IBM_PLAN = 'doqumentation_ibm_plan';
const VALID_IBM_PLANS = ['open', 'payg', 'premium'] as const;
export type IBMQuantumPlan = typeof VALID_IBM_PLANS[number];

/** All Jupyter storage keys, exported for migration. */
export const ALL_JUPYTER_KEYS = [
  STORAGE_KEY_URL, STORAGE_KEY_TOKEN,
  STORAGE_KEY_IBM_TOKEN, STORAGE_KEY_IBM_CRN, STORAGE_KEY_IBM_SAVED_AT,
  STORAGE_KEY_IBM_TTL_DAYS, STORAGE_KEY_SIM_MODE, STORAGE_KEY_SIM_BACKEND,
  STORAGE_KEY_FAKE_DEVICE, STORAGE_KEY_FAKE_BACKENDS_CACHE,
  STORAGE_KEY_ACTIVE_MODE, STORAGE_KEY_SUPPRESS_WARNINGS,
  STORAGE_KEY_CE_URL, STORAGE_KEY_CE_TOKEN, STORAGE_KEY_CE_SAVED_AT,
  STORAGE_KEY_BACKEND_OVERRIDE, STORAGE_KEY_IBM_PLAN,
  STORAGE_KEY_WORKSHOP_POOL,
];

/** Metadata for an available backend shown in the backend selector UI. */
export interface AvailableBackend {
  environment: JupyterConfig['environment'];
  label: string;
  detail?: string;
}

const VALID_OVERRIDE_ENVIRONMENTS: JupyterConfig['environment'][] = [
  'custom', 'code-engine', 'github-pages', 'rasqberry',
];

/**
 * Get or set the user's backend override (preferred execution backend).
 * null means auto-detect (default priority: Custom > CE > Binder > Local).
 */
export function getBackendOverride(): JupyterConfig['environment'] | null {
  if (typeof window === 'undefined') return null;
  const val = getItem(STORAGE_KEY_BACKEND_OVERRIDE);
  if (val && VALID_OVERRIDE_ENVIRONMENTS.includes(val as JupyterConfig['environment'])) {
    return val as JupyterConfig['environment'];
  }
  return null;
}

export function setBackendOverride(env: JupyterConfig['environment'] | null): void {
  if (typeof window === 'undefined') return;
  if (env === null) {
    removeItem(STORAGE_KEY_BACKEND_OVERRIDE);
  } else {
    setItem(STORAGE_KEY_BACKEND_OVERRIDE, env);
  }
}

/**
 * Returns all backends that are currently available (have credentials or match hostname).
 * Used by the settings page to show the backend selector when multiple are available.
 */
export function getAvailableBackends(): AvailableBackend[] {
  if (typeof window === 'undefined') return [];
  const backends: AvailableBackend[] = [];
  const hostname = window.location.hostname;

  // Custom server?
  const customUrl = getItem(STORAGE_KEY_URL);
  if (customUrl && /^https?:\/\//i.test(customUrl)) {
    backends.push({ environment: 'custom', label: 'Custom Server', detail: customUrl });
  }

  // Code Engine? Workshop pool takes priority over single URL.
  const workshop = getWorkshopPool();
  if (workshop && workshop.pool.length > 0) {
    backends.push({
      environment: 'code-engine',
      label: 'Code Engine',
      detail: `Workshop (${workshop.pool.length} instances)`,
    });
  } else {
    checkCEExpiry();
    const ceUrl = getItem(STORAGE_KEY_CE_URL);
    if (ceUrl) {
      backends.push({ environment: 'code-engine', label: 'Code Engine', detail: ceUrl });
    }
  }

  // GitHub Pages / doqumentation.org?
  if (isGitHubPagesHostname(hostname)) {
    backends.push({ environment: 'github-pages', label: 'Binder', detail: 'mybinder.org' });
  }

  // Local / RasQberry?
  if (isLocalHostname(hostname)) {
    backends.push({ environment: 'rasqberry', label: 'Local / RasQberry' });
  }

  return backends;
}

function isGitHubPagesHostname(hostname: string): boolean {
  return (
    hostname.includes('github.io') ||
    hostname.includes('githubusercontent.com') ||
    hostname.endsWith('doqumentation.org')
  );
}

function isLocalHostname(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.includes('rasqberry') ||
    hostname.endsWith('.local') ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(hostname)
  );
}

/**
 * Build a JupyterConfig for a specific environment, or null if that
 * environment's prerequisites are not met (e.g. credentials expired).
 */
function buildConfigFor(env: JupyterConfig['environment']): JupyterConfig | null {
  switch (env) {
    case 'custom': {
      const customUrl = getItem(STORAGE_KEY_URL);
      if (!customUrl || !/^https?:\/\//i.test(customUrl)) return null;
      return {
        enabled: true,
        baseUrl: customUrl,
        wsUrl: customUrl.replace(/^http(s?):\/\//, 'ws$1://'),
        token: getItem(STORAGE_KEY_TOKEN) || '',
        thebeEnabled: true,
        labEnabled: true,
        environment: 'custom',
      };
    }
    case 'code-engine': {
      // Workshop pool takes priority over single CE URL
      const wsPool = getWorkshopPool();
      if (wsPool && wsPool.pool.length > 0) {
        const assigned = assignWorkshopInstance();
        if (assigned) {
          return {
            enabled: true,
            baseUrl: assigned,
            wsUrl: assigned.replace(/^http(s?):\/\//, 'ws$1://'),
            token: wsPool.token,
            thebeEnabled: true,
            labEnabled: true,
            binderUrl: assigned + '/build/gh/placeholder',
            environment: 'code-engine',
          };
        }
      }
      // Fall through to single CE URL
      const ceUrl = getItem(STORAGE_KEY_CE_URL);
      if (!ceUrl || !/^https?:\/\//i.test(ceUrl)) return null;
      checkCEExpiry();
      const ceUrlAfterCheck = getItem(STORAGE_KEY_CE_URL);
      if (!ceUrlAfterCheck) return null;
      const ceBase = ceUrlAfterCheck.replace(/\/+$/, '');
      return {
        enabled: true,
        baseUrl: ceBase,
        wsUrl: ceBase.replace(/^http(s?):\/\//, 'ws$1://'),
        token: getItem(STORAGE_KEY_CE_TOKEN) || '',
        thebeEnabled: true,
        labEnabled: true,
        binderUrl: ceBase + '/build/gh/placeholder',
        environment: 'code-engine',
      };
    }
    case 'github-pages': {
      if (!isGitHubPagesHostname(window.location.hostname)) return null;
      return {
        enabled: true,
        baseUrl: '',
        wsUrl: '',
        token: '',
        thebeEnabled: true,
        labEnabled: false,
        binderUrl: 'https://mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks',
        environment: 'github-pages',
      };
    }
    case 'rasqberry': {
      const hostname = window.location.hostname;
      if (!isLocalHostname(hostname)) return null;
      const port = window.location.port;
      const isDocker = port && port !== '80' && port !== '443' && port !== '8888';
      const origin = window.location.origin;
      return {
        enabled: true,
        baseUrl: isDocker ? origin : `http://${hostname}:8888`,
        wsUrl: isDocker ? origin.replace(/^http(s?):\/\//, 'ws$1://') : `ws://${hostname}:8888`,
        token: isDocker ? '' : 'rasqberry',
        thebeEnabled: true,
        labEnabled: true,
        environment: 'rasqberry',
      };
    }
    default:
      return null;
  }
}

/**
 * Detect the current environment and return appropriate Jupyter config.
 * Respects user's backend override if set and still valid.
 */
export function detectJupyterConfig(): JupyterConfig {
  if (typeof window === 'undefined') {
    return getDisabledConfig('unknown');
  }

  // Check user override first
  const override = getBackendOverride();
  if (override) {
    const config = buildConfigFor(override);
    if (config) return config;
    // Override no longer valid (e.g. CE credentials expired) — clear it
    setBackendOverride(null);
  }

  // Auto-detect: Custom > Code Engine > GitHub Pages > Local
  return buildConfigFor('custom')
    ?? buildConfigFor('code-engine')
    ?? buildConfigFor('github-pages')
    ?? buildConfigFor('rasqberry')
    ?? getDisabledConfig('unknown');
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
  if (!stored) return DEFAULT_TTL_DAYS;
  const n = Number(stored);
  return isFinite(n) && n >= 1 && n <= 365 ? n : DEFAULT_TTL_DAYS;
}

export function setCredentialTTLDays(days: number): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_IBM_TTL_DAYS, String(days));
}

export function getIBMQuantumPlan(): IBMQuantumPlan {
  if (typeof window === 'undefined') return 'open';
  const stored = getItem(STORAGE_KEY_IBM_PLAN);
  return stored && (VALID_IBM_PLANS as readonly string[]).includes(stored)
    ? (stored as IBMQuantumPlan)
    : 'open';
}

export function setIBMQuantumPlan(plan: IBMQuantumPlan): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_IBM_PLAN, plan);
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
  checkCredentialExpiry();
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

// ── Code Engine credential storage ──

/** Check if CE credentials have expired. Auto-clears if expired. Uses same TTL as IBM credentials. */
function checkCEExpiry(): boolean {
  const savedAt = getItem(STORAGE_KEY_CE_SAVED_AT);
  if (!savedAt) return false;
  if (Date.now() - Number(savedAt) > getCredentialTTLMs()) {
    clearCodeEngineCredentials();
    return true;
  }
  return false;
}

export function getCodeEngineUrl(): string {
  if (typeof window === 'undefined') return '';
  checkCEExpiry();
  return getItem(STORAGE_KEY_CE_URL) || '';
}

export function getCodeEngineToken(): string {
  if (typeof window === 'undefined') return '';
  checkCEExpiry();
  return getItem(STORAGE_KEY_CE_TOKEN) || '';
}

export function saveCodeEngineCredentials(url: string, token: string): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_CE_URL, url.replace(/\/+$/, ''));
  setItem(STORAGE_KEY_CE_TOKEN, token);
  setItem(STORAGE_KEY_CE_SAVED_AT, String(Date.now()));
}

export function clearCodeEngineCredentials(): void {
  if (typeof window === 'undefined') return;
  removeItem(STORAGE_KEY_CE_URL);
  removeItem(STORAGE_KEY_CE_TOKEN);
  removeItem(STORAGE_KEY_CE_SAVED_AT);
}

export function getCEDaysRemaining(): number {
  if (typeof window === 'undefined') return -1;
  const savedAt = getItem(STORAGE_KEY_CE_SAVED_AT);
  if (!savedAt) return -1;
  const remaining = getCredentialTTLMs() - (Date.now() - Number(savedAt));
  return Math.max(0, Math.ceil(remaining / (24 * 60 * 60 * 1000)));
}

// ── Workshop pool (multi-instance Code Engine for classrooms) ──

export interface WorkshopPool {
  pool: string[];
  token: string;
  version: number;
}

/** Save a workshop pool configuration. Validates that all URLs are https. */
export function saveWorkshopPool(pool: string[], token: string): void {
  if (typeof window === 'undefined') return;
  const validated = pool
    .map(u => u.replace(/\/+$/, ''))
    .filter(u => /^https:\/\//i.test(u));
  if (validated.length === 0) return;
  const existing = getWorkshopPool();
  const version = existing ? existing.version + 1 : 1;
  setItem(STORAGE_KEY_WORKSHOP_POOL, JSON.stringify({ pool: validated, token, version }));
}

/** Read the current workshop pool, or null if not configured. */
export function getWorkshopPool(): WorkshopPool | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = getItem(STORAGE_KEY_WORKSHOP_POOL);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed.pool) && parsed.pool.length > 0) return parsed;
    return null;
  } catch {
    return null;
  }
}

/** Clear the workshop pool and session assignment. */
export function clearWorkshopPool(): void {
  if (typeof window === 'undefined') return;
  removeItem(STORAGE_KEY_WORKSHOP_POOL);
  try {
    sessionStorage.removeItem(SESSION_KEY_WORKSHOP_ASSIGNED);
    sessionStorage.removeItem(SESSION_KEY_WORKSHOP_POOL_VERSION);
  } catch { /* ignore */ }
}

/**
 * Get or assign an instance from the workshop pool for this tab.
 * Sticky via sessionStorage — once assigned, this tab stays on the same instance.
 * Re-assigns if the pool version has changed or the assigned URL is no longer in the pool.
 */
export function assignWorkshopInstance(): string | null {
  if (typeof window === 'undefined') return null;
  const pool = getWorkshopPool();
  if (!pool || pool.pool.length === 0) return null;

  try {
    const current = sessionStorage.getItem(SESSION_KEY_WORKSHOP_ASSIGNED);
    const savedVersion = sessionStorage.getItem(SESSION_KEY_WORKSHOP_POOL_VERSION);

    // Keep current assignment if still valid and pool version matches
    if (current && pool.pool.includes(current) && savedVersion === String(pool.version)) {
      return current;
    }

    // Assign: pick random instance
    const idx = Math.floor(Math.random() * pool.pool.length);
    const assigned = pool.pool[idx];
    sessionStorage.setItem(SESSION_KEY_WORKSHOP_ASSIGNED, assigned);
    sessionStorage.setItem(SESSION_KEY_WORKSHOP_POOL_VERSION, String(pool.version));
    return assigned;
  } catch {
    // sessionStorage unavailable — pick random without sticking
    return pool.pool[Math.floor(Math.random() * pool.pool.length)];
  }
}

/** Get the currently assigned workshop instance for this tab, without assigning a new one. */
export function getWorkshopAssignment(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return sessionStorage.getItem(SESSION_KEY_WORKSHOP_ASSIGNED);
  } catch {
    return null;
  }
}

/** Stats for a single workshop instance, returned by the /stats endpoint. */
export type InstanceStats = {
  url: string;
  kernels: number;
  kernelsBusy: number;
  connections: number;
  uptimeSeconds: number;
  memoryMb: number | null;
  memoryTotalMb: number | null;
  peakKernels: number;
  peakConnections: number;
  totalSseConnections: number;
  status: 'online' | 'starting' | 'offline';
};

const OFFLINE_STATS: Omit<InstanceStats, 'url' | 'status'> = {
  kernels: 0, kernelsBusy: 0, connections: 0, uptimeSeconds: 0,
  memoryMb: null, memoryTotalMb: null,
  peakKernels: 0, peakConnections: 0, totalSseConnections: 0,
};

/**
 * Query /stats on each instance in the pool. Returns enriched stats per instance.
 * Used by the organizer dashboard and optionally for load-aware assignment.
 */
export async function getWorkshopInstanceStats(
  pool: string[],
): Promise<InstanceStats[]> {
  const results = await Promise.all(
    pool.map(async (url): Promise<InstanceStats> => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        const resp = await fetch(`${url}/stats`, { signal: controller.signal, mode: 'cors' });
        clearTimeout(timeout);
        if (resp.ok) {
          const data = await resp.json();
          return {
            url,
            kernels: data.kernels ?? 0,
            kernelsBusy: data.kernels_busy ?? 0,
            connections: data.connections ?? 0,
            uptimeSeconds: data.uptime_seconds ?? 0,
            memoryMb: data.memory_mb ?? null,
            memoryTotalMb: data.memory_total_mb ?? null,
            peakKernels: data.peak_kernels ?? 0,
            peakConnections: data.peak_connections ?? 0,
            totalSseConnections: data.total_sse_connections ?? 0,
            status: 'online',
          };
        }
        if (resp.status === 502 || resp.status === 503) {
          return { url, ...OFFLINE_STATS, status: 'starting' };
        }
        return { url, ...OFFLINE_STATS, status: 'offline' };
      } catch {
        return { url, ...OFFLINE_STATS, status: 'offline' };
      }
    }),
  );
  return results;
}

// ── Simulator mode ──

export type SimulatorBackend = 'aer' | 'fake';

export function getSimulatorMode(): boolean {
  if (typeof window === 'undefined') return false;
  const stored = getItem(STORAGE_KEY_SIM_MODE);
  return stored === null ? true : stored === 'true';
}

export function setSimulatorMode(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_SIM_MODE, String(enabled));
}

const VALID_SIMULATOR_BACKENDS: readonly SimulatorBackend[] = ['aer', 'fake'];

export function getSimulatorBackend(): SimulatorBackend {
  if (typeof window === 'undefined') return 'aer';
  const stored = getItem(STORAGE_KEY_SIM_BACKEND);
  return stored && VALID_SIMULATOR_BACKENDS.includes(stored as SimulatorBackend)
    ? (stored as SimulatorBackend)
    : 'aer';
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
  try {
    const cached = getItem(STORAGE_KEY_FAKE_BACKENDS_CACHE);
    return cached ? JSON.parse(cached) : null;
  } catch {
    return null;
  }
}

export function setCachedFakeBackends(backends: Array<{name: string; qubits: number}>): void {
  if (typeof window === 'undefined') return;
  setItem(STORAGE_KEY_FAKE_BACKENDS_CACHE, JSON.stringify(backends));
}

// ── Active mode (conflict resolution when both credentials + simulator set) ──

export type ActiveMode = 'credentials' | 'simulator';

const VALID_ACTIVE_MODES: readonly ActiveMode[] = ['credentials', 'simulator'];

export function getActiveMode(): ActiveMode | null {
  if (typeof window === 'undefined') return null;
  const stored = getItem(STORAGE_KEY_ACTIVE_MODE);
  return stored && VALID_ACTIVE_MODES.includes(stored as ActiveMode)
    ? (stored as ActiveMode)
    : null;
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
export async function testJupyterConnection(
  url: string,
  token: string,
  onStatus?: (message: string) => void,
): Promise<{
  success: boolean;
  message: string;
}> {
  const headers: HeadersInit = {};
  if (token) {
    headers['Authorization'] = `token ${token}`;
  }
  const apiUrl = `${url}/api/status`;

  // Retry up to 6 times (total ~90s) to handle CE cold starts.
  const maxAttempts = 6;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      if (attempt === 1) {
        onStatus?.('Connecting...');
      } else {
        onStatus?.(`Server is starting up... (attempt ${attempt}/${maxAttempts})`);
      }

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers,
        mode: 'cors',
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (response.ok) {
        return { success: true, message: 'Connected!' };
      } else if (response.status === 502 || response.status === 503) {
        // Server starting up — retry
        if (attempt < maxAttempts) continue;
        return {
          success: false,
          message: `Server not ready after ${maxAttempts} attempts (${response.status}). Try again in a moment.`,
        };
      } else {
        return {
          success: false,
          message: `Connection failed: ${response.status} ${response.statusText}`,
        };
      }
    } catch (error) {
      // Timeout or network error — retry on cold start
      if (attempt < maxAttempts) continue;
      return {
        success: false,
        message: `Connection error: ${error instanceof Error ? error.message : 'Unknown error'}`,
      };
    }
  }
  return { success: false, message: 'Connection failed after all attempts.' };
}

/**
 * Get the JupyterLab URL for a specific notebook
 */
export function getLabUrl(config: JupyterConfig, notebookPath: string): string | null {
  if (!config.labEnabled || !config.baseUrl) {
    return null;
  }

  // Notebook path maps directly to the container/notebooks branch layout
  // (e.g. tutorials/hello-world.ipynb). Bare names get tutorials/ prefix.
  const cleanPath = mapBinderNotebookPath(notebookPath);
  const encodedPath = cleanPath.split('/').map(encodeURIComponent).join('/');
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

export function clearBinderSession(): void {
  sessionStorage.removeItem(BINDER_SESSION_KEY);
}

/** Map notebookPath to the notebooks branch layout. Bare names get tutorials/ prefix. */
export function mapBinderNotebookPath(notebookPath: string, locale?: string): string {
  let nbPath = notebookPath;
  if (!nbPath.includes('/')) {
    nbPath = `tutorials/${nbPath}`;
  }
  return locale && locale !== 'en' ? `${locale}/${nbPath}` : nbPath;
}

/** Active Binder EventSource — stored so it can be cancelled externally. */
let activeBinderES: EventSource | null = null;

/** Cancel an in-progress Binder build. Safe to call when no build is active. */
export function cancelBinderBuild(): void {
  if (activeBinderES) {
    activeBinderES.close();
    activeBinderES = null;
  }
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
    // Probe the server to confirm the container is still alive.
    // A dead/culled container returns a network error or non-200 status.
    return fetch(`${existing.url}api/status?token=${encodeURIComponent(existing.token)}`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    }).then((resp) => {
      if (resp.ok) {
        touchBinderSession();
        onProgress?.('ready');
        return existing;
      }
      // Server responded but session is invalid — clear and rebuild
      clearBinderSession();
      return ensureBinderSession(config, onProgress);
    }).catch(() => {
      // Network error / timeout — container is gone, clear and rebuild
      clearBinderSession();
      return ensureBinderSession(config, onProgress);
    });
  }

  if (!config.binderUrl) return Promise.reject(new Error('No Binder URL'));

  return new Promise((resolve, reject) => {
    const buildUrl = config.binderUrl!.replace('/v2/', '/build/');
    onProgress?.('connecting');
    const es = new EventSource(buildUrl);
    activeBinderES = es;
    let settled = false;

    const cleanup = () => {
      activeBinderES = null;
    };

    // 20-minute timeout — Binder builds can be slow but shouldn't hang forever
    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      onProgress?.('failed');
      es.close();
      reject(new Error('Binder build timed out after 20 minutes'));
    }, 20 * 60 * 1000);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.phase) onProgress?.(data.phase);
        if (data.phase === 'ready' && data.url && data.token) {
          settled = true;
          clearTimeout(timeout);
          cleanup();
          saveBinderSession(data.url, data.token);
          es.close();
          resolve({ url: data.url, token: data.token, lastUsed: Date.now() });
        }
        if (data.phase === 'failed') {
          settled = true;
          clearTimeout(timeout);
          cleanup();
          es.close();
          reject(new Error('Binder build failed'));
        }
      } catch { /* ignore parse errors from heartbeat comments */ }
    };
    es.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      cleanup();
      es.close();

      // Workshop failover: try next instance in the pool
      const wsPool = getWorkshopPool();
      if (wsPool && wsPool.pool.length > 1) {
        const current = getWorkshopAssignment();
        const currentIdx = current ? wsPool.pool.indexOf(current) : -1;
        const nextIdx = (currentIdx + 1) % wsPool.pool.length;
        const next = wsPool.pool[nextIdx];
        try {
          sessionStorage.setItem(SESSION_KEY_WORKSHOP_ASSIGNED, next);
        } catch { /* ignore */ }
        // Rebuild config with new instance and retry once
        const retryConfig: JupyterConfig = {
          ...config,
          baseUrl: next,
          wsUrl: next.replace(/^http(s?):\/\//, 'ws$1://'),
          token: wsPool.token,
          binderUrl: next + '/build/gh/placeholder',
        };
        onProgress?.('connecting');
        ensureBinderSession(retryConfig, onProgress).then(resolve).catch(reject);
        return;
      }

      onProgress?.('failed');
      reject(new Error('Binder connection error'));
    };
  });
}

/**
 * Open a notebook in Binder JupyterLab, reusing an existing session if available.
 *
 * Opens a blank tab immediately (to avoid popup blockers — window.open must be
 * called synchronously from the user click handler), then navigates it to
 * JupyterLab when the Binder session is ready.
 *
 * First call: starts a Binder build via SSE, stores the session URL + token,
 * and navigates the tab to JupyterLab when ready.
 * Subsequent calls (within 8 min): navigates directly (session already exists).
 */
/** Default English phase hints for the CE loading tab */
const CE_TAB_PHASE_HINTS: Record<string, string> = {
  connecting: 'Connecting to Code Engine\u2026',
  launching:  'Starting Jupyter server\u2026',
  ready:      'Connected!',
};

/** Default English phase hints for the Binder loading tab */
const BINDER_TAB_PHASE_HINTS: Record<string, string> = {
  connecting: 'Connecting to mybinder.org\u2026',
  waiting:    'Waiting in queue\u2026',
  fetching:   'Fetching repository (2\u20135 min)\u2026',
  building:   'Building Docker image (5\u201310 min)\u2026',
  pushing:    'Pushing image to registry (2\u20135 min)\u2026',
  built:      'Image ready \u2014 launching JupyterLab\u2026',
  launching:  'Starting JupyterLab server (2\u20135 min)\u2026',
};

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function makeTabHtml(title: string, initialPhase: string): string {
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  body { font-family: system-ui, sans-serif; padding: 2rem; color: #333; background: #fafafa; }
  #phase { font-size: 1.1rem; margin-bottom: 0.5rem; }
  #elapsed { font-size: 0.9rem; color: #888; }
  #warning { margin-top: 1rem; padding: 0.75rem 1rem; border-radius: 6px;
    background: #fff8e1; border: 1px solid #ffe082; color: #b45309; display: none; }
</style></head><body>
  <div id="phase">${escapeHtml(initialPhase)}</div>
  <div id="elapsed"></div>
  <div id="warning">\u26a0 Cache not warmed \u2014 total build time 10\u201325 min.
    Close this tab and use Colab instead, or come back later.</div>
</body></html>`;
}

function formatElapsedCompact(s: number): string {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r > 0 ? `${m}m ${r}s` : `${m}m`;
}

export function openBinderLab(
  config: JupyterConfig,
  notebookPath: string,
  locale?: string,
  onProgress?: (phase: string) => void,
): void {
  const nbPath = mapBinderNotebookPath(notebookPath, locale);
  const isCE = config.environment === 'code-engine';
  const phaseHints = isCE ? CE_TAB_PHASE_HINTS : BINDER_TAB_PHASE_HINTS;
  const tabTitle = isCE ? 'Starting Code Engine\u2026' : 'Starting Binder\u2026';
  const initialPhase = isCE ? 'Connecting to Code Engine\u2026' : 'Connecting to mybinder.org\u2026';

  // Open tab synchronously from click handler to avoid popup blockers.
  const tab = window.open('about:blank', '_blank');
  if (tab) {
    tab.document.open();
    tab.document.write(makeTabHtml(tabTitle, initialPhase));
    tab.document.close();
  }

  const startTime = Date.now();
  let timerInterval: ReturnType<typeof setInterval> | null = null;

  // Start elapsed timer in the tab
  if (tab) {
    timerInterval = setInterval(() => {
      if (tab.closed) { if (timerInterval) clearInterval(timerInterval); return; }
      try {
        const el = tab.document.getElementById('elapsed');
        if (el) el.textContent = formatElapsedCompact(Math.floor((Date.now() - startTime) / 1000));
      } catch { /* tab navigated away or closed */ }
    }, 1000);
  }

  ensureBinderSession(config, (phase) => {
    onProgress?.(phase);
    if (!tab || tab.closed) return;
    try {
      const phaseEl = tab.document.getElementById('phase');
      if (phaseEl) phaseEl.textContent = phaseHints[phase] || phase;
      if (phase === 'building') {
        const warn = tab.document.getElementById('warning');
        if (warn) warn.style.display = 'block';
      }
    } catch { /* tab navigated away */ }
  }).then((session) => {
    if (timerInterval) clearInterval(timerInterval);
    const encodedNbPath = nbPath.split('/').map(encodeURIComponent).join('/');
    const labUrl = `${session.url}lab/tree/${encodedNbPath}?token=${encodeURIComponent(session.token)}`;
    if (tab && !tab.closed) {
      tab.location.href = labUrl;
    } else {
      window.open(labUrl, '_blank');
    }
    onProgress?.('ready');
  }).catch(() => {
    if (timerInterval) clearInterval(timerInterval);
    if (tab && !tab.closed) {
      try {
        const phaseEl = tab.document.getElementById('phase');
        if (phaseEl) {
          phaseEl.textContent = isCE
            ? 'Code Engine connection failed. Close this tab and check your settings.'
            : 'Binder build failed. Close this tab and try again, or use Colab.';
          phaseEl.style.color = '#d32f2f';
        }
      } catch { tab.close(); }
    }
  });
}

/**
 * Get the Google Colab URL for a notebook.
 * Uses the /github/ scheme (Colab's /url/ scheme blocks non-GitHub domains).
 * Points to processed notebooks with pip install cells injected.
 * EN: main repo notebooks branch. Translated: satellite repo gh-pages branch.
 */
export function getColabUrl(notebookPath: string, locale?: string): string {
  // Reuse shared path mapping (adds tutorials/ prefix for bare names)
  const nbPath = mapBinderNotebookPath(notebookPath);
  if (locale && locale !== 'en') {
    return `https://colab.research.google.com/github/JanLahmann/doqumentation-${locale}/blob/gh-pages/notebooks/${nbPath}`;
  }
  return `https://colab.research.google.com/github/JanLahmann/doQumentation/blob/notebooks/${nbPath}`;
}
