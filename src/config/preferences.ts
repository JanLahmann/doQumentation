/**
 * User Preferences — settings for learning progress, bookmarks,
 * display preferences, and other user state.
 *
 * Separate from jupyter.ts (which handles execution config).
 * All functions include SSR guards for Docusaurus static builds.
 * Storage is backed by cookies (cross-subdomain) + localStorage via storage.ts.
 *
 * Progress and bookmarks are stored compactly (progressCodec.ts): visited and
 * executed pages as a bitset over the append-only page index (pageIndex.json),
 * bookmarks as short slot ids. Only those small values are shared across the
 * language sites; paths outside the index and the (localized) bookmark titles
 * stay in this site's localStorage. The old JSON cookies are converted by
 * migrateLegacyProgress() on first load.
 */

import { getItem, setItem, removeItem, getCookieItem } from './storage';
import pageIndexData from './pageIndex.json';
import {
  buildLookup,
  decodeBitset,
  decodeBookmarkPaths,
  decodePathSet,
  encodeBitset,
  encodeBookmarkPaths,
  encodePathSet,
  normalizeIndexPath,
  parseLegacyArray,
  parseLegacyBookmarks,
  titleFromPath,
  type LegacyBookmark,
} from './progressCodec';

// ── Storage keys ──

const KEY_VISITED = 'dq-visited';               // bitset, shared
const KEY_VISITED_EXTRA = 'dq-visited-extra';   // JSON paths outside the index, this site only
const KEY_EXECUTED = 'dq-executed';             // bitset, shared
const KEY_EXECUTED_EXTRA = 'dq-executed-extra'; // JSON paths outside the index, this site only
const KEY_BOOKMARKS = 'dq-bm';                  // slot ids, shared
const KEY_BOOKMARK_META = 'dq-bookmark-meta';   // {path: {t: title, s: savedAt}}, this site only
// Old JSON formats (≈100 B per page in a cookie) — read once, converted, deleted.
const LEGACY_KEY_VISITED_PAGES = 'dq-visited-pages';
const LEGACY_KEY_EXECUTED_PAGES = 'dq-executed-pages';
const LEGACY_KEY_BOOKMARKS = 'dq-bookmarks';

const KEY_LAST_PAGE = 'dq-last-page';
const KEY_LAST_PAGE_TITLE = 'dq-last-page-title';
const KEY_LAST_PAGE_TS = 'dq-last-page-ts';
const KEY_BINDER_HINT = 'dq-binder-hint-dismissed';
const KEY_ONBOARDING_COMPLETED = 'dq-onboarding-completed';
const KEY_ONBOARDING_VISITS = 'dq-onboarding-visit-count';
const KEY_CODE_FONT_SIZE = 'dq-code-font-size';
const KEY_HIDE_STATIC_OUTPUTS = 'dq-hide-static-outputs';
const KEY_SIDEBAR_COLLAPSED = 'dq-sidebar-collapsed';
const KEY_RECENT_PAGES = 'dq-recent-pages';

/** All shared preference storage keys, exported for migration. */
export const ALL_PREFERENCE_KEYS = [
  KEY_VISITED, KEY_EXECUTED, KEY_LAST_PAGE, KEY_LAST_PAGE_TITLE,
  KEY_LAST_PAGE_TS, KEY_BINDER_HINT, KEY_ONBOARDING_COMPLETED, KEY_ONBOARDING_VISITS,
  KEY_BOOKMARKS, KEY_CODE_FONT_SIZE, KEY_HIDE_STATIC_OUTPUTS, KEY_SIDEBAR_COLLAPSED,
  KEY_RECENT_PAGES,
];

// ── Helpers ──

/** Cap for the per-site list of paths outside the page index. */
const MAX_EXTRA_PAGES = 2000;

const PAGE_INDEX: readonly string[] = pageIndexData.paths;
let lookupCache: Map<string, number> | null = null;
function lookup(): Map<string, number> {
  if (!lookupCache) lookupCache = buildLookup(PAGE_INDEX);
  return lookupCache;
}

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

