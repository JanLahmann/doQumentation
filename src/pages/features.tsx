/**
 * Features Page
 *
 * Showcases all implemented features of the doQumentation platform,
 * organized into card-grid sections.
 */

import React from 'react';
import Layout from '@theme/Layout';

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
          {linkLabel || 'Learn more'} &rarr;
        </a>
      )}
    </div>
  );
}

export default function Features(): JSX.Element {
  return (
    <Layout
      title="Features"
      description="All features of the doQumentation platform — live code execution, simulator mode, learning progress, and more."
    >
      <main className="container margin-vert--lg">
        <div className="features-page">
          <h1>Features</h1>
          <p className="features-page__intro">
            doQumentation turns IBM Quantum's open-source content into an
            interactive learning platform with live code execution, simulator
            mode, and learning progress tracking.
          </p>

          {/* ── Content Library ── */}
          <section className="features-page__section">
            <h2>Content Library</h2>
            <div className="features-page__grid">
              <FeatureCard
                title="381 Pages of Content"
                description="42 Tutorials, 171 Guides, 154 Course pages, and 14 Modules — all sourced from IBM Quantum's open-source Qiskit documentation."
                link="/tutorials"
                linkLabel="Browse tutorials"
              />
              <FeatureCard
                title="Auto-Sync from Upstream"
                description="Content is automatically synced from IBM's GitHub repository, keeping tutorials and courses up to date with the latest Qiskit releases."
              />
              <FeatureCard
                title="Structured Navigation"
                description="Auto-generated sidebars with collapsible categories. Tutorials, Guides, Courses, and Modules each have their own organized sidebar."
              />
            </div>
          </section>

          {/* ── Live Code Execution ── */}
          <section className="features-page__section">
            <h2>Live Code Execution</h2>
            <div className="features-page__grid">
              <FeatureCard
                title="Run / Back Toggle"
                description="Every notebook page has a Run button that activates all code cells with a live Jupyter kernel. Click Back to return to the static view."
              />
              <FeatureCard
                title="Three Execution Backends"
                description="Free remote execution via Binder (no install needed), full offline via Docker, or self-hosted on a RasQberry Pi."
                link="/jupyter-settings#advanced"
                linkLabel="Configure backend"
              />
              <FeatureCard
                title="Cell Execution Feedback"
                description="Visual feedback on every cell: amber border while running, green when done, red on error. A legend appears in the toolbar when the kernel is ready."
              />
              <FeatureCard
                title="Contextual Error Hints"
                description="Automatic detection of ModuleNotFoundError, NameError, and kernel disconnection. Actionable hints appear below the cell with suggested fixes."
              />
              <FeatureCard
                title="One-Click Pip Install"
                description="When a missing package is detected, a clickable 'Install' button appears. After install completes, the failed cell re-runs automatically."
              />
              <FeatureCard
                title="Open in JupyterLab"
                description="Every notebook page has a button to open the full .ipynb in JupyterLab for advanced editing and exploration."
              />
            </div>
          </section>

          {/* ── IBM Quantum Integration ── */}
          <section className="features-page__section">
            <h2>IBM Quantum Integration</h2>
            <div className="features-page__grid">
              <FeatureCard
                title="Credential Store"
                description="Save your IBM Quantum API token and CRN once in Settings. Stored locally in your browser with 7-day auto-expiry for security."
                link="/jupyter-settings#ibm-quantum"
                linkLabel="Set up credentials"
              />
              <FeatureCard
                title="Auto-Injection"
                description="Credentials are silently injected into the kernel on startup. No need to paste tokens into every notebook — just click Run."
              />
              <FeatureCard
                title="Simulator Mode"
                description="Run all notebooks without an IBM Quantum account. Choose AerSimulator for ideal simulation, or pick from 8 FakeBackends that model real device noise. Zero setup required."
                link="/jupyter-settings#simulator-mode"
                linkLabel="Enable simulator"
              />
              <FeatureCard
                title="Execution Mode Badge"
                description="The toolbar shows which mode is active — the simulator name (e.g. 'FakeSherbrooke') or 'IBM Quantum' — so you always know how your code is running."
              />
            </div>
          </section>

          {/* ── Learning & Progress ── */}
          <section className="features-page__section">
            <h2>Learning &amp; Progress</h2>
            <div className="features-page__grid">
              <FeatureCard
                title="Progress Tracking"
                description="Pages you visit get a checkmark (✓) in the sidebar. Notebooks you execute get a play indicator (▶). Track your journey through the content."
              />
              <FeatureCard
                title="Category Badges"
                description="Each sidebar category shows a badge like '3/10' so you can see progress at a glance. Click to clear per-section progress."
              />
              <FeatureCard
                title="Resume Reading"
                description="The homepage shows a 'Continue where you left off' card with your last visited page and when you were there."
                link="/"
                linkLabel="Go to homepage"
              />
            </div>
          </section>

          {/* ── Search, UI & Deployment ── */}
          <section className="features-page__section">
            <h2>Search, UI &amp; Deployment</h2>
            <div className="features-page__grid">
              <FeatureCard
                title="Local Search"
                description="Full-text search across all 381 pages, works offline. Results appear instantly as you type."
              />
              <FeatureCard
                title="Dark Mode"
                description="Full dark theme support. Circuit diagrams and Matplotlib outputs auto-invert for readability."
              />
              <FeatureCard
                title="Video Embeds"
                description="Course videos with YouTube mapping for reliable playback. Falls back to IBM Video when YouTube is unavailable."
              />
              <FeatureCard
                title="Docker Deployment"
                description="Multi-stage Docker build with CI/CD to GitHub Container Registry. Full stack (site + Jupyter) or lightweight static-only image."
              />
              <FeatureCard
                title="Mobile Responsive"
                description="Hamburger navigation, horizontal code scrolling, and responsive card grids. Works on phones and tablets."
              />
              <FeatureCard
                title="Math Rendering"
                description="KaTeX for fast, high-quality LaTeX math rendering across all content pages — equations, matrices, and quantum notation."
              />
            </div>
          </section>
        </div>
      </main>
    </Layout>
  );
}
