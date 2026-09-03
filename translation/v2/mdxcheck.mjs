#!/usr/bin/env node
// Compile rendered MDX pages the way Docusaurus parses them (MDX 3 + math +
// GFM + directives) and report the ones acorn/micromark reject. The v1 lint
// checks syntax classes it knows; this asks the parser. Usage:
//   node translation/v2/mdxcheck.mjs <file.mdx>...      (exit 1 on any failure)
import {compile} from '@mdx-js/mdx';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import remarkDirective from 'remark-directive';
import remarkFrontmatter from 'remark-frontmatter';
import {readFile} from 'node:fs/promises';

let failed = 0;
for (const file of process.argv.slice(2)) {
  // Docusaurus escapes trailing {#custom-id} on headings before MDX sees
  // them (its heading plugin restores the id); do the same, or every
  // explicit anchor reads as an expression.
  const src = (await readFile(file, 'utf8')).replace(/^(#{1,6} .*?)\{#([^}]+)\}\s*$/gm, '$1\\{#$2\\}');
  try {
    await compile(src, {remarkPlugins: [remarkFrontmatter, remarkMath, remarkGfm, remarkDirective], format: 'mdx'});
  } catch (e) {
    failed++;
    const where = e.line ? `${e.line}:${e.column}` : '';
    console.log(`FAIL ${file} ${where} ${(e.reason || e.message || '').split('\n')[0]}`);
  }
}
console.log(`mdxcheck: ${process.argv.length - 2} file(s), ${failed} failed`);
process.exit(failed ? 1 : 0);
