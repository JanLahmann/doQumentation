/**
 * User Preferences — localStorage-backed settings for learning progress,
 * bookmarks, display preferences, and other user state.
 *
 * Separate from jupyter.ts (which handles execution config).
 * All functions include SSR guards for Docusaurus static builds.
 */

// ── Storage keys ──

const KEY_VISITED_PAGES = 'dq-visited-pages';
const KEY_EXECUTED_PAGES = 'dq-executed-pages';
const KEY_LAST_PAGE = 'dq-last-page';
const KEY_LAST_PAGE_TITLE = 'dq-last-page-title';
const KEY_LAST_PAGE_TS = 'dq-last-page-ts';
const KEY_BINDER_HINT = 'dq-binder-hint-dismissed';
const KEY_ONBOARDING_COMPLETED = 'dq-onboarding-completed';
const KEY_ONBOARDING_VISITS = 'dq-onboarding-visit-count';
const KEY_BOOKMARKS = 'dq-bookmarks';
const KEY_CODE_FONT_SIZE = 'dq-code-font-size';
const KEY_HIDE_STATIC_OUTPUTS = 'dq-hide-static-outputs';
const KEY_SIDEBAR_COLLAPSED = 'dq-sidebar-collapsed';
const KEY_RECENT_PAGES = 'dq-recent-pages';

// ── Helpers ──

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

/** Wrapper for localStorage.setItem that silently handles QuotaExceededError. */
function safeSave(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // QuotaExceededError or SecurityError — silently fail rather than crash
  }
}

function getJsonSet(key: string): Set<string> {
  if (!isBrowser()) return new Set();
  try {
    const raw = localStorage.getItem(key);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function saveJsonSet(key: string, set: Set<string>): void {
  if (!isBrowser()) return;
  safeSave(key, JSON.stringify([...set]));
}

// ── Page visit tracking ──

/** Mark a page as visited. Called automatically by the page tracker client module. */
export function markPageVisited(path: string): void {
  if (!isBrowser()) return;
  const visited = getJsonSet(KEY_VISITED_PAGES);
  visited.add(normalizePath(path));
  saveJsonSet(KEY_VISITED_PAGES, visited);
}

/** Check if a page has been visited. */
export function isPageVisited(path: string): boolean {
  return getJsonSet(KEY_VISITED_PAGES).has(normalizePath(path));
}

/** Get all visited page paths. */
export function getVisitedPages(): Set<string> {
  return getJsonSet(KEY_VISITED_PAGES);
}

/** Remove a single page from visited set. */
export function unmarkPageVisited(path: string): void {
  if (!isBrowser()) return;
  const visited = getJsonSet(KEY_VISITED_PAGES);
  visited.delete(normalizePath(path));
  saveJsonSet(KEY_VISITED_PAGES, visited);
}

/** Clear visited pages matching a path prefix (e.g. "/tutorials" or "/learning/courses/basics-of-quantum-information/single-systems"). */
export function clearVisitedByPrefix(prefix: string): void {
  if (!isBrowser()) return;
  const visited = getJsonSet(KEY_VISITED_PAGES);
  const norm = normalizePath(prefix);
  for (const p of visited) {
    if (p.startsWith(norm)) {
      visited.delete(p);
    }
  }
  saveJsonSet(KEY_VISITED_PAGES, visited);
}

/** Clear all visited pages. */
export function clearAllVisited(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_VISITED_PAGES);
}

// ── Execution history ──

/** Mark a page as executed (user clicked Run). */
export function markPageExecuted(path: string): void {
  if (!isBrowser()) return;
  const executed = getJsonSet(KEY_EXECUTED_PAGES);
  executed.add(normalizePath(path));
  saveJsonSet(KEY_EXECUTED_PAGES, executed);
}

/** Check if a page has been executed. */
export function isPageExecuted(path: string): boolean {
  return getJsonSet(KEY_EXECUTED_PAGES).has(normalizePath(path));
}

/** Get all executed page paths. */
export function getExecutedPages(): Set<string> {
  return getJsonSet(KEY_EXECUTED_PAGES);
}

/** Clear all execution history. */
export function clearAllExecuted(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_EXECUTED_PAGES);
}

