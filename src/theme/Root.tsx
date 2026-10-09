import React from 'react';
import BetaNotice from '@site/src/components/BetaNotice';
import TranslationFeedback from '@site/src/components/TranslationFeedback';
import TrailingSlashFix from '@site/src/components/TrailingSlashFix';

export default function Root({children}: {children: React.ReactNode}): React.JSX.Element {
  return (
    <>
      <TrailingSlashFix />
      <BetaNotice />
      <TranslationFeedback />
      {children}
    </>
  );
}
