/**
 * BookmarkButton — toggle the current page in/out of the user's bookmarks.
 *
 * Extracted from the EditThisPage swizzle so the unified DocItem footer
 * can render it inside the feedback group rather than next to the edit
 * links.
 */

import React, {useState, useEffect} from 'react';
import {translate} from '@docusaurus/Translate';
import {
  isBookmarked,
  addBookmark,
  removeBookmark,
} from '../../config/preferences';

export default function BookmarkButton(): React.JSX.Element {
  const [bookmarked, setBookmarked] = useState(false);

  useEffect(() => {
    setBookmarked(isBookmarked(window.location.pathname));
  }, []);

  const handleToggle = () => {
    const path = window.location.pathname;
    const title =
      document.title?.replace(/ \| doQumentation$/, '') || path;
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
  );
}
