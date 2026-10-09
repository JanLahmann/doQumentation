/**
 * Loads thebelab 0.4.0 (static/vendor/thebelab/, served from the site so an
 * offline Pi can run code) only when a page actually starts a session.
 *
 * It is about 1.6 MB (450 KB gzipped), more than half of the site's
 * JavaScript; as a global script it was downloaded, parsed and run on every
 * page, which kept phones from responding 1.3–2.6 s longer. Its chunks
 * (1.index.js, 2.index.js) and fonts still load from /vendor/thebelab/ via
 * the public path patched into index.js.
 */

export const THEBELAB_SRC = '/vendor/thebelab/index.js';
// Generous: the script is large and a workshop Wi-Fi or a phone can be slow.
const LOAD_TIMEOUT_MS = 60000;

let loadPromise: Promise<void> | null = null;
let prefetched = false;

/** Inject the thebelab script once and resolve when window.thebelab exists. */
export function loadThebelab(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  if (window.thebelab) return Promise.resolve();
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = THEBELAB_SRC;
    script.async = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const fail = (err: Error) => {
      if (timer) clearTimeout(timer);
      script.remove();
      loadPromise = null; // the next Run / Retry tries again
      reject(err);
    };
    script.onload = () => {
      if (timer) clearTimeout(timer);
      if (window.thebelab) resolve();
      else fail(new Error('thebelab loaded but window.thebelab is missing'));
    };
    script.onerror = () => fail(new Error(`failed to load ${THEBELAB_SRC}`));
    timer = setTimeout(
      () => fail(new Error(`${THEBELAB_SRC} did not load within ${LOAD_TIMEOUT_MS / 1000} s`)),
      LOAD_TIMEOUT_MS,
    );
    document.head.appendChild(script);
  });
  return loadPromise;
}

/**
 * Warm the HTTP cache on a page with runnable code, once the browser is idle,
 * so the first Run doesn't wait for the download. Download only, nothing is
 * parsed or run. Skipped when the visitor asked to save data or is on 2G.
 */
export function prefetchThebelab(): void {
  if (prefetched || typeof window === 'undefined' || window.thebelab || loadPromise) return;
  prefetched = true;
  const conn = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string };
  }).connection;
  if (conn?.saveData || /(^|-)2g$/.test(conn?.effectiveType ?? '')) return;
  const add = () => {
    if (window.thebelab || loadPromise) return;
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.as = 'script';
    link.href = THEBELAB_SRC;
    document.head.appendChild(link);
  };
  const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => void };
  // Wait for the page's own load first, then for an idle moment.
  const schedule = () => {
    if (w.requestIdleCallback) w.requestIdleCallback(add, { timeout: 10000 });
    else setTimeout(add, 3000);
  };
  if (document.readyState === 'complete') schedule();
  else window.addEventListener('load', schedule, { once: true });
}
