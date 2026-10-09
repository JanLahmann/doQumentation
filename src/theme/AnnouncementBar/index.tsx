import React from 'react';
import AnnouncementBar from '@theme-original/AnnouncementBar';
import type AnnouncementBarType from '@theme/AnnouncementBar';
import type {WrapperProps} from '@docusaurus/types';
import BetaNotice from '@site/src/components/BetaNotice';
import TranslationFeedback from '@site/src/components/TranslationFeedback';

type Props = WrapperProps<typeof AnnouncementBarType>;

// Our site-wide banners sit where Docusaurus puts its announcement bar:
// after the "Skip to main content" link (so that stays the first Tab stop)
// and above the navbar, where they were before. They used to render from
// src/theme/Root, ahead of the skip link.
export default function AnnouncementBarWrapper(props: Props): React.JSX.Element {
  return (
    <>
      <AnnouncementBar {...props} />
      <BetaNotice />
      <TranslationFeedback />
    </>
  );
}
