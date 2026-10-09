/**
 * Swizzled (ejected) DocSidebarItem/Link — the Docusaurus 3.10 original plus
 * a single unified progress indicator per sidebar item.
 *
 * Pure MDX pages:    nothing (unvisited) | ✓ gray (visited)
 * Notebook pages:    </> gray (unvisited) | </> blue (visited) | </> green (executed)
 *
 * Clicking the indicator (when clickable) clears visited/executed status.
 *
 * Ejected rather than wrapped so the indicator sits inside the <li>: a
 * wrapper element between <ul> and <li> is invalid list markup. Keep the
 * <li>/<Link> part in step with @docusaurus/theme-classic's
 * lib/theme/DocSidebarItem/Link when Docusaurus is upgraded.
 */

import React, { useState, useEffect, useCallback } from 'react';
import clsx from 'clsx';
import type {Props} from '@theme/DocSidebarItem/Link';
import {ThemeClassNames} from '@docusaurus/theme-common';
import {isActiveSidebarItem} from '@docusaurus/plugin-content-docs/client';
import Link from '@docusaurus/Link';
import isInternalUrl from '@docusaurus/isInternalUrl';
import IconExternalLink from '@theme/Icon/ExternalLink';
import {translate} from '@docusaurus/Translate';
import {
  isPageVisited,
  isPageExecuted,
  unmarkPageVisited,
  unmarkPageExecuted,
} from '../../../config/preferences';
import { PAGE_VISITED_EVENT } from '../../../clientModules/pageTracker';
import styles from './styles.module.css';

function LinkLabel({label}: {label: string}) {
  return (
    <span title={label} className={styles.linkLabel}>
      {label}
    </span>
  );
}

export default function DocSidebarItemLink({
  item,
  onItemClick,
  activePath,
  level,
  index: _index,
  ...props
}: Props): React.JSX.Element {
  const [visited, setVisited] = useState(false);
  const [executed, setExecuted] = useState(false);

  const {href, label, className, autoAddBaseUrl} = item;
  const isLinkActive = isActiveSidebarItem(item, activePath);
  const isInternalLink = isInternalUrl(href);
  const isNotebook = !!(item.customProps as {notebook?: unknown} | undefined)?.notebook;

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
      unmarkPageExecuted(href);
      setVisited(false);
      setExecuted(false);
      window.dispatchEvent(new CustomEvent(PAGE_VISITED_EVENT));
    }
  };

  const isActive = activePath?.endsWith(href || '__none__');

  // Determine indicator state
  let indicator: React.JSX.Element | null = null;

  if (isNotebook) {
    if (executed) {
      indicator = (
        <button
          type="button"
          className="dq-sidebar-indicator dq-sidebar-indicator--nb-executed"
          onClick={handleUnmark}
          title={translate({id: 'sidebar.notebookExecuted', message: 'Executed — click to clear'})}
          aria-label={translate({id: 'sidebar.notebookExecuted', message: 'Executed — click to clear'})}
        >&lt;/&gt;</button>
      );
    } else if (visited && !isActive) {
      indicator = (
        <button
          type="button"
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
          role="img"
          aria-label={translate({id: 'sidebar.notebookPage', message: 'Interactive notebook'})}
        >&lt;/&gt;</span>
      );
    }
  } else if (visited && !isActive) {
    indicator = (
      <button
        type="button"
        className="dq-sidebar-indicator dq-sidebar-indicator--visited"
        onClick={handleUnmark}
        title={translate({id: 'sidebar.clearVisited', message: 'Visited — click to clear'})}
        aria-label={translate({id: 'sidebar.clearVisited', message: 'Visited — click to clear'})}
      >{'✓'}</button>
    );
  }

  return (
    <li
      className={clsx(
        ThemeClassNames.docs.docSidebarItemLink,
        ThemeClassNames.docs.docSidebarItemLinkLevel(level),
        'menu__list-item',
        'dq-sidebar-link',
        className,
      )}
      key={label}>
      <Link
        className={clsx(
          'menu__link',
          !isInternalLink && styles.menuExternalLink,
          {
            'menu__link--active': isLinkActive,
          },
        )}
        autoAddBaseUrl={autoAddBaseUrl}
        aria-current={isLinkActive ? 'page' : undefined}
        to={href}
        {...(isInternalLink && {
          onClick: onItemClick ? () => onItemClick(item) : undefined,
        })}
        {...props}>
        <LinkLabel label={label} />
        {!isInternalLink && <IconExternalLink />}
      </Link>
      {indicator}
    </li>
  );
}