interface PathSetKeys { bits: string; extra: string }
const VISITED: PathSetKeys = { bits: KEY_VISITED, extra: KEY_VISITED_EXTRA };
const EXECUTED: PathSetKeys = { bits: KEY_EXECUTED, extra: KEY_EXECUTED_EXTRA };

function readStringArray(raw: string | null): string[] {
  return parseLegacyArray(raw).filter((p): p is string => typeof p === 'string' && !!p);
}

// Decoding is memoized on the raw stored strings: the sidebar asks
// isPageVisited() once per item.
const memo = new Map<string, { bits: string | null; extra: string | null; set: Set<string> }>();

function readPathSetShared(keys: PathSetKeys): Set<string> {
  if (!isBrowser()) return new Set();
  try {
    const bits = getItem(keys.bits);
    const extra = getItem(keys.extra);
    const hit = memo.get(keys.bits);
    if (hit && hit.bits === bits && hit.extra === extra) return hit.set;
    const set = decodePathSet(bits, readStringArray(extra), PAGE_INDEX);
    memo.set(keys.bits, { bits, extra, set });
    return set;
  } catch {
    return new Set();
  }
}

function readPathSet(keys: PathSetKeys): Set<string> {
  return new Set(readPathSetShared(keys));
}

function encodeForSave(keys: PathSetKeys, set: Set<string>): { bits: string; extras: string[] } {
  const { bits, extras } = encodePathSet(set, lookup());
  // Keep slots this build doesn't know (set by a newer build in another tab).
  const unknown = decodeBitset(getItem(keys.bits)).filter((id) => id >= PAGE_INDEX.length);
  const merged = unknown.length ? encodeBitset([...decodeBitset(bits), ...unknown]) : bits;
  return { bits: merged, extras: extras.slice(-MAX_EXTRA_PAGES) };
}

function savePathSet(keys: PathSetKeys, set: Set<string>): void {
  if (!isBrowser()) return;
  const { bits, extras } = encodeForSave(keys, set);
  setItem(keys.bits, bits);
  if (extras.length) setItem(keys.extra, JSON.stringify(extras));
  else removeItem(keys.extra);
}

function clearPathSet(keys: PathSetKeys): void {
  removeItem(keys.bits);
  removeItem(keys.extra);
}

// ── Page visit tracking ──

/** Mark a page as visited. Called automatically by the page tracker client module. */
export function markPageVisited(path: string): void {
  if (!isBrowser()) return;
  const norm = normalizePath(path);
  if (readPathSetShared(VISITED).has(norm)) return; // nothing to write
  const visited = readPathSet(VISITED);
  visited.add(norm);
  savePathSet(VISITED, visited);
}

/** Check if a page has been visited. */
export function isPageVisited(path: string): boolean {
  return readPathSetShared(VISITED).has(normalizePath(path));
}

/** Get all visited page paths. */
export function getVisitedPages(): Set<string> {
  return readPathSet(VISITED);
}

/** Remove a single page from visited set. */
export function unmarkPageVisited(path: string): void {
  if (!isBrowser()) return;
  const visited = readPathSet(VISITED);
  if (!visited.delete(normalizePath(path))) return;
  savePathSet(VISITED, visited);
}

/** Clear visited pages matching a path prefix (e.g. "/tutorials" or "/learning/courses/basics-of-quantum-information/single-systems"). */
export function clearVisitedByPrefix(prefix: string): void {
  if (!isBrowser()) return;
  const visited = readPathSet(VISITED);
  const norm = normalizePath(prefix);
  for (const p of visited) {
    if (p.startsWith(norm)) {
      visited.delete(p);
    }
  }
  savePathSet(VISITED, visited);
}

/** Clear all visited pages. */
export function clearAllVisited(): void {
  if (!isBrowser()) return;
  clearPathSet(VISITED);
}

// ── Execution history ──

/** Mark a page as executed (user clicked Run). */
export function markPageExecuted(path: string): void {
  if (!isBrowser()) return;
  const norm = normalizePath(path);
  if (readPathSetShared(EXECUTED).has(norm)) return;
  const executed = readPathSet(EXECUTED);
  executed.add(norm);
  savePathSet(EXECUTED, executed);
}

