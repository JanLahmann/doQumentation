/**
 * Umami Analytics integration for doQumentation.
 *
 * Privacy-friendly, cookie-free tracking. Auto-disabled on localhost/Docker.
 * Custom events for code execution actions.
 * Locale automatically derived from hostname (e.g. de.doqumentation.org → "de").
 */

type AnalyticsEvent =
  | 'Run Code'
  | 'Run All'
  | 'Binder Launch'
  | 'Colab Open'
  | 'Tutorial Feedback'
  | 'Translation Feedback'
  | 'Notebook Download'
  | 'Outbound'
  | 'Outbound IBM';

interface EventProps {
  page?: string;
  notebook?: string;
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

export function trackEvent(event: AnalyticsEvent, props?: EventProps): void {
  if (!isTrackingEnabled()) return;
  const data = { locale: getLocale(), ...props } as Record<string, string>;
  window.umami?.track(event, data);
}

/**
 * Track a pageview with locale metadata.
 * Call once on page load (e.g. from a client module).
 */
export function trackPageview(): void {
  if (!isTrackingEnabled()) return;
  // Umami auto-tracks pageviews via its script, but we send a custom
  // "Pageview" event with locale to enable locale breakdown in dashboard.
  window.umami?.track('Pageview', { locale: getLocale(), page: window.location.pathname });
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
  // Keep the IBM-specific event for backward compatibility with existing
  // dashboards; also fire the unified "Outbound" event so non-IBM links
  // (GitHub, etc.) show up alongside IBM ones in a single view.
  const props = {
    locale: getLocale(),
    category,
    host,
    path: parsed.pathname,
    url: parsed.origin + parsed.pathname,
    from: window.location.pathname,
  };
  window.umami?.track('Outbound', props);
  if (isIBMHost(host)) {
    window.umami?.track('Outbound IBM', props);
  }
}

/** @deprecated use trackOutbound — kept so older callers still compile. */
export function trackOutboundIBM(href: string): void {
  trackOutbound(href);
}
