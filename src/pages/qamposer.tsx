/**
 * Qamposer Circuit Composer Page
 *
 * Visual quantum circuit editor embedded from @qamposer/react. Simulations
 * run on doQumentation's existing thebelab kernel and honor the user's
 * settings (ideal simulator, noisy fake backend, or real IBM Quantum
 * hardware).
 *
 * Currently unlisted — reachable only via the direct URL /qamposer.
 * Not linked from the navbar, footer, homepage, or features page yet.
 * Flag `noindex` is set so search engines don't index it prematurely.
 */

import React from 'react';
import Layout from '@theme/Layout';
import Head from '@docusaurus/Head';
import Translate, {translate} from '@docusaurus/Translate';
import QamposerEmbed from '@site/src/components/QamposerEmbed';

export default function QamposerPage(): JSX.Element {
  return (
    <Layout
      title={translate({id: 'qamposer.title', message: 'Circuit Composer'})}
      description={translate({
        id: 'qamposer.description',
        message: 'Experimental visual quantum circuit composer — build circuits with drag-and-drop gates and run them on your configured backend.',
      })}
    >
      <Head>
        <meta name="robots" content="noindex, nofollow" />
      </Head>
      <main className="container margin-vert--lg">
        <div className="qamposer-page">
          {/* Discreet experimental banner */}
          <div
            role="status"
            style={{
              padding: '8px 14px',
              borderRadius: 6,
              background: 'var(--ifm-color-warning-contrast-background)',
              color: 'var(--ifm-color-warning-contrast-foreground)',
              fontSize: '0.85rem',
              marginBottom: 16,
              border: '1px solid var(--ifm-color-warning-dark)',
              display: 'inline-block',
            }}
          >
            <Translate id="qamposer.experimental">
              Experimental — interface may change. Not yet linked from the main navigation.
            </Translate>
          </div>

          <h1>
            <Translate id="qamposer.heading">Circuit Composer</Translate>
          </h1>

          <p style={{maxWidth: 760}}>
            <Translate id="qamposer.intro">
              Build quantum circuits visually with drag-and-drop gates from QAMPoser.
              Circuits are simulated on the same Jupyter kernel used by
              doQumentation's interactive tutorials, so they honor your
              Simulator Mode and IBM Quantum settings automatically.
            </Translate>
          </p>

          <QamposerEmbed defaultQubits={3} />

          <section style={{marginTop: 32}}>
            <h2>
              <Translate id="qamposer.howItWorks.heading">How it works</Translate>
            </h2>
            <ul>
              <li>
                <Translate id="qamposer.howItWorks.editor">
                  Drag gates from the operations panel onto the circuit.
                  The OpenQASM code updates in real time.
                </Translate>
              </li>
              <li>
                <Translate id="qamposer.howItWorks.simulate">
                  Clicking Run Simulation sends the circuit to the active
                  Jupyter kernel — the same kernel used by tutorial pages.
                </Translate>
              </li>
              <li>
                <Translate id="qamposer.howItWorks.routing">
                  The execution target is determined by your doQumentation
                  settings: ideal simulator, noisy fake backend, or real
                  IBM Quantum hardware.
                </Translate>{' '}
                <a href="/jupyter-settings">
                  <Translate id="qamposer.howItWorks.settingsLink">
                    Open Settings
                  </Translate>
                </a>
              </li>
              <li>
                <Translate id="qamposer.howItWorks.realDevice">
                  Real-hardware runs require an explicit confirmation each
                  time, and the live preview is automatically disabled in
                  real-device mode to avoid accidental job submissions.
                </Translate>
              </li>
            </ul>
          </section>
        </div>
      </main>
    </Layout>
  );
}
