/**
 * FeedbackWidget — the "Was doQumentation helpful here?" question + 👍/👎.
 *
 * Extracted from src/components/TutorialFeedback so the unified DocItem
 * footer can render it. The TutorialFeedback wrapper now returns null,
 * keeping the existing inline <TutorialFeedback /> imports in ~240 MDX
 * files as harmless no-ops without needing to rewrite them.
 */

import React, {useState} from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import {translate} from '@docusaurus/Translate';
import {trackEvent} from '../../config/analytics';

function FeedbackWidgetClient(): React.JSX.Element {
  const [submitted, setSubmitted] = useState(false);

  const handleFeedback = (rating: 'helpful' | 'not_helpful') => {
    trackEvent('Tutorial Feedback', {
      page: window.location.pathname,
      notebook: rating,
    });
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="dq-feedback-thanks">
        {translate({
          id: 'tutorialFeedback.thanks',
          message: 'Thanks for your feedback!',
        })}
      </div>
    );
  }

  return (
    <div className="dq-feedback-question">
      <span className="dq-feedback-question__label">
        {translate({
          id: 'tutorialFeedback.question',
          message: 'Was doQumentation helpful here?',
          description: 'Per-page feedback question — focuses on doQumentation\'s presentation, code execution, navigation, etc. (not the IBM-authored content)',
        })}
      </span>
      <button
        className="dq-feedback-thumb dq-feedback-thumb--up"
        onClick={() => handleFeedback('helpful')}
        aria-label={translate({id: 'tutorialFeedback.helpful', message: 'Yes, helpful'})}
        title={translate({id: 'tutorialFeedback.helpful', message: 'Yes, helpful'})}
      >
        &#x1F44D;
      </button>
      <button
        className="dq-feedback-thumb dq-feedback-thumb--down"
        onClick={() => handleFeedback('not_helpful')}
        aria-label={translate({id: 'tutorialFeedback.notHelpful', message: 'Not helpful'})}
        title={translate({id: 'tutorialFeedback.notHelpful', message: 'Not helpful'})}
      >
        &#x1F44E;
      </button>
    </div>
  );
}

export default function FeedbackWidget(): React.JSX.Element {
  return <BrowserOnly>{() => <FeedbackWidgetClient />}</BrowserOnly>;
}
