#!/usr/bin/env node
// Every sidebar label must have an entry in each locale's
// i18n/<locale>/docusaurus-plugin-content-docs/current.json.
//
// Docusaurus falls back to English silently when a key is missing, so a new
// upstream category (or a changed `key`, see toc_children_to_sidebar in
// scripts/sync-content.py) shows English on every language site and no build
// notices. This loads sidebars.ts exactly as Docusaurus does (after
// sync-content.py has written .generated/), derives the translation keys
// Docusaurus uses, and fails when a locale lacks one.
//
// Fix a failure by adding the keys with `npx docusaurus write-translations
// --locale <locale>` (keep only the docs current.json change) and translating
// their "message" values.
//
// Usage: node scripts/check-sidebar-translations.js [--locale xx ...]

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const jiti = require('jiti')(root, {interopDefault: true});
const sidebars = jiti(path.join(root, 'sidebars.ts'));

function keysOf(items, sidebar, out) {
  for (const item of items) {
    if (typeof item !== 'object' || item === null) continue;
    if (item.type === 'category') {
      out.add(`sidebar.${sidebar}.category.${item.key ?? item.label}`);
      keysOf(item.items || [], sidebar, out);
    } else if (item.type === 'link') {
      out.add(`sidebar.${sidebar}.link.${item.key ?? item.label}`);
    } else if ((item.type === 'doc' || item.type === 'ref') && item.label) {
      out.add(`sidebar.${sidebar}.doc.${item.key ?? item.label}`);
    }
  }
  return out;
}

const expected = new Set();
for (const [name, items] of Object.entries(sidebars)) {
  if (Array.isArray(items)) keysOf(items, name, expected);
}

const args = process.argv.slice(2);
const only = args.flatMap((a, i) => (args[i - 1] === '--locale' ? [a] : []));
const locales = (only.length ? only : fs.readdirSync(path.join(root, 'i18n')))
  .filter((l) => l !== 'en')
  .filter((l) => fs.existsSync(path.join(root, 'i18n', l, 'docusaurus-plugin-content-docs', 'current.json')))
  .sort();

let failed = 0;
for (const locale of locales) {
  const file = path.join(root, 'i18n', locale, 'docusaurus-plugin-content-docs', 'current.json');
  const have = JSON.parse(fs.readFileSync(file, 'utf8'));
  const missing = [...expected].filter((k) => !(k in have));
  if (missing.length) {
    failed++;
    console.log(`${locale}: ${missing.length} sidebar label(s) without a translation entry`);
    for (const k of missing.slice(0, 10)) console.log(`  ${k}`);
    if (missing.length > 10) console.log(`  … and ${missing.length - 10} more`);
  }
}

console.log(`${expected.size} sidebar keys checked in ${locales.length} locale(s)`);
if (failed) {
  console.log('Add them: npx docusaurus write-translations --locale <locale>, then translate the new "message" values.');
  process.exit(1);
}
