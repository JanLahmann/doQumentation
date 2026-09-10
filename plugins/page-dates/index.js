/**
 * Docusaurus plugin that exposes per-page date metadata via globalData,
 * for the source-date footer to render.
 *
 * Input (read from disk at build time):
 *   - src/config/upstreamFileMeta.json   (written by scripts/sync-content.py)
 *       per EN doc: upstream_path, upstream_date, upstream_sha, en_date
 *
 * Output (per build, scoped to the current locale):
 *   globalData["page-dates"]["default"] = {
 *     locale: "de",
 *     pages: {
 *       "guides/primitives.mdx": {
 *         upstreamPath: "docs/guides/primitives.ipynb",
 *         upstreamDate: "2026-04-27",
 *         enDate: "2026-05-07",
 *       },
 *     },
 *   }
 *
 * The dates are the same for every locale: since the v2 pipeline (2026-09)
 * a translated page is rendered from the current English skeleton, so the
 * English version it is based on IS the one dated here. The v1 per-locale
 * "translation base date" from translation/status.json was retired with
 * that file on 2026-09-10.
 *
 * The footer hook reads this with usePluginData("page-dates")
 * and looks up the current doc by its source path.
 */

const fs = require("fs");
const path = require("path");

const PLUGIN_NAME = "page-dates";

module.exports = function pageDatesPlugin(context, _options) {
  const { siteDir, i18n } = context;
  const locale = i18n.currentLocale;

  return {
    name: PLUGIN_NAME,

    async loadContent() {
      const metaPath = path.join(siteDir, "src", "config", "upstreamFileMeta.json");
      let meta = { files: {} };
      if (fs.existsSync(metaPath)) {
        meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
      }

      // Build the locale-scoped page map
      const pages = {};

      // Seed from the upstream manifest: the EN-side data, the same for
      // every locale.
      for (const [relPath, m] of Object.entries(meta.files || {})) {
        pages[relPath] = {
          upstreamPath: m.upstream_path || "",
          upstreamDate: m.upstream_date || "",
          enDate: m.en_date || "",
        };
      }

      return { locale, pages };
    },

    async contentLoaded({ content, actions }) {
      actions.setGlobalData(content);
    },
  };
};
