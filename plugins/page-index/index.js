/**
 * Docusaurus plugin that keeps the stable page index (src/config/pageIndex.json)
 * in step with the docs.
 *
 * Why: learning progress (visited / executed pages) is shared across the 17
 * language subdomains through cookies on .doqumentation.org. To keep those
 * cookies tiny it is stored as a bitset: bit N = the page at position N of
 * pageIndex.json. A page's position must therefore never change, or every
 * learner's progress would shift onto other pages. The list is APPEND-ONLY:
 * new pages get the next free slot, removed pages keep theirs.
 *
 * Every build compares the docs' permalinks with the committed index:
 *   DQ_PAGE_INDEX=write  append the missing pages (sorted) and rewrite the file
 *                        (sync-upstream.yml runs this, so a content sync carries
 *                        its new pages in the same PR)
 *   DQ_PAGE_INDEX=check  fail the build when a page is missing (ci.yml)
 *   (unset)              warn only. A page missing from the index still works:
 *                        its progress is kept in localStorage on that language
 *                        site only, it just isn't shared across languages.
 *
 * Order is checked separately by scripts/check-page-index.mjs (CI compares the
 * PR's file with the base branch's: the base list must be a prefix).
 */

const fs = require("fs");
const path = require("path");

const INDEX_FILE = path.join("src", "config", "pageIndex.json");

function readIndex(file) {
  if (!fs.existsSync(file)) return [];
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  return Array.isArray(data.paths) ? data.paths : [];
}

function writeIndex(file, paths) {
  const body = {
    _comment:
      "Append-only page index for the compact progress cookies (plugins/page-index). " +
      "Never reorder or delete entries; new pages are appended by DQ_PAGE_INDEX=write.",
    version: 1,
    paths,
  };
  fs.writeFileSync(file, JSON.stringify(body, null, 2) + "\n", "utf8");
}

function normalize(permalink, baseUrl) {
  let p = permalink;
  if (baseUrl && baseUrl !== "/" && p.startsWith(baseUrl)) {
    p = "/" + p.slice(baseUrl.length);
  }
  try {
    p = decodeURI(p);
  } catch {
    /* keep as is */
  }
  return p.replace(/\/+$/, "") || "/";
}

module.exports = function pageIndexPlugin(context) {
  const { siteDir, baseUrl } = context;
  const file = path.join(siteDir, INDEX_FILE);

  return {
    name: "page-index",

    async allContentLoaded({ allContent }) {
      const docsPlugin = allContent["docusaurus-plugin-content-docs"] || {};
      const permalinks = new Set();
      for (const instance of Object.values(docsPlugin)) {
        for (const version of (instance && instance.loadedVersions) || []) {
          for (const doc of version.docs || []) {
            permalinks.add(normalize(doc.permalink, baseUrl));
          }
        }
      }

      const indexed = readIndex(file);
      const known = new Set(indexed);
      const missing = [...permalinks].filter((p) => !known.has(p)).sort();
      if (missing.length === 0) return;

      const mode = process.env.DQ_PAGE_INDEX || "";
      if (mode === "write") {
        writeIndex(file, [...indexed, ...missing]);
        console.log(`[page-index] appended ${missing.length} page(s) to ${INDEX_FILE}`);
        return;
      }
      const list = missing.slice(0, 20).join("\n  ");
      const more = missing.length > 20 ? `\n  … and ${missing.length - 20} more` : "";
      const msg =
        `[page-index] ${missing.length} page(s) are not in ${INDEX_FILE}:\n  ${list}${more}\n` +
        `Their progress stays per language site. Append them with: ` +
        `DQ_PAGE_INDEX=write npx docusaurus build --locale en (and commit ${INDEX_FILE}).`;
      if (mode === "check") throw new Error(msg);
      console.warn(msg);
    },
  };
};
