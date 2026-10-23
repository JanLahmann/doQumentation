/**
 * Docusaurus plugin for the per-locale SEO of the subdomain sites
 * (https://<locale>.doqumentation.org, each built alone with --locale XX).
 *
 * hreflang: Docusaurus itself emits one full set of alternates per page
 * (every locale's i18n.localeConfigs url + x-default), so this plugin adds
 * none. It used to inject a second set, which left every page with two.
 *
 * NOINDEXES untranslated-fallback pages.
 *   A non-EN locale build serves EN content (with a "not yet translated"
 *   banner) for any page not yet genuinely translated. Indexing that page would
 *   put EN text under a non-EN subdomain — thin/duplicate content. We detect
 *   such pages by the doqumentation-untranslated-fallback MDX-comment marker in
 *   the i18n MDX source (the marker is stripped from the rendered HTML, so we
 *   read the source at build time) and inject
 *   `<meta name="robots" content="noindex, follow">` into the page.
 *   `follow` keeps link equity flowing. docusaurus.config.ts also leaves them
 *   out of the sitemap. EN builds have no fallbacks, so nothing is noindexed
 *   there.
 *
 * Also: points robots.txt at THIS build's sitemap.
 *   static/robots.txt names https://doqumentation.org/sitemap.xml, and every
 *   locale build copies it, so each subdomain told crawlers to read the EN
 *   sitemap and its own sitemap.xml was never advertised. The `Sitemap:` line
 *   is rewritten to the current locale's URL from i18n.localeConfigs.
 */

const fs = require("fs");
const path = require("path");

const PLUGIN_NAME = "hreflang";

const FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}";

// Pages that should not be crawled.
// Mirrors robots.txt Disallow and Docusaurus' generated utility pages.
const EXCLUDE_PATHS = new Set(["/admin", "/404", "/search"]);

/** Recursively collect every .html file under dir. */
function walkHtml(dir, acc) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkHtml(full, acc);
    } else if (entry.isFile() && entry.name.endsWith(".html")) {
      acc.push(full);
    }
  }
  return acc;
}

/**
 * Convert an emitted HTML file path to its site route path.
 *   outDir/index.html            -> /
 *   outDir/guides.html           -> /guides
 *   outDir/guides/foo.html       -> /guides/foo
 *   outDir/guides/foo/index.html -> /guides/foo
 * (trailingSlash:false in this project, so we normalize to no trailing slash.)
 */
function fileToRoute(file, outDir) {
  let rel = path.relative(outDir, file).split(path.sep).join("/");
  rel = rel.replace(/index\.html$/, "").replace(/\.html$/, "");
  rel = rel.replace(/\/$/, "");
  return "/" + rel; // leading slash; "" -> "/"
}

/**
 * Build the set of route paths that are untranslated fallbacks for `locale`,
 * by scanning the i18n MDX source for the fallback marker. Returns an empty Set
 * for EN (no fallbacks) or when the i18n dir is absent.
 *
 * Source layout: i18n/<locale>/docusaurus-plugin-content-docs/current/<path>.mdx
 * Route:         /<path-without-extension>  (index.mdx -> the dir route)
 */
function collectFallbackRoutes(siteDir, locale) {
  const routes = new Set();
  if (!locale || locale === "en") return routes;

  const root = path.join(
    siteDir,
    "i18n",
    locale,
    "docusaurus-plugin-content-docs",
    "current"
  );
  if (!fs.existsSync(root)) return routes;

  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
      } else if (entry.isFile() && /\.mdx?$/.test(entry.name)) {
        let content;
        try {
          content = fs.readFileSync(full, "utf8");
        } catch {
          continue;
        }
        if (!content.includes(FALLBACK_MARKER)) continue;
        let rel = path.relative(root, full).split(path.sep).join("/");
        rel = rel.replace(/\.mdx?$/, "").replace(/\/?index$/, "");
        routes.add("/" + rel.replace(/^\/+/, "").replace(/\/$/, ""));
      }
    }
  }
  return routes;
}

