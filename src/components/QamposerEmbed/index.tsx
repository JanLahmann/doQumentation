/**
 * QamposerEmbed
 *
 * SSR-safe wrapper around QAMPoser's QamposerMicro component.
 *
 * @qamposer/react touches `document` at module-load time, so it must never
 * be imported from code that runs during Docusaurus static site generation.
 * We isolate all @qamposer/react usage in ./QamposerEmbedClient and pull
 * that module in via `require()` from inside a `<BrowserOnly>` render
 * callback — this is the Docusaurus-canonical pattern and guarantees the
 * server bundle never evaluates it.
 *
 * Shows the currently-active execution mode as a prominent badge so users
 * can see at a glance whether their simulation will run on an ideal
 * simulator, a noisy fake backend, or real IBM Quantum hardware. For
 * real-device mode, wraps the adapter's simulate() with an explicit
 * confirmation dialog to prevent accidental hardware job submissions.
 */

import React from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import './styles.css';

export interface QamposerEmbedProps {
  /** Initial qubit count (default: 3) */
  defaultQubits?: number;
  /** Show the QamposerMicro header (default: true) */
  showHeader?: boolean;
}

const LOADING_FALLBACK = (
  <div className="qamposer-embed qamposer-embed--loading">
    Loading circuit composer…
  </div>
);

export default function QamposerEmbed(props: QamposerEmbedProps): JSX.Element {
  return (
    <BrowserOnly fallback={LOADING_FALLBACK}>
      {() => {
        // require() here (not a top-level import) — runs only in the browser,
        // so @qamposer/react's module-level `document` access is safe.
        // eslint-disable-next-line @typescript-eslint/no-var-requires, global-require
        const QamposerEmbedClient = require('./QamposerEmbedClient').default;
        return <QamposerEmbedClient {...props} />;
      }}
    </BrowserOnly>
  );
}
