/**
 * Build-time fixes for upstream content, applied to every page of every
 * locale (locale pages are rendered from PO files and carry copies of the
 * same links and markup, so a fix here needs no translation round).
 *
 *  - fixTablesPreprocessor  (markdown.preprocessor): a paragraph written on
 *    the line right after a table's last row is swallowed into the table by
 *    GFM (on Teleportation it turned into unreadable maths). Insert the
 *    missing blank line.
 *  - remarkContentFixes     (remark plugin):
 *      links   rewrite link forms that 404 here: relative `../api/…` (IBM
 *              API reference), `/docs/api/…`, `/…/index`, bare `/docs`,
 *              pages IBM renamed, `.rst`/`.ipynb` links in the Qiskit
 *              addon tutorials, IBM URLs written without `https://`.
 *      images  wrap very wide output images (circuit drawings with
 *              fold=-1) in a horizontally scrollable box, so they keep a
 *              legible height instead of shrinking to a sliver.
 *      anchors upstream marks link targets with `<span id="…"></span>` and
 *              `<a id="…"></a>`. MDX renders JSX html tags as plain
 *              elements, so Docusaurus never registers those ids and
 *              reports every link to them as a broken anchor. Render them
 *              through <AnchorTarget> (src/theme/MDXComponents), which
 *              registers the id; the page source and its PO entries stay
 *              as they are.
 *
 * The broken-link ratchet (scripts/check-broken-links.py) fails CI when a
 * build reports a broken link that is not in its baseline.
 */
const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------- tables

const FENCE = /^\s{0,3}(`{3,}|~{3,})/;
const TABLE_ROW = /^\s{0,3}\|/;
const DELIMITER_ROW = /^\s{0,3}\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

/**
 * Insert a blank line between a pipe table's last row and a following
 * non-blank line. A table is a `|` header row followed by a delimiter row;
 * fenced code is left alone.
 */
function fixTables(text) {
  if (!text.includes('|')) return text;
  const lines = text.split('\n');
  const out = [];
  let fence = null;
  let inTable = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const m = FENCE.exec(line);
    if (fence) {
      if (m && m[1][0] === fence[0] && m[1].length >= fence.length) fence = null;
      out.push(line);
      continue;
    }
    if (m) {
      fence = m[1];
      inTable = false;
      out.push(line);
      continue;
    }
    if (inTable) {
      if (TABLE_ROW.test(line)) {
        out.push(line);
        continue;
      }
      inTable = false;
      if (line.trim() !== '') out.push('');
    } else if (TABLE_ROW.test(line) && i + 1 < lines.length && DELIMITER_ROW.test(lines[i + 1])
               && lines[i + 1].includes('-')) {
      inTable = true;
    }
    out.push(line);
  }
  return out.join('\n');
}

function fixTablesPreprocessor({fileContent}) {
  return fixTables(fileContent);
}

// ----------------------------------------------------------------- links

const IBM_API = 'https://docs.quantum.ibm.com/api/';

// Pages IBM renamed; upstream still links some of them by the old name.
const RENAMED = {
  '/guides/v2-primitives': '/guides/qiskit-runtime-primitives',
  '/guides/configure-error-mitigation': '/guides/error-mitigation-and-suppression-techniques',
};

function splitHash(url) {
  const i = url.search(/[?#]/);
  return i < 0 ? [url, ''] : [url.slice(0, i), url.slice(i)];
}

/** Return the working URL for `url` on the page at `filePath`, or `url`. */
function fixUrl(url, filePath) {
  if (typeof url !== 'string' || url === '') return url;
  let m;
  // Relative links into IBM's API reference (sync only rewrites /docs/…).
  if ((m = /^(?:\.\.\/)+api\/(.*)$/.exec(url))) return IBM_API + m[1];
  if ((m = /^\/docs\/api\/(.*)$/.exec(url))) return IBM_API + m[1];
  // IBM URLs written without a scheme resolve relative to the page.
  if (/^(?:quantum\.cloud\.ibm\.com|docs\.quantum\.ibm\.com|learning\.quantum\.ibm\.com)\//.test(url)) {
    return 'https://' + url;
  }
  // Qiskit addon tutorials link their own Sphinx docs by source file name.
  const addon = filePath && /[\\/]qiskit-addons[\\/]([^\\/]+)[\\/]/.exec(filePath);
  if (addon && /^\.{1,2}\//.test(url)) {
    const [p, rest] = splitHash(url);
    if (/\.(rst|ipynb)$/.test(p)) {
      const target = path.posix.normalize(`tutorials/${p}`).replace(/\.(rst|ipynb)$/, '.html');
      return `https://qiskit.github.io/qiskit-addon-${addon[1]}/${target}${rest}`;
    }
  }
  if (!url.startsWith('/')) return url;
  let [p, rest] = splitHash(url);
  if (p === '/docs' || p === '/docs/') return '/' + rest;
  if (p.endsWith('/index')) p = p.slice(0, -'/index'.length) || '/';
  if (RENAMED[p]) p = RENAMED[p];
  return p + rest;
}