/** Check if a page has been executed. */
export function isPageExecuted(path: string): boolean {
  return readPathSetShared(EXECUTED).has(normalizePath(path));
}

/** Get all executed page paths. */
export function getExecutedPages(): Set<string> {
  return readPathSet(EXECUTED);
}

/** Clear all execution history. */
export function clearAllExecuted(): void {
  if (!isBrowser()) return;
  clearPathSet(EXECUTED);
}

/** Un-mark a single page as executed (exact path, not prefix). */
export function unmarkPageExecuted(path: string): void {
  if (!isBrowser()) return;
  const executed = readPathSet(EXECUTED);
  if (!executed.delete(normalizePath(path))) return;
  savePathSet(EXECUTED, executed);
}

/** Clear executed pages matching a path prefix. */
export function clearExecutedByPrefix(prefix: string): void {
  if (!isBrowser()) return;
  const executed = readPathSet(EXECUTED);
  const norm = normalizePath(prefix);
  for (const p of executed) {
    if (p.startsWith(norm)) {
      executed.delete(p);
    }
  }
  savePathSet(EXECUTED, executed);
}

// ── Migration from the old JSON cookies ──

function readLegacyBoth(key: string): { cookie: string | null; local: string | null } {
  let local: string | null = null;
  try {
    local = localStorage.getItem(key);
  } catch { /* ignore */ }
  return { cookie: getCookieItem(key), local };
}

function backupLocal(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* ignore */ }
}

/**
 * Convert the old progress/bookmark values (JSON arrays in cookies of up to
 * ~65 KB, plus this site's localStorage copies) to the compact format, merging
 * with anything already stored compactly, then delete the old keys.
 *
 * Order matters: the merged result is first written to localStorage, then the
 * old cookies are deleted (they would otherwise eat the cookie budget), then
 * the compact values are written to the shared cookies. Safe to run on every
 * load: it does nothing once the old keys are gone.
 */
export function migrateLegacyProgress(): void {
  if (!isBrowser()) return;
  try {
    const legacyVisited = readLegacyBoth(LEGACY_KEY_VISITED_PAGES);
    const legacyExecuted = readLegacyBoth(LEGACY_KEY_EXECUTED_PAGES);
    const legacyBookmarks = readLegacyBoth(LEGACY_KEY_BOOKMARKS);
    const all = [legacyVisited, legacyExecuted, legacyBookmarks];
    if (all.every((v) => v.cookie === null && v.local === null)) return;

    // 1. Merge.
    const visited = readPathSet(VISITED);
    for (const p of [...readStringArray(legacyVisited.cookie), ...readStringArray(legacyVisited.local)]) {
      visited.add(normalizePath(p));
    }
    const executed = readPathSet(EXECUTED);
    for (const p of [...readStringArray(legacyExecuted.cookie), ...readStringArray(legacyExecuted.local)]) {
      executed.add(normalizePath(p));
    }
    const bookmarks = getBookmarksArray();
    const meta = getBookmarkMeta();
    const have = new Set(bookmarks.map((b) => b.path));
    const legacy: LegacyBookmark[] = [
      ...parseLegacyBookmarks(legacyBookmarks.cookie),
      ...parseLegacyBookmarks(legacyBookmarks.local),
    ];
    for (const b of legacy) {
      const path = normalizePath(b.path);
      if (!meta[path] && b.title) meta[path] = { t: b.title, s: b.savedAt };
      if (have.has(path)) continue;
      have.add(path);
      bookmarks.push({ path, title: b.title || titleFromPath(path), savedAt: b.savedAt });
    }
    if (bookmarks.length > MAX_BOOKMARKS) bookmarks.length = MAX_BOOKMARKS;

    // 2. Back up the result in localStorage before anything is deleted.
    const v = encodeForSave(VISITED, visited);
    const x = encodeForSave(EXECUTED, executed);
    backupLocal(KEY_VISITED, v.bits);
    backupLocal(KEY_VISITED_EXTRA, v.extras.length ? JSON.stringify(v.extras) : null);
    backupLocal(KEY_EXECUTED, x.bits);
    backupLocal(KEY_EXECUTED_EXTRA, x.extras.length ? JSON.stringify(x.extras) : null);
    backupLocal(KEY_BOOKMARKS, encodeBookmarkPaths(bookmarks.map((b) => b.path), lookup()));
    setBookmarkMeta(meta, bookmarks);

    // 3. Drop the old (large) cookies and localStorage copies.
    removeItem(LEGACY_KEY_VISITED_PAGES);
    removeItem(LEGACY_KEY_EXECUTED_PAGES);
    removeItem(LEGACY_KEY_BOOKMARKS);

    // 4. Share the compact values.
    savePathSet(VISITED, visited);
    savePathSet(EXECUTED, executed);
    saveBookmarksArray(bookmarks);
  } catch {
    // best-effort; the old keys stay until a later load succeeds
  }
}
// ── Last visited page (resume reading) ──

