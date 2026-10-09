import React, { useState } from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import Translate, {translate} from '@docusaurus/Translate';

const STORAGE_KEY = 'dq-beta-notice-dismissed';

function BetaNoticeBanner(): React.JSX.Element | null {
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(STORAGE_KEY) === '1',
  );

  if (dismissed) return null;

  return (
    <div className="beta-notice">
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
        className="beta-notice__close"
        onClick={() => {
          sessionStorage.setItem(STORAGE_KEY, '1');
          setDismissed(true);
        }}
        aria-label={translate({id: 'betaNotice.dismiss', message: 'Dismiss beta notice'})}
      >
        &times;
      </button>
    </div>
  );
}

export default function BetaNotice(): React.JSX.Element {
  return (
    <BrowserOnly>{() => <BetaNoticeBanner />}</BrowserOnly>
  );
}
