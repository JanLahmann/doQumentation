/**
 * Swizzled EditThisPage — replaces the default single "Edit this page" link
 * with two clearer feedback paths plus a bookmark toggle:
 *
 *  • Content link
 *      For IBM-upstream pages: "Suggest a content edit on IBM Quantum docs"
 *        → github.com/Qiskit/documentation/edit/main/<upstream_path>
 *      For doQ-original pages: "Edit this page on doQumentation"
 *        → github.com/JanLahmann/doQumentation/edit/main/docs/<rel>
 *
 *  • Site/translation issue link (always shown)
 *      "Site or translation issue?" → opens a new issue on our repo with a
 *       prefilled template (page URL + issue-type checklist).
 *
 *  • Bookmark toggle (unchanged)
 */

import React, { useState, useEffect } from 'react';
import {translate} from '@docusaurus/Translate';
import {usePluginData} from '@docusaurus/useGlobalData';
import {
  isBookmarked,
  addBookmark,
  removeBookmark,
} from '../../config/preferences';

// Props are still typed via the original component for upgrade-safety.
import OriginalEditThisPage from '@theme-original/EditThisPage';
type Props = React.ComponentProps<typeof OriginalEditThisPage>;

type PageEntry = {
  upstreamPath?: string;
};
type PageDatesData = {
  locale: string;
  pages: Record<string, PageEntry>;
};

const DOQ_REPO = 'https://github.com/JanLahmann/doQumentation';
const IBM_REPO = 'https://github.com/Qiskit/documentation';

/**
 * Extract the manifest key (e.g. "tutorials/hello-world.mdx") from the
 * GitHub edit URL Docusaurus passes us. Returns null if the URL doesn't
 * match the expected pattern.
 */
function editUrlToRelPath(editUrl: string | undefined): string | null {
  if (!editUrl) return null;
  const m = editUrl.match(/\/tree\/[^/]+\/docs\/(.+)$/);
  return m ? m[1] : null;
}

function buildContentEditUrl(
  isUpstream: boolean,
  upstreamPath: string | undefined,
  relPath: string | null,
): string | null {
  if (isUpstream && upstreamPath) {
    return `${IBM_REPO}/edit/main/${upstreamPath}`;
  }
  if (relPath) {
    return `${DOQ_REPO}/edit/main/docs/${relPath}`;
  }
  return null;
}

function buildSiteIssueUrl(pagePath: string): string {
  // Use GitHub's issue-creation form with a prefilled body. The user can
  // pick a template from the dropdown; we just hand them the page URL and
  // the categories so they don't have to type that part.
  const body = [
    'Page: https://doqumentation.org' + pagePath,
    '',
    'What kind of issue is this? (delete the ones that don\'t apply)',
    '- [ ] Site/frontend bug (rendering, navigation, broken UI)',
    '- [ ] Translation problem (wrong, missing, or awkward translation)',
    '- [ ] Code execution issue (Binder, Jupyter, kernel, output)',
    '- [ ] Search, sidebar, or other UX issue',
    '- [ ] Accessibility issue',
    '- [ ] Idea / feature request for doQumentation itself',
    '',
    'Note: for issues with the **content itself** (typos, technical errors)',
    'please file upstream at https://github.com/Qiskit/documentation/issues',
    '— that\'s the canonical source for IBM Quantum docs.',
    '',
    '## Description',
    '',
  ].join('\n');
  return `${DOQ_REPO}/issues/new?body=${encodeURIComponent(body)}`;
}

export default function EditThisPage(_props: Props): JSX.Element {
  const data = usePluginData('page-dates') as PageDatesData | undefined;
  const relPath = editUrlToRelPath(_props.editUrl);
  const entry = relPath ? data?.pages?.[relPath] : undefined;
  const isUpstreamPage = !!entry;

  const contentEditUrl = buildContentEditUrl(
    isUpstreamPage, entry?.upstreamPath, relPath,
  );

  const [bookmarked, setBookmarked] = useState(false);
  const [siteIssueUrl, setSiteIssueUrl] = useState<string>(
    `${DOQ_REPO}/issues/new`,
  );

  useEffect(() => {
    setBookmarked(isBookmarked(window.location.pathname));
    setSiteIssueUrl(buildSiteIssueUrl(window.location.pathname));
  }, []);

  const handleToggle = () => {
    const path = window.location.pathname;
    const title = document.title?.replace(/ \| doQumentation$/, '') || path;
    if (bookmarked) {
      removeBookmark(path);
      setBookmarked(false);
    } else {
      addBookmark(path, title);
      setBookmarked(true);
    }
    window.dispatchEvent(new CustomEvent('dq:bookmarks-changed'));
  };

  return (
    <div className="dq-edit-bookmark-row">
      {contentEditUrl && (
        <a
          href={contentEditUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="dq-content-edit-link"
          title={isUpstreamPage
            ? translate({
                id: 'feedback.contentEdit.ibm.tooltip',
                message: 'Open this page in the IBM Quantum docs GitHub repo for editing',
              })
            : translate({
                id: 'feedback.contentEdit.doq.tooltip',
                message: 'Open this page in the doQumentation GitHub repo for editing',
              })}
        >
          {isUpstreamPage
            ? translate({
                id: 'feedback.contentEdit.ibm.label',
                message: 'Suggest a content edit on IBM Quantum docs',
              })
            : translate({
                id: 'feedback.contentEdit.doq.label',
                message: 'Edit this page on doQumentation',
              })}
        </a>
      )}
      <a
        href={siteIssueUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="dq-site-issue-link"
        title={translate({
          id: 'feedback.siteIssue.tooltip',
          message: 'Report a site, translation, or code-execution issue (not the content itself — that goes to the IBM Quantum repo)',
        })}
      >
        {translate({
          id: 'feedback.siteIssue.label',
          message: 'Site or translation issue?',
        })}
      </a>
      <button
        className={`dq-bookmark-button${bookmarked ? ' dq-bookmark-button--active' : ''}`}
        onClick={handleToggle}
        title={bookmarked
          ? translate({id: 'bookmark.remove', message: 'Remove bookmark from homepage'})
          : translate({id: 'bookmark.add', message: 'Save to your bookmarks list on the homepage'})}
        aria-label={bookmarked
          ? translate({id: 'bookmark.remove', message: 'Remove bookmark from homepage'})
          : translate({id: 'bookmark.add', message: 'Save to your bookmarks list on the homepage'})}
      >
        <span className="dq-bookmark-button__icon" aria-hidden="true">
          {bookmarked ? '★' : '☆'}
        </span>
        {bookmarked
          ? translate({id: 'bookmark.active', message: 'Bookmarked'})
          : translate({id: 'bookmark.inactive', message: 'Bookmark'})}
      </button>
    </div>
  );
}