export interface LastPage {
  path: string;
  title: string;
  timestamp: number;
}

/** Record the current page as the last visited. */
export function setLastPage(path: string, title: string): void {
  if (!isBrowser()) return;
  const norm = normalizePath(path);
  // Only track content pages, not the homepage or settings
  if (norm === '/' || norm === '/jupyter-settings') return;
  setItem(KEY_LAST_PAGE, norm);
  setItem(KEY_LAST_PAGE_TITLE, title);
  setItem(KEY_LAST_PAGE_TS, String(Date.now()));
}

/** Get the last visited page info, or null if none. */
export function getLastPage(): LastPage | null {
  if (!isBrowser()) return null;
  const path = getItem(KEY_LAST_PAGE);
  const title = getItem(KEY_LAST_PAGE_TITLE);
  const ts = getItem(KEY_LAST_PAGE_TS);
  if (!path || !ts) return null;
  return { path, title: title || path, timestamp: Number(ts) };
}

// ── Binder hint (migrated from ExecutableCode) ──

export function isBinderHintDismissed(): boolean {
  if (!isBrowser()) return false;
  return getItem(KEY_BINDER_HINT) === 'true';
}

export function dismissBinderHint(): void {
  if (!isBrowser()) return;
  setItem(KEY_BINDER_HINT, 'true');
}

// ── Onboarding ──

export function isOnboardingCompleted(): boolean {
  if (!isBrowser()) return true; // SSR: treat as completed
  return getItem(KEY_ONBOARDING_COMPLETED) === 'true';
}

export function completeOnboarding(): void {
  if (!isBrowser()) return;
  setItem(KEY_ONBOARDING_COMPLETED, 'true');
}

/** Increment visit count and return the new value. Auto-completes after 3 visits. */
export function incrementOnboardingVisits(): number {
  if (!isBrowser()) return 99;
  const count = Number(getItem(KEY_ONBOARDING_VISITS) || '0') + 1;
  setItem(KEY_ONBOARDING_VISITS, String(count));
  if (count >= 3) {
    setItem(KEY_ONBOARDING_COMPLETED, 'true');
  }
  return count;
}

export function resetOnboarding(): void {
  if (!isBrowser()) return;
  removeItem(KEY_ONBOARDING_COMPLETED);
  removeItem(KEY_ONBOARDING_VISITS);
}

// ── Bookmarks ──

export interface Bookmark {
  path: string;
  title: string;
  savedAt: number;
}

const MAX_BOOKMARKS = 50;

type BookmarkMeta = Record<string, { t: string; s: number }>;

