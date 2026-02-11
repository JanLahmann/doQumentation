/**
 * Docusaurus Client Module — Display Preferences
 *
 * Applies user display preferences (code font size) on page load.
 * Registered in docusaurus.config.ts as a clientModule.
 */

import { getCodeFontSize } from '../config/preferences';

export const DISPLAY_PREFS_EVENT = 'dq:display-prefs-changed';

function applyCodeFontSize(): void {
  const size = getCodeFontSize();
  document.documentElement.style.setProperty('--dq-code-font-size', size + 'px');
}

// Apply on initial load
export function onRouteDidUpdate(): void {
  applyCodeFontSize();
}

// Also listen for live changes from the Settings page
if (typeof window !== 'undefined') {
  window.addEventListener(DISPLAY_PREFS_EVENT, applyCodeFontSize);
}
