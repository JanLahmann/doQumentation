/**
 * Swizzled DocSidebarItem/Link — wraps the original to add
 * a single unified progress indicator per sidebar item.
 *
 * Pure MDX pages:    nothing (unvisited) | ✓ gray (visited)
 * Notebook pages:    </> gray (unvisited) | </> blue (visited) | </> green (executed)
 *
 * Clicking the indicator (when clickable) clears visited/executed status.
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
  const isNotebook = !!(props.item as any)?.customProps?.notebook;

  const refresh = useCallback(() => {
    if (href) {
      setVisited(isPageVisited(href));
      setExecuted(isPageExecuted(href));
    }
  }, [href]);

  useEffect(() => { refresh(); }, [refresh]);

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
      setExecuted(false);
      window.dispatchEvent(new CustomEvent(PAGE_VISITED_EVENT));
    }
  };

  const isActive = props.activePath?.endsWith(href || '__none__');

  // Determine indicator state
  let indicator: JSX.Element | null = null;

  if (isNotebook) {
    if (executed) {
      indicator = (
        <button
          className="dq-sidebar-indicator dq-sidebar-indicator--nb-executed"
          onClick={handleUnmark}
          title={translate({id: 'sidebar.notebookExecuted', message: 'Executed — click to clear'})}
          aria-label={translate({id: 'sidebar.notebookExecuted', message: 'Executed — click to clear'})}
        >&lt;/&gt;</button>
      );
    } else if (visited && !isActive) {
      indicator = (
        <button
          className="dq-sidebar-indicator dq-sidebar-indicator--nb-visited"
          onClick={handleUnmark}
          title={translate({id: 'sidebar.notebookVisited', message: 'Visited — click to clear'})}
          aria-label={translate({id: 'sidebar.notebookVisited', message: 'Visited — click to clear'})}
        >&lt;/&gt;</button>
      );
    } else {
      indicator = (
        <span
          className="dq-sidebar-indicator dq-sidebar-indicator--nb-unvisited"
          title={translate({id: 'sidebar.notebookPage', message: 'Interactive notebook'})}
          aria-label={translate({id: 'sidebar.notebookPage', message: 'Interactive notebook'})}
        >&lt;/&gt;</span>
      );
    }
  } else if (visited && !isActive) {
    indicator = (
      <button
        className="dq-sidebar-indicator dq-sidebar-indicator--visited"
        onClick={handleUnmark}
        title={translate({id: 'sidebar.clearVisited', message: 'Visited — click to clear'})}
        aria-label={translate({id: 'sidebar.clearVisited', message: 'Visited — click to clear'})}
      >{'\u2713'}</button>
    );
  }

  return (
    <div className="dq-sidebar-link">
      <OriginalLink {...props} />
      {indicator}
    </div>
  );
}
