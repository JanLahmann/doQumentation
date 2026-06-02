/**
 * Docusaurus plugin that injects per-page hreflang alternate links into the
 * static HTML at build time, for international SEO.
 *
 * Why a postBuild HTML rewrite (and not headTags / injectHtmlTags)?
 *   - Each locale is deployed to its OWN subdomain (https://<locale>.doqumentation.org)
 *     and built in isolation via `docusaurus build --locale XX`. A build only
 *     knows its own locale + URL, so Docusaurus's built-in path-based hreflang
 *     (which assumes /de/, /es/ under one domain) does not apply here.
 *   - Because routing is subdomain-per-locale, a page's PATH is identical across
 *     every locale — only the subdomain changes. So the equivalent of
 *     `/guides/foo` in German is `https://de.doqumentation.org/guides/foo`.
 *   - hreflang must be in the crawled HTML <head>; client-side injection is
 *     unreliable for SEO. headTags/injectHtmlTags are global (no per-page path),
 *     so we walk the emitted HTML in postBuild and inject path-aware tags.
 *
 * Emits, into every indexable page's <head>:
 *   <link rel="alternate" hreflang="<locale>" href="https://<sub>.doqumentation.org<path>" />  (× all locales)
 *   <link rel="alternate" hreflang="x-default" href="https://doqumentation.org<path>" />        (EN canonical)
 *
 * The locale → subdomain URL map is read from i18n.localeConfigs (the single
 * source of truth in docusaurus.config.ts), so adding a locale there is enough.
 *
 * Also: NOINDEXES untranslated-fallback pages.
 *   A non-EN locale build serves EN content (with a "not yet translated"
 *   banner) for any page not yet genuinely translated. Indexing that page would
 *   put EN text under a non-EN subdomain — thin/duplicate content. We detect
 *   such pages by the doqumentation-untranslated-fallback MDX-comment marker in
 *   the i18n MDX source (the marker is stripped from the rendered HTML, so we
 *   read the source at build time) and inject
 *   `<meta name="robots" content="noindex, follow">` into the page.
 *   `follow` keeps link equity flowing. Fallback pages are then also skipped for
 *   hreflang (Google: don't list noindex pages as alternates). EN builds have no
 *   fallbacks, so nothing is noindexed there.
 */

const fs = require("fs");
const path = require("path");

const PLUGIN_NAME = "hreflang";

const FALLBACK_MARKER = "{/* doqumentation-untranslated-fallback */}";

// Pages that must not advertise alternates / should not be crawled.
// Mirrors robots.txt Disallow and Docusaurus' generated utility pages.
const EXCLUDE_PATHS = new Set(["/admin", "/404", "/search"]);

// hreflang values must be BCP-47. Map a few of our internal locale codes to
// valid tags; everything else is passed through unchanged (de, es, fr, ...).
// German regional dialects have no standard 2-letter tag, so we tag them as
// German regional variants where ISO 639-3 / BCP-47 has a code, else fall back
// to `de` (better than emitting an invalid tag Google will ignore).
const HREFLANG_OVERRIDES = {
  tl: "fil", // Filipino
  // German dialects → closest valid BCP-47 / ISO 639-3 tag
  swg: "swg", // Swabian (ISO 639-3, valid)
  gsw: "gsw", // Swiss German (ISO 639-2/3, valid)
  nds: "nds", // Low German (ISO 639-2, valid)
  bar: "bar", // Bavarian (ISO 639-3, valid)
  ksh: "ksh", // Kölsch (ISO 639-3, valid)
  // No standard code — fall back to generic German so the alternate is still valid:
  bad: "de",
  sax: "de",
  bln: "de",
  aut: "de-AT",
};

function toHreflang(locale) {
  return HREFLANG_OVERRIDES[locale] || locale;
}

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

module.exports = function hreflangPlugin(context, _options) {
  const { i18n, siteDir } = context;
  const localeConfigs = i18n.localeConfigs || {};
  const currentLocale = i18n.currentLocale;
  const fallbackRoutes = collectFallbackRoutes(siteDir, currentLocale);

  // Build [hreflang, baseUrl] pairs once. baseUrl has no trailing slash.
  const alternates = Object.entries(localeConfigs)
    .filter(([, cfg]) => cfg && cfg.url)
    .map(([locale, cfg]) => ({
      hreflang: toHreflang(locale),
      base: String(cfg.url).replace(/\/$/, ""),
    }));

  const enBase = (localeConfigs.en && localeConfigs.en.url
    ? String(localeConfigs.en.url)
    : "https://doqumentation.org"
  ).replace(/\/$/, "");

  return {
    name: PLUGIN_NAME,

    async postBuild({ outDir }) {
      if (alternates.length === 0) return;

      const files = walkHtml(outDir, []);
      let injected = 0;
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
            const updated = html.replace(/<\/head>/i, `${meta}</head>`);
            if (updated !== html) {
              fs.writeFileSync(file, updated, "utf8");
              noindexed++;
            }
          }
          continue;
        }

        // Skip pages the build marked noindex (e.g. password-gated admin).
        if (/<meta[^>]+name=["']robots["'][^>]+noindex/i.test(html)) continue;
        // Idempotent: don't double-inject on re-runs.
        if (html.includes('data-rh-hreflang')) continue;

        const links = alternates
          .map(
            (a) =>
              `<link data-rh-hreflang rel="alternate" hreflang="${a.hreflang}" href="${a.base}${route === "/" ? "/" : route}" />`
          )
          .join("");
        const xDefault = `<link data-rh-hreflang rel="alternate" hreflang="x-default" href="${enBase}${route === "/" ? "/" : route}" />`;

        const tags = links + xDefault;
        const updated = html.replace(/<\/head>/i, `${tags}</head>`);
        if (updated !== html) {
          fs.writeFileSync(file, updated, "utf8");
          injected++;
        }
      }

      console.log(
        `[${PLUGIN_NAME}] ${currentLocale}: injected alternates into ${injected} page(s) ` +
          `(${alternates.length} locales + x-default); noindexed ${noindexed} fallback page(s)`
      );
    },
  };
};
