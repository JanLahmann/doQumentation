/**
 * Compact encodings for learning progress and bookmarks.
 *
 * Progress (visited / executed pages) is shared across the language
 * subdomains through cookies, which travel with every request. The old format
 * (URL-encoded JSON arrays of paths, ~100 bytes per page) grew without limit
 * and, for a learner who had visited everything, pushed the Cookie header past
 * what the static host accepts (~64 KB), blanking the site on every language.
 *
 * New format: one bit per page over the append-only page index
 * (src/config/pageIndex.json, kept by plugins/page-index). Six bits per
 * base64url character, so ~460 pages cost ~80 characters, with no escaping
 * needed in a cookie. Paths not in the index are returned separately as
 * "extras" (the caller keeps them in localStorage on that site only).
 *
 * This module is pure (no DOM, no imports) so node's test runner can load it
 * directly: tests/js/progressCodec.test.mjs.
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const BITSET_VERSION = '1';
const BOOKMARK_VERSION = '1';

/** Normalize a path the same way the index does: decoded, no trailing slash. */
export function normalizeIndexPath(path: string): string {
  let p = path;
  try {
    p = decodeURI(p);
  } catch {
    /* keep as is */
  }
  return p.replace(/\/+$/, '') || '/';
}

/** Build a path → slot lookup for an index. */
export function buildLookup(index: readonly string[]): Map<string, number> {
  const map = new Map<string, number>();
  index.forEach((p, i) => {
    const key = normalizeIndexPath(p);
    if (!map.has(key)) map.set(key, i);
  });
  return map;
}

/** Encode a set of slot numbers as "1.<base64url bits>" (trailing zeros trimmed). */
export function encodeBitset(ids: Iterable<number>): string {
  const sextets: number[] = [];
  for (const id of ids) {
    if (!Number.isInteger(id) || id < 0) continue;
    const c = Math.floor(id / 6);
    while (sextets.length <= c) sextets.push(0);
    sextets[c] |= 1 << (id % 6);
  }
  while (sextets.length && sextets[sextets.length - 1] === 0) sextets.pop();
  return BITSET_VERSION + '.' + sextets.map((s) => ALPHABET[s]).join('');
}

/** Decode "1.<base64url bits>" to slot numbers. Unknown/garbled input → []. */
export function decodeBitset(value: string | null | undefined): number[] {
  if (!value) return [];
  const dot = value.indexOf('.');
  if (dot < 0 || value.slice(0, dot) !== BITSET_VERSION) return [];
  const body = value.slice(dot + 1);
  const ids: number[] = [];
  for (let c = 0; c < body.length; c++) {
    const s = ALPHABET.indexOf(body[c]);
    if (s < 0) return [];
    for (let b = 0; b < 6; b++) {
      if (s & (1 << b)) ids.push(c * 6 + b);
    }
  }
  return ids;
}

/** Split a set of paths into the bitset (indexed pages) and the extras (the rest). */
export function encodePathSet(
  paths: Iterable<string>,
  lookup: Map<string, number>,
): { bits: string; extras: string[] } {
  const ids: number[] = [];
  const extras: string[] = [];
  const seenExtra = new Set<string>();
  for (const raw of paths) {
    if (typeof raw !== 'string' || !raw) continue;
    const p = normalizeIndexPath(raw);
    const id = lookup.get(p);
    if (id !== undefined) ids.push(id);
    else if (!seenExtra.has(p)) {
      seenExtra.add(p);
      extras.push(p);
    }
  }
  return { bits: encodeBitset(ids), extras };
}

/** Inverse of encodePathSet. Slots beyond the index (a newer build) are ignored. */
export function decodePathSet(
  bits: string | null | undefined,
  extras: readonly string[],
  index: readonly string[],
): Set<string> {
  const out = new Set<string>();
  for (const id of decodeBitset(bits)) {
    if (id < index.length) out.add(normalizeIndexPath(index[id]));
  }
  for (const p of extras) {
    if (typeof p === 'string' && p) out.add(normalizeIndexPath(p));
  }
  return out;
}

/**
 * Merge two bitsets, keeping slots this build does not know yet.
 * (A tab running an older build must not wipe bits a newer build set.)
 */
export function unionBitsets(a: string | null | undefined, b: string | null | undefined): string {
  return encodeBitset([...decodeBitset(a), ...decodeBitset(b)]);
}

// ── Bookmarks: "1.<token>!<token>…", newest first ──
// token = base36 slot for an indexed page, or "~" + escaped path otherwise.

function escapePath(p: string): string {
  return encodeURIComponent(p).replace(/!/g, '%21');
}

export function encodeBookmarkPaths(paths: readonly string[], lookup: Map<string, number>): string {
  const tokens: string[] = [];
  const seen = new Set<string>();
  for (const raw of paths) {
    const p = normalizeIndexPath(raw);
    if (seen.has(p)) continue;
    seen.add(p);
    const id = lookup.get(p);
    tokens.push(id !== undefined ? id.toString(36) : '~' + escapePath(p));
  }
  return BOOKMARK_VERSION + '.' + tokens.join('!');
}

export function decodeBookmarkPaths(value: string | null | undefined, index: readonly string[]): string[] {
  if (!value) return [];
  const dot = value.indexOf('.');
  if (dot < 0 || value.slice(0, dot) !== BOOKMARK_VERSION) return [];
  const body = value.slice(dot + 1);
  if (!body) return [];
  const out: string[] = [];
  for (const tok of body.split('!')) {
    if (!tok) continue;
    if (tok[0] === '~') {
      try {
        out.push(normalizeIndexPath(decodeURIComponent(tok.slice(1))));
      } catch {
        /* skip garbled token */
      }
    } else {
      const id = parseInt(tok, 36);
      if (Number.isInteger(id) && id >= 0 && id < index.length) out.push(normalizeIndexPath(index[id]));
    }
  }
  return out;
}

/** Readable fallback title for a bookmark whose title this language site has not seen. */
export function titleFromPath(path: string): string {
  const seg = normalizeIndexPath(path).split('/').filter(Boolean).pop() || path;
  const words = seg.replace(/^\d+[-_.\s]+/, '').replace(/[-_]+/g, ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : path;
}

// ── Migration from the old JSON cookies ──

/** Parse an old-format JSON array value; anything else → []. */
export function parseLegacyArray(raw: string | null | undefined): unknown[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export interface LegacyBookmark {
  path: string;
  title: string;
  savedAt: number;
}

/** Old bookmarks value (JSON array of {path,title,savedAt}) → clean list. */
export function parseLegacyBookmarks(raw: string | null | undefined): LegacyBookmark[] {
  const out: LegacyBookmark[] = [];
  for (const b of parseLegacyArray(raw)) {
    if (!b || typeof b !== 'object') continue;
    const o = b as Record<string, unknown>;
    if (typeof o.path !== 'string' || !o.path) continue;
    out.push({
      path: normalizeIndexPath(o.path),
      title: typeof o.title === 'string' ? o.title : '',
      savedAt: typeof o.savedAt === 'number' ? o.savedAt : 0,
    });
  }
  return out;
}
