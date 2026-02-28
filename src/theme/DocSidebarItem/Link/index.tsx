/**
 * Swizzled DocSidebarItem/Link — wraps the original to add
 * visited (checkmark) and executed (play icon) indicators.
 * Clicking the indicator unmarks the page.
 */

import React, { useState, useEffect, useCallback } from 'react';
import OriginalLink from '@theme-original/DocSidebarItem/Link';
import {translate} from '@docusaurus/Translate';
import {
  isPageVisited,
  isPageExecuted,
  unmarkPageVisited,
} from '../../../config/preferences';
import { PAGE_VISITED_EVENT } from '../../../clientModules/pageTracker';

type Props = React.ComponentProps<typeof OriginalLink>;

export default function DocSidebarItemLink(props: Props): JSX.Element {
  const [visited, setVisited] = useState(false);
  const [executed, setExecuted] = useState(false);

  const href = props.item?.href;

  const refresh = useCallback(() => {
    if (href) {
      setVisited(isPageVisited(href));
      setExecuted(isPageExecuted(href));
    }
  }, [href]);

  // Check on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Re-check whenever any page is visited (fired by pageTracker client module)
  useEffect(() => {
    const onPageVisited = () => refresh();
    window.addEventListener(PAGE_VISITED_EVENT, onPageVisited);
    return () => window.removeEventListener(PAGE_VISITED_EVENT, onPageVisited);
  }, [refresh]);

  const handleUnmark = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (href) {
      unmarkPageVisited(href);
      setVisited(false);
      // Notify parent category badges to update their counts
      window.dispatchEvent(new CustomEvent(PAGE_VISITED_EVENT));
    }
  };

  const showIndicator = visited && !props.activePath?.endsWith(href || '__none__');

  return (
    <div className="dq-sidebar-link">
      <OriginalLink {...props} />
      {showIndicator && (
        <button
          className={`dq-sidebar-indicator${executed ? ' dq-sidebar-indicator--executed' : ''}`}
          onClick={handleUnmark}
          title={translate({id: 'sidebar.clearVisited', message: 'Click to clear visited status'})}
          aria-label={translate({id: 'sidebar.clearVisited', message: 'Click to clear visited status'})}
        >
          {executed ? '\u25B6' : '\u2713'}
        </button>
      )}
    </div>
  );
}
