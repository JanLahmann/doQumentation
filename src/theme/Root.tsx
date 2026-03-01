import React from 'react';
import BetaNotice from '@site/src/components/BetaNotice';

export default function Root({children}: {children: React.ReactNode}): JSX.Element {
  return (
    <>
      <BetaNotice />
      {children}
    </>
  );
}
