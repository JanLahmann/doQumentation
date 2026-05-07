/**
 * Map a doQumentation page path to its original URL on IBM Quantum.
 * Returns null if no mapping exists (e.g. index pages, settings, workshop).
 *
 * Used by:
 *  - src/theme/EditThisPage  (the inline "View original" link)
 *  - src/theme/DocItem/Footer (the source-date block)
 */
export function getOriginalPageUrl(pathname: string): string | null {
  // Strip locale prefix (e.g. /de/guides/... → /guides/...)
  const path = pathname
    .replace(/^\/[a-z]{2}(-[a-z]+)?(?=\/)/, "")
    .replace(/\/$/, "");

  if (path.startsWith("/guides/")) {
    const slug = path.replace("/guides/", "");
    if (slug && slug !== "index")
      return `https://docs.quantum.ibm.com/guides/${slug}`;
  }
  if (path.startsWith("/tutorials/")) {
    const slug = path.replace("/tutorials/", "");
    if (slug && slug !== "index")
      return `https://learning.quantum.ibm.com/tutorial/${slug}`;
  }
  if (path.startsWith("/learning/courses/")) {
    const parts = path.replace("/learning/courses/", "").split("/");
    if (parts[0])
      return `https://learning.quantum.ibm.com/course/${parts[0]}`;
  }
  if (path.startsWith("/learning/modules/")) {
    const parts = path.replace("/learning/modules/", "").split("/");
    if (parts[0])
      return `https://learning.quantum.ibm.com/course/${parts[0]}`;
  }
  if (path.startsWith("/qiskit-addons/")) {
    const parts = path.replace("/qiskit-addons/", "").split("/");
    if (parts[0] && parts[0] !== "index")
      return `https://qiskit.github.io/qiskit-addon-${parts[0]}`;
  }
  return null;
}
