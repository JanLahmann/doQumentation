/**
 * Umami Analytics integration for doQumentation.
 *
 * Privacy-friendly, cookie-free tracking. Auto-disabled on localhost/Docker.
 * Custom events for code execution actions.
 */

type AnalyticsEvent =
  | 'Run Code'
  | 'Run All'
  | 'Binder Launch'
  | 'Colab Open';

interface EventProps {
  page?: string;
  notebook?: string;
}

declare global {
  interface Window {
    umami?: {
      track: (event: string, data?: Record<string, string>) => void;
    };
  }
}

function isTrackingEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.hostname.endsWith('doqumentation.org');
}

export function trackEvent(event: AnalyticsEvent, props?: EventProps): void {
  if (!isTrackingEnabled()) return;
  window.umami?.track(event, props as Record<string, string>);
}
