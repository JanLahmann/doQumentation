import React from 'react';
import TrailingSlashFix from '@site/src/components/TrailingSlashFix';

// The beta notice and translation-feedback banners render from
// src/theme/AnnouncementBar (after the skip link), not here.
export default function Root({children}: {children: React.ReactNode}): React.JSX.Element {
  return (
    <>
      <TrailingSlashFix />
      {children}
    </>
  );
}
