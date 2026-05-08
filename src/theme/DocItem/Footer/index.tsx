import React from 'react';
import OriginalFooter from '@theme-original/DocItem/Footer';
import EditThisPage from '@theme/EditThisPage';
// OriginalFooter is kept only for its Props type (upgrade-safety).
// We no longer render it — the feedback panel below replaces it.
import {useDoc} from '@docusaurus/plugin-content-docs/client';
import {usePluginData} from '@docusaurus/useGlobalData';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Translate from '@docusaurus/Translate';
import {getOriginalPageUrl} from '../../../lib/originalUrl';
import FeedbackWidget from '../../../components/FeedbackWidget';
import BookmarkButton from '../../../components/BookmarkButton';

type Props = React.ComponentProps<typeof OriginalFooter>;

type PageEntry = {
  upstreamPath: string;
  upstreamDate: string;
  enDate: string;
  translationBaseDate?: string;
  translationBaseSource?: string;
};

type PageDatesData = {
  locale: string;
  pages: Record<string, PageEntry>;
};

/**
 * Strip the @site path prefix from useDoc().metadata.source so we can look
 * the entry up in the page-dates manifest, which is keyed by relative path
 * (e.g. "guides/primitives.mdx").
 *
 * For EN pages, metadata.source is @site/docs/<rel>.
 * For translated pages, it's @site/i18n/<locale>/docusaurus-plugin-content-docs/current/<rel>.
 */
function sourceToRelPath(source: string | undefined): string | null {
  if (!source) return null;
  let s = source;
  s = s.replace(/^@site\/docs\//, '');
  s = s.replace(
    /^@site\/i18n\/[^/]+\/docusaurus-plugin-content-docs\/current\//,
    '',
  );
  if (s === source) return null;
  return s;
}

function formatDate(iso: string, locale: string): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  // Construct as UTC to avoid TZ-induced day shifts; render in user locale.
  const date = new Date(Date.UTC(y, m - 1, d));
  try {
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    }).format(date);
  } catch {
    return iso;
  }
}

function PageDates({entry, locale, currentPath}: {
  entry: PageEntry;
  locale: string;
  currentPath: string;
}): JSX.Element | null {
  const originalUrl = getOriginalPageUrl(currentPath);
  const enUrl =
    locale !== 'en'
      ? `https://doqumentation.org${currentPath.replace(/^\/[a-z]{2}(-[a-z]+)?(?=\/)/, '')}`
      : null;

  const upstreamDate = formatDate(entry.upstreamDate, locale);
  const enDate = formatDate(entry.enDate, locale);
  const baseDate = formatDate(entry.translationBaseDate || '', locale);
  const isApprox = entry.translationBaseSource === 'promoted-fallback';

  // Nothing to show — bail
  if (!upstreamDate && !enDate && !baseDate) return null;

  return (
    <div className="dq-page-dates">
      {upstreamDate && (
        <div className="dq-page-dates__row">
          <Translate
            id="pageDates.source"
            description="Footer line showing the upstream IBM Quantum source page and its date"
            values={{
              link: originalUrl ? (
                <a
                  href={originalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="dq-page-dates__link"
                >
                  <Translate id="pageDates.sourceLinkLabel" description="Link text for the upstream IBM Quantum source page">
                    IBM Quantum docs
                  </Translate>
                </a>
              ) : (
                <span><Translate id="pageDates.sourceLinkLabel">IBM Quantum docs</Translate></span>
              ),
              date: <span className="dq-page-dates__date">{upstreamDate}</span>,
            }}
          >
            {'Source: {link} — updated {date}'}
          </Translate>
        </div>
      )}

      {enDate && locale !== 'en' && enUrl && (
        <div className="dq-page-dates__row">
          <Translate
            id="pageDates.enVersion"
            description="Footer line shown on translated pages, linking to the EN version on doQumentation"
            values={{
              link: (
                <a
                  href={enUrl}
                  className="dq-page-dates__link"
                >
                  <Translate id="pageDates.enVersionLinkLabel" description="Link text for the English version on doQumentation">
                    English version
                  </Translate>
                </a>
              ),
              date: <span className="dq-page-dates__date">{enDate}</span>,
            }}
          >
            {'{link} on doQumentation — updated {date}'}
          </Translate>
        </div>
      )}

      {enDate && locale === 'en' && (
        <div className="dq-page-dates__row">
          <Translate
            id="pageDates.thisPage"
            description="Footer line on EN pages showing when the doQumentation page was last updated"
            values={{
              date: <span className="dq-page-dates__date">{enDate}</span>,
            }}
          >
            {'This page on doQumentation — updated {date}'}
          </Translate>
        </div>
      )}

      {baseDate && locale !== 'en' && (
        <div className="dq-page-dates__row dq-page-dates__row--translation">
          {isApprox ? (
            <Translate
              id="pageDates.translationBaseApprox"
              description="Translation freshness line, approximate (the EN base revision is unknown, fell back to the promote date)"
              values={{
                date: <span className="dq-page-dates__date">{baseDate}</span>,
              }}
            >
              {'This translation based on the English version of approx. {date}'}
            </Translate>
          ) : (
            <Translate
              id="pageDates.translationBase"
              description="Translation freshness line: 'This translation is based on the English version of <date>'"
              values={{
                date: <span className="dq-page-dates__date">{baseDate}</span>,
              }}
            >
              {'This translation based on the English version of {date}'}
            </Translate>
          )}
        </div>
      )}
    </div>
  );
}

function isFeedbackPage(relPath: string | null): boolean {
  // The feedback widget (👍/👎 + question) was historically only on
  // tutorial-style pages via inline <TutorialFeedback />. Keep the same
  // gate now that it's mounted from the footer instead of MDX:
  //   - tutorials/...
  //   - learning/...  (courses + modules)
  // Skip guides, qiskit-addons, workshop, about — they didn't have it before.
  if (!relPath) return false;
  return relPath.startsWith('tutorials/') || relPath.startsWith('learning/');
}

export default function DocItemFooter(props: Props): JSX.Element {
  const {metadata} = useDoc();
  const data = usePluginData('page-dates') as PageDatesData | undefined;
  const {i18n} = useDocusaurusContext();
  const locale = i18n.currentLocale;

  const relPath = sourceToRelPath(metadata?.source);
  const entry = relPath ? data?.pages?.[relPath] : undefined;
  const showFeedback = isFeedbackPage(relPath);

  return (
    <div className="dq-footer-block">
      {entry && (
        <PageDates
          entry={entry}
          locale={locale}
          currentPath={metadata?.permalink || ''}
        />
      )}
      <div className="dq-footer-actions">
        <div className="dq-footer-actions__left">
          {showFeedback && <FeedbackWidget />}
          <BookmarkButton />
        </div>
        <div className="dq-footer-actions__right">
          {/* EditThisPage is swizzled to render the two purpose-built
              feedback links: site/translation issue + content edit. */}
          {metadata?.editUrl && <EditThisPage editUrl={metadata.editUrl} />}
        </div>
      </div>
    </div>
  );
}
