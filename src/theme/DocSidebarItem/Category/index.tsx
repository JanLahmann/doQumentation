/**
 * Swizzled DocSidebarItem/Category — wraps the original to add
 * an aggregate progress badge (e.g. "3/10") showing visited/total pages.
 * Clicking the badge clears visited + executed status for all pages in the group.
 */

import React, { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import OriginalCategory from '@theme-original/DocSidebarItem/Category';
import {
  isPageVisited,
  clearVisitedByPrefix,
  clearExecutedByPrefix,
  getSidebarCollapseState,
  setSidebarCollapseState,
} from '../../../config/preferences';
import { PAGE_VISITED_EVENT } from '../../../clientModules/pageTracker';

type SidebarItem = {
  type: string;
  href?: string;
  items?: SidebarItem[];
};

/** Recursively collect all leaf-link hrefs from a sidebar item tree. */
function collectHrefs(items: SidebarItem[]): string[] {
  const hrefs: string[] = [];
  for (const item of items) {
    if (item.href) hrefs.push(item.href);
    if (item.items) hrefs.push(...collectHrefs(item.items));
  }
  return hrefs;
}

/** Find the longest common prefix path for a set of hrefs. */
function commonPrefix(hrefs: string[]): string {
  if (hrefs.length === 0) return '/';
  const parts = hrefs[0].split('/');
  let prefix = '';
  for (let i = 0; i < parts.length; i++) {
    const candidate = parts.slice(0, i + 1).join('/');
    if (hrefs.every(h => h.startsWith(candidate + '/') || h === candidate)) {
      prefix = candidate;
    } else {
      break;
    }
  }
  return prefix || '/';
}

type Props = React.ComponentProps<typeof OriginalCategory>;

export default function DocSidebarItemCategory(props: Props): JSX.Element {
  const [visitedCount, setVisitedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const badgeRef = useRef<HTMLSpanElement | null>(null);

  const items = (props.item?.items || []) as SidebarItem[];
  const allHrefs = React.useMemo(() => collectHrefs(items), [items]);
  const categoryLabel = props.item?.label || '';

  const refresh = useCallback(() => {
    setTotalCount(allHrefs.length);
    let count = 0;
    for (const href of allHrefs) {
      if (isPageVisited(href)) count++;
    }
    setVisitedCount(count);
  }, [allHrefs]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const onPageVisited = () => refresh();
    window.addEventListener(PAGE_VISITED_EVENT, onPageVisited);
    return () => window.removeEventListener(PAGE_VISITED_EVENT, onPageVisited);
  }, [refresh]);

  // Create badge element once — stable across re-renders.
  // Uses <span role="button"> so it can be placed inside <a> links (valid HTML).
  useEffect(() => {
    const badge = document.createElement('span');
    badge.className = 'dq-category-badge';
    badge.setAttribute('role', 'button');
    badge.setAttribute('tabindex', '0');
    badgeRef.current = badge;

    const handleClear = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      const prefix = commonPrefix(allHrefs);
      clearVisitedByPrefix(prefix);
      clearExecutedByPrefix(prefix);
      setVisitedCount(0);
      window.dispatchEvent(new CustomEvent(PAGE_VISITED_EVENT));
    };
    badge.addEventListener('click', handleClear);
    badge.addEventListener('keydown', (e) => {
      if ((e as KeyboardEvent).key === 'Enter' || (e as KeyboardEvent).key === ' ') {
        handleClear(e);
      }
    });

    return () => { badge.remove(); badgeRef.current = null; };
  }, [allHrefs]);

  // (Re-)inject badge into the collapsible's flex flow after every render.
  // Must survive React re-renders of OriginalCategory (e.g. collapse restore).
  useLayoutEffect(() => {
    const badge = badgeRef.current;
    if (!badge || !wrapperRef.current) return;

    const collapsible = wrapperRef.current.querySelector('.menu__list-item-collapsible');
    if (!collapsible) return;

    // href categories: .menu__caret is a separate <button> sibling — badge before it.
    // no-href categories: caret is ::after on the link — badge inside the link (flex).
    const caretButton = collapsible.querySelector(':scope > .menu__caret');
    if (caretButton) {
      // Already in the right place — skip.
      if (badge.parentNode === collapsible) return;
      collapsible.insertBefore(badge, caretButton);
    } else {
      const link = collapsible.querySelector(':scope > .menu__link');
      if (!link) return;
      // Already in the right place — skip.
      if (badge.parentNode === link) return;
      link.appendChild(badge);
    }
  });

  // Update badge text and visibility when counts change
  useEffect(() => {
    const badge = badgeRef.current;
    if (!badge) return;
    if (visitedCount > 0 && totalCount > 0) {
      badge.textContent = `${visitedCount}/${totalCount}`;
      badge.title = `${visitedCount} of ${totalCount} visited — click to clear`;
      badge.setAttribute('aria-label',
        `Clear progress for this section (${visitedCount} of ${totalCount} visited)`);
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  }, [visitedCount, totalCount]);

  // Sidebar collapse memory: observe DOM changes and persist state
  useEffect(() => {
    if (!wrapperRef.current || !categoryLabel) return;

    const listItem = wrapperRef.current.querySelector('.menu__list-item');
    if (!listItem) return;

    // Restore saved state on mount
    const savedState = getSidebarCollapseState(categoryLabel);
    if (savedState !== null) {
      const isCurrentlyCollapsed = listItem.classList.contains('menu__list-item--collapsed');
      if (savedState !== isCurrentlyCollapsed) {
        // Click the collapsible header to toggle
        const header = listItem.querySelector('.menu__link--sublist-caret') as HTMLElement;
        if (header) header.click();
      }
    }

    // Observe class changes to detect collapse/expand
    const observer = new MutationObserver(() => {
      const collapsed = listItem.classList.contains('menu__list-item--collapsed');
      setSidebarCollapseState(categoryLabel, collapsed);
    });
    observer.observe(listItem, { attributes: true, attributeFilter: ['class'] });

    return () => observer.disconnect();
  }, [categoryLabel]);

  return (
    <div className="dq-sidebar-category" ref={wrapperRef}>
      <OriginalCategory {...props} />
    </div>
  );
}
