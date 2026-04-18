/**
 * Admin Page — hidden reference page for admins and workshop hosts.
 * Not linked from navbar. Access via /admin.
 */

import React from 'react';
import Layout from '@theme/Layout';
import BrowserOnly from '@docusaurus/BrowserOnly';

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

        <Section title="Live Pod Status">
          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-emphasis-600)', marginBottom: '0.75rem' }}>
            Real-time health of CE workshop pods. Polls each pod's <code>/stats</code> endpoint every
            5 seconds and shows progress bars + sparklines for the last 15 minutes. Health thresholds
            derived from stress test data (~6 sessions per vCPU, memory and CPU saturation lines).
            CE credentials are read from the <a href="/jupyter-settings#code-engine-config">Settings page</a>.
          </p>
          <BrowserOnly>
            {() => {
              // Lazy load the component to keep it out of the SSR build
              // (it uses localStorage and live fetch — both browser-only).
              const PodMonitor = require('@site/src/components/admin/PodMonitor').default;
              return <PodMonitor />;
            }}
          </BrowserOnly>

          <h3 style={{ marginTop: '1.5rem' }}>How to read it</h3>

          <p style={{ fontSize: '0.9rem' }}>
            <strong>Current value matters less than direction.</strong> A pod at 78% capacity that's
            been steady for 5 minutes is fine. A pod at 60% capacity that's climbed 30% in the last
            minute is about to be in trouble. Watch the sparkline shape, not just the number.
          </p>

          <h4 style={{ marginTop: '1rem' }}>Status colors</h4>
          <ul style={{ fontSize: '0.9rem' }}>
            <li>
              <strong>● healthy (green)</strong> — all signals under 50% of pod capacity. No action.
              Don't even check the dashboard during this state.
            </li>
            <li>
              <strong>⚠ stressed (yellow)</strong> — one signal between 50% and 80%. Workshop will
              still work, but new users may see slower kernel starts and slight cell-execution lag.
              <strong> Watch the sparkline.</strong> If trending up, prepare to act. If flat or down,
              ignore and check again in a few minutes.
            </li>
            <li>
              <strong>✗ saturated (orange)</strong> — one signal above 80% (or CPU load above 100%).
              <strong> New users are likely failing right now.</strong> Read the recommendation banner
              under the card — it tells you whether to restart, escalate pod size, or wait it out.
              The component will tell you which signal (kernels / memory / load) is the problem.
            </li>
            <li>
              <strong>⛔ unreachable (red)</strong> — pod not responding for {'>'}3 seconds. Either
              cold-starting (typical 15-150s if image needs to be pulled to a fresh node) or crashed.
              First user click will auto-restart it. If it stays unreachable for {'>'}3 minutes,
              check IBM Cloud console.
            </li>
          </ul>

          <h4 style={{ marginTop: '1rem' }}>The four metrics</h4>
          <ul style={{ fontSize: '0.9rem' }}>
            <li>
              <strong>Kernels</strong> — number of active Jupyter kernels. Capacity estimate is
              <code>~6 × cpu_count</code>, derived from stress test measurements (1, 4, 8, 12 vCPU).
              Each kernel is one workshop participant's session. The threshold line on the sparkline
              shows 80% of capacity.
            </li>
            <li>
              <strong>Memory</strong> — pod memory used, as percent of cgroup limit (NOT host memory).
              <strong> Memory is rarely the constraint</strong> for typical 5-15 qubit workshop content
              — measured max ~44% across all stress tests. If memory crosses 50%, you're either
              running advanced courses with 25-qubit statevector simulations (expected) or a kernel
              has leaked (uncommon but possible). Restart the pod if it climbs to {'>'}80%.
            </li>
            <li>
              <strong>CPU load</strong> — Linux 1-minute load average, as percent of vCPU count.
              <code>50%</code> = half-utilized, <code>100%</code> = fully utilized. Above 100% means
              the pod is oversubscribed and queue lengths are growing. Threshold line shows
              <code>cpu_count</code> (= 100% saturation). Sustained {'>'}120% = users will see
              noticeable cell-execution delays.
            </li>
            <li>
              <strong>Connections</strong> — active WebSocket connections to Jupyter kernels. Should
              roughly track Kernels (one WS per active user). Big gap between Connections and Kernels
              means orphaned kernels (users left without disconnecting cleanly). If the gap grows
              over time without dropping, kernels are leaking — restart between sections.
            </li>
          </ul>

          <h4 style={{ marginTop: '1rem' }}>Reading sparklines</h4>
          <ul style={{ fontSize: '0.9rem' }}>
            <li><strong>Flat at low value</strong> — comfortable. Don't act.</li>
            <li><strong>Steady climb</strong> — workshop is filling up. Normal at the start of a session.</li>
            <li><strong>Sudden spike</strong> — instructor said "click now" and everyone connected. Will normalize within 30-60s if pod has headroom.</li>
            <li><strong>Spike that doesn't drain</strong> — pod hit a hard limit. Check recommendation, consider restart.</li>
            <li><strong>Sawtooth (up-down-up-down)</strong> — kernels are starting and culling. Healthy pattern during a workshop with cell runs interspersed with idle reading time.</li>
            <li><strong>Dashed threshold line on sparkline</strong> — shows 80% of estimated capacity. When the line crosses this, you're in stressed territory.</li>
          </ul>

          <h4 style={{ marginTop: '1rem' }}>Pause button</h4>
          <p style={{ fontSize: '0.9rem' }}>
            The <strong>⏸ Pause</strong> button stops polling without unmounting the component.
            Use it during a presentation or screen-share when you don't want network noise or constant
            UI updates. Click <strong>▶ Resume</strong> to restart polling. Note: while paused,
            sparklines stop updating but existing history is preserved.
          </p>

          <h4 style={{ marginTop: '1rem' }}>Where the data comes from</h4>
          <p style={{ fontSize: '0.9rem' }}>
            The dashboard reads pod URLs from your configured workshop pool in
            <a href="/jupyter-settings#code-engine"> Settings → Code Engine</a>. If no pool is
            configured, you can paste a single CE URL into the inline input and monitor that
            pod directly. The <code>/stats</code> endpoint is unauthenticated (no token needed)
            and CORS-restricted to <code>https://doqumentation.org</code>, so the dashboard works
            from this site but not from local development unless you set <code>CORS_ORIGIN=*</code>
            on the CE app.
          </p>
        </Section>

        <Section title="Analytics">
          <LinkList items={[
            { label: 'Umami Dashboard (admin)', url: 'https://cloud.umami.is', description: 'Full dashboard — requires login' },
            { label: 'Shared Dashboard (read-only)', url: 'https://cloud.umami.is/share/MIkvtSY8pncOTN1G', description: 'Public link — share with workshop hosts' },
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
              <strong>Deploy IBM Cloud Code Engine instances</strong> — Go to{' '}
              <a href={`${GITHUB_REPO}/actions/workflows/codeengine-image.yml`} target="_blank" rel="noopener noreferrer">
                Actions &gt; Code Engine Image
              </a>
              {' '}&gt; Run workflow. Pick the pod size from the table below based on your workshop
              size; <code>instance_count=1</code> is fine for up to ~80 users on a single 12 vCPU pod.
              Wait ~5 min for the build and CE deploy. <strong>Note:</strong> the workflow defaults
              to <code>cpu=1, memory=4G</code> which is too small for any real workshop — always
              override these in the workflow_dispatch inputs.
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
            <li>
              <strong>Open the <a href="#live-pod-status">Live Pod Status</a> dashboard at the top
              of this page</strong> on a second screen or browser tab. It shows real-time pod
              health and tells you when to act. See "How to read it" for color legend and
              recommendations.
            </li>
            <li>
              <strong>Watch sparkline direction, not just current values.</strong> Steady at 70%
              is fine; climbing through 70% means trouble in the next 60 seconds.
            </li>
            <li>
              <strong>If status goes orange/red</strong>: read the recommendation banner under the
              card. Most common fixes: ask students to space out cell runs, restart the pod
              between sections (clears zombie kernels), or escalate pod size for the next session.
            </li>
            <li>If an instance goes down, affected users automatically reconnect to another one (multi-pod mode only).</li>
          </ul>

          <h3>After the workshop</h3>
          <ul>
            <li>
              <strong>Pods scale to zero automatically</strong> when idle (no requests for ~30s with
              <code>scale-down-delay=0</code>). No charges outside the workshop.
            </li>
            <li>
              <strong>Between back-to-back workshops on the same day, restart the pod manually.</strong>
              {' '}A known Jupyter Server bug under heavy load (uncovered during stress testing)
              can leave zombie kernels that don't get culled, causing pod memory to creep up.
              Restart fixes it cleanly:
              <CodeBlock>{`# Trigger a fresh pod (no-op update creates a new revision)
ibmcloud ce app update --name ce-doqumentation-01 --max-scale 1`}</CodeBlock>
            </li>
            <li>
              <strong>Resize the pod between workshops if your needs change</strong> (e.g., workshop
              size grew or shrank). CE forces fixed CPU/memory ratios; valid combinations include
              <code>1/4, 2/4, 4/8, 8/16, 12/24</code>:
              <CodeBlock>{`ibmcloud ce app update --name ce-doqumentation-01 --cpu 12 --memory 24G`}</CodeBlock>
            </li>
            <li>
              To fully remove (will rebuild from CI on the next workflow run, so this is a hard
              teardown): <code>ibmcloud ce app delete --name ce-doqumentation-01 --force</code>
            </li>
          </ul>

          <h3>Sizing &amp; cost estimates</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-emphasis-700)' }}>
            Validated against the stress test harness ({' '}
            <code>scripts/workshop-stress-test.py</code>) on 1, 4, 8, and 12 vCPU pods. Capacity
            scales roughly linearly with CPU count (~6 sustained sessions per vCPU). Memory is
            essentially never the constraint for typical 5-15 qubit workshop content. Multi-pod
            workshops are not yet validated end-to-end (the frontend pool/random-assignment logic
            exists but hasn't been stress-tested with real CE deploys).
          </p>
          <table>
            <thead>
              <tr>
                <th>Workshop size</th>
                <th>Pod config</th>
                <th>Instance count</th>
                <th>Est. cost (3h active)</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>5-15 users</td>
                <td>4 vCPU / 8 GB</td>
                <td>1</td>
                <td>Free tier</td>
                <td>Simplest config</td>
              </tr>
              <tr>
                <td>15-30 users</td>
                <td>4 vCPU / 8 GB</td>
                <td>1</td>
                <td>~$0.50</td>
                <td>Tight at upper end</td>
              </tr>
              <tr>
                <td><strong>30-50 users</strong></td>
                <td><strong>8 vCPU / 16 GB</strong></td>
                <td><strong>1</strong></td>
                <td>~$1-2</td>
                <td>Recommended sweet spot</td>
              </tr>
              <tr>
                <td>50-80 users</td>
                <td>12 vCPU / 24 GB</td>
                <td>1</td>
                <td>~$2-3</td>
                <td>Single-pod simplicity</td>
              </tr>
              <tr>
                <td>80-100 users</td>
                <td>12 vCPU / 24 GB</td>
                <td>1</td>
                <td>~$2-3</td>
                <td>Borderline; ~96% success at 5s burst, 100% with 75s+ stagger</td>
              </tr>
              <tr>
                <td>100-150 users</td>
                <td>12 vCPU / 24 GB</td>
                <td>2</td>
                <td>~$4-6</td>
                <td>Multi-pod (untested end-to-end)</td>
              </tr>
              <tr>
                <td>150+ users</td>
                <td>12 vCPU / 24 GB</td>
                <td>3+</td>
                <td>scale linearly</td>
                <td>Multi-pod required; test before relying on it</td>
              </tr>
            </tbody>
          </table>

          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-emphasis-700)', marginTop: '0.75rem' }}>
            <strong>CE billing only counts active vCPU-seconds.</strong> Pods scale to zero when
            idle (no requests for ~30s with <code>scale-down-delay=0</code>), so the cost only
            accumulates while the workshop is actually using the pod. Idle cost = $0. The numbers
            above assume ~3 hours of continuous use at average 50% CPU utilization. Real costs
            will be lower if students spend most of their time reading rather than executing.
          </p>

          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-emphasis-700)' }}>
            <strong>Cold-start tax</strong>: the first user of the day pays ~15-150 seconds while
            CE pulls the 905 MB image and Jupyter Server boots. On a fresh K8s node with no cached
            image, this can hit 2.5 minutes. Solution: visit each CE URL once in your browser
            ~5 minutes before the workshop starts to pre-warm the pods.
          </p>
        </Section>

        <Section title="Infrastructure">
          <LinkList items={[
            { label: 'Main Repository', url: GITHUB_REPO },
            { label: 'Live Site', url: 'https://doqumentation.org' },
            { label: 'Binder', url: 'https://mybinder.org/v2/gh/JanLahmann/doQumentation/0fc67252' },
            { label: 'Docker Image', url: 'https://github.com/JanLahmann/doQumentation/pkgs/container/doqumentation' },
          ]} />

          <h3>Binder Federation (cache warming)</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--ifm-color-emphasis-600)', marginBottom: '0.5rem' }}>
            Click a link to check if the Binder image is cached on that federation member. A cached image starts in seconds; uncached triggers a rebuild (~2-5 min).
          </p>
          <LinkList items={[
            { label: '2i2c (primary, ~70% traffic)', url: 'https://2i2c.mybinder.org/build/gh/JanLahmann/doQumentation/notebooks' },
            { label: 'BIDS (UC Berkeley)', url: 'https://bids.mybinder.org/build/gh/JanLahmann/doQumentation/notebooks' },
            { label: 'GESIS (Germany)', url: 'https://notebooks.gesis.org/binder/build/gh/JanLahmann/doQumentation/notebooks' },
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