/** Clear executed pages matching a path prefix. */
export function clearExecutedByPrefix(prefix: string): void {
  if (!isBrowser()) return;
  const executed = getJsonSet(KEY_EXECUTED_PAGES);
  const norm = normalizePath(prefix);
  for (const p of executed) {
    if (p.startsWith(norm)) {
      executed.delete(p);
    }
  }
  saveJsonSet(KEY_EXECUTED_PAGES, executed);
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
  safeSave(KEY_LAST_PAGE, norm);
  safeSave(KEY_LAST_PAGE_TITLE, title);
  safeSave(KEY_LAST_PAGE_TS, String(Date.now()));
}

/** Get the last visited page info, or null if none. */
export function getLastPage(): LastPage | null {
  if (!isBrowser()) return null;
  const path = localStorage.getItem(KEY_LAST_PAGE);
  const title = localStorage.getItem(KEY_LAST_PAGE_TITLE);
  const ts = localStorage.getItem(KEY_LAST_PAGE_TS);
  if (!path || !ts) return null;
  return { path, title: title || path, timestamp: Number(ts) };
}

// ── Binder hint (migrated from ExecutableCode) ──

export function isBinderHintDismissed(): boolean {
  if (!isBrowser()) return false;
  return localStorage.getItem(KEY_BINDER_HINT) === 'true';
}

export function dismissBinderHint(): void {
  if (!isBrowser()) return;
  safeSave(KEY_BINDER_HINT, 'true');
}

// ── Onboarding ──

export function isOnboardingCompleted(): boolean {
  if (!isBrowser()) return true; // SSR: treat as completed
  return localStorage.getItem(KEY_ONBOARDING_COMPLETED) === 'true';
}

export function completeOnboarding(): void {
  if (!isBrowser()) return;
  safeSave(KEY_ONBOARDING_COMPLETED, 'true');
}

/** Increment visit count and return the new value. Auto-completes after 3 visits. */
export function incrementOnboardingVisits(): number {
  if (!isBrowser()) return 99;
  const count = Number(localStorage.getItem(KEY_ONBOARDING_VISITS) || '0') + 1;
  safeSave(KEY_ONBOARDING_VISITS, String(count));
  if (count >= 3) {
    safeSave(KEY_ONBOARDING_COMPLETED, 'true');
  }
  return count;
}

export function resetOnboarding(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_ONBOARDING_COMPLETED);
  localStorage.removeItem(KEY_ONBOARDING_VISITS);
}

// ── Bookmarks ──

export interface Bookmark {
  path: string;
  title: string;
  savedAt: number;
}

const MAX_BOOKMARKS = 50;

