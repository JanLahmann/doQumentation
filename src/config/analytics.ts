/**
 * Umami Analytics integration for doQumentation.
 *
 * Privacy-friendly, cookie-free tracking. Auto-disabled on localhost/Docker.
 * Page views are Umami's automatic ones (the locale shows as the hostname, e.g. de.doqumentation.org);
 * custom events follow the family naming below. Events also carry a `locale` property derived
 * from the hostname (de.doqumentation.org → "de").
 */

type AnalyticsEvent =
  | 'Run Code'
  | 'Run All'
  | 'Binder Launch'
  | 'Colab Open'
  | 'Tutorial Feedback'
  | 'Translation Feedback'
  | 'Notebook Download';

interface EventProps {
  page?: string;
  notebook?: string;
  rating?: string;
  locale?: string;
  category?: string;
  host?: string;
  path?: string;
  url?: string;
  from?: string;
}

declare global {
  interface Window {
    umami?: {
      track: (event: string | Function, data?: Record<string, string>) => void;
    };
  }
}

function isTrackingEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.hostname.endsWith('doqumentation.org');
}

function getLocale(): string {
  if (typeof window === 'undefined') return 'en';
  const host = window.location.hostname;
  // de.doqumentation.org → "de", doqumentation.org → "en"
  const parts = host.split('.');
  return parts.length > 2 ? parts[0] : 'en';
}

/**
 * Fun with Quantum family taxonomy v2 (Fun-with-Quantum/family/EVENTS.md): every family site
 * reports to one Umami website, so event names are `<Site>: <what happened>` (lower case after
 * the colon) and details go in properties. Call sites keep the short internal names below; this
 * table is the only place the reported names live.
 */
const SITE = 'doQumentation';

const EVENTS: Record<AnalyticsEvent, { name: string; props?: Record<string, string> }> = {
  'Run Code': { name: `${SITE}: code run` },
  'Run All': { name: `${SITE}: run all` },
  'Binder Launch': { name: `${SITE}: notebook launch`, props: { target: 'binder' } },
  'Colab Open': { name: `${SITE}: notebook launch`, props: { target: 'colab' } },
  'Notebook Download': { name: `${SITE}: notebook download` },
  'Tutorial Feedback': { name: `${SITE}: tutorial feedback` },
  'Translation Feedback': { name: `${SITE}: translation feedback` },
};

const OUTBOUND_EVENT = `${SITE}: outbound click`;

export function trackEvent(event: AnalyticsEvent, props?: EventProps): void {
  if (!isTrackingEnabled()) return;
  const { name, props: fixed } = EVENTS[event];
  window.umami?.track(name, { locale: getLocale(), ...fixed, ...props } as Record<string, string>);
}

/**
 * Categorize an outbound IBM URL by href. Categories distinguish
 * the Quantum platform (the product) from docs, learning, IBM Cloud,
 * and marketing — keys off the link as written, since redirects happen
 * after the user has navigated away.
 */
export function categorizeIBMUrl(host: string, path: string): string {
  if (host === 'quantum.cloud.ibm.com') {
    if (path.startsWith('/docs')) return 'quantum-docs';
    if (path.startsWith('/learning')) return 'quantum-learning';
    return 'quantum-platform';
  }
  if (host === 'docs.quantum.ibm.com' || host === 'docs.quantum-computing.ibm.com') {
    return 'quantum-docs';
  }
  if (host === 'learning.quantum.ibm.com') return 'quantum-learning';
  if (host === 'qiskit-code-assistant.quantum.ibm.com') return 'quantum-platform';
  if (host === 'cloud.ibm.com' || host === 'iam.cloud.ibm.com' || host === 'dataplatform.cloud.ibm.com') {
    return 'ibm-cloud';
  }
  if (host === 'video.ibm.com') return 'ibm-video';
  if (host === 'www.ibm.com' || host === 'ibm.com' || host === 'newsroom.ibm.com' || host === 'research.ibm.com') {
    return 'ibm-marketing';
  }
  return 'ibm-other';
}

/** True for any *.ibm.com hostname (and bare ibm.com). */
export function isIBMHost(host: string): boolean {
  return host === 'ibm.com' || host.endsWith('.ibm.com');
}

/**
 * Categorize any outbound host. IBM gets fine-grained buckets via
 * categorizeIBMUrl; GitHub is its own category; everything else is
 * "external-other" (kept low-cardinality on purpose — host is also
 * sent as a property if you need to drill in).
 */
export function categorizeOutboundUrl(host: string, path: string): string {
  if (isIBMHost(host)) return categorizeIBMUrl(host, path);
  if (host === 'github.com' || host.endsWith('.github.com') || host === 'github.io' || host.endsWith('.github.io')) {
    return 'github';
  }
  return 'external-other';
}

/** True if this hostname should be tracked as an outbound click. */
function isTrackedOutboundHost(host: string): boolean {
  if (typeof window === 'undefined') return false;
  // Skip same-site and our locale subdomains.
  if (host === window.location.hostname) return false;
  if (host.endsWith('doqumentation.org')) return false;
  return true;
}

export function trackOutbound(href: string): void {
  if (!isTrackingEnabled()) return;
  let parsed: URL;
  try { parsed = new URL(href); } catch { return; }
  const host = parsed.hostname;
  if (!isTrackedOutboundHost(host)) return;
  const category = categorizeOutboundUrl(host, parsed.pathname);
  // One outbound event for every host; the IBM buckets live in `category` (filter ibm-* / quantum-*).
  const props = {
    locale: getLocale(),
    category,
    host,
    path: parsed.pathname,
    url: parsed.origin + parsed.pathname,
    from: window.location.pathname,
  };
  window.umami?.track(OUTBOUND_EVENT, props);
}