/** Titles and save times, per language site (titles are localized). */
function getBookmarkMeta(): BookmarkMeta {
  try {
    const raw = getItem(KEY_BOOKMARK_META);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

/** Store meta for the given bookmarks only (drops entries of removed bookmarks). */
function setBookmarkMeta(meta: BookmarkMeta, bookmarks: Bookmark[]): void {
  const kept: BookmarkMeta = {};
  for (const b of bookmarks) {
    const m = meta[b.path];
    if (m) kept[b.path] = m;
  }
  if (Object.keys(kept).length) setItem(KEY_BOOKMARK_META, JSON.stringify(kept));
  else removeItem(KEY_BOOKMARK_META);
}

function getBookmarksArray(): Bookmark[] {
  if (!isBrowser()) return [];
  try {
    const paths = decodeBookmarkPaths(getItem(KEY_BOOKMARKS), PAGE_INDEX);
    const meta = getBookmarkMeta();
    return paths.map((path) => ({
      path,
      title: meta[path]?.t || titleFromPath(path),
      savedAt: meta[path]?.s || 0,
    }));
  } catch {
    return [];
  }
}

function saveBookmarksArray(bookmarks: Bookmark[]): void {
  if (!isBrowser()) return;
  if (bookmarks.length === 0) {
    removeItem(KEY_BOOKMARKS);
    removeItem(KEY_BOOKMARK_META);
    return;
  }
  setItem(KEY_BOOKMARKS, encodeBookmarkPaths(bookmarks.map((b) => b.path), lookup()));
  const meta = getBookmarkMeta();
  for (const b of bookmarks) {
    if (b.title && b.title !== titleFromPath(b.path)) meta[b.path] = { t: b.title, s: b.savedAt };
  }
  setBookmarkMeta(meta, bookmarks);
}

/**
 * Remember a bookmarked page's title on this language site (called on every
 * page view), so bookmarks made on another language site get a real title.
 */
export function refreshBookmarkTitle(path: string, title: string): void {
  if (!isBrowser() || !title) return;
  const norm = normalizePath(path);
  if (!getBookmarksArray().some((b) => b.path === norm)) return;
  const meta = getBookmarkMeta();
  if (meta[norm]?.t === title) return;
  meta[norm] = { t: title, s: meta[norm]?.s || Date.now() };
  setItem(KEY_BOOKMARK_META, JSON.stringify(meta));
}

export function addBookmark(path: string, title: string): void {
  if (!isBrowser()) return;
  const norm = normalizePath(path);
  const bookmarks = getBookmarksArray().filter(b => b.path !== norm);
  bookmarks.unshift({ path: norm, title, savedAt: Date.now() });
  if (bookmarks.length > MAX_BOOKMARKS) bookmarks.length = MAX_BOOKMARKS;
  saveBookmarksArray(bookmarks);
}

export function removeBookmark(path: string): void {
  if (!isBrowser()) return;
  const norm = normalizePath(path);
  saveBookmarksArray(getBookmarksArray().filter(b => b.path !== norm));
}

export function isBookmarked(path: string): boolean {
  return getBookmarksArray().some(b => b.path === normalizePath(path));
}

export function getBookmarks(): Bookmark[] {
  return getBookmarksArray();
}

export function clearAllBookmarks(): void {
  if (!isBrowser()) return;
  removeItem(KEY_BOOKMARKS);
}

// ── Display preferences ──

const DEFAULT_CODE_FONT_SIZE = 14;

export function getCodeFontSize(): number {
  if (!isBrowser()) return DEFAULT_CODE_FONT_SIZE;
  const val = Number(getItem(KEY_CODE_FONT_SIZE));
  return val >= 10 && val <= 22 ? val : DEFAULT_CODE_FONT_SIZE;
}

export function setCodeFontSize(size: number): void {
  if (!isBrowser()) return;
  const clamped = Math.max(10, Math.min(22, Math.round(size)));
  setItem(KEY_CODE_FONT_SIZE, String(clamped));
}

export function getHideStaticOutputs(): boolean {
  if (!isBrowser()) return false;
  return getItem(KEY_HIDE_STATIC_OUTPUTS) === 'true';
}

export function setHideStaticOutputs(hide: boolean): void {
  if (!isBrowser()) return;
  setItem(KEY_HIDE_STATIC_OUTPUTS, String(hide));
}

// ── Sidebar collapse memory ──

function getCollapseMap(): Record<string, boolean> {
  if (!isBrowser()) return {};
  try {
    const raw = getItem(KEY_SIDEBAR_COLLAPSED);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function getSidebarCollapseState(label: string): boolean | null {
  const map = getCollapseMap();
  return label in map ? map[label] : null;
}

export function setSidebarCollapseState(label: string, collapsed: boolean): void {
  if (!isBrowser()) return;
  const map = getCollapseMap();
  map[label] = collapsed;
  setItem(KEY_SIDEBAR_COLLAPSED, JSON.stringify(map));
}

export function clearSidebarCollapseStates(): void {
  if (!isBrowser()) return;
  removeItem(KEY_SIDEBAR_COLLAPSED);
}

// ── Recently viewed pages ──

export interface RecentPage {
  path: string;
  title: string;
  ts: number;
}

const MAX_RECENT_PAGES = 10;

export function addRecentPage(path: string, title: string): void {
  if (!isBrowser()) return;
  const norm = normalizePath(path);
  // Skip homepage and settings
  if (norm === '/' || norm === '/jupyter-settings') return;
  try {
    const raw = getItem(KEY_RECENT_PAGES);
    const parsed = raw ? JSON.parse(raw) : [];
    const pages: RecentPage[] = Array.isArray(parsed) ? parsed : [];
    // Remove duplicate, add to front
    const filtered = pages.filter(p => p.path !== norm);
    filtered.unshift({ path: norm, title, ts: Date.now() });
    if (filtered.length > MAX_RECENT_PAGES) filtered.length = MAX_RECENT_PAGES;
    setItem(KEY_RECENT_PAGES, JSON.stringify(filtered));
  } catch { /* ignore */ }
}

export function getRecentPages(): RecentPage[] {
  if (!isBrowser()) return [];
  try {
    const raw = getItem(KEY_RECENT_PAGES);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function clearRecentAndLastPage(): void {
  if (!isBrowser()) return;
  removeItem(KEY_RECENT_PAGES);
  removeItem(KEY_LAST_PAGE);
  removeItem(KEY_LAST_PAGE_TITLE);
  removeItem(KEY_LAST_PAGE_TS);
}

// ── Bulk clear ──

/** Clear all user preferences (visited, executed, last page, bookmarks, display, etc.). Does NOT touch Jupyter/credential settings. */
export function clearAllPreferences(): void {
  if (!isBrowser()) return;
  clearPathSet(VISITED);
  clearPathSet(EXECUTED);
  removeItem(KEY_BOOKMARK_META);
  removeItem(LEGACY_KEY_VISITED_PAGES);
  removeItem(LEGACY_KEY_EXECUTED_PAGES);
  removeItem(LEGACY_KEY_BOOKMARKS);
  removeItem(KEY_LAST_PAGE);
  removeItem(KEY_LAST_PAGE_TITLE);
  removeItem(KEY_LAST_PAGE_TS);
  removeItem(KEY_BINDER_HINT);
  removeItem(KEY_ONBOARDING_COMPLETED);
  removeItem(KEY_ONBOARDING_VISITS);
  removeItem(KEY_BOOKMARKS);
  removeItem(KEY_CODE_FONT_SIZE);
  removeItem(KEY_HIDE_STATIC_OUTPUTS);
  removeItem(KEY_SIDEBAR_COLLAPSED);
  removeItem(KEY_RECENT_PAGES);
}

// ── Stats ──

export interface ProgressStats {
  visitedCount: number;
  executedCount: number;
  visitedByCategory: Record<string, number>;
}

/** Get summary statistics about user progress. */
export function getProgressStats(): ProgressStats {
  const visited = readPathSetShared(VISITED);
  const executed = readPathSetShared(EXECUTED);

  const byCategory: Record<string, number> = {};
  for (const p of visited) {
    const cat = getCategoryFromPath(p);
    byCategory[cat] = (byCategory[cat] || 0) + 1;
  }

  return {
    visitedCount: visited.size,
    executedCount: executed.size,
    visitedByCategory: byCategory,
  };
}

// ── Path utilities ──

/** Normalize a path: strip trailing slash. */
function normalizePath(path: string): string {
  // Same normalization as the page index (URI-decoded, no trailing slash), so
  // "/workshop/03_Qiskit%20101" and "/workshop/03_Qiskit 101" are one page.
  return normalizeIndexPath(path);
}

/** Extract the content category from a path. */
function getCategoryFromPath(path: string): string {
  if (path.startsWith('/tutorials')) return 'tutorials';
  if (path.startsWith('/guides')) return 'guides';
  if (path.startsWith('/learning/courses')) return 'courses';
  if (path.startsWith('/learning/modules')) return 'modules';
  return 'other';
}
