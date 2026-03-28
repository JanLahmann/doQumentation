/**
 * Admin Page — hidden reference page for admins and workshop hosts.
 * Not linked from navbar. Access via /admin.
 */

import React from 'react';
import Layout from '@theme/Layout';

const GITHUB_REPO = 'https://github.com/JanLahmann/doQumentation';
const GITHUB_ACTIONS = `${GITHUB_REPO}/actions`;

const LOCALE_REPOS = [
  'de', 'es', 'uk', 'fr', 'it', 'pt', 'ja', 'tl', 'ar', 'he',
  'ms', 'id', 'th', 'ko', 'pl', 'ro', 'cs',
  'swg', 'bad', 'bar', 'ksh', 'nds', 'gsw', 'sax', 'bln', 'aut',
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '2rem' }}>
      <h2>{title}</h2>
      {children}
    </div>
  );
}

function LinkList({ items }: { items: { label: string; url: string; description?: string }[] }) {
  return (
    <ul style={{ listStyle: 'none', padding: 0 }}>
      {items.map((item) => (
        <li key={item.url} style={{ marginBottom: '0.5rem' }}>
          <a href={item.url} target="_blank" rel="noopener noreferrer">
            {item.label}
          </a>
          {item.description && <span style={{ color: 'var(--ifm-color-emphasis-600)', marginLeft: '0.5rem' }}>— {item.description}</span>}
        </li>
      ))}
    </ul>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre style={{
      background: 'var(--ifm-code-background)',
      padding: '0.75rem 1rem',
      borderRadius: '4px',
      fontSize: '0.85rem',
      overflowX: 'auto',
    }}>
      <code>{children}</code>
    </pre>
  );
}

export default function AdminPage(): JSX.Element {
  return (
    <Layout title="Admin" description="Admin reference page" noIndex>
      <main className="container margin-vert--lg" style={{ maxWidth: '800px' }}>
        <h1>Admin Panel</h1>
        <p style={{ color: 'var(--ifm-color-emphasis-600)' }}>
          Internal reference for admins and workshop hosts. Not indexed by search engines.
        </p>

        <Section title="Analytics">
          <LinkList items={[
            { label: 'Umami Dashboard', url: 'https://cloud.umami.is', description: 'Page views, custom events, locale distribution' },
          ]} />
          <p>Tracked events: <code>Run Code</code>, <code>Run All</code>, <code>Binder Launch</code>, <code>Colab Open</code></p>
          <p>Analytics auto-disabled on localhost/Docker. Cookie-free, GDPR-compliant.</p>
        </Section>

        <Section title="CI/CD Status">
          <LinkList items={[
            { label: 'Build and Deploy (EN)', url: `${GITHUB_ACTIONS}/workflows/deploy.yml`, description: 'English site → GitHub Pages' },
            { label: 'Deploy Locale Sites', url: `${GITHUB_ACTIONS}/workflows/deploy-locales.yml`, description: '26 locale builds → satellite repos' },
            { label: 'Binder Cache', url: `${GITHUB_ACTIONS}/workflows/binder.yml`, description: 'Daily cache warming for 3 federation members' },
            { label: 'Check Translation Freshness', url: `${GITHUB_ACTIONS}/workflows/check-translations.yml`, description: 'Daily hash comparison' },
            { label: 'Docker Image', url: `${GITHUB_ACTIONS}/workflows/docker.yml`, description: 'Multi-arch ghcr.io build (manual trigger)' },
            { label: 'Code Engine Image', url: `${GITHUB_ACTIONS}/workflows/codeengine-image.yml`, description: 'CE kernel image + auto-deploy' },
          ]} />
        </Section>

        <Section title="Translation">
          <h3>Status</h3>
          <CodeBlock>python translation/scripts/translation-status.py --all</CodeBlock>

          <h3>Translate a new language</h3>
          <CodeBlock>{`# CLI
Read translation/translation-prompt.md. Translate all untranslated pages to Korean (ko).

# Web UI (claude.ai Code tab)
Read translation/translation-prompt-web.md. Continue translations to Korean.`}</CodeBlock>

          <h3>Validate, fix, and promote drafts</h3>
          <CodeBlock>{`python translation/scripts/validate-translation.py --locale XX --dir translation/drafts
python translation/scripts/fix-heading-anchors.py --locale XX --dir translation/drafts --apply
python translation/scripts/sync-translations.py --locale XX --dir translation/drafts
python translation/scripts/promote-drafts.py --locale XX
python translation/scripts/translate-content.py populate-locale --locale XX
git add -f i18n/XX/docusaurus-plugin-content-docs/current/`}</CodeBlock>

          <h3>Documentation</h3>
          <LinkList items={[
            { label: 'Translation Prompt (CLI)', url: `${GITHUB_REPO}/blob/main/translation/translation-prompt.md` },
            { label: 'Translation Prompt (Web)', url: `${GITHUB_REPO}/blob/main/translation/translation-prompt-web.md` },
            { label: 'Contributing Translations', url: `${GITHUB_REPO}/blob/main/CONTRIBUTING-TRANSLATIONS.md` },
          ]} />
        </Section>

        <Section title="Workshop">
          <LinkList items={[
            { label: 'Workshop Setup Guide', url: '/workshop-setup', description: 'Full instructor guide' },
          ]} />
          <h3>Quick checklist</h3>
          <ol>
            <li>Deploy Code Engine instances (set <code>instance_count</code> in CI workflow)</li>
            <li>Generate workshop URL with participant count</li>
            <li>Test participant auto-import (<code>#workshop=BASE64</code>)</li>
            <li>Verify sticky session assignment</li>
            <li>Share workshop URL with participants</li>
          </ol>
        </Section>

        <Section title="Infrastructure">
          <LinkList items={[
            { label: 'Main Repository', url: GITHUB_REPO },
            { label: 'Live Site', url: 'https://doqumentation.org' },
            { label: 'Binder', url: 'https://mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks' },
            { label: 'Docker Image', url: 'https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation' },
          ]} />

          <h3>Satellite Repos (locale deploys)</h3>
          <div style={{ columnCount: 3, columnGap: '1rem', fontSize: '0.85rem' }}>
            {LOCALE_REPOS.map((locale) => (
              <div key={locale} style={{ marginBottom: '0.25rem' }}>
                <a href={`https://github.com/JanLahmann/doqumentation-${locale}`} target="_blank" rel="noopener noreferrer">
                  {locale}
                </a>
                {' → '}
                <a href={`https://${locale}.doqumentation.org`} target="_blank" rel="noopener noreferrer">
                  {locale}.doqumentation.org
                </a>
              </div>
            ))}
          </div>
        </Section>
      </main>
    </Layout>
  );
}
