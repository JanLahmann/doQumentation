/**
 * Legal Page — Impressum + Privacy Policy (Datenschutzerklärung).
 * Required for German-hosted websites under TMG/DDG §5 and GDPR.
 */

import React from 'react';
import Layout from '@theme/Layout';

export default function LegalPage(): JSX.Element {
  return (
    <Layout title="Legal / Impressum" description="Legal notice and privacy policy">
      <main className="container margin-vert--lg" style={{ maxWidth: '800px' }}>

        <h1>Legal Notice (Impressum)</h1>

        <p>Information in accordance with §5 DDG (German Digital Services Act):</p>

        <p>
          <strong>Jan-R. Lahmann</strong><br />
          Personal open-source project
        </p>

        <h3>Contact</h3>
        <p>
          For questions, feedback, or legal inquiries, please open an issue on GitHub:<br />
          <a href="https://github.com/JanLahmann/doQumentation/issues" target="_blank" rel="noopener noreferrer">
            github.com/JanLahmann/doQumentation/issues
          </a>
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
          This website is designed to be privacy-friendly. We do not use cookies,
          do not collect personal data, and do not require user accounts.
        </p>

        <h3>Analytics</h3>
        <p>
          We use <a href="https://umami.is" target="_blank" rel="noopener noreferrer">Umami</a> for
          anonymous usage statistics. Umami is a privacy-focused analytics tool that:
        </p>
        <ul>
          <li>Does not use cookies</li>
          <li>Does not collect personal data or IP addresses</li>
          <li>Does not track users across websites</li>
          <li>Is GDPR-compliant without requiring a consent banner</li>
        </ul>
        <p>
          We collect only aggregated, anonymous page view counts and custom events
          (e.g., code execution button clicks) to understand how the site is used.
          No individual user can be identified from this data.
        </p>

        <h3>Hosting</h3>
        <p>
          This website is hosted on <a href="https://pages.github.com" target="_blank" rel="noopener noreferrer">GitHub Pages</a>.
          GitHub may collect technical data (IP addresses, browser type) in server logs
          as described in their <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" target="_blank" rel="noopener noreferrer">privacy statement</a>.
        </p>

        <h3>External Services</h3>
        <p>This site loads resources from the following third-party services:</p>
        <ul>
          <li><strong>Google Fonts</strong> — web fonts (<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">privacy policy</a>)</li>
          <li><strong>jsDelivr CDN</strong> — JavaScript libraries (<a href="https://www.jsdelivr.com/terms/privacy-policy-jsdelivr-net" target="_blank" rel="noopener noreferrer">privacy policy</a>)</li>
          <li><strong>mybinder.org</strong> — code execution via Binder (only when user clicks "Open in JupyterLab")</li>
          <li><strong>Google Colab</strong> — notebook execution (only when user clicks "Open in Colab")</li>
        </ul>

        <h3>Local Storage</h3>
        <p>
          This site uses your browser's localStorage to remember preferences
          (e.g., learning progress, bookmarks, display settings). This data stays
          in your browser and is never sent to any server. You can clear it at any
          time via the <a href="/jupyter-settings">Settings page</a> or your browser settings.
        </p>

        <h3>Your Rights (GDPR)</h3>
        <p>
          Since we do not collect personal data, there is typically no personal data
          to access, correct, or delete. If you believe we hold any personal data
          about you, please <a href="https://github.com/JanLahmann/doQumentation/issues" target="_blank" rel="noopener noreferrer">contact us via GitHub</a>.
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
