/**
 * Doc page <title> and description, with the lesson's course for /learning/.
 *
 * Upstream gives many lessons the same short title ("Introduction",
 * "Overview": 41 pages, the course overviews among them) and every lesson
 * of a course the course's blurb as
 * description, so search results could not tell them apart. A lesson's
 * title gets its section and course from the sidebar breadcrumbs (labels are
 * already translated in every locale): "Introduction · Single systems ·
 * Basics of quantum information", and its description starts with them.
 * The page's H1 and every other page are unchanged.
 */
import React from 'react';
import {PageMetadata} from '@docusaurus/theme-common';
import {useDoc, useSidebarBreadcrumbs} from '@docusaurus/plugin-content-docs/client';

/** Breadcrumb labels [Courses|Modules, <course>, (<section>,) <this page>] →
 *  [(<section>,) <course>]. A course's own overview page ("Overview") is the
 *  course category's link, so its labels end at the course. */
function lessonContext(permalink: string, title: string, labels: string[]): string[] {
  if (!/^\/learning\/(courses|modules)\//.test(permalink) || labels.length < 2) return [];
  const course = labels[1];
  if (title === course) return [];
  if (labels.length === 2) return [course];
  const parent = labels[labels.length - 2];
  return parent === course ? [course] : [parent, course];
}

export default function DocItemMetadata(): React.JSX.Element {
  const {metadata, frontMatter, assets} = useDoc();
  const labels = (useSidebarBreadcrumbs() ?? []).map((item) => item.label);
  const context = lessonContext(metadata.permalink, metadata.title, labels);
  const title = [metadata.title, ...context].join(' · ');
  const description = context.length && metadata.description
    ? `${title}. ${metadata.description}`
    : metadata.description;
  return (
    <PageMetadata
      title={title}
      description={description}
      keywords={frontMatter.keywords}
      image={assets.image ?? frontMatter.image}
    />
  );
}
