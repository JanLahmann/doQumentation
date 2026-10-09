/**
 * Map a doQumentation page path to its original URL on IBM Quantum.
 * Returns null if no mapping exists (e.g. index pages, settings, workshop).
 *
 * Used by:
 *  - src/theme/EditThisPage  (the inline "View original" link)
 *  - src/theme/DocItem/Footer (the source-date block)
 */
// Current IBM Quantum hosts. The legacy docs./learning.quantum.ibm.com URLs
// redirect twice, and their module URLs (/course/<module>) end in a 404.
const IBM_DOCS = "https://quantum.cloud.ibm.com/docs/en";
const IBM_LEARNING = "https://quantum.cloud.ibm.com/learning/en";

export function getOriginalPageUrl(pathname: string): string | null {
  // Strip locale prefix (e.g. /de/guides/... → /guides/...)
  const path = pathname
    .replace(/^\/[a-z]{2}(-[a-z]+)?(?=\/)/, "")
    .replace(/\/$/, "");

  if (path.startsWith("/guides/")) {
    const slug = path.replace("/guides/", "");
    if (slug && slug !== "index")
      return `${IBM_DOCS}/guides/${slug}`;
  }
  if (path.startsWith("/tutorials/")) {
    const slug = path.replace("/tutorials/", "");
    if (slug && slug !== "index")
      return `${IBM_DOCS}/tutorials/${slug}`;
  }
  // Courses and modules: the lesson itself, not the course's front page.
  for (const kind of ["courses", "modules"]) {
    const prefix = `/learning/${kind}/`;
    if (path.startsWith(prefix)) {
      const rest = path.slice(prefix.length).replace(/\/index$/, "");
      if (rest && rest !== "index")
        return `${IBM_LEARNING}/${kind}/${rest}`;
    }
  }
  if (path.startsWith("/qiskit-addons/")) {
    const parts = path.replace("/qiskit-addons/", "").split("/");
    if (parts[0] && parts[0] !== "index")
      return `https://qiskit.github.io/qiskit-addon-${parts[0]}`;
  }
  return null;
}
