/**
 * Docusaurus plugin that exposes per-page date metadata via globalData,
 * for the source-date footer to render.
 *
 * Inputs (read from disk at build time):
 *   - src/config/upstreamFileMeta.json   (written by scripts/sync-content.py)
 *       per EN doc: upstream_path, upstream_date, upstream_sha, en_date
 *   - translation/status.json            (written by promote-drafts.py)
 *       per locale × path (when promoted): en_base_commit_date, en_base_source
 *
 * Output (per build, scoped to the current locale):
 *   globalData["page-dates"]["default"] = {
 *     locale: "de",
 *     pages: {
 *       "guides/primitives.mdx": {
 *         upstreamPath: "docs/guides/primitives.ipynb",
 *         upstreamDate: "2026-04-27",
 *         enDate: "2026-05-07",
 *         translationBaseDate: "2026-04-09",   // only for non-en
 *         translationBaseSource: "promoted-fallback" | undefined,
 *       },
 *     },
 *   }
 *
 * The footer hook (Phase 4) reads this with usePluginData("page-dates")
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
      const statusPath = path.join(siteDir, "translation", "status.json");

      let meta = { files: {} };
      if (fs.existsSync(metaPath)) {
        meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
      }

      let status = {};
      if (fs.existsSync(statusPath)) {
        status = JSON.parse(fs.readFileSync(statusPath, "utf8"));
      }

      // Build the locale-scoped page map
      const pages = {};

      // 1) Seed from upstream manifest — this is the EN-side data, and
      //    serves as the base for every locale (upstream + en dates are
      //    locale-independent).
      for (const [relPath, m] of Object.entries(meta.files || {})) {
        pages[relPath] = {
          upstreamPath: m.upstream_path || "",
          upstreamDate: m.upstream_date || "",
          enDate: m.en_date || "",
        };
      }

      // 2) For non-EN locales, layer on the translation base date from
      //    status.json. We only show this on translated pages, and only
      //    when the entry was actually promoted (so a draft/needs-fix
      //    entry doesn't leak through as a phantom translation date).
      if (locale !== "en") {
        const localeEntries = status[locale] || {};
        for (const [relPath, entry] of Object.entries(localeEntries)) {
          if (entry.status !== "promoted") continue;
          if (!entry.en_base_commit_date) continue;
          // Make sure we have a row to attach to — translated pages might
          // exist that aren't in the upstream manifest (e.g., workshop
          // content). Synthesize an empty row in that case.
          if (!pages[relPath]) {
            pages[relPath] = {
              upstreamPath: "",
              upstreamDate: "",
              enDate: "",
            };
          }
          // Clamp translation base to enDate. The freshness invariant is
          // upstream_date ≥ en_date ≥ translation_base_date — by definition,
          // a translation cannot be based on an EN revision newer than the
          // EN content currently on doQumentation. Older promote-drafts
          // runs and the Phase 2 backfill recorded en_base_commit_date by
          // walking the *local* docs/ git history, which moves on every
          // sync-content.py run for whitespace/transform reasons and so
          // could land at a date well after the actual upstream content
          // the translator saw. Clamping fixes that without rewriting
          // status.json. Going forward, promote-drafts.py records the
          // upstream content date directly, so clamping is a no-op there.
          let baseDate = entry.en_base_commit_date;
          const enDate = pages[relPath].enDate;
          let clamped = false;
          if (enDate && baseDate > enDate) {
            baseDate = enDate;
            clamped = true;
          }
          pages[relPath].translationBaseDate = baseDate;
          if (clamped) {
            pages[relPath].translationBaseSource = "clamped";
          } else if (entry.en_base_source) {
            pages[relPath].translationBaseSource = entry.en_base_source;
          }
        }
      }

      return { locale, pages };
    },

    async contentLoaded({ content, actions }) {
      actions.setGlobalData(content);
    },
  };
};
