/**
 * Docusaurus Client Module — Outbound Link Tracker
 *
 * Fires a Umami "Outbound" event whenever a user clicks a link to
 * an external host. IBM links additionally fire "Outbound IBM" for
 * backward compatibility with the existing dashboard. Categorization
 * happens in analytics.ts (IBM gets fine-grained buckets, GitHub is
 * its own category, everything else is "external-other").
 *
 * Listens on mousedown + auxclick so middle-click and cmd/ctrl-click
 * are tracked before navigation tears the page down.
 */

import { trackOutbound } from '../config/analytics';

function findAnchor(target: EventTarget | null): HTMLAnchorElement | null {
  let node = target as Node | null;
  while (node && node.nodeType === 1) {
    const el = node as HTMLElement;
    if (el.tagName === 'A' && (el as HTMLAnchorElement).href) {
      return el as HTMLAnchorElement;
    }
    node = el.parentNode;
  }
  return null;
}

function handleClick(e: MouseEvent): void {
  if (e.button !== 0 && e.button !== 1) return;
  const a = findAnchor(e.target);
  if (!a) return;
  trackOutbound(a.href);
}

let installed = false;
export function onRouteDidUpdate(): void {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  window.addEventListener('mousedown', handleClick, true);
  window.addEventListener('auxclick', handleClick, true);
}
