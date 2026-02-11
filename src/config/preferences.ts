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

// ── Helpers ──

function isBrowser(): boolean {
  return typeof window !== 'undefined';
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
  localStorage.setItem(key, JSON.stringify([...set]));
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
  localStorage.setItem(KEY_LAST_PAGE, norm);
  localStorage.setItem(KEY_LAST_PAGE_TITLE, title);
  localStorage.setItem(KEY_LAST_PAGE_TS, String(Date.now()));
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
  localStorage.setItem(KEY_BINDER_HINT, 'true');
}

// ── Bulk clear ──

/** Clear all user preferences (visited, executed, last page). Does NOT touch Jupyter/credential settings. */
export function clearAllPreferences(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(KEY_VISITED_PAGES);
  localStorage.removeItem(KEY_EXECUTED_PAGES);
  localStorage.removeItem(KEY_LAST_PAGE);
  localStorage.removeItem(KEY_LAST_PAGE_TITLE);
  localStorage.removeItem(KEY_LAST_PAGE_TS);
  localStorage.removeItem(KEY_BINDER_HINT);
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
