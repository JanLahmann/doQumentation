// Unit tests for the compact progress/bookmark encoding (src/config/progressCodec.ts).
// Run: node --test 'tests/js/*.test.mjs'   (Node >= 22.18 / 23.6 strips the TypeScript types natively)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  buildLookup,
  decodeBitset,
  decodeBookmarkPaths,
  decodePathSet,
  encodeBitset,
  encodeBookmarkPaths,
  encodePathSet,
  normalizeIndexPath,
  parseLegacyArray,
  parseLegacyBookmarks,
  titleFromPath,
  unionBitsets,
} from '../../src/config/progressCodec.ts';

const INDEX = JSON.parse(
  readFileSync(new URL('../../src/config/pageIndex.json', import.meta.url), 'utf8'),
).paths;
const LOOKUP = buildLookup(INDEX);

// A small synthetic index for the exact-value tests (independent of the real one).
const SMALL = ['/a', '/b', '/c/d', '/e', '/f', '/g', '/h', '/workshop/03_Qiskit 101 Hands-on'];
const SMALL_LOOKUP = buildLookup(SMALL);

test('bitset round trip, exact values', () => {
  assert.equal(encodeBitset([]), '1.');
  assert.equal(encodeBitset([0]), '1.B');
  assert.equal(encodeBitset([5]), '1.g');
  assert.equal(encodeBitset([6]), '1.AB');
  assert.equal(encodeBitset([0, 1, 2, 3, 4, 5]), '1._');
  for (const ids of [[], [0], [7, 3, 100], [459, 0, 1, 2], Array.from({ length: 500 }, (_, i) => i)]) {
    assert.deepEqual(decodeBitset(encodeBitset(ids)), [...new Set(ids)].sort((a, b) => a - b));
  }
});

test('bitset is cookie-safe (encodeURIComponent leaves it unchanged)', () => {
  const v = encodeBitset(Array.from({ length: 600 }, (_, i) => (i * 7) % 600));
  assert.equal(encodeURIComponent(v), v);
});

test('garbage and unknown versions decode to nothing', () => {
  for (const bad of [null, undefined, '', 'xyz', '2.AAAB', '1.A$B', '["/a"]']) {
    assert.deepEqual(decodeBitset(bad), []);
  }
});

test('path set: indexed pages in the bitset, others as extras', () => {
  const { bits, extras } = encodePathSet(['/a', '/c/d/', '/zzz', '/zzz', '/workshop/03_Qiskit%20101%20Hands-on'], SMALL_LOOKUP);
  assert.deepEqual(extras, ['/zzz']);
  assert.deepEqual(
    [...decodePathSet(bits, extras, SMALL)].sort(),
    ['/a', '/c/d', '/workshop/03_Qiskit 101 Hands-on', '/zzz'],
  );
});

test('slots beyond the index (newer build) are ignored on decode but kept by union', () => {
  const bits = encodeBitset([1, 50]);
  assert.deepEqual([...decodePathSet(bits, [], SMALL)], ['/b']);
  assert.deepEqual(decodeBitset(unionBitsets(bits, encodeBitset([2]))), [1, 2, 50]);
});

test('bookmarks round trip keeps order and unindexed paths', () => {
  const paths = ['/e', '/a', '/not/indexed!x', '/a', '/h/'];
  const enc = encodeBookmarkPaths(paths, SMALL_LOOKUP);
  assert.deepEqual(decodeBookmarkPaths(enc, SMALL), ['/e', '/a', '/not/indexed!x', '/h']);
  assert.deepEqual(decodeBookmarkPaths('', SMALL), []);
  assert.deepEqual(decodeBookmarkPaths('1.', SMALL), []);
  assert.deepEqual(decodeBookmarkPaths('[{"path":"/a"}]', SMALL), []);
});

test('legacy parsing tolerates junk', () => {
  assert.deepEqual(parseLegacyArray('not json'), []);
  assert.deepEqual(parseLegacyArray('{"a":1}'), []);
  assert.deepEqual(
    parseLegacyBookmarks('[{"path":"/a/","title":"A","savedAt":5},{"title":"no path"},7,null]'),
    [{ path: '/a', title: 'A', savedAt: 5 }],
  );
});

test('titleFromPath gives a readable fallback', () => {
  assert.equal(titleFromPath('/learning/courses/basics-of-quantum-information/single-systems'), 'Single systems');
  assert.equal(titleFromPath('/qiskit-addons/obp/01_getting_started'), 'Getting started');
});

test('real page index is sane', () => {
  assert.ok(INDEX.length > 300, `index has ${INDEX.length} entries`);
  assert.equal(new Set(INDEX).size, INDEX.length, 'no duplicates');
  for (const p of INDEX) {
    assert.equal(normalizeIndexPath(p), p, `entry is normalized: ${p}`);
  }
});

test('migration of a "visited everything" legacy cookie (~65 KB) to a tiny bitset', () => {
  // The old format: JSON array of every path, URL-encoded into the cookie.
  const legacyVisited = JSON.stringify(INDEX);
  const legacyExecuted = JSON.stringify(INDEX.filter((_, i) => i % 2 === 0));
  const legacySize = encodeURIComponent(legacyVisited).length + encodeURIComponent(legacyExecuted).length;
  assert.ok(legacySize > 40_000, `legacy cookies are large (${legacySize} B)`);

  const visited = encodePathSet(parseLegacyArray(legacyVisited), LOOKUP);
  const executed = encodePathSet(parseLegacyArray(legacyExecuted), LOOKUP);
  assert.deepEqual(visited.extras, []);
  assert.ok(visited.bits.length <= 2 + Math.ceil(INDEX.length / 6), `visited bitset ${visited.bits.length} chars`);
  assert.ok(encodeURIComponent(visited.bits).length < 120);

  // Nobody loses progress: every legacy path decodes back.
  assert.deepEqual([...decodePathSet(visited.bits, visited.extras, INDEX)].sort(), [...INDEX].sort());
  assert.deepEqual(
    [...decodePathSet(executed.bits, executed.extras, INDEX)].sort(),
    INDEX.filter((_, i) => i % 2 === 0).sort(),
  );
});
