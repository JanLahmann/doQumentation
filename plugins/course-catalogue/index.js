/**
 * Docusaurus plugin that builds the course catalogue page at /learning/courses.
 *
 * Input:
 *   - src/data/courses.json: the hand-maintained part (group, order, hours,
 *     level per course; the module list).
 *   - The docs plugin's loaded content, AFTER translation: the sidebar's
 *     course categories (localized labels → card titles), each course
 *     overview's description, and every page link inside the course (for the
 *     learner's progress).
 *
 * Output: one route, /learning/courses, rendered by
 * src/components/CourseCatalogue, with the merged data passed as a module
 * (so the data loads only on that page, not on every page via globalData).
 *
 * Runs in allContentLoaded(), the hook that sees other plugins' content.
 * Because the sidebar labels and doc descriptions are already translated
 * there, each of the 17 locale builds gets localized titles without any
 * hard-coded English.
 */

const path = require("path");
const fs = require("fs");

const PLUGIN_NAME = "course-catalogue";
const DOCS_PLUGIN = "docusaurus-plugin-content-docs";

/** Collect page links inside a sidebar subtree, the way the sidebar's
 * progress counter does (src/theme/DocSidebarItem/Category: every item's
 * href, linked sub-categories included, the category's own link excluded). */
function collectHrefs(items, docsById) {
  const out = [];
  for (const item of items || []) {
    if (item.type === "doc" || item.type === "ref") {
      const doc = docsById.get(item.id);
      if (doc) out.push(doc.permalink);
    } else if (item.type === "link") {
      out.push(item.href);
    } else if (item.type === "category") {
      if (item.link && item.link.type === "doc") {
        const doc = docsById.get(item.link.id);
        if (doc) out.push(doc.permalink);
      }
      out.push(...collectHrefs(item.items, docsById));
    }
  }
  return out;
}

/** Find the sidebar category whose link is the overview doc `indexId`. */
function findCategory(items, indexId) {
  for (const item of items || []) {
    if (item.type !== "category") continue;
    if (item.link && item.link.type === "doc" && item.link.id === indexId) return item;
    const found = findCategory(item.items, indexId);
    if (found) return found;
  }
  return null;
}

module.exports = function courseCataloguePlugin(context) {
  const dataPath = path.join(context.siteDir, "src", "data", "courses.json");

  return {
    name: PLUGIN_NAME,

    getPathsToWatch() {
      return [dataPath];
    },

    async allContentLoaded({ allContent, actions }) {
      const docsContent = allContent[DOCS_PLUGIN] && allContent[DOCS_PLUGIN].default;
      const version = docsContent && docsContent.loadedVersions && docsContent.loadedVersions[0];
      if (!version) return;

      const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
      const docsById = new Map(version.docs.map((d) => [d.id, d]));
      const sidebarItems = Object.values(version.sidebars || {}).flat();

      const entry = (kind, slug) => {
        const indexId = `learning/${kind}/${slug}/index`;
        const doc = docsById.get(indexId);
        if (!doc) return null; // course not synced in this build
        const category = findCategory(sidebarItems, indexId);
        return {
          slug,
          title: (category && category.label) || doc.title,
          description: doc.description || "",
          href: doc.permalink,
          pages: category ? collectHrefs(category.items, docsById) : [],
        };
      };

      const courses = [];
      for (const c of data.courses) {
        const e = entry("courses", c.slug);
        if (e) courses.push({ ...e, group: c.group, hours: c.hours ?? null, level: c.level || null, isNew: !!c.isNew, series: c.series ?? null });
      }
      const modules = [];
      for (const m of data.modules || []) {
        const e = entry("modules", m.slug);
        if (e) modules.push(e);
      }
      if (courses.length === 0) return;

      const catalogue = {
        groups: data.groups,
        beginnerChoices: (data.beginnerChoices || []).filter((b) => courses.some((c) => c.slug === b.slug)),
        courses,
        modules,
      };
      const catalogueJson = await actions.createData("catalogue.json", JSON.stringify(catalogue));
      const baseUrl = context.baseUrl.endsWith("/") ? context.baseUrl : `${context.baseUrl}/`;
      actions.addRoute({
        path: `${baseUrl}learning/courses`,
        component: "@site/src/components/CourseCatalogue",
        exact: true,
        modules: { catalogue: catalogueJson },
      });
    },
  };
};
