/**
 * Cross-subdomain storage — cookie-backed storage that shares state
 * across *.doqumentation.org subdomains.
 *
 * On doqumentation.org domains: dual-writes to cookies + localStorage.
 * On localhost/Docker/Pi: pure localStorage (no cookies, no overhead).
 *
 * Values > 3.8 KB are automatically chunked across multiple cookies.
 * All operations are SSR-safe and error-swallowing (replaces safeSave).
 *
 * Size guard: cookies travel with every request, and the static host drops a
 * request whose Cookie header is too large (~64 KB; the site then goes blank on
 * every language). A write that would push our cookies past COOKIE_BUDGET is
 * kept in localStorage only (this language site) instead — see setItem.
 */

const COOKIE_DOMAIN = '.doqumentation.org';
const MAX_AGE = 31536000; // 1 year in seconds
const CHUNK_SIZE = 3800; // bytes per cookie (under 4KB limit with metadata)
const MAX_CHUNKS_CLEANUP = 10; // how many stale chunks to clean up beyond current count

/** Total size (name=value pairs as sent in the Cookie header) we allow ourselves. */
export const COOKIE_BUDGET = 8 * 1024;

/**
 * Keys that are NEVER put in a cookie: localStorage only, on the language site
 * where they were saved.
 *
 * - The IBM Quantum API key, CRN and their saved-at time (SECURITY_REVIEW S1):
 *   a cookie would send the key to the static host with every request for a
 *   year and expose it to every *.doqumentation.org page. Decision 2026-10:
 *   credentials are entered per language site; expiry follows the "saved
 *   credentials" period setting (doqumentation_ibm_ttl_days, still shared).
 * - Per-site companions of the compact progress cookies (preferences.ts):
 *   paths outside the page index, and localized bookmark titles.
 *
 * Existing cookies of these keys are moved into localStorage by
 * migrateLocalOnlyCookies() on the site where they are found.
 */
const LOCAL_ONLY_KEYS = new Set<string>([
  'doqumentation_ibm_token',
  'doqumentation_ibm_crn',
  'doqumentation_ibm_saved_at',
  'dq-visited-extra',
  'dq-executed-extra',
  'dq-bookmark-meta',
]);

// NOTE (SECURITY_REVIEW S1): the Jupyter / Code Engine server tokens are still
// shared across `*.doqumentation.org` via cookies (workshop UX). The IBM Quantum
// key is not — see LOCAL_ONLY_KEYS.

export function isLocalOnlyKey(key: string): boolean {
  return LOCAL_ONLY_KEYS.has(key);
}

// ── In-memory cache (rebuilt whenever document.cookie changes) ──

let cache: Map<string, string> | null = null;
let cacheSource: string | null = null;
let warnedOverflow = false;

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

/** Whether we should use cookies for cross-subdomain sharing. */
function shouldUseCookies(): boolean {
  if (!isBrowser()) return false;
  return window.location.hostname.endsWith('doqumentation.org');
}

// ── Cookie primitives ──

function rawCookiePairs(): string[] {
  if (!isBrowser()) return [];
  return document.cookie.split('; ').filter(Boolean);
}

