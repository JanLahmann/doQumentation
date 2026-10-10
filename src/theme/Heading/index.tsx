import React, {type ReactNode} from 'react';
import Heading from '@theme-original/Heading';
import useBrokenLinks from '@docusaurus/useBrokenLinks';
import type {Props} from '@theme/Heading';

// Same rule as github-slugger (Docusaurus's heading ids) for plain titles.
function slugify(text: string): string {
  return text.toLowerCase().trim().replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, '').replace(/ /g, '-');
}

/**
 * Docusaurus renders a page's h1 without an id ("not in the TOC"), but
 * upstream pages link to page titles the way IBM's site anchors them
 * (`/guides/circuit-transpilation-settings#compare-transpiler-settings`).
 * Keep the h1's id, or derive it from the title for the title Docusaurus
 * adds from front matter, and register it so those links resolve.
 */
export default function HeadingWrapper(props: Props): ReactNode {
  const brokenLinks = useBrokenLinks();
  if (props.as !== 'h1') return <Heading {...props} />;
  const {as: _as, id: givenId, ...rest} = props;
  const id = givenId ?? (typeof rest.children === 'string' ? slugify(rest.children) : undefined);
  if (!id) return <Heading {...props} />;
  brokenLinks.collectAnchor(id);
  return <h1 {...rest} id={id} />;
}
