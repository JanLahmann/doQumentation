import React, { useEffect, useState } from 'react';
import Translate, {translate} from '@docusaurus/Translate';

// Dismissal lasts for the browser session. The banner is in the static HTML
// (so it does not push the page down when it appears); an inline head script
// in docusaurus.config.ts sets `html[data-dq-beta-dismissed]` from this key
// before first paint, and custom.css hides the banner under that attribute.
export const BETA_NOTICE_STORAGE_KEY = 'dq-beta-notice-dismissed';

function readDismissed(): boolean {
  try {
    return sessionStorage.getItem(BETA_NOTICE_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export default function BetaNotice(): React.JSX.Element | null {
  // Start "shown" on both server and client so hydration matches; the head
  // script has already hidden it if it was dismissed.
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    if (readDismissed()) setDismissed(true);
  }, []);

  if (dismissed) return null;

  return (
    <div
      className="beta-notice"
      role="region"
      aria-label={translate({id: 'betaNotice.regionLabel', message: 'Beta notice', description: 'Accessible name of the beta notice banner at the top of every page'})}
    >
      <span className="beta-notice__text">
        <Translate
          id="betaNotice.textWithDiscussions"
          values={{
            issueLink: (
              <a
                href="https://github.com/JanLahmann/doQumentation/issues"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Translate id="betaNotice.issueLink">Open a GitHub issue</Translate>
              </a>
            ),
            discussionLink: (
              <a
                href="https://github.com/JanLahmann/doQumentation/discussions"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Translate id="betaNotice.discussionLink">Ask in Discussions</Translate>
              </a>
            ),
          }}
        >
          {'This project is in beta. Found a bug? {issueLink}. Question or idea? {discussionLink} — we\'d love your feedback!'}
        </Translate>
      </span>
      <button
        type="button"
        className="beta-notice__close"
        onClick={() => {
          try { sessionStorage.setItem(BETA_NOTICE_STORAGE_KEY, '1'); } catch { /* private mode */ }
          // Keeps it hidden on the next page, before that page's effect runs.
          document.documentElement.setAttribute('data-dq-beta-dismissed', '');
          setDismissed(true);
        }}
        aria-label={translate({id: 'betaNotice.dismiss', message: 'Dismiss beta notice'})}
      >
        &times;
      </button>
    </div>
  );
}
