import React from 'react';
import BetaNotice from '@site/src/components/BetaNotice';
import TranslationFeedback from '@site/src/components/TranslationFeedback';

export default function Root({children}: {children: React.ReactNode}): JSX.Element {
  return (
    <>
      <BetaNotice />
      <TranslationFeedback />
      {children}
    </>
  );
}
