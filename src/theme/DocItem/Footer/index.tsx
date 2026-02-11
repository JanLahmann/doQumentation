import React from 'react';
import OriginalFooter from '@theme-original/DocItem/Footer';

type Props = React.ComponentProps<typeof OriginalFooter>;

export default function DocItemFooter(props: Props): JSX.Element {
  return <OriginalFooter {...props} />;
}
