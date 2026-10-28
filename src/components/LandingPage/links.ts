/** Labels and routes of the landing pages, for their "related" lists. */

import {translate} from '@docusaurus/Translate';
import type {LandingLink} from './index';

export type LandingKey = 'run' | 'simulator' | 'workshop' | 'offline' | 'colab' | 'progress' | 'paths';

/** All landing pages but `except` (all of them when it is omitted). */
export function landingLinks(except?: LandingKey): LandingLink[] {
  const all: Record<LandingKey, LandingLink> = {
    run: {to: '/run-qiskit-in-browser',
      label: translate({id: 'landing.link.run', message: 'Run Qiskit code in your browser'})},
    simulator: {to: '/simulator-mode',
      label: translate({id: 'landing.link.simulator', message: 'Run the tutorials without an IBM Quantum account'})},
    workshop: {to: '/workshop-setup',
      label: translate({id: 'landing.link.workshop', message: 'Host a Qiskit workshop'})},
    offline: {to: '/workshop-offline',
      label: translate({id: 'landing.link.offline', message: 'Offline class on a Raspberry Pi'})},
    colab: {to: '/open-in-colab',
      label: translate({id: 'landing.link.colab', message: 'Open the tutorials in Google Colab or JupyterLab'})},
    progress: {to: '/learning-progress',
      label: translate({id: 'landing.link.progress', message: 'Track your progress through the courses'})},
    paths: {to: '/learning-paths',
      label: translate({id: 'landing.link.paths', message: "Follow IBM Quantum's learning paths"})},
  };
  return (Object.keys(all) as LandingKey[]).filter((k) => k !== except).map((k) => all[k]);
}
