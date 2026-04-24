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
  | 'Notebook Download';

interface EventProps {
  page?: string;
  notebook?: string;
  locale?: string;
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
