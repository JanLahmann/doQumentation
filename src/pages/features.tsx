/**
 * Features Page
 *
 * Showcases all implemented features of the doQumentation platform,
 * organized into card-grid sections.
 */

import React from 'react';
import Layout from '@theme/Layout';
import Translate, {translate} from '@docusaurus/Translate';

interface FeatureCardProps {
  title: string;
  description: string;
  link?: string;
  linkLabel?: string;
}

function FeatureCard({ title, description, link, linkLabel }: FeatureCardProps) {
  return (
    <div className="feature-card">
      <h3 className="feature-card__title">{title}</h3>
      <p className="feature-card__desc">{description}</p>
      {link && (
        <a className="feature-card__link" href={link}>
          {linkLabel || translate({id: 'features.learnMore', message: 'Learn more'})} &rarr;
        </a>
      )}
    </div>
  );
}

export default function Features(): JSX.Element {
  return (
    <Layout
      title={translate({id: 'features.title', message: 'Features'})}
      description={translate({id: 'features.description', message: 'All features of the doQumentation platform — live code execution, simulator mode, learning progress, and more.'})}
    >
      <main className="container margin-vert--lg">
        <div className="features-page">
          <h1><Translate id="features.heading">Features</Translate></h1>
          <p className="features-page__intro">
            <Translate id="features.intro">
              doQumentation turns IBM Quantum's open-source content into an
              interactive learning platform with live code execution, simulator
              mode, and learning progress tracking.
            </Translate>
          </p>

          {/* ── Content Library ── */}
          <section className="features-page__section">
            <h2><Translate id="features.contentLibrary.heading">Content Library</Translate></h2>
            <div className="features-page__grid">
              <FeatureCard
                title={translate({id: 'features.contentLibrary.pages.title', message: '381 Pages of Content'})}
                description={translate({id: 'features.contentLibrary.pages.desc', message: "42 Tutorials, 171 Guides, 154 Course pages, and 14 Modules — all sourced from IBM Quantum's open-source Qiskit documentation."})}
                link="/tutorials"
                linkLabel={translate({id: 'features.contentLibrary.pages.link', message: 'Browse tutorials'})}
              />
              <FeatureCard
                title={translate({id: 'features.contentLibrary.sync.title', message: 'Auto-Sync from Upstream'})}
                description={translate({id: 'features.contentLibrary.sync.desc', message: "Content is automatically synced from IBM's GitHub repository, keeping tutorials and courses up to date with the latest Qiskit releases."})}
              />
              <FeatureCard
                title={translate({id: 'features.contentLibrary.nav.title', message: 'Structured Navigation'})}
                description={translate({id: 'features.contentLibrary.nav.desc', message: 'Auto-generated sidebars with collapsible categories. Tutorials, Guides, Courses, and Modules each have their own organized sidebar.'})}
              />
            </div>
          </section>

          {/* ── Live Code Execution ── */}
          <section className="features-page__section">
            <h2><Translate id="features.execution.heading">Live Code Execution</Translate></h2>
            <div className="features-page__grid">
              <FeatureCard
                title={translate({id: 'features.execution.toggle.title', message: 'Run / Back Toggle'})}
                description={translate({id: 'features.execution.toggle.desc', message: 'Every notebook page has a Run button that activates all code cells with a live Jupyter kernel. Click Back to return to the static view.'})}
              />
              <FeatureCard
                title={translate({id: 'features.execution.backends.title', message: 'Three Execution Backends'})}
                description={translate({id: 'features.execution.backends.desc', message: 'Free remote execution via Binder (no install needed), full offline via Docker, or self-hosted on a RasQberry Pi.'})}
                link="/jupyter-settings#advanced"
                linkLabel={translate({id: 'features.execution.backends.link', message: 'Configure backend'})}
              />
              <FeatureCard
                title={translate({id: 'features.execution.feedback.title', message: 'Cell Execution Feedback'})}
                description={translate({id: 'features.execution.feedback.desc', message: 'Visual feedback on every cell: amber border while running, green when done, red on error. A legend appears in the toolbar when the kernel is ready.'})}
              />
              <FeatureCard
                title={translate({id: 'features.execution.errors.title', message: 'Contextual Error Hints'})}
                description={translate({id: 'features.execution.errors.desc', message: 'Automatic detection of ModuleNotFoundError, NameError, and kernel disconnection. Actionable hints appear below the cell with suggested fixes.'})}
              />
              <FeatureCard
                title={translate({id: 'features.execution.pip.title', message: 'One-Click Pip Install'})}
                description={translate({id: 'features.execution.pip.desc', message: "When a missing package is detected, a clickable 'Install' button appears. After install completes, the failed cell re-runs automatically."})}
              />
              <FeatureCard
                title={translate({id: 'features.execution.lab.title', message: 'Open in JupyterLab'})}
                description={translate({id: 'features.execution.lab.desc', message: 'Every notebook page has a button to open the full .ipynb in JupyterLab for advanced editing and exploration.'})}
              />
            </div>
          </section>

          {/* ── IBM Quantum Integration ── */}
          <section className="features-page__section">
            <h2><Translate id="features.ibm.heading">IBM Quantum Integration</Translate></h2>
            <div className="features-page__grid">
              <FeatureCard
                title={translate({id: 'features.ibm.credentials.title', message: 'Credential Store'})}
                description={translate({id: 'features.ibm.credentials.desc', message: 'Save your IBM Quantum API token and CRN once in Settings. Stored locally in your browser with 7-day auto-expiry for security.'})}
                link="/jupyter-settings#ibm-quantum"
                linkLabel={translate({id: 'features.ibm.credentials.link', message: 'Set up credentials'})}
              />
              <FeatureCard
                title={translate({id: 'features.ibm.injection.title', message: 'Auto-Injection'})}
                description={translate({id: 'features.ibm.injection.desc', message: 'Credentials are silently injected into the kernel on startup. No need to paste tokens into every notebook — just click Run.'})}
              />
              <FeatureCard
                title={translate({id: 'features.ibm.simulator.title', message: 'Simulator Mode'})}
                description={translate({id: 'features.ibm.simulator.desc', message: 'Run all notebooks without an IBM Quantum account. Choose AerSimulator for ideal simulation, or pick from dozens of FakeBackends that model real device noise. Zero setup required.'})}
                link="/jupyter-settings#simulator-mode"
                linkLabel={translate({id: 'features.ibm.simulator.link', message: 'Enable simulator'})}
              />
              <FeatureCard
                title={translate({id: 'features.ibm.badge.title', message: 'Execution Mode Badge'})}
                description={translate({id: 'features.ibm.badge.desc', message: "The toolbar shows which mode is active — the simulator name (e.g. 'FakeSherbrooke') or 'IBM Quantum' — so you always know how your code is running."})}
              />
            </div>
          </section>

          {/* ── Learning & Progress ── */}
          <section className="features-page__section">
            <h2><Translate id="features.progress.heading">Learning &amp; Progress</Translate></h2>
            <div className="features-page__grid">
              <FeatureCard
                title={translate({id: 'features.progress.tracking.title', message: 'Progress Tracking'})}
                description={translate({id: 'features.progress.tracking.desc', message: 'Pages you visit get a checkmark (✓) in the sidebar. Notebooks you execute get a play indicator (▶). Track your journey through the content.'})}
              />
              <FeatureCard
                title={translate({id: 'features.progress.badges.title', message: 'Category Badges'})}
                description={translate({id: 'features.progress.badges.desc', message: "Each sidebar category shows a badge like '3/10' so you can see progress at a glance. Click to clear per-section progress."})}
              />
              <FeatureCard
                title={translate({id: 'features.progress.resume.title', message: 'Resume Reading'})}
                description={translate({id: 'features.progress.resume.desc', message: "The homepage shows a 'Continue where you left off' card with your last visited page and when you were there."})}
                link="/"
                linkLabel={translate({id: 'features.progress.resume.link', message: 'Go to homepage'})}
              />
            </div>
          </section>

          {/* ── Search, UI & Deployment ── */}
          <section className="features-page__section">
            <h2><Translate id="features.ui.heading">Search, UI &amp; Deployment</Translate></h2>
            <div className="features-page__grid">
              <FeatureCard
                title={translate({id: 'features.ui.search.title', message: 'Local Search'})}
                description={translate({id: 'features.ui.search.desc', message: 'Full-text search across all 381 pages, works offline. Results appear instantly as you type.'})}
              />
              <FeatureCard
                title={translate({id: 'features.ui.dark.title', message: 'Dark Mode'})}
                description={translate({id: 'features.ui.dark.desc', message: 'Full dark theme support. Circuit diagrams and Matplotlib outputs auto-invert for readability.'})}
              />
              <FeatureCard
                title={translate({id: 'features.ui.video.title', message: 'Video Embeds'})}
                description={translate({id: 'features.ui.video.desc', message: 'Course videos with YouTube mapping for reliable playback. Falls back to IBM Video when YouTube is unavailable.'})}
              />
              <FeatureCard
                title={translate({id: 'features.ui.docker.title', message: 'Docker Deployment'})}
                description={translate({id: 'features.ui.docker.desc', message: 'Multi-stage Docker build with CI/CD to GitHub Container Registry. Full stack (site + Jupyter) or lightweight static-only image.'})}
              />
              <FeatureCard
                title={translate({id: 'features.ui.mobile.title', message: 'Mobile Responsive'})}
                description={translate({id: 'features.ui.mobile.desc', message: 'Hamburger navigation, horizontal code scrolling, and responsive card grids. Works on phones and tablets.'})}
              />
              <FeatureCard
                title={translate({id: 'features.ui.math.title', message: 'Math Rendering'})}
                description={translate({id: 'features.ui.math.desc', message: 'KaTeX for fast, high-quality LaTeX math rendering across all content pages — equations, matrices, and quantum notation.'})}
              />
            </div>
          </section>
        </div>
      </main>
    </Layout>
  );
}