// ---------------------------------------------------------------- images

// Output images wider than WIDE_RATIO × their height become a scroll box:
// fitted to the ~850 px column they would be under ~170 px tall.
const WIDE_RATIO = 5;

function readDims(file) {
  let fd;
  try {
    fd = fs.openSync(file, 'r');
    const buf = Buffer.alloc(4096);
    const n = fs.readSync(fd, buf, 0, buf.length, 0);
    const b = buf.subarray(0, n);
    if (b.length > 24 && b.readUInt32BE(0) === 0x89504e47) {
      return {width: b.readUInt32BE(16), height: b.readUInt32BE(20)};
    }
    const i = b.indexOf('ispe');
    if (b.indexOf('ftyp') === 4 && i > 0 && i + 16 <= b.length) {
      return {width: b.readUInt32BE(i + 8), height: b.readUInt32BE(i + 12)};
    }
  } catch {
    // missing or unreadable: not wide as far as we know
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
  return null;
}

function isWideImage(url, staticDir) {
  if (typeof url !== 'string' || !/^\/(docs|learning)\/images\//.test(url)) return false;
  const dims = readDims(path.join(staticDir, decodeURI(splitHash(url)[0])));
  return !!dims && dims.height > 0 && dims.width / dims.height > WIDE_RATIO;
}

// --------------------------------------------------------------- anchors

const ANCHOR_TAGS = new Set(['span', 'a']);

/** `<span id="x">` / `<a id="x">` (no href) → `<AnchorTarget as="span" id="x">`. */
function fixAnchorTarget(node) {
  if (!ANCHOR_TAGS.has(node.name)) return;
  const attrs = node.attributes.filter((a) => a.type === 'mdxJsxAttribute');
  if (attrs.some((a) => a.name === 'href')) return;
  if (!attrs.some((a) => a.name === 'id' && typeof a.value === 'string' && a.value)) return;
  node.attributes.push({type: 'mdxJsxAttribute', name: 'as', value: node.name});
  node.name = 'AnchorTarget';
}

// ------------------------------------------------------------ the plugin

function remarkContentFixes(options = {}) {
  const staticDir = options.staticDir || path.join(process.cwd(), 'static');
  return (tree, file) => {
    const filePath = file && (file.path || (file.history && file.history[0]));
    const walk = (node) => {
      if (node.type === 'link' || node.type === 'definition') {
        node.url = fixUrl(node.url, filePath);
      } else if ((node.type === 'mdxJsxFlowElement' || node.type === 'mdxJsxTextElement') && node.attributes) {
        for (const a of node.attributes) {
          if (a.type === 'mdxJsxAttribute' && a.name === 'href' && typeof a.value === 'string') {
            a.value = fixUrl(a.value, filePath);
          }
        }
        fixAnchorTarget(node);
      }
      if (!node.children) return;
      node.children.forEach(walk);
      node.children = node.children.map((child) => {
        if (child.type !== 'paragraph') return child;
        const content = child.children.filter((c) => !(c.type === 'text' && c.value.trim() === ''));
        if (content.length !== 1 || content[0].type !== 'image' || !isWideImage(content[0].url, staticDir)) {
          return child;
        }
        // The box caps the height (CSS); the image links to the full-size
        // file. pathname:// = a plain link to a static file, not a route.
        const image = content[0];
        child.children = [{type: 'link', url: `pathname://${image.url}`, title: null, children: [image]}];
        return {
          type: 'mdxJsxFlowElement',
          name: 'div',
          attributes: [
            {type: 'mdxJsxAttribute', name: 'className', value: 'doq-wide-image'},
            // A scrollable region must be reachable by keyboard.
            {type: 'mdxJsxAttribute', name: 'tabIndex', value: '0'},
          ],
          children: [child],
        };
      });
    };
    walk(tree);
  };
}

module.exports = {remarkContentFixes, fixTablesPreprocessor, fixTables, fixUrl, fixAnchorTarget, readDims};
