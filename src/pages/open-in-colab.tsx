/** Landing page: open the tutorials in Google Colab or JupyterLab. */

import React from 'react';
import {translate} from '@docusaurus/Translate';
import LandingPage from '@site/src/components/LandingPage';
import {landingLinks} from '@site/src/components/LandingPage/links';

export default function OpenInColab(): React.JSX.Element {
  return (
    <LandingPage
      title={translate({id: 'landing.colab.title', message: 'Open IBM Quantum Tutorials in Google Colab or JupyterLab'})}
      description={translate({id: 'landing.colab.description', message: "Open any IBM Quantum Qiskit tutorial as a notebook in Google Colab or JupyterLab with one click. Qiskit installs itself; translated notebooks in 17 languages."})}
      heading={translate({id: 'landing.colab.heading', message: 'Open the tutorials in Google Colab or JupyterLab'})}
      intro={<p>{translate({id: 'landing.colab.intro', message: 'At the top of every notebook page on doQumentation, Open in: JupyterLab (Binder) and Colab take the tutorial to a full notebook, where you can add cells, keep experimenting and save your work. Download saves the notebook file.'})}</p>}
      cta={{to: '/tutorials/hello-world', label: translate({id: 'landing.colab.cta', message: 'Open a tutorial'})}}
      image="/img/landing/open-in-colab.png"
      imageAlt={translate({id: 'landing.colab.imageAlt', message: 'The top of a tutorial page: Open in JupyterLab (Binder), Colab or Download.'})}
      sections={[
        {heading: translate({id: 'landing.colab.colab.heading', message: 'Google Colab'}),
          body: <p>{translate({id: 'landing.colab.colab.body', message: "The notebook opens in your Google account's Colab. Its first cell installs Qiskit and the packages the tutorial needs, and Colab runs it for you when the notebook opens. Save a copy to your Google Drive to keep your changes."})}</p>},
        {heading: translate({id: 'landing.colab.lab.heading', message: 'JupyterLab'}),
          body: <p>{translate({id: 'landing.colab.lab.body', message: 'JupyterLab (Binder) starts a full JupyterLab with Qiskit already installed, on the same free Binder service that runs the code on the page. A progress display shows how far the start has got.'})}</p>},
        {heading: translate({id: 'landing.colab.lang.heading', message: 'In your language'}),
          body: <p>{translate({id: 'landing.colab.lang.body', message: 'On a translated site, for example the German or Japanese one, JupyterLab and Colab open the translated notebook, so the explanations between the code cells stay in your language.'})}</p>},
      ]}
      faq={[
        {question: translate({id: 'landing.colab.faq.install.q', message: 'Do I have to install Qiskit in Colab?'}),
          answer: translate({id: 'landing.colab.faq.install.a', message: 'No. The first cell of every notebook installs what the tutorial needs, and Colab runs it automatically when the notebook opens.'})},
        {question: translate({id: 'landing.colab.faq.account.q', message: 'Do I need a Google account?'}),
          answer: translate({id: 'landing.colab.faq.account.a', message: 'For Colab, yes. JupyterLab and the Run button on the page need no account.'})},
        {question: translate({id: 'landing.colab.faq.save.q', message: 'How do I keep my changes?'}),
          answer: translate({id: 'landing.colab.faq.save.a', message: "In Colab, save a copy to your Google Drive. In JupyterLab, download the notebook before you close the tab; the Binder session is temporary. Download on the page saves the original notebook."})},
      ]}
      tryLinks={[
        {to: '/tutorials/hello-world', label: translate({id: 'landing.colab.try.hello', message: 'Hello world: your first quantum circuit'})},
        {to: '/tutorials/grovers-algorithm', label: translate({id: 'landing.colab.try.grover', message: "Grover's algorithm"})},
        {to: '/tutorials/chsh-inequality', label: translate({id: 'landing.colab.try.chsh', message: 'CHSH inequality'})},
      ]}
      related={landingLinks('colab')}
    />
  );
}