/** Remove the site-wide `index, follow` robots meta (docusaurus.config.ts
 *  headTags) from a page that sets noindex itself. */
function dropIndexRobots(html) {
  return html.replace(/<meta[^>]+name=["']robots["'][^>]+content=["']index,[^"']*["'][^>]*>/gi, "");
}

/** Percent-encode spaces in the canonical, hreflang and og:url URLs. Docusaurus
 *  writes a route with spaces (the workshop notebooks' file names) into them
 *  raw, and Google then picks a canonical of its own. */
function encodeHeadUrls(html) {
  return html.replace(
    /(<link[^>]+rel=["'](?:canonical|alternate)["'][^>]*\bhref=["']|<meta[^>]+property=["']og:url["'][^>]*\bcontent=["'])([^"']*)/gi,
    (_, tag, url) => tag + url.replace(/ /g, "%20")
  );
}

module.exports = function hreflangPlugin(context, _options) {
  const { i18n, siteDir } = context;
  const localeConfigs = i18n.localeConfigs || {};
  const currentLocale = i18n.currentLocale;
  const fallbackRoutes = collectFallbackRoutes(siteDir, currentLocale);

  const ownBase = String(
    (localeConfigs[currentLocale] && localeConfigs[currentLocale].url) || context.siteConfig.url
  ).replace(/\/$/, "");

  return {
    name: PLUGIN_NAME,

    async postBuild({ outDir }) {
      const robots = path.join(outDir, "robots.txt");
      if (fs.existsSync(robots)) {
        const text = fs.readFileSync(robots, "utf8");
        const updated = text.replace(/^Sitemap:.*$/m, `Sitemap: ${ownBase}/sitemap.xml`);
        if (updated !== text) fs.writeFileSync(robots, updated, "utf8");
      }

      const files = walkHtml(outDir, []);
      let noindexed = 0;

      for (const file of files) {
        const route = fileToRoute(file, outDir);
        if (EXCLUDE_PATHS.has(route)) continue;

        let html;
        try {
          html = fs.readFileSync(file, "utf8");
        } catch {
          continue;
        }

        const encoded = encodeHeadUrls(html);
        if (encoded !== html) {
          fs.writeFileSync(file, encoded, "utf8");
          html = encoded;
        }

        // Untranslated fallback (EN content under a non-EN subdomain): noindex
        // it so it isn't indexed as thin/duplicate content, and skip hreflang
        // (don't advertise a noindex page as an alternate). `follow` keeps link
        // equity flowing through the page's links.
        if (fallbackRoutes.has(route)) {
          if (
            !/<meta[^>]+name=["']robots["'][^>]+noindex/i.test(html) &&
            !html.includes("data-dq-fallback-noindex")
          ) {
            const meta =
              '<meta data-dq-fallback-noindex name="robots" content="noindex, follow" />';
            const updated = dropIndexRobots(html).replace(/<\/head>/i, `${meta}</head>`);
            if (updated !== html) {
              fs.writeFileSync(file, updated, "utf8");
              noindexed++;
            }
          }
          continue;
        }

        // Pages the build marked noindex (e.g. password-gated admin): drop the
        // site-wide "index, follow" robots tag there so the page does not
        // carry two conflicting robots metas.
        if (/<meta[^>]+name=["']robots["'][^>]+noindex/i.test(html)) {
          const cleaned = dropIndexRobots(html);
          if (cleaned !== html) fs.writeFileSync(file, cleaned, "utf8");
        }
      }

      console.log(`[${PLUGIN_NAME}] ${currentLocale}: noindexed ${noindexed} fallback page(s)`);
    },
  };
};

// docusaurus.config.ts drops these routes from each locale's sitemap.xml.
module.exports.collectFallbackRoutes = collectFallbackRoutes;
