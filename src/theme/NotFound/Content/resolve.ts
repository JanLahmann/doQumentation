/**
 * Pure helpers for the 404 page: decide whether a missing URL is really a
 * page we have under a slightly different path, and suggest near matches.
 *
 * The set of real pages comes from Docusaurus' own route table
 * (`@generated/routes`, already in the main bundle), so no network request
 * is needed and a redirect only ever targets a route that renders a page —
 * never the 404 page again, so it cannot loop.
 */

export type RouteLike = {path?: string; exact?: boolean; routes?: RouteLike[]};

/** Every leaf (exact) route path, e.g. "/guides/transpile". */
export function collectPagePaths(routes: RouteLike[], out = new Set<string>()): Set<string> {
  for (const r of routes) {
    if (r.path && r.exact && r.path !== '*') out.add(r.path);
    if (r.routes) collectPagePaths(r.routes, out);
  }
  return out;
}

function safeDecode(p: string): string {
  try {
    return decodeURI(p);
  } catch {
    return p;
  }
}

/** Collapse duplicate slashes and drop trailing ones ("/" stays "/"). */
function normalize(p: string): string {
  const s = p.replace(/\/{2,}/g, '/').replace(/\/+$/, '');
  return s === '' ? '/' : s;
}

// Language segment in IBM URLs (/docs/en/…, /learning/ja/…) or one a visitor
// may add by habit (/de/guides/…). Two letters, optional region.
const LANG = '[a-z]{2}(?:[-_][a-zA-Z]{2,4})?';

/**
 * Paths to try, in order, for a URL that did not match a page. Every rule is
 * only applied when its result is a real page, so the list may be generous.
 *
 * IBM → here (from the link rewrites in scripts/sync-content.py, MDX_TRANSFORMS):
 *   /docs/tutorials/X → /tutorials/X, /docs/guides/X → /guides/X;
 *   /learning/courses/… and /learning/modules/… keep their path.
 *   IBM's current site adds a language segment: /docs/en/guides/X,
 *   /learning/en/courses/X.
 */
export function redirectCandidates(rawPath: string): string[] {
  const path = normalize(safeDecode(rawPath));
  const out: string[] = [];
  const add = (p: string) => {
    const n = normalize(p);
    if (!out.includes(n)) out.push(n);
  };

  const variants = [path];
  // Upstream file links (…/foo.ipynb, …/foo.mdx) and old static links (…/foo.html).
  const noExt = path.replace(/\.(html?|mdx?|ipynb)$/i, '');
  if (noExt !== path) variants.push(noExt);

  for (const v of variants) {
    add(v);
    let m: RegExpMatchArray | null;
    // /docs[/en]/(tutorials|guides)/… → /(tutorials|guides)/…
    if ((m = v.match(new RegExp(`^/docs(?:/${LANG})?/(tutorials|guides)(/.*)?$`)))) {
      add(`/${m[1]}${m[2] ?? ''}`);
    }
    // /learning/en/(courses|modules)/… → /learning/(courses|modules)/…
    if ((m = v.match(new RegExp(`^/learning/${LANG}(/.*)?$`)))) {
      add(`/learning${m[1] ?? ''}`);
    }
    // /de/guides/… (a language prefix; our languages live on subdomains)
    if ((m = v.match(new RegExp(`^/${LANG}(/(?:tutorials|guides|learning|qiskit-addons)(?:/.*)?)$`)))) {
      add(m[1]);
    }
  }
  // Same again in lower case (/Guides/Transpile).
  for (const p of [...out]) add(p.toLowerCase());
  // No course catalogue page at /learning/courses: the /learning index lists them.
  for (const p of [...out]) {
    if (p === '/learning/courses') add('/learning');
  }
  return out;
}

/** First candidate that is a real page and not the current path. */
export function findRedirect(rawPath: string, pages: Set<string>): string | null {
  const current = safeDecode(rawPath);
  for (const c of redirectCandidates(rawPath)) {
    if (c !== current && pages.has(c)) return c;
  }
  return null;
}

function editDistance(a: string, b: string, max: number): number {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      rowMin = Math.min(rowMin, cur[j]);
    }
    if (rowMin > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

const lastSegment = (p: string) => p.slice(p.lastIndexOf('/') + 1);

/**
 * Up to `limit` real pages close to the missing path: pages under it (a folder
 * URL), then pages whose last segment equals or nearly equals its last segment
 * (a typo or a wrong section).
 */
export function suggestPages(rawPath: string, pages: Set<string>, limit = 6): string[] {
  const candidates = redirectCandidates(rawPath);
  const out: string[] = [];
  const push = (p: string) => {
    if (out.length < limit && !out.includes(p)) out.push(p);
  };
  const all = [...pages].filter((p) => p !== '/' && !p.startsWith('/admin'));

  // 1. Pages inside the requested folder, shallowest first.
  for (const c of candidates) {
    if (c === '/') continue;
    all
      .filter((p) => p.startsWith(c + '/'))
      .sort((a, b) => a.split('/').length - b.split('/').length || a.localeCompare(b))
      .forEach(push);
  }

  // 2. Same or similar last segment anywhere.
  // (Every candidate shares the requested URL's last segment, minus extension.)
  const seg = lastSegment(candidates[0]).toLowerCase().replace(/\.(html?|mdx?|ipynb)$/i, '');
  if (seg.length >= 3) {
    const max = Math.max(1, Math.min(3, Math.floor(seg.length / 4)));
    all
      .map((p) => ({p, d: editDistance(seg, lastSegment(p).toLowerCase(), max)}))
      .filter((x) => x.d <= max)
      .sort((a, b) => a.d - b.d || a.p.length - b.p.length)
      .forEach((x) => push(x.p));
  }
  return out;
}

/** Words for the search box from the missing URL's last segment. */
export function searchTermFromPath(rawPath: string): string {
  const seg = lastSegment(normalize(safeDecode(rawPath)));
  return seg
    .replace(/\.(html?|mdx?|ipynb)$/i, '')
    .replace(/[-_+.]+/g, ' ')
    .trim();
}

/**
 * For an IBM-style address with no page here (/docs/…, /learning/en/…), the
 * same path on IBM Quantum's site, which adds a missing /en itself
 * (/docs/api/qiskit → /docs/en/api/qiskit). Same target as the upstream link
 * rewrite for /docs/ pages we do not mirror (scripts/sync-content.py).
 */
export function ibmUrlFor(rawPath: string): string | null {
  const path = normalize(safeDecode(rawPath));
  if (/^\/docs\/./.test(path) || new RegExp(`^/learning/${LANG}/.`).test(path)) {
    return `https://quantum.cloud.ibm.com${encodeURI(path)}`;
  }
  return null;
}
