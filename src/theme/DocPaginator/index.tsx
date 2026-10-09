import React, {type ReactNode} from 'react';
import OriginalDocPaginator from '@theme-original/DocPaginator';
import type {Props} from '@theme/DocPaginator';
import {useLocation} from '@docusaurus/router';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';

/**
 * Keep Previous/Next inside the current section.
 *
 * The whole site is one sidebar (Tutorials → Guides → Courses → Modules), and
 * Docusaurus paginates straight across it: a course overview's "Previous" was
 * the last guide, and a course's exam had "Next" into the alphabetically next,
 * unrelated course. We drop a prev/next link whose target lies in a different
 * section than the current page. A section is
 *   - one course:  /learning/courses/<course>/…
 *   - one module:  /learning/modules/<module>/…
 *   - otherwise the top-level folder: /tutorials/…, /guides/…
 * Decided by URL only, so it works the same on every locale site (same paths,
 * translated titles) and needs no front matter in docs/.
 */
function sectionKey(path: string, baseUrl: string): string {
  let p = path;
  if (baseUrl && baseUrl !== '/' && p.startsWith(baseUrl)) {
    p = p.slice(baseUrl.length);
  }
  const segs = p.split(/[?#]/)[0].split('/').filter(Boolean);
  if (segs[0] === 'learning' && (segs[1] === 'courses' || segs[1] === 'modules')) {
    return segs.slice(0, 3).join('/');
  }
  return segs[0] ?? '';
}

export default function DocPaginator(props: Props): ReactNode {
  const {pathname} = useLocation();
  const {
    siteConfig: {baseUrl},
  } = useDocusaurusContext();
  const here = sectionKey(pathname, baseUrl);
  const same = (link: Props['previous']) =>
    link && sectionKey(link.permalink, baseUrl) === here ? link : undefined;
  const previous = same(props.previous);
  const next = same(props.next);
  if (!previous && !next) {
    return null;
  }
  return <OriginalDocPaginator {...props} previous={previous} next={next} />;
}
