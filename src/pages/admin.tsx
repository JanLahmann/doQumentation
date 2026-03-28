/**
 * Admin Page — hidden reference page for admins and workshop hosts.
 * Not linked from navbar. Access via /admin.
 */

import React from 'react';
import Layout from '@theme/Layout';

const GITHUB_REPO = 'https://github.com/JanLahmann/doQumentation';

const LOCALE_REPOS: { code: string; english: string; local: string }[] = [
  { code: 'de', english: 'German', local: 'Deutsch' },
  { code: 'es', english: 'Spanish', local: 'Español' },
  { code: 'uk', english: 'Ukrainian', local: 'Українська' },
  { code: 'fr', english: 'French', local: 'Français' },
  { code: 'it', english: 'Italian', local: 'Italiano' },
  { code: 'pt', english: 'Portuguese', local: 'Português' },
  { code: 'ja', english: 'Japanese', local: '日本語' },
  { code: 'tl', english: 'Filipino', local: 'Filipino' },
  { code: 'ar', english: 'Arabic', local: 'العربية' },
  { code: 'he', english: 'Hebrew', local: 'עברית' },
  { code: 'ms', english: 'Malay', local: 'Bahasa Melayu' },
  { code: 'id', english: 'Indonesian', local: 'Bahasa Indonesia' },
  { code: 'th', english: 'Thai', local: 'ไทย' },
  { code: 'ko', english: 'Korean', local: '한국어' },
  { code: 'pl', english: 'Polish', local: 'Polski' },
  { code: 'ro', english: 'Romanian', local: 'Română' },
  { code: 'cs', english: 'Czech', local: 'Čeština' },
  { code: 'swg', english: 'Swabian', local: 'Schwäbisch' },
  { code: 'bad', english: 'Baden', local: 'Badisch' },
  { code: 'bar', english: 'Bavarian', local: 'Bairisch' },
  { code: 'ksh', english: 'Colognian', local: 'Kölsch' },
  { code: 'nds', english: 'Low German', local: 'Plattdeutsch' },
  { code: 'gsw', english: 'Swiss German', local: 'Schweizerdeutsch' },
  { code: 'sax', english: 'Saxon', local: 'Sächsisch' },
  { code: 'bln', english: 'Berlin', local: 'Berlinerisch' },
  { code: 'aut', english: 'Austrian', local: 'Österreichisch' },
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
      <main className="container margin-vert--lg" style={{ maxWidth: '800px' }} data-umami-ignore>
        <h1>Admin Panel</h1>
        <p style={{ color: 'var(--ifm-color-emphasis-600)' }}>
          Internal reference for admins and workshop hosts. Not indexed by search engines.
        </p>

        <Section title="Analytics">
          <LinkList items={[
            { label: 'Umami Dashboard', url: 'https://cloud.umami.is', description: 'Page views, custom events, locale distribution' },
          ]} />
          <p>Tracked events: <code>Run Code</code>, <code>Run All</code>, <code>Binder Launch</code>, <code>Colab Open</code>, <code>Pageview</code> (with locale)</p>
          <p>Analytics auto-disabled on localhost/Docker. Cookie-free, GDPR-compliant. Filter by hostname in dashboard to see per-locale traffic.</p>
        </Section>

        <Section title="Workshop Setup">
          <LinkList items={[
            { label: 'Full Workshop Setup Guide', url: '/workshop-setup', description: 'Detailed step-by-step instructor guide' },
          ]} />

          <h3>Before the workshop</h3>
          <ol>
            <li>
              <strong>Deploy Code Engine instances</strong> — Go to{' '}
              <a href={`${GITHUB_REPO}/actions/workflows/codeengine-image.yml`} target="_blank" rel="noopener noreferrer">
                Actions &gt; Code Engine Image
              </a>
              {' '}&gt; Run workflow. Set <code>instance_count</code> (1 for 10-15 users, 2 for 20-30, 3 for 40-50),
              <code>cpu</code> (4), <code>memory</code> (8G). Wait ~5 min.
            </li>
            <li>
              <strong>Set Jupyter token</strong> on each instance:
              <CodeBlock>{`ibmcloud ce project select --name ce-doqumentation-01
for i in 01 02 03; do
  ibmcloud ce app update --name "ce-doqumentation-\${i}" \\
    --env JUPYTER_TOKEN="your-secure-token-here" \\
    --env CORS_ORIGIN="https://doqumentation.org"
done`}</CodeBlock>
            </li>
            <li>
              <strong>Generate workshop URL</strong> — Encode pool config as base64:
              <CodeBlock>{`CONFIG='{"pool":["https://ce-01.xxx.codeengine.appdomain.cloud","https://ce-02.xxx.codeengine.appdomain.cloud"],"token":"your-token"}'
echo -n "$CONFIG" | base64`}</CodeBlock>
              Workshop URL: <code>https://doqumentation.org/jupyter-settings#workshop=&lt;BASE64&gt;</code>
            </li>
            <li>
              <strong>Stress test</strong> (optional):
              <CodeBlock>{`python scripts/workshop-stress-test.py \\
  --pool https://ce-01...,https://ce-02... \\
  --token your-token --users 10 --cells-per-user 2 --simple`}</CodeBlock>
            </li>
            <li><strong>Warm up instances</strong> — Visit each CE URL once in your browser, or run stress test with <code>--users 1</code></li>
          </ol>

          <h3>During the workshop</h3>
          <ul>
            <li>Share the workshop URL via <strong>QR code</strong> on a slide, chat, or email</li>
            <li>Participants click the link — everything auto-configures. <strong>No IBM Cloud account needed</strong> for participants</li>
            <li>Monitor: open <strong>Settings &gt; Code Engine</strong> to see instance status, active kernels, and memory usage</li>
            <li>If an instance goes down, affected users automatically reconnect to another one</li>
          </ul>

          <h3>After the workshop</h3>
          <ul>
            <li>Instances scale to zero automatically when idle — no charges outside the workshop</li>
            <li>To fully remove: <code>ibmcloud ce app delete --name ce-doqumentation-01</code></li>
          </ul>

          <h3>Cost estimates</h3>
          <table>
            <thead><tr><th>Workshop size</th><th>Instances</th><th>Est. cost (3h)</th></tr></thead>
            <tbody>
              <tr><td>10-15 users</td><td>1</td><td>Free tier</td></tr>
              <tr><td>20-30 users</td><td>2</td><td>~$1-2</td></tr>
              <tr><td>40-50 users</td><td>3</td><td>~$2-3</td></tr>
            </tbody>
          </table>
        </Section>

        <Section title="Infrastructure">
          <LinkList items={[
            { label: 'Main Repository', url: GITHUB_REPO },
            { label: 'Live Site', url: 'https://doqumentation.org' },
            { label: 'Binder', url: 'https://mybinder.org/v2/gh/JanLahmann/doQumentation/notebooks' },
            { label: 'Docker Image', url: 'https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation' },
          ]} />

          <h3>Satellite Repos (locale deploys)</h3>
          <div style={{ columnCount: 2, columnGap: '1.5rem', fontSize: '0.85rem' }}>
            {LOCALE_REPOS.map(({ code, english, local }) => (
              <div key={code} style={{ marginBottom: '0.35rem' }}>
                <a href={`https://${code}.doqumentation.org`} target="_blank" rel="noopener noreferrer">
                  <strong>{code}</strong>
                </a>
                {' '}
                <span style={{ color: 'var(--ifm-color-emphasis-600)' }}>
                  {english} ({local})
                </span>
                {' '}
                <a href={`https://github.com/JanLahmann/doqumentation-${code}`} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8em' }}>
                  [repo]
                </a>
              </div>
            ))}
          </div>
        </Section>
      </main>
    </Layout>
  );
}
