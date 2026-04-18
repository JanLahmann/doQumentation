/**
 * Swizzled EditThisPage — wraps the original to add
 * a bookmark toggle button and "View original" link next to "Edit this page".
 */

import React, { useState, useEffect } from 'react';
import OriginalEditThisPage from '@theme-original/EditThisPage';
import {translate} from '@docusaurus/Translate';
import {
  isBookmarked,
  addBookmark,
  removeBookmark,
} from '../../config/preferences';

type Props = React.ComponentProps<typeof OriginalEditThisPage>;

/**
 * Map a doQumentation page path to its original URL on IBM Quantum / upstream.
 * Returns null if no mapping exists (e.g. index pages, settings).
 */
function getOriginalPageUrl(pathname: string): string | null {
  // Strip locale prefix (e.g. /de/guides/... → /guides/...)
  const path = pathname.replace(/^\/[a-z]{2}(-[a-z]+)?(?=\/)/, '').replace(/\/$/, '');

  if (path.startsWith('/guides/')) {
    const slug = path.replace('/guides/', '');
    if (slug && slug !== 'index') return `https://docs.quantum.ibm.com/guides/${slug}`;
  }
  if (path.startsWith('/tutorials/')) {
    const slug = path.replace('/tutorials/', '');
    if (slug && slug !== 'index') return `https://learning.quantum.ibm.com/tutorial/${slug}`;
  }
  if (path.startsWith('/learning/courses/')) {
    // /learning/courses/{course}/{lesson} → learning.quantum.ibm.com/course/{course}
    const parts = path.replace('/learning/courses/', '').split('/');
    if (parts[0]) return `https://learning.quantum.ibm.com/course/${parts[0]}`;
  }
  if (path.startsWith('/learning/modules/')) {
    const parts = path.replace('/learning/modules/', '').split('/');
    if (parts[0]) return `https://learning.quantum.ibm.com/course/${parts[0]}`;
  }
  if (path.startsWith('/qiskit-addons/')) {
    // /qiskit-addons/{addon}/... → qiskit.github.io/qiskit-addon-{addon}
    const parts = path.replace('/qiskit-addons/', '').split('/');
    if (parts[0] && parts[0] !== 'index') return `https://qiskit.github.io/qiskit-addon-${parts[0]}`;
  }
  return null;
}

export default function EditThisPage(props: Props): JSX.Element {
  const [bookmarked, setBookmarked] = useState(false);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);

  useEffect(() => {
    setBookmarked(isBookmarked(window.location.pathname));
    setOriginalUrl(getOriginalPageUrl(window.location.pathname));
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
          ? translate({id: 'bookmark.remove', message: 'Remove bookmark'})
          : translate({id: 'bookmark.add', message: 'Bookmark this page'})}
        aria-label={bookmarked
          ? translate({id: 'bookmark.remove', message: 'Remove bookmark'})
          : translate({id: 'bookmark.add', message: 'Bookmark this page'})}
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
