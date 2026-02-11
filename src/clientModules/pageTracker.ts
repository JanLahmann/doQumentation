/**
 * Docusaurus Client Module — Page Visit Tracker
 *
 * Automatically tracks page visits and records the last visited page.
 * Registered in docusaurus.config.ts as a clientModule.
 * Runs on every client-side route change.
 */

import { markPageVisited, setLastPage } from '../config/preferences';

/** Custom event name broadcast after a page visit is recorded. */
export const PAGE_VISITED_EVENT = 'dq:page-visited';

// Docusaurus client module lifecycle hook:
// Called on every client-side route change (including initial load).
export function onRouteDidUpdate({ location }: { location: Location }): void {
  const path = location.pathname;

  // Track the visit
  markPageVisited(path);

  // Record as last page (setLastPage ignores homepage and settings internally)
  const title = document.title?.replace(/ \| doQumentation$/, '') || path;
  setLastPage(path, title);

  // Notify sidebar items to re-check their visited state
  window.dispatchEvent(new CustomEvent(PAGE_VISITED_EVENT, { detail: path }));
}
