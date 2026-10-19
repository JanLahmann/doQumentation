/**
 * Static redirect pages for retired and renamed pages.
 *
 * src/theme/NotFound/Content/retiredPages.json (scripts/generate-retired-pages.py)
 * maps old routes to where the page went. The 404 page follows it in the
 * browser, but crawlers still got HTTP 404 for every old URL. This writes
 * <old route>.html (GitHub Pages serves it for the extensionless URL) with a
 * canonical link and an immediate meta refresh, which search engines treat
 * as a permanent redirect.
 *
 * Skipped: an old route that still has a page of its own, and an internal
 * target this build has no page for (the 404 page handles those as before).
 */

const fs = require("fs");
const path = require("path");

const REDIRECTS = path.join(__dirname, "..", "..", "src", "theme", "NotFound", "Content", "retiredPages.json");

function hasPage(outDir, route) {
  const rel = route.replace(/^\//, "");
  return [`${rel}.html`, path.join(rel, "index.html")].some((f) => fs.existsSync(path.join(outDir, f)));
}

function escapeAttr(s) {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function stub(target) {
  const t = escapeAttr(target);
  return `<!doctype html><html><head><meta charset="utf-8"><title>Moved</title>` +
    `<link rel="canonical" href="${t}"><meta name="robots" content="noindex">` +
    `<meta http-equiv="refresh" content="0; url=${t}"></head>` +
    `<body><a href="${t}">${t}</a></body></html>\n`;
}

module.exports = function retiredRedirectsPlugin(context) {
  const site = String(context.siteConfig.url).replace(/\/$/, "");
  return {
    name: "retired-redirects",
    async postBuild({ outDir }) {
      const { redirects = {} } = JSON.parse(fs.readFileSync(REDIRECTS, "utf8"));
      let written = 0;
      for (const [from, to] of Object.entries(redirects)) {
        if (!from.startsWith("/") || from.includes("..") || hasPage(outDir, from)) continue;
        const internal = to.startsWith("/");
        if (internal && !hasPage(outDir, to)) continue;
        const file = path.join(outDir, `${from.replace(/^\//, "")}.html`);
        fs.mkdirSync(path.dirname(file), { recursive: true });
        fs.writeFileSync(file, stub(internal ? site + to : to), "utf8");
        written++;
      }
      console.log(`[retired-redirects] ${context.i18n.currentLocale}: ${written} redirect page(s)`);
    },
  };
};
