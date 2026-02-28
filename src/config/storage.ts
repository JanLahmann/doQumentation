/**
 * Cross-subdomain storage — cookie-backed storage that shares state
 * across *.doqumentation.org subdomains.
 *
 * On doqumentation.org domains: dual-writes to cookies + localStorage.
 * On localhost/Docker/Pi: pure localStorage (no cookies, no overhead).
 *
 * Values > 3.8 KB are automatically chunked across multiple cookies.
 * All operations are SSR-safe and error-swallowing (replaces safeSave).
 */

const COOKIE_DOMAIN = '.doqumentation.org';
const MAX_AGE = 31536000; // 1 year in seconds
const CHUNK_SIZE = 3800; // bytes per cookie (under 4KB limit with metadata)
const MAX_CHUNKS_CLEANUP = 10; // how many stale chunks to clean up beyond current count

// ── In-memory cache ──

let cache: Map<string, string> | null = null;

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

/** Whether we should use cookies for cross-subdomain sharing. */
function shouldUseCookies(): boolean {
  if (!isBrowser()) return false;
  return window.location.hostname.endsWith('doqumentation.org');
}

// ── Cookie primitives ──

function parseCookies(): Map<string, string> {
  const map = new Map<string, string>();
  if (!isBrowser()) return map;
  const pairs = document.cookie.split('; ');
  for (const pair of pairs) {
    if (!pair) continue;
    const eqIdx = pair.indexOf('=');
    if (eqIdx < 0) continue;
    const key = pair.slice(0, eqIdx);
    const val = decodeURIComponent(pair.slice(eqIdx + 1));
    map.set(key, val);
  }
  return map;
}

function setCookie(key: string, value: string): void {
  const encoded = encodeURIComponent(value);
  document.cookie =
    `${key}=${encoded}; Domain=${COOKIE_DOMAIN}; Path=/; Secure; SameSite=Lax; Max-Age=${MAX_AGE}`;
}

function deleteCookie(key: string): void {
  document.cookie =
    `${key}=; Domain=${COOKIE_DOMAIN}; Path=/; Secure; SameSite=Lax; Max-Age=0`;
}

// ── Chunking ──

function writeChunkedCookie(key: string, value: string): void {
  if (value.length <= CHUNK_SIZE) {
    // Fits in a single cookie — clean up any old chunks
    setCookie(key, value);
    deleteChunks(key, 0);
  } else {
    // Split into chunks
    const numChunks = Math.ceil(value.length / CHUNK_SIZE);
    for (let i = 0; i < numChunks; i++) {
      setCookie(`${key}__${i}`, value.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE));
    }
    setCookie(`${key}__n`, String(numChunks));
    // Delete the base key cookie (data is in chunks now)
    deleteCookie(key);
    // Clean up any extra old chunks beyond current count
    deleteChunks(key, numChunks);
  }
}

function readChunkedCookie(key: string, cookies: Map<string, string>): string | null {
  // Try simple (non-chunked) cookie first
  const simple = cookies.get(key);
  if (simple !== undefined) return simple;

  // Try chunked
  const nStr = cookies.get(`${key}__n`);
  if (nStr === undefined) return null;
  const n = parseInt(nStr, 10);
  if (isNaN(n) || n <= 0) return null;

  let result = '';
  for (let i = 0; i < n; i++) {
    const chunk = cookies.get(`${key}__${i}`);
    if (chunk === undefined) return null; // corrupted — fall through to localStorage
    result += chunk;
  }
  return result;
}

function deleteChunkedCookie(key: string): void {
  deleteCookie(key);
  // Find and delete chunk cookies
  const cookies = parseCookies();
  const nStr = cookies.get(`${key}__n`);
  const n = nStr ? parseInt(nStr, 10) : 0;
  deleteChunks(key, 0, Math.max(n, MAX_CHUNKS_CLEANUP));
  deleteCookie(`${key}__n`);
}

function deleteChunks(key: string, startFrom: number, maxScan?: number): void {
  const end = startFrom + (maxScan ?? MAX_CHUNKS_CLEANUP);
  for (let i = startFrom; i < end; i++) {
    deleteCookie(`${key}__${i}`);
  }
  if (startFrom === 0) {
    deleteCookie(`${key}__n`);
  }
}

// ── Cache initialization ──

function ensureCache(): Map<string, string> {
  if (cache === null) {
    cache = new Map();
    if (shouldUseCookies()) {
      const cookies = parseCookies();
      // We need to reconstruct values from chunked cookies.
      // Collect all base keys (excluding chunk suffixes).
      const seen = new Set<string>();
      for (const cookieKey of cookies.keys()) {
        const base = cookieKey.replace(/__\d+$/, '').replace(/__n$/, '');
        seen.add(base);
      }
      for (const base of seen) {
        const val = readChunkedCookie(base, cookies);
        if (val !== null) {
          cache.set(base, val);
        }
      }
    }
  }
  return cache;
}

// ── Public API ──

export function getItem(key: string): string | null {
  if (!isBrowser()) return null;
  try {
    if (shouldUseCookies()) {
      const c = ensureCache();
      const val = c.get(key);
      if (val !== undefined) return val;
    }
    // Fallback to localStorage
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function setItem(key: string, value: string): void {
  if (!isBrowser()) return;
  try {
    // Always write to localStorage (fast local cache)
    localStorage.setItem(key, value);
  } catch {
    // QuotaExceededError or SecurityError — continue to cookie write
  }
  try {
    if (shouldUseCookies()) {
      writeChunkedCookie(key, value);
      ensureCache().set(key, value);
    }
  } catch {
    // Cookie write failed — localStorage still has the value
  }
}

export function removeItem(key: string): void {
  if (!isBrowser()) return;
  try {
    localStorage.removeItem(key);
  } catch { /* ignore */ }
  try {
    if (shouldUseCookies()) {
      deleteChunkedCookie(key);
      ensureCache().delete(key);
    }
  } catch { /* ignore */ }
}

/**
 * One-time migration: copy existing localStorage values to cookies.
 * Only runs on doqumentation.org domains. Skips keys already in cookies.
 */
export function migrateLocalStorageToCookies(keys: string[]): void {
  if (!isBrowser() || !shouldUseCookies()) return;
  try {
    const cookies = parseCookies();
    let migrated = 0;
    for (const key of keys) {
      // Skip if already in cookies (simple or chunked)
      if (cookies.has(key) || cookies.has(`${key}__n`)) continue;
      const val = localStorage.getItem(key);
      if (val !== null) {
        writeChunkedCookie(key, val);
        ensureCache().set(key, val);
        migrated++;
      }
    }
    if (migrated > 0 && typeof console !== 'undefined' && console.debug) {
      console.debug(`[doQumentation] Migrated ${migrated} settings to cross-subdomain storage`);
    }
  } catch {
    // Migration is best-effort
  }
}
