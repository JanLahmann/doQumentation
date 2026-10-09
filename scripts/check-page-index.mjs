#!/usr/bin/env node
/**
 * Check that src/config/pageIndex.json stayed append-only.
 *
 * Learners' progress cookies are bitsets over this list (bit N = entry N), so
 * reordering or deleting an entry would move everyone's progress onto other
 * pages. CI runs this against the base branch's copy:
 *
 *   node scripts/check-page-index.mjs <base.json> [head.json]
 *
 * Passes when the base list is a prefix of the head list and the head list has
 * no duplicates. A missing/empty base file passes (first introduction).
 */
import { readFileSync, existsSync } from 'node:fs';

const [basePath, headPath = 'src/config/pageIndex.json'] = process.argv.slice(2);
if (!basePath) {
  console.error('usage: check-page-index.mjs <base.json> [head.json]');
  process.exit(2);
}

function load(p) {
  if (!existsSync(p)) return null;
  const text = readFileSync(p, 'utf8').trim();
  if (!text) return null;
  const data = JSON.parse(text);
  if (!Array.isArray(data.paths)) throw new Error(`${p}: no "paths" array`);
  return data.paths;
}

const base = load(basePath) || [];
const head = load(headPath);
if (!head) {
  console.error(`${headPath} is missing`);
  process.exit(1);
}

const errors = [];
const seen = new Set();
head.forEach((p, i) => {
  if (seen.has(p)) errors.push(`duplicate entry at ${i}: ${p}`);
  seen.add(p);
});
if (head.length < base.length) {
  errors.push(`entries were removed: base has ${base.length}, head has ${head.length}`);
}
for (let i = 0; i < Math.min(base.length, head.length); i++) {
  if (base[i] !== head[i]) {
    errors.push(`slot ${i} changed: "${base[i]}" -> "${head[i]}" (the index is append-only)`);
    if (errors.length > 10) break;
  }
}

if (errors.length) {
  console.error('pageIndex.json is not append-only:\n  ' + errors.join('\n  '));
  process.exit(1);
}
console.log(`pageIndex.json OK: ${base.length} base entries kept, ${head.length - base.length} appended`);
