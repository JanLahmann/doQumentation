/**
 * Docusaurus Client Module — Page Visit Tracker
 *
 * Automatically tracks page visits and records the last visited page.
 * Registered in docusaurus.config.ts as a clientModule.
 * Runs on every client-side route change.
 */

import {
  markPageVisited, setLastPage, addRecentPage, refreshBookmarkTitle, migrateLegacyProgress, ALL_PREFERENCE_KEYS,
} from '../config/preferences';
import { ALL_JUPYTER_KEYS } from '../config/jupyter';
import { migrateLocalStorageToCookies, migrateLocalOnlyCookies } from '../config/storage';

/** Custom event name broadcast after a page visit is recorded. */
export const PAGE_VISITED_EVENT = 'dq:page-visited';

// Storage migrations, once per page load, in this order:
//  1. cookies of local-only keys (IBM API key/CRN) → this site's localStorage
//  2. old JSON progress/bookmark cookies → compact format (frees the cookie budget)
//  3. localStorage-only values → shared cookies (cross-subdomain sharing)
let migrationDone = false;

// Docusaurus client module lifecycle hook:
// Called on every client-side route change (including initial load).
export function onRouteDidUpdate({ location }: { location: Location }): void {
  if (!migrationDone) {
    migrationDone = true;
    migrateLocalOnlyCookies();
    migrateLegacyProgress();
    migrateLocalStorageToCookies([...ALL_PREFERENCE_KEYS, ...ALL_JUPYTER_KEYS]);
  }
  const path = location.pathname;

  // Track the visit
  markPageVisited(path);

  // Defer title read — React hasn't updated <Head> yet when this hook fires,
  // so document.title may still be the previous page's or the site default.
  // setTimeout(100) gives React enough time to flush the <Head> update.
  setTimeout(() => {
    const raw = document.title?.replace(/ \| doQumentation$/, '') || '';
    // Skip bare site title (means <Head> hasn't resolved a page-specific title)
    const title = (raw && raw !== 'doQumentation') ? raw : path;
    setLastPage(path, title);
    addRecentPage(path, title);
    if (title !== path) refreshBookmarkTitle(path, title);
  }, 100);

  // Notify sidebar items to re-check their visited state
  window.dispatchEvent(new CustomEvent(PAGE_VISITED_EVENT, { detail: path }));
}
