/**
 * ResumeCard — "Continue where you left off" card for the homepage.
 * Reads the last visited page from localStorage and shows a link.
 * Renders nothing on first visit or if no content page has been visited.
 */

import React, { useState, useEffect } from 'react';
import { getLastPage, type LastPage } from '../../config/preferences';

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

export default function ResumeCard(): JSX.Element | null {
  const [lastPage, setLastPage] = useState<LastPage | null>(null);

  useEffect(() => {
    setLastPage(getLastPage());
  }, []);

  if (!lastPage) return null;

  return (
    <a className="dq-resume-card" href={lastPage.path}>
      <span className="dq-resume-card__icon" aria-hidden="true">&#9654;</span>
      <span className="dq-resume-card__text">
        <span className="dq-resume-card__label">Continue where you left off</span>
        <span className="dq-resume-card__title">{lastPage.title}</span>
      </span>
      <span className="dq-resume-card__time">{timeAgo(lastPage.timestamp)}</span>
    </a>
  );
}
