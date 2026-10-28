/** Landing page: run Qiskit code in the browser, no install. */

import React from 'react';
import {translate} from '@docusaurus/Translate';
import LandingPage from '@site/src/components/LandingPage';
import {landingLinks} from '@site/src/components/LandingPage/links';

export default function RunQiskitInBrowser(): React.JSX.Element {
  return (
    <LandingPage
      title={translate({id: 'landing.run.title', message: 'Run Qiskit Code in Your Browser — No Install'})}
      description={translate({id: 'landing.run.description', message: "Run IBM Quantum's Qiskit tutorials and courses live in your browser: click Run on any page. No Python install, no account needed to start."})}
      heading={translate({id: 'landing.run.heading', message: 'Run Qiskit code in your browser'})}
      intro={<p>{translate({id: 'landing.run.intro', message: "Every tutorial, guide and course page on doQumentation has a Run button. Click it and the page's code cells become live: edit them, run them, and see the circuits and plots appear below. There is nothing to install and you need no account to start."})}</p>}
      cta={{to: '/tutorials/hello-world', label: translate({id: 'landing.run.cta', message: 'Run your first quantum circuit'})}}
      image="/img/landing/run-in-browser.png"
      imageAlt={translate({id: 'landing.run.imageAlt', message: 'A tutorial page with live code cells: a cell has just run and shows its output.'})}
      sections={[
        {heading: translate({id: 'landing.run.how.heading', message: 'How it works'}),
          body: <p>{translate({id: 'landing.run.how.body', message: 'Run connects the page to a Jupyter kernel with Qiskit already installed. On doqumentation.org that kernel comes from Binder, a free service; the first start can take a moment. Cells run in order, show a colour while running (amber), when done (green) or on an error (red), and Run All executes the whole page with a progress counter.'})}</p>},
        {heading: translate({id: 'landing.run.help.heading', message: 'Help when something goes wrong'}),
          body: <p>{translate({id: 'landing.run.help.body', message: "When a cell fails, doQumentation recognizes common causes, such as a missing package, a name defined in an earlier cell or a lost connection, and says what to do. A missing package gets an Install button; after the install the cell runs again on its own."})}</p>},
        {heading: translate({id: 'landing.run.where.heading', message: 'Other ways to run the same code'}),
          body: <p>{translate({id: 'landing.run.where.body', message: 'Prefer a notebook? Every notebook page opens in Google Colab or in JupyterLab with one click. For classes, the same pages run on IBM Cloud Code Engine or fully offline from a Raspberry Pi.'})}</p>},
      ]}
      faq={[
        {question: translate({id: 'landing.run.faq.install.q', message: 'Do I need to install Python or Qiskit?'}),
          answer: translate({id: 'landing.run.faq.install.a', message: 'No. The code runs in a Jupyter kernel that already has Qiskit installed. Your browser only shows the page and sends the cells to the kernel.'})},
        {question: translate({id: 'landing.run.faq.account.q', message: 'Do I need an IBM Quantum account?'}),
          answer: translate({id: 'landing.run.faq.account.a', message: 'No. By default the code runs on a simulator. Add your IBM Quantum credentials in Settings only if you want to run on real quantum hardware.'})},
        {question: translate({id: 'landing.run.faq.cost.q', message: 'Is it free?'}),
          answer: translate({id: 'landing.run.faq.cost.a', message: 'Yes. doQumentation is open source, and the default kernels come from Binder, a free public service.'})},
        {question: translate({id: 'landing.run.faq.save.q', message: 'Are my code changes saved?'}),
          answer: translate({id: 'landing.run.faq.save.a', message: 'No. Edits live in the running kernel and the page; reloading the page brings back the original code. To keep your work, open the notebook in Colab or JupyterLab.'})},
      ]}
      tryLinks={[
        {to: '/tutorials/hello-world', label: translate({id: 'landing.run.try.hello', message: 'Hello world: your first quantum circuit'})},
        {to: '/tutorials/chsh-inequality', label: translate({id: 'landing.run.try.chsh', message: 'CHSH inequality'})},
        {to: '/tutorials/grovers-algorithm', label: translate({id: 'landing.run.try.grover', message: "Grover's algorithm"})},
      ]}
      related={landingLinks('run')}
    />
  );
}
