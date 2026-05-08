/**
 * Swizzled EditThisPage — wraps the original to add
 * a bookmark toggle button and "View original" link next to "Edit this page".
 */

import React, { useState, useEffect } from 'react';
import OriginalEditThisPage from '@theme-original/EditThisPage';
import {translate} from '@docusaurus/Translate';
import {usePluginData} from '@docusaurus/useGlobalData';
import {
  isBookmarked,
  addBookmark,
  removeBookmark,
} from '../../config/preferences';
import {getOriginalPageUrl} from '../../lib/originalUrl';

type Props = React.ComponentProps<typeof OriginalEditThisPage>;

type PageDatesData = {
  locale: string;
  pages: Record<string, unknown>;
};

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

export default function EditThisPage(props: Props): JSX.Element {
  const data = usePluginData('page-dates') as PageDatesData | undefined;
  const relPath = editUrlToRelPath(props.editUrl);
  const isUpstreamPage = !!(relPath && data?.pages?.[relPath]);

  const [bookmarked, setBookmarked] = useState(false);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);

  useEffect(() => {
    setBookmarked(isBookmarked(window.location.pathname));
    // Only show the "View original" link for pages that come from the
    // IBM upstream — doQumentation-original tutorials (e.g. hello-world)
    // have no upstream counterpart and would otherwise produce a broken
    // link to learning.quantum.ibm.com.
    if (isUpstreamPage) {
      setOriginalUrl(getOriginalPageUrl(window.location.pathname));
    } else {
      setOriginalUrl(null);
    }
  }, [isUpstreamPage]);

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
      <OriginalEditThisPage {...props} />
      {originalUrl && (
        <a
          href={originalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="dq-original-link"
          title={translate({id: 'original.tooltip', message: 'View this page on the IBM Quantum Platform'})}
        >
          {translate({id: 'original.label', message: 'View original on IBM Quantum Platform'})}
        </a>
      )}
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
          {bookmarked ? '\u2605' : '\u2606'}
        </span>
        {bookmarked
          ? translate({id: 'bookmark.active', message: 'Bookmarked'})
          : translate({id: 'bookmark.inactive', message: 'Bookmark'})}
      </button>
    </div>
  );
}