function getBookmarksArray(): Bookmark[] {
  if (!isBrowser()) return [];
  try {
    const raw = localStorage.getItem(KEY_BOOKMARKS);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveBookmarksArray(bookmarks: Bookmark[]): void {
  if (!isBrowser()) return;
  safeSave(KEY_BOOKMARKS, JSON.stringify(bookmarks));
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
  localStorage.removeItem(KEY_BOOKMARKS);
}

// ── Display preferences ──

const DEFAULT_CODE_FONT_SIZE = 14;

export function getCodeFontSize(): number {
  if (!isBrowser()) return DEFAULT_CODE_FONT_SIZE;
  const val = Number(localStorage.getItem(KEY_CODE_FONT_SIZE));
  return val >= 10 && val <= 22 ? val : DEFAULT_CODE_FONT_SIZE;
}

export function setCodeFontSize(size: number): void {
  if (!isBrowser()) return;
  const clamped = Math.max(10, Math.min(22, Math.round(size)));
  safeSave(KEY_CODE_FONT_SIZE, String(clamped));
}

export function getHideStaticOutputs(): boolean {
  if (!isBrowser()) return false;
  return localStorage.getItem(KEY_HIDE_STATIC_OUTPUTS) === 'true';
}

export function setHideStaticOutputs(hide: boolean): void {
  if (!isBrowser()) return;
  safeSave(KEY_HIDE_STATIC_OUTPUTS, String(hide));
}

// ── Sidebar collapse memory ──

function getCollapseMap(): Record<string, boolean> {
  if (!isBrowser()) return {};
  try {
    const raw = localStorage.getItem(KEY_SIDEBAR_COLLAPSED);
    return raw ? JSON.parse(raw) : {};
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
  safeSave(KEY_SIDEBAR_COLLAPSED, JSON.stringify(map));
}

export function clearSidebarCollapseStates(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_SIDEBAR_COLLAPSED);
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
    const raw = localStorage.getItem(KEY_RECENT_PAGES);
    const pages: RecentPage[] = raw ? JSON.parse(raw) : [];
    // Remove duplicate, add to front
    const filtered = pages.filter(p => p.path !== norm);
    filtered.unshift({ path: norm, title, ts: Date.now() });
    if (filtered.length > MAX_RECENT_PAGES) filtered.length = MAX_RECENT_PAGES;
    safeSave(KEY_RECENT_PAGES, JSON.stringify(filtered));
  } catch { /* ignore */ }
}

export function getRecentPages(): RecentPage[] {
  if (!isBrowser()) return [];
  try {
    const raw = localStorage.getItem(KEY_RECENT_PAGES);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function clearRecentPages(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_RECENT_PAGES);
  localStorage.removeItem(KEY_LAST_PAGE);
  localStorage.removeItem(KEY_LAST_PAGE_TITLE);
  localStorage.removeItem(KEY_LAST_PAGE_TS);
}

// ── Bulk clear ──

/** Clear all user preferences (visited, executed, last page, bookmarks, display, etc.). Does NOT touch Jupyter/credential settings. */
export function clearAllPreferences(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_VISITED_PAGES);
  localStorage.removeItem(KEY_EXECUTED_PAGES);
  localStorage.removeItem(KEY_LAST_PAGE);
  localStorage.removeItem(KEY_LAST_PAGE_TITLE);
  localStorage.removeItem(KEY_LAST_PAGE_TS);
  localStorage.removeItem(KEY_BINDER_HINT);
  localStorage.removeItem(KEY_ONBOARDING_COMPLETED);
  localStorage.removeItem(KEY_ONBOARDING_VISITS);
  localStorage.removeItem(KEY_BOOKMARKS);
  localStorage.removeItem(KEY_CODE_FONT_SIZE);
  localStorage.removeItem(KEY_HIDE_STATIC_OUTPUTS);
  localStorage.removeItem(KEY_SIDEBAR_COLLAPSED);
  localStorage.removeItem(KEY_RECENT_PAGES);
}

// ── Stats ──

export interface ProgressStats {
  visitedCount: number;
  executedCount: number;
  visitedByCategory: Record<string, number>;
}

/** Get summary statistics about user progress. */
export function getProgressStats(): ProgressStats {
  const visited = getJsonSet(KEY_VISITED_PAGES);
  const executed = getJsonSet(KEY_EXECUTED_PAGES);

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

/** Normalize a path: strip trailing slash, lowercase. */
function normalizePath(path: string): string {
  let p = path.replace(/\/+$/, '') || '/';
  // Don't lowercase — paths are case-sensitive
  return p;
}

/** Extract the content category from a path. */
function getCategoryFromPath(path: string): string {
  if (path.startsWith('/tutorials')) return 'tutorials';
  if (path.startsWith('/guides')) return 'guides';
  if (path.startsWith('/learning/courses')) return 'courses';
  if (path.startsWith('/learning/modules')) return 'modules';
  return 'other';
}