function parseCookies(): Map<string, string> {
  const map = new Map<string, string>();
  for (const pair of rawCookiePairs()) {
    const eqIdx = pair.indexOf('=');
    if (eqIdx < 0) continue;
    const key = pair.slice(0, eqIdx);
    let val = pair.slice(eqIdx + 1);
    try {
      val = decodeURIComponent(val);
    } catch {
      /* keep raw */
    }
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

/** Encoded byte length of a string once it's URL-encoded into a cookie value. */
function encodedLen(s: string): number {
  return encodeURIComponent(s).length;
}

/**
 * Split a string into pieces whose URL-ENCODED size each stays under CHUNK_SIZE.
 *
 * Chunking must be measured on the *encoded* length, not the raw JS string length:
 * a CJK/Arabic/Cyrillic character is one UTF-16 unit but 3–9 bytes once
 * encodeURIComponent-ed, so a 3800-char slice of localized text can blow past the
 * 4 KB per-cookie browser limit and be silently dropped. We grow each chunk char
 * by char and cut before it would exceed the budget — never splitting a character.
 */
function chunkByEncodedSize(value: string): string[] {
  const chunks: string[] = [];
  let current = '';
  for (const ch of value) {           // iterate by code point (won't split surrogates)
    if (encodedLen(current + ch) > CHUNK_SIZE && current) {
      chunks.push(current);
      current = ch;
    } else {
      current += ch;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

/** Whether a cookie name belongs to `key` (the key itself or one of its chunks). */
function belongsTo(cookieName: string, key: string): boolean {
  if (!cookieName.startsWith(key)) return false;
  const rest = cookieName.slice(key.length);
  return rest === '' || rest === '__n' || /^__\d+$/.test(rest);
}

/** Bytes the Cookie header spends on every cookie except `key`'s own. */
function otherCookiesSize(key: string): number {
  let total = 0;
  for (const pair of rawCookiePairs()) {
    const name = pair.slice(0, Math.max(0, pair.indexOf('=')));
    if (belongsTo(name, key)) continue;
    total += pair.length + 2; // "; " separator
  }
  return total;
}

/** Header bytes `key` would cost once written as `parts`. */
function cookieCost(key: string, parts: string[]): number {
  if (parts.length === 1) return key.length + 1 + encodedLen(parts[0]) + 2;
  let total = `${key}__n=${parts.length}`.length + 2;
  parts.forEach((p, i) => { total += `${key}__${i}`.length + 1 + encodedLen(p) + 2; });
  return total;
}

/** Write `value` as cookie(s). Returns false (and writes nothing) if it would break the budget. */
function writeChunkedCookie(key: string, value: string): boolean {
  const parts = encodedLen(value) <= CHUNK_SIZE ? [value] : chunkByEncodedSize(value);
  if (otherCookiesSize(key) + cookieCost(key, parts) > COOKIE_BUDGET) return false;
  if (parts.length === 1) {
    // Fits in a single cookie — clean up any old chunks
    setCookie(key, value);
    deleteChunks(key, 0);
  } else {
    for (let i = 0; i < parts.length; i++) {
      setCookie(`${key}__${i}`, parts[i]);
    }
    setCookie(`${key}__n`, String(parts.length));
    // Delete the base key cookie (data is in chunks now)
    deleteCookie(key);
    // Clean up any extra old chunks beyond current count
    deleteChunks(key, parts.length);
  }
  return true;
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
  deleteChunks(key, 0, Math.max(n || 0, MAX_CHUNKS_CLEANUP));
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

function hasCookie(key: string, cookies: Map<string, string>): boolean {
  return cookies.has(key) || cookies.has(`${key}__n`);
}

// ── Cache initialization ──

/**
 * Values reconstructed from the cookies. Rebuilt when document.cookie changed
 * (another language site in another tab may have written progress meanwhile;
 * a stale cache would make the next read-modify-write drop its update).
 */
function ensureCache(): Map<string, string> {
  const raw = shouldUseCookies() ? document.cookie : '';
  if (cache === null || raw !== cacheSource) {
    cache = new Map();
    cacheSource = raw;
    if (raw) {
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
    if (shouldUseCookies() && !LOCAL_ONLY_KEYS.has(key)) {
      const val = ensureCache().get(key);
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
  if (LOCAL_ONLY_KEYS.has(key)) return;
  try {
    if (shouldUseCookies()) {
      if (!writeChunkedCookie(key, value)) {
        // Over budget: keep this key in localStorage only, and drop its old
        // cookie so getItem doesn't serve a stale shared value.
        deleteChunkedCookie(key);
        if (!warnedOverflow) {
          warnedOverflow = true;
          console.warn(
            `[doQumentation] Cookie budget (${COOKIE_BUDGET} B) reached; "${key}" is kept on this language site only.`,
          );
        }
      }
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
    }
  } catch { /* ignore */ }
}

/** Read a key's cookie value only (no localStorage fallback). For migrations. */
export function getCookieItem(key: string): string | null {
  if (!isBrowser() || !shouldUseCookies()) return null;
  try {
    return readChunkedCookie(key, parseCookies());
  } catch {
    return null;
  }
}

/** Delete a key's cookie(s) only, leaving localStorage alone. For migrations. */
export function removeCookieItem(key: string): void {
  if (!isBrowser() || !shouldUseCookies()) return;
  try {
    deleteChunkedCookie(key);
  } catch { /* ignore */ }
}

/**
 * Move the cookies of local-only keys (e.g. an IBM API key saved before
 * 2026-10) into this site's localStorage, then delete the cookies. The cookie
 * value wins over an older localStorage copy (it was the last write).
 */
export function migrateLocalOnlyCookies(): void {
  if (!isBrowser() || !shouldUseCookies()) return;
  try {
    const cookies = parseCookies();
    for (const key of LOCAL_ONLY_KEYS) {
      if (!hasCookie(key, cookies)) continue;
      const val = readChunkedCookie(key, cookies);
      if (val !== null) {
        try {
          localStorage.setItem(key, val);
        } catch {
          continue; // keep the cookie rather than lose the value
        }
      }
      deleteChunkedCookie(key);
    }
  } catch {
    // best-effort
  }
}

/**
 * One-time migration: copy existing localStorage values to cookies.
 * Only runs on doqumentation.org domains. Skips keys already in cookies
 * and local-only keys.
 */
export function migrateLocalStorageToCookies(keys: string[]): void {
  if (!isBrowser() || !shouldUseCookies()) return;
  try {
    const cookies = parseCookies();
    let migrated = 0;
    for (const key of keys) {
      if (LOCAL_ONLY_KEYS.has(key)) continue;
      // Skip if already in cookies (simple or chunked)
      if (hasCookie(key, cookies)) continue;
      const val = localStorage.getItem(key);
      if (val !== null && writeChunkedCookie(key, val)) {
        migrated++;
      }
    }
    if (migrated > 0 && typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
      console.debug(`[doQumentation] Migrated ${migrated} settings to cross-subdomain storage`);
    }
  } catch {
    // Migration is best-effort
  }
}
