/**
 * RecentPages — shows a compact list of recently visited pages on the homepage.
 * Renders nothing if no recent pages exist.
 */

import React, { useState, useEffect } from 'react';
import { getRecentPages, type RecentPage } from '../../config/preferences';

function timeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function RecentPages(): JSX.Element | null {
  const [pages, setPages] = useState<RecentPage[]>([]);

  useEffect(() => {
    // Show at most 5 recent pages, skip the current page and bare-title entries
    const recent = getRecentPages()
      .filter(p => p.path !== window.location.pathname && p.title !== 'doQumentation');
    setPages(recent.slice(0, 5));
  }, []);

  if (pages.length === 0) return null;

  return (
    <div className="dq-recent-pages">
      <div className="dq-recent-pages__title">Recent pages</div>
      <div className="dq-recent-pages__items">
        {pages.map((page) => (
          <a key={page.path} className="dq-recent-page-item" href={page.path}>
            <span className="dq-recent-page-item__title">{page.title}</span>
            <span className="dq-recent-page-item__time">{timeAgo(page.ts)}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
