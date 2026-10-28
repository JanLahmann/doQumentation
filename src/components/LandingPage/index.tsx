/**
 * LandingPage — one page per doQumentation differentiator.
 *
 * These pages, the home page and /features are what we want search engines
 * to index: everything mirrored from IBM is noindexed. Each page has one
 * topic, a screenshot, a few short sections, an FAQ (also emitted as
 * FAQPage JSON-LD) and links to tutorials that show the feature.
 */

import React from 'react';
import Layout from '@theme/Layout';
import Head from '@docusaurus/Head';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import {translate} from '@docusaurus/Translate';

export interface LandingSection {
  heading: string;
  body: React.ReactNode;
}

export interface LandingFaq {
  question: string;
  /** Plain text: it is also the JSON-LD answer. */
  answer: string;
}

export interface LandingLink {
  label: string;
  to: string;
}

interface LandingPageProps {
  /** <title>, also og:title. Keep it under 60 characters. */
  title: string;
  /** Meta description, also og:description. Keep it under 160 characters. */
  description: string;
  heading: string;
  intro: React.ReactNode;
  cta: LandingLink;
  /** Path under static/, e.g. '/img/landing/run.png'. */
  image?: string;
  imageAlt?: string;
  sections: LandingSection[];
  faq: LandingFaq[];
  /** Tutorials or guides that show the feature. */
  tryLinks: LandingLink[];
  /** Other landing pages. */
  related: LandingLink[];
}

export default function LandingPage(props: LandingPageProps): React.JSX.Element {
  const imageUrl = useBaseUrl(props.image ?? '');
  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: props.faq.map((f) => ({
      '@type': 'Question',
      name: f.question,
      acceptedAnswer: {'@type': 'Answer', text: f.answer},
    })),
  };
  return (
    <Layout title={props.title} description={props.description}>
      <Head>
        {/* Layout appends " | doQumentation"; social cards get the bare title. */}
        <meta property="og:title" content={props.title} />
        <script type="application/ld+json">{JSON.stringify(faqJsonLd)}</script>
      </Head>
      <main className="container margin-vert--lg">
        <article className="features-page landing-page">
          <h1>{props.heading}</h1>
          <div className="features-page__intro">{props.intro}</div>
          <p>
            <Link className="hero-banner__cta" to={props.cta.to}>{props.cta.label}</Link>
          </p>
          {props.image && (
            <img className="landing-page__image" src={imageUrl} alt={props.imageAlt ?? ''} loading="lazy" />
          )}
          {props.sections.map((s) => (
            <section key={s.heading} className="features-page__section">
              <h2>{s.heading}</h2>
              {s.body}
            </section>
          ))}
          <section className="features-page__section">
            <h2>{translate({id: 'landing.common.try', message: 'Try it on these pages'})}</h2>
            <ul>
              {props.tryLinks.map((l) => (
                <li key={l.to}><Link to={l.to}>{l.label}</Link></li>
              ))}
            </ul>
          </section>
          <section className="features-page__section landing-page__faq">
            <h2>{translate({id: 'landing.common.faq', message: 'Frequently asked questions'})}</h2>
            {props.faq.map((f) => (
              <details key={f.question}>
                <summary>{f.question}</summary>
                <p>{f.answer}</p>
              </details>
            ))}
          </section>
          <nav className="features-page__section landing-page__related"
               aria-label={translate({id: 'landing.common.related', message: 'More of what doQumentation adds'})}>
            <h2>{translate({id: 'landing.common.related', message: 'More of what doQumentation adds'})}</h2>
            <ul>
              {props.related.map((l) => (
                <li key={l.to}><Link to={l.to}>{l.label}</Link></li>
              ))}
              <li>
                <Link to="/features">{translate({id: 'landing.common.allFeatures', message: 'All features'})}</Link>
              </li>
            </ul>
          </nav>
        </article>
      </main>
    </Layout>
  );
}
