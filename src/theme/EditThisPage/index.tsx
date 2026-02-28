/**
 * Swizzled EditThisPage — wraps the original to add
 * a bookmark toggle button next to "Edit this page".
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

export default function EditThisPage(props: Props): JSX.Element {
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
    window.dispatchEvent(new CustomEvent('dq:bookmarks-changed'));
  };

  return (
    <div className="dq-edit-bookmark-row">
      <OriginalEditThisPage {...props} />
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
