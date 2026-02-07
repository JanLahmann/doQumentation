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
    localStorage.setItem(STORAGE_KEY_URL, url);
    localStorage.setItem(STORAGE_KEY_TOKEN, token);
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
  
  const tokenParam = config.token ? `?token=${config.token}` : '';
  return `${config.baseUrl}/lab/tree/${notebookPath}${tokenParam}`;
}

/**
 * Get the classic notebook URL for a specific notebook
 */
export function getNotebookUrl(config: JupyterConfig, notebookPath: string): string | null {
  if (!config.enabled || !config.baseUrl) {
    return null;
  }
  
  const tokenParam = config.token ? `?token=${config.token}` : '';
  return `${config.baseUrl}/notebooks/${notebookPath}${tokenParam}`;
}
