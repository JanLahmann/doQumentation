/**
 * Swizzled EditThisPage — replaces the default single "Edit this page"
 * link with two purpose-built feedback links:
 *
 *  • Site/translation issue (primary action; the thing we own)
 *      → github.com/JanLahmann/doQumentation/issues/new with a body
 *        template prefilling the page URL + an issue-type checklist
 *
 *  • Content edit (secondary action; for typos/errors in the IBM source)
 *      Upstream pages → github.com/Qiskit/documentation/edit/main/<upstream_path>
 *      doQ-original   → github.com/JanLahmann/doQumentation/edit/main/docs/<rel>
 *
 * Bookmark and the feedback question/thumbs no longer live here — they
 * moved into the unified DocItem footer (see src/theme/DocItem/Footer).
 */

import React, {useEffect, useState} from 'react';
import {translate} from '@docusaurus/Translate';
import {usePluginData} from '@docusaurus/useGlobalData';

// Props are still typed via the original component for upgrade-safety.
import OriginalEditThisPage from '@theme-original/EditThisPage';
type Props = React.ComponentProps<typeof OriginalEditThisPage>;

type PageEntry = {upstreamPath?: string};
type PageDatesData = {locale: string; pages: Record<string, PageEntry>};

const DOQ_REPO = 'https://github.com/JanLahmann/doQumentation';
const IBM_REPO = 'https://github.com/Qiskit/documentation';

function editUrlToRelPath(editUrl: string | undefined): string | null {
  if (!editUrl) return null;
  const m = editUrl.match(/\/tree\/[^/]+\/docs\/(.+)$/);
  return m ? m[1] : null;
}

function buildContentEditUrl(
  isUpstream: boolean,
  upstreamPath: string | undefined,
  relPath: string | null,
): string | null {
  if (isUpstream && upstreamPath) {
    return `${IBM_REPO}/edit/main/${upstreamPath}`;
  }
  if (relPath) {
    return `${DOQ_REPO}/edit/main/docs/${relPath}`;
  }
  return null;
}

function buildSiteIssueUrl(pagePath: string): string {
  const body = [
    'Page: https://doqumentation.org' + pagePath,
    '',
    'What kind of issue is this? (delete the ones that don\'t apply)',
    '- [ ] Site/frontend bug (rendering, navigation, broken UI)',
    '- [ ] Translation problem (wrong, missing, or awkward translation)',
    '- [ ] Code execution issue (Binder, Jupyter, kernel, output)',
    '- [ ] Search, sidebar, or other UX issue',
    '- [ ] Accessibility issue',
    '- [ ] Idea / feature request for doQumentation itself',
    '',
    'Note: for issues with the **content itself** (typos, technical errors)',
    'please file upstream at https://github.com/Qiskit/documentation/issues',
    '— that\'s the canonical source for IBM Quantum docs.',
    '',
    '## Description',
    '',
  ].join('\n');
  return `${DOQ_REPO}/issues/new?body=${encodeURIComponent(body)}`;
}

export default function EditThisPage(props: Props): JSX.Element {
  const data = usePluginData('page-dates') as PageDatesData | undefined;
  const relPath = editUrlToRelPath(props.editUrl);
  const entry = relPath ? data?.pages?.[relPath] : undefined;
  const isUpstreamPage = !!entry;

  const contentEditUrl = buildContentEditUrl(
    isUpstreamPage, entry?.upstreamPath, relPath,
  );

  const [siteIssueUrl, setSiteIssueUrl] = useState<string>(
    `${DOQ_REPO}/issues/new`,
  );
  useEffect(() => {
    setSiteIssueUrl(buildSiteIssueUrl(window.location.pathname));
  }, []);

  return (
    <div className="dq-feedback-actions">
      <a
        href={siteIssueUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="dq-site-issue-link"
        title={translate({
          id: 'feedback.siteIssue.tooltip',
          message: 'Report a site, translation, or code-execution issue with doQumentation',
        })}
      >
        {translate({
          id: 'feedback.siteIssue.label',
          message: 'Site or translation issue?',
        })}
      </a>
      {contentEditUrl && (
        <a
          href={contentEditUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="dq-content-edit-link"
          title={isUpstreamPage
            ? translate({
                id: 'feedback.contentEdit.ibm.tooltip',
                message: 'Content typo or technical error? IBM owns the source — click to open it in the IBM Quantum docs repo on GitHub.',
              })
            : translate({
                id: 'feedback.contentEdit.doq.tooltip',
                message: 'Open this page in the doQumentation GitHub repo for editing',
              })}
        >
          {isUpstreamPage
            ? translate({
                id: 'feedback.contentEdit.ibm.label',
                message: 'Content issue? Edit on IBM Quantum docs',
              })
            : translate({
                id: 'feedback.contentEdit.doq.label',
                message: 'Edit this page on doQumentation',
              })}
        </a>
      )}
    </div>
  );
}
