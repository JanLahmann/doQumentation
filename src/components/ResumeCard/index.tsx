/**
 * ResumeCard — "Continue where you left off" card for the homepage.
 * Reads the last visited page from localStorage and shows a link.
 * Renders nothing on first visit or if no content page has been visited.
 */

import React, { useState, useEffect } from 'react';
import Translate, {translate} from '@docusaurus/Translate';
import { getLastPage, type LastPage } from '../../config/preferences';

function timeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return translate({id: 'resumeCard.justNow', message: 'just now', description: 'Resume card: the last page was visited less than a minute ago'});
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return translate({id: 'resumeCard.minutesAgo', message: '{n}m ago', description: 'Resume card: minutes since the last visit, short form'}, {n: minutes});
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return translate({id: 'resumeCard.hoursAgo', message: '{n}h ago', description: 'Resume card: hours since the last visit, short form'}, {n: hours});
  const days = Math.floor(hours / 24);
  return translate({id: 'resumeCard.daysAgo', message: '{n}d ago', description: 'Resume card: days since the last visit, short form'}, {n: days});
}

export default function ResumeCard(): React.JSX.Element | null {
  const [lastPage, setLastPage] = useState<LastPage | null>(null);

  useEffect(() => {
    setLastPage(getLastPage());
  }, []);

  if (!lastPage) return null;

  return (
    <a className="dq-resume-card" href={lastPage.path}>
      <span className="dq-resume-card__icon" aria-hidden="true">&#9654;</span>
      <span className="dq-resume-card__text">
        <span className="dq-resume-card__label"><Translate id="resumeCard.label" description="Label of the homepage card that links back to the last page visited">Continue where you left off</Translate></span>
        <span className="dq-resume-card__title">{lastPage.title}</span>
      </span>
      <span className="dq-resume-card__time">{timeAgo(lastPage.timestamp)}</span>
    </a>
  );
}
