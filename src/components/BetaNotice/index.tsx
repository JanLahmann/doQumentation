import React, { useState } from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import Translate, {translate} from '@docusaurus/Translate';

const STORAGE_KEY = 'dq-beta-notice-dismissed';

function BetaNoticeBanner(): JSX.Element | null {
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(STORAGE_KEY) === '1',
  );

  if (dismissed) return null;

  return (
    <div className="beta-notice">
      <span className="beta-notice__text">
        <Translate
          id="betaNotice.text"
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
          }}
        >
          {'This project is in beta. Found a bug or have an idea? {issueLink} — we\'d love your feedback!'}
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

export default function BetaNotice(): JSX.Element {
  return (
    <BrowserOnly>{() => <BetaNoticeBanner />}</BrowserOnly>
  );
}
