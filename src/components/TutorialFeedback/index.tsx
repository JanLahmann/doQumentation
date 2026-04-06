import React, {useState} from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import {translate} from '@docusaurus/Translate';
import {trackEvent} from '../../config/analytics';

function FeedbackWidget(): JSX.Element {
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
      <div className="tutorial-feedback tutorial-feedback--thanks">
        {translate({
          id: 'tutorialFeedback.thanks',
          message: 'Thanks for your feedback!',
        })}
      </div>
    );
  }

  return (
    <div className="tutorial-feedback">
      <span className="tutorial-feedback__label">
        {translate({
          id: 'tutorialFeedback.question',
          message: 'How was the doQumentation experience?',
          description: 'Feedback about our site (presentation, code execution, navigation) — NOT about the tutorial content, which is from IBM',
        })}
      </span>
      <span className="tutorial-feedback__hint">
        {translate({
          id: 'tutorialFeedback.hint',
          message: '(website, code execution, navigation — tutorial content is by IBM Quantum)',
          description: 'Clarifies we only ask about our frontend/execution, not the IBM-authored content',
        })}
      </span>
      <button
        className="tutorial-feedback__btn tutorial-feedback__btn--up"
        onClick={() => handleFeedback('helpful')}
        aria-label={translate({id: 'tutorialFeedback.helpful', message: 'Yes, helpful'})}
        title={translate({id: 'tutorialFeedback.helpful', message: 'Yes, helpful'})}
      >
        &#x1F44D;
      </button>
      <button
        className="tutorial-feedback__btn tutorial-feedback__btn--down"
        onClick={() => handleFeedback('not_helpful')}
        aria-label={translate({id: 'tutorialFeedback.notHelpful', message: 'Not helpful'})}
        title={translate({id: 'tutorialFeedback.notHelpful', message: 'Not helpful'})}
      >
        &#x1F44E;
      </button>
    </div>
  );
}

export default function TutorialFeedback(): JSX.Element {
  return <BrowserOnly>{() => <FeedbackWidget />}</BrowserOnly>;
}
