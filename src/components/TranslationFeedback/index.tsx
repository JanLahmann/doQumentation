import React, {useState} from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {translate} from '@docusaurus/Translate';
import {trackEvent} from '../../config/analytics';

const STORAGE_KEY = 'dq-translation-feedback';

function TranslationBanner(): JSX.Element | null {
  const {i18n: {currentLocale}} = useDocusaurusContext();

  const [state, setState] = useState<'open' | 'thanks' | 'dismissed'>(() => {
    const val = sessionStorage.getItem(STORAGE_KEY);
    return val === '1' ? 'dismissed' : 'open';
  });

  if (currentLocale === 'en' || state === 'dismissed') return null;

  if (state === 'thanks') {
    return (
      <div className="translation-feedback translation-feedback--thanks">
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
      notebook: rating, // reusing the notebook field for the rating value
    });
    setState('thanks');
    setTimeout(() => {
      sessionStorage.setItem(STORAGE_KEY, '1');
      setState('dismissed');
    }, 2500);
  };

  const dismiss = () => {
    sessionStorage.setItem(STORAGE_KEY, '1');
    setState('dismissed');
  };

  return (
    <div className="translation-feedback">
      <span className="translation-feedback__label">
        {translate({
          id: 'translationFeedback.question',
          message: 'How is the translation quality?',
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

export default function TranslationFeedback(): JSX.Element {
  return <BrowserOnly>{() => <TranslationBanner />}</BrowserOnly>;
}
