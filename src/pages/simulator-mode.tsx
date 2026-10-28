/** Landing page: run the tutorials without an IBM Quantum account. */

import React from 'react';
import {translate} from '@docusaurus/Translate';
import LandingPage from '@site/src/components/LandingPage';
import {landingLinks} from '@site/src/components/LandingPage/links';

export default function SimulatorMode(): React.JSX.Element {
  return (
    <LandingPage
      title={translate({id: 'landing.simulator.title', message: 'Run IBM Quantum Tutorials Without an IBM Account'})}
      description={translate({id: 'landing.simulator.description', message: "Run IBM Quantum's Qiskit tutorials on a simulator in your browser: ideal or with realistic device noise. No IBM Quantum account, no token, no setup."})}
      heading={translate({id: 'landing.simulator.heading', message: 'Run the tutorials without an IBM Quantum account'})}
      intro={<p>{translate({id: 'landing.simulator.intro', message: "IBM's tutorials are written for real quantum computers and expect an IBM Quantum account. On doQumentation, simulator mode is on by default: code that would send a job to IBM Quantum runs on a local simulator instead, so you can run the tutorials without an account."})}</p>}
      cta={{to: '/jupyter-settings', label: translate({id: 'landing.simulator.cta', message: 'Choose a simulator in Settings'})}}
      image="/img/landing/simulator-mode.png"
      imageAlt={translate({id: 'landing.simulator.imageAlt', message: 'The Execution Mode setting: AerSimulator, FakeBackend or IBM Quantum real hardware.'})}
      sections={[
        {heading: translate({id: 'landing.simulator.choose.heading', message: 'Ideal or noisy'}),
          body: <p>{translate({id: 'landing.simulator.choose.body', message: 'Choose AerSimulator for ideal, noise-free results, or one of dozens of fake backends that model the noise and layout of real IBM quantum computers. The toolbar shows which one is active, so you always know where your code runs.'})}</p>},
        {heading: translate({id: 'landing.simulator.real.heading', message: 'Switch to real hardware when you are ready'}),
          body: <p>{translate({id: 'landing.simulator.real.body', message: 'Save your IBM Quantum API key and instance in Settings and switch the mode to IBM Quantum. The credentials are stored in your browser and passed to the kernel when it starts, so you never paste a token into a notebook.'})}</p>},
        {heading: translate({id: 'landing.simulator.limits.heading', message: 'What a simulator cannot do'}),
          body: <p>{translate({id: 'landing.simulator.limits.body', message: 'A few cells need IBM Quantum itself, for example to list your jobs or read a real device\'s calibration. doQumentation recognizes them and says so instead of showing an error.'})}</p>},
      ]}
      faq={[
        {question: translate({id: 'landing.simulator.faq.account.q', message: 'Can I run IBM Quantum tutorials without an account?'}),
          answer: translate({id: 'landing.simulator.faq.account.a', message: 'Yes. Simulator mode is the default on doQumentation, so the tutorials run on a simulator with no account, no API key and no setup.'})},
        {question: translate({id: 'landing.simulator.faq.fake.q', message: 'What is a fake backend?'}),
          answer: translate({id: 'landing.simulator.faq.fake.a', message: "A fake backend is Qiskit's model of a real IBM quantum computer: its qubit layout, gate set and measured noise. Results look like results from the real device, without a queue."}),
        },
        {question: translate({id: 'landing.simulator.faq.same.q', message: 'Will I get the same results as on real hardware?'}),
          answer: translate({id: 'landing.simulator.faq.same.a', message: 'Not exactly. An ideal simulator has no noise at all; a fake backend uses a recorded snapshot of a device\'s noise. Both are good for learning and testing, and the tutorials explain which results to expect.'})},
        {question: translate({id: 'landing.simulator.faq.large.q', message: 'Are there limits?'}),
          answer: translate({id: 'landing.simulator.faq.large.a', message: 'A simulator runs on the kernel\'s computer, so large circuits with many qubits can be slow or run out of memory. Most tutorials are sized so that they still run.'})},
      ]}
      tryLinks={[
        {to: '/tutorials/grovers-algorithm', label: translate({id: 'landing.simulator.try.grover', message: "Grover's algorithm"})},
        {to: '/guides/simulate-with-qiskit-aer', label: translate({id: 'landing.simulator.try.aer', message: 'Exact and noisy simulation with Qiskit Aer'})},
        {to: '/guides/local-testing-mode', label: translate({id: 'landing.simulator.try.local', message: 'Local testing mode'})},
      ]}
      related={landingLinks('simulator')}
    />
  );
}
