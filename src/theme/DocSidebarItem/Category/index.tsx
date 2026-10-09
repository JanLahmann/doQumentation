/**
 * Swizzled DocSidebarItem/Category — wraps the original to add
 * an aggregate progress badge (e.g. "3/10") showing visited/total pages.
 * The badge is display-only; progress is cleared in Settings.
 *
 * No wrapper element: the original renders the <li>, and nothing may sit
 * between <ul> and <li>. The <li> gets a per-instance class through
 * item.className, which the effects below use to find it.
 */

import React, { useState, useEffect, useLayoutEffect, useCallback, useRef, useId, useMemo } from 'react';
import clsx from 'clsx';
import OriginalCategory from '@theme-original/DocSidebarItem/Category';
import {translate} from '@docusaurus/Translate';
import {
  isPageVisited,
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

type Props = React.ComponentProps<typeof OriginalCategory>;

export default function DocSidebarItemCategory(props: Props): React.JSX.Element {
  const [visitedCount, setVisitedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const badgeRef = useRef<HTMLSpanElement | null>(null);
  const badgeTextRef = useRef<HTMLSpanElement | null>(null);
  const badgeLabelRef = useRef<HTMLSpanElement | null>(null);

  // A class unique to this instance, to find the original's <li>.
  const uid = 'dq-sc-' + useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const item = useMemo(
    () => ({...props.item, className: clsx(props.item.className, 'dq-sidebar-category', uid)}),
    [props.item, uid],
  );
  const getListItem = useCallback(
    () => document.querySelector<HTMLElement>('li.' + uid),
    [uid],
  );

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
  // Display-only: it used to clear the section's progress on click or Enter,
  // with no confirmation, and readers took it for a status counter (UX review
  // 2026-10-08). Clearing lives in Settings → Learning Progress.
  useEffect(() => {
    // "3/10" is shown but hidden from screen readers; they get the
    // visually hidden "3 of 10 visited" instead (inside the category link
    // for categories without a page, next to it otherwise).
    const badge = document.createElement('span');
    badge.className = 'dq-category-badge';
    const text = document.createElement('span');
    text.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.className = 'dq-sr-only';
    badge.append(text, label);
    badgeRef.current = badge;
    badgeTextRef.current = text;
    badgeLabelRef.current = label;
    return () => { badge.remove(); badgeRef.current = null; };
  }, []);

  // (Re-)inject badge into the collapsible's flex flow after every render.
  // Must survive React re-renders of OriginalCategory (e.g. collapse restore).
  useLayoutEffect(() => {
    const badge = badgeRef.current;
    const li = getListItem();
    if (!badge || !li) return;

    const collapsible = li.querySelector(':scope > .menu__list-item-collapsible');
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
      const label = translate(
        {id: 'sidebar.categoryProgress', message: '{visited} of {total} visited'},
        {visited: String(visitedCount), total: String(totalCount)},
      );
      if (badgeTextRef.current) badgeTextRef.current.textContent = `${visitedCount}/${totalCount}`;
      if (badgeLabelRef.current) badgeLabelRef.current.textContent = ` (${label})`;
      badge.title = label;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  }, [visitedCount, totalCount]);

  // Sidebar collapse memory: observe DOM changes and persist state
  useEffect(() => {
    if (!categoryLabel) return;

    const listItem = getListItem();
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
  }, [categoryLabel, getListItem]);

  return <OriginalCategory {...props} item={item} />;
}
