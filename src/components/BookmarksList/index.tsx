/**
 * BookmarksList — shows bookmarked pages on the homepage.
 * Renders nothing if no bookmarks exist.
 */

import React, { useState, useEffect } from 'react';
import {translate} from '@docusaurus/Translate';
import {
  getBookmarks,
  removeBookmark,
  type Bookmark,
} from '../../config/preferences';

export default function BookmarksList(): JSX.Element | null {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);

  useEffect(() => {
    setBookmarks(getBookmarks());

    // Listen for bookmark changes from DocItem/Footer
    const onChanged = () => setBookmarks(getBookmarks());
    window.addEventListener('dq:bookmarks-changed', onChanged);
    return () => window.removeEventListener('dq:bookmarks-changed', onChanged);
  }, []);

  if (bookmarks.length === 0) return null;

  const handleRemove = (e: React.MouseEvent, path: string) => {
    e.preventDefault();
    e.stopPropagation();
    removeBookmark(path);
    setBookmarks(getBookmarks());
  };

  return (
    <div className="dq-bookmarks-list">
      <div className="dq-bookmarks-list__title">{translate({id: 'bookmarksList.title', message: 'Bookmarks'})}</div>
      <div className="dq-bookmarks-list__items">
        {bookmarks.slice(0, 10).map((b) => (
          <a key={b.path} className="dq-bookmark-item" href={b.path}>
            <span className="dq-bookmark-item__title">{b.title}</span>
            <button
              className="dq-bookmark-item__remove"
              onClick={(e) => handleRemove(e, b.path)}
              title={translate({id: 'bookmark.remove', message: 'Remove bookmark'})}
              aria-label={translate({id: 'bookmark.remove', message: 'Remove bookmark'})}
            >
              &times;
            </button>
          </a>
        ))}
      </div>
    </div>
  );
}
