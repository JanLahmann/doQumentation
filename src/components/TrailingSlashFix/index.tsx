/**
 * GitHub Pages answers /guides/ with 404.html (trailingSlash: false), and the
 * client router then shows the real page because its matching ignores a
 * trailing slash — but the address bar keeps "/guides/", which is what gets
 * bookmarked and shared. Drop the slash in place (router history, no reload)
 * when the slash-less path is a real page. Unknown paths are left to the 404
 * page (src/theme/NotFound/Content).
 */
import {useEffect} from 'react';
import {useHistory, useLocation} from '@docusaurus/router';
import routes from '@generated/routes';
import {collectPagePaths, type RouteLike} from '@site/src/theme/NotFound/Content/resolve';

let pageSet: Set<string> | null = null;

export default function TrailingSlashFix(): null {
  const {pathname, search, hash} = useLocation();
  const history = useHistory();
  useEffect(() => {
    if (pathname.length < 2 || !pathname.endsWith('/')) return;
    const target = pathname.replace(/\/+$/, '');
    let decoded = target;
    try {
      decoded = decodeURI(target);
    } catch {
      // keep the raw path
    }
    pageSet ??= collectPagePaths(routes as RouteLike[]);
    if (pageSet.has(decoded)) history.replace(target + search + hash);
  }, [pathname, search, hash, history]);
  return null;
}
