/**
 * Legal Page — who runs the site + Privacy Policy (Datenschutzerklärung).
 * doQumentation is a non-profit open-source project (maintainer's decision:
 * a short "who runs this site" note instead of a full Impressum).
 */

import React from 'react';
import Layout from '@theme/Layout';

export default function LegalPage(): React.JSX.Element {
  return (
    <Layout title="Legal & Privacy" description="Who runs doQumentation, and the privacy policy">
      <main className="container margin-vert--lg" style={{ maxWidth: '800px' }}>

        <h1>Who Runs This Site</h1>

        <p>
          doQumentation is a non-profit, open-source project, maintained by{' '}
          <strong>Jan-R. Lahmann</strong> as part of the{' '}
          <a href="https://rasqberry.org/" target="_blank" rel="noopener noreferrer">RasQberry</a> project.
        </p>

        <h3>Contact</h3>
        <p>
          For questions, feedback, or legal and privacy inquiries, please use{' '}
          <a href="https://github.com/JanLahmann/doQumentation/discussions" target="_blank" rel="noopener noreferrer">GitHub Discussions</a>{' '}
          or open an{' '}
          <a href="https://github.com/JanLahmann/doQumentation/issues" target="_blank" rel="noopener noreferrer">issue on GitHub</a>.
        </p>

        <h3>Disclaimer</h3>
        <p>
          This is a personal, non-commercial open-source project. The content is derived from
          IBM's open-source <a href="https://github.com/Qiskit/documentation" target="_blank" rel="noopener noreferrer">Qiskit documentation</a> (CC BY-SA 4.0).
          IBM, Qiskit, and IBM Quantum are trademarks of International Business Machines Corporation.
          This project is not affiliated with or endorsed by IBM.
        </p>

        <hr style={{ margin: '2rem 0' }} />

        <h1>Privacy Policy (Datenschutzerklärung)</h1>

        <h3>Overview</h3>
        <p>
          The person responsible for this website under the GDPR is the maintainer named
          above, reachable through the contact given there.
        </p>
        <p>
          This website is designed to be privacy-friendly. The site itself sets no cookies,
          does not ask for personal data, and does not require user accounts. Fonts, maths
          styles and the code-execution library are served from this site itself. Some
          features do contact third-party services; they are listed below, together with
          when that happens.
        </p>

        <h3>Analytics</h3>
        <p>
          We use <a href="https://umami.is" target="_blank" rel="noopener noreferrer">Umami</a> (the
          hosted service Umami Cloud) for anonymous usage statistics. Each page loads the Umami
          script from <code>cloud.umami.is</code> and reports page views and a few events there, so
          Umami's servers receive your IP address with these requests, as with any web request.
          According to Umami, it:
        </p>
        <ul>
          <li>Does not use cookies</li>
          <li>Does not store IP addresses or other personal data</li>
          <li>Does not track users across websites</li>
          <li>Is GDPR-compliant without requiring a consent banner</li>
        </ul>
        <p>
          We collect only aggregated, anonymous page view counts and custom events
          (e.g., code execution button clicks, links followed to other sites) to understand
          how the site is used. No individual user can be identified from this data.
          See Umami's <a href="https://umami.is/privacy" target="_blank" rel="noopener noreferrer">privacy policy</a>.
          The offline Docker and RasQberry images contain no analytics.
        </p>

        <h3>Hosting</h3>
        <p>
          This website is hosted on <a href="https://pages.github.com" target="_blank" rel="noopener noreferrer">GitHub Pages</a>.
          GitHub may collect technical data (IP addresses, browser type) in server logs
          as described in their <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" target="_blank" rel="noopener noreferrer">privacy statement</a>.
        </p>

        <h3>External Services</h3>
        <p>These third-party services are contacted only in the situations described:</p>
        <ul>
          <li>
            <strong>Code execution (mybinder.org)</strong> — when you first click <em>Run</em> on a
            code cell, or click <em>Open in JupyterLab</em>, your browser asks <a href="https://mybinder.org" target="_blank" rel="noopener noreferrer">mybinder.org</a> (a
            public service of the Binder Project, run by members of its federation) to start a
            temporary Jupyter server. The code you run, and its results, are processed on that
            server. See Binder's <a href="https://mybinder.readthedocs.io/en/latest/about/user-guidelines.html#security-and-privacy" target="_blank" rel="noopener noreferrer">security and privacy notes</a>.
            If you set up another server in <a href="/jupyter-settings">Settings</a> (IBM Cloud Code
            Engine, a workshop server, or your own or a local Jupyter server), code runs there instead,
            and its access token is sent to that server.
          </li>
          <li>
            <strong>IBM Quantum</strong> — only if you enter an IBM Quantum API key (and instance CRN)
            in Settings to run on real hardware. The key is kept in your browser (deleted after the
            period you choose there, 1 day by default) and is sent to the Jupyter server that runs
            your code, which uses it to connect to IBM Quantum (<code>quantum.cloud.ibm.com</code>)
            when your code calls Qiskit Runtime. IBM then receives the key and your jobs
            (<a href="https://www.ibm.com/privacy" target="_blank" rel="noopener noreferrer">IBM privacy statement</a>).
          </li>
          <li>
            <strong>MathJax via cdnjs (Cloudflare)</strong> — only when a code cell's output
            contains LaTeX formulas, the code-execution library loads MathJax from <code>cdnjs.cloudflare.com</code> to
            display them (<a href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener noreferrer">privacy policy</a>).
          </li>
          <li>
            <strong>Google Colab</strong> — notebook execution, only when you click <em>Open in Colab</em> (<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">privacy policy</a>).
          </li>
          <li>
            <strong>YouTube and IBM Video</strong> — some course pages embed lecture videos. When such a
            page is shown, the player is loaded from YouTube (<code>youtube-nocookie.com</code>, or <code>youtube.com</code> when
            the page shows an interactive transcript) or from IBM Video (<code>video.ibm.com</code>). These
            providers receive your IP address and may set cookies under their own policies
            (<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google</a>,{' '}
            <a href="https://www.ibm.com/privacy" target="_blank" rel="noopener noreferrer">IBM</a>).
          </li>
          <li>
            <strong>Qiskit Ecosystem badge</strong> — the badge image on the home page is loaded
            from IBM's link service <code>qisk.it</code>, which forwards to <a href="https://shields.io" target="_blank" rel="noopener noreferrer">shields.io</a> (<code>img.shields.io</code>).
          </li>
        </ul>

        <h3>Local Storage</h3>
        <p>
          This site uses your browser's localStorage to remember preferences
          (e.g., learning progress, bookmarks, display settings). This data stays
          in your browser and is not sent to us. The only exceptions are the credentials
          you enter in Settings (an IBM Quantum API key, a server token), which are sent to
          the services described above when you run code. You can clear all of it at any
          time via the <a href="/jupyter-settings">Settings page</a> or your browser settings.
        </p>

        <h3>Your Rights (GDPR)</h3>
        <p>
          Since we do not collect personal data, there is typically no personal data
          to access, correct, or delete. If you believe we hold any personal data
          about you, please contact us via{' '}
          <a href="https://github.com/JanLahmann/doQumentation/discussions" target="_blank" rel="noopener noreferrer">GitHub Discussions</a> or{' '}
          <a href="https://github.com/JanLahmann/doQumentation/issues" target="_blank" rel="noopener noreferrer">issues</a>.
        </p>
        <p>
          You have the right to lodge a complaint with a supervisory authority.
          For Germany, this is the relevant state data protection authority
          (Landesdatenschutzbeauftragter) of your federal state.
        </p>

      </main>
    </Layout>
  );
}
