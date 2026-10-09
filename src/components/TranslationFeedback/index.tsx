import React, {useEffect, useState} from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {translate} from '@docusaurus/Translate';
import {trackEvent} from '../../config/analytics';

// Dismissal lasts for the browser session. Like the beta notice, the banner is
// in the static HTML so it does not shift the page when it appears; an inline
// head script (docusaurus.config.ts) sets `html[data-dq-tf-dismissed]` from
// this key before first paint, and custom.css hides the banner under it.
const STORAGE_KEY = 'dq-translation-feedback';

function remember(): void {
  try { sessionStorage.setItem(STORAGE_KEY, '1'); } catch { /* private mode */ }
  // Keeps it hidden on the next page, before that page's effect runs.
  document.documentElement.setAttribute('data-dq-tf-dismissed', '');
}

export default function TranslationFeedback(): React.JSX.Element | null {
  const {i18n: {currentLocale}} = useDocusaurusContext();

  // 'open' on server and client so hydration matches; read storage after mount.
  const [state, setState] = useState<'open' | 'thanks' | 'dismissed'>('open');
  useEffect(() => {
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === '1') setState('dismissed');
    } catch { /* private mode */ }
  }, []);

  if (currentLocale === 'en' || state === 'dismissed') return null;

  if (state === 'thanks') {
    return (
      <div className="translation-feedback translation-feedback--thanks" role="status">
        {translate({
          id: 'translationFeedback.thanks',
          message: 'Thanks for your feedback on the translation!',
        })}
      </div>
    );
  }

  const handleRating = (rating: 'good' | 'ok' | 'poor') => {
    trackEvent('Translation Feedback', {
      page: window.location.pathname,
      locale: currentLocale,
      rating,
    });
    setState('thanks');
    setTimeout(() => {
      remember();
      setState('dismissed');
    }, 2500);
  };

  const dismiss = () => {
    remember();
    setState('dismissed');
  };

  return (
    <div
      className="translation-feedback"
      role="region"
      aria-label={translate({
        id: 'translationFeedback.regionLabel',
        message: 'Translation feedback',
        description: 'Accessible name of the translation-quality feedback bar on translated pages',
      })}>
      <span className="translation-feedback__label">
        {translate({
          id: 'translationFeedback.question',
          message: 'How is the translation quality on this page?',
          description: 'Question about AI-generated translation accuracy',
        })}
      </span>
      <button
        className="translation-feedback__btn"
        onClick={() => handleRating('good')}
        title={translate({id: 'translationFeedback.good', message: 'Good'})}
      >
        &#x1F44D;
      </button>
      <button
        className="translation-feedback__btn"
        onClick={() => handleRating('ok')}
        title={translate({id: 'translationFeedback.ok', message: 'OK'})}
      >
        &#x1F44C;
      </button>
      <button
        className="translation-feedback__btn"
        onClick={() => handleRating('poor')}
        title={translate({id: 'translationFeedback.poor', message: 'Poor'})}
      >
        &#x1F44E;
      </button>
      <button
        className="translation-feedback__close"
        onClick={dismiss}
        aria-label={translate({id: 'translationFeedback.dismiss', message: 'Dismiss'})}
      >
        &times;
      </button>
    </div>
  );
}
