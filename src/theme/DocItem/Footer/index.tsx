/**
 * Swizzled DocItem/Footer — wraps the original to add
 * a bookmark toggle button above the footer.
 */

import React, { useState, useEffect } from 'react';
import OriginalFooter from '@theme-original/DocItem/Footer';
import {
  isBookmarked,
  addBookmark,
  removeBookmark,
} from '../../../config/preferences';

export const BOOKMARKS_CHANGED_EVENT = 'dq:bookmarks-changed';

type Props = React.ComponentProps<typeof OriginalFooter>;

export default function DocItemFooter(props: Props): JSX.Element {
  const [bookmarked, setBookmarked] = useState(false);

  useEffect(() => {
    setBookmarked(isBookmarked(window.location.pathname));
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
    window.dispatchEvent(new CustomEvent(BOOKMARKS_CHANGED_EVENT));
  };

  return (
    <>
      <button
        className={`dq-bookmark-button${bookmarked ? ' dq-bookmark-button--active' : ''}`}
        onClick={handleToggle}
        title={bookmarked ? 'Remove bookmark' : 'Bookmark this page'}
        aria-label={bookmarked ? 'Remove bookmark' : 'Bookmark this page'}
      >
        <span className="dq-bookmark-button__icon" aria-hidden="true">
          {bookmarked ? '\u2605' : '\u2606'}
        </span>
        {bookmarked ? 'Bookmarked' : 'Bookmark'}
      </button>
      <OriginalFooter {...props} />
    </>
  );
}
