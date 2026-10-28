/** Landing page: track your progress through the courses. */

import React from 'react';
import {translate} from '@docusaurus/Translate';
import LandingPage from '@site/src/components/LandingPage';
import {landingLinks} from '@site/src/components/LandingPage/links';

export default function LearningProgress(): React.JSX.Element {
  return (
    <LandingPage
      title={translate({id: 'landing.progress.title', message: 'Track Your Progress Through IBM Quantum Courses'})}
      description={translate({id: 'landing.progress.description', message: "See which IBM Quantum course pages and tutorials you have read and run, continue where you left off, and bookmark pages. No account, no sign-up."})}
      heading={translate({id: 'landing.progress.heading', message: 'Track your progress through the courses'})}
      intro={<p>{translate({id: 'landing.progress.intro', message: "IBM Quantum's courses run to dozens of lessons. doQumentation marks what you have read and what you have run, so you can see how far you are and pick up where you stopped, with no account and no sign-up."})}</p>}
      cta={{to: '/learning/courses', label: translate({id: 'landing.progress.cta', message: 'Browse the course catalogue'})}}
      image="/img/landing/learning-progress.png"
      imageAlt={translate({id: 'landing.progress.imageAlt', message: 'The sidebar with progress counters per section and marks on read and run pages.'})}
      sections={[
        {heading: translate({id: 'landing.progress.marks.heading', message: 'Read and run, at a glance'}),
          body: <p>{translate({id: 'landing.progress.marks.body', message: 'Pages you have read get a checkmark (✓) in the sidebar. Notebook pages carry a </> mark that turns blue once you have read the page and green once you have run its code. Each section shows a counter such as 3/10.'})}</p>},
        {heading: translate({id: 'landing.progress.resume.heading', message: 'Continue where you left off'}),
          body: <p>{translate({id: 'landing.progress.resume.body', message: 'The home page shows a "Continue where you left off" card with the last page you read, your five most recent pages and your bookmarks. Star any page to bookmark it.'})}</p>},
        {heading: translate({id: 'landing.progress.store.heading', message: 'Stays in your browser'}),
          body: <p>{translate({id: 'landing.progress.store.body', message: "Progress and bookmarks are kept in your browser, not in an account. They follow you between the language versions of the site on the same browser, and you can clear them in Settings."})}</p>},
      ]}
      faq={[
        {question: translate({id: 'landing.progress.faq.account.q', message: 'Do I need an account to track my progress?'}),
          answer: translate({id: 'landing.progress.faq.account.a', message: 'No. Progress and bookmarks are kept in your browser.'})},
        {question: translate({id: 'landing.progress.faq.devices.q', message: 'Does my progress move to another device?'}),
          answer: translate({id: 'landing.progress.faq.devices.a', message: 'No. Each browser keeps its own progress; clearing the browser data clears it too.'})},
        {question: translate({id: 'landing.progress.faq.reset.q', message: 'How do I reset my progress?'}),
          answer: translate({id: 'landing.progress.faq.reset.a', message: "Click a page's mark in the sidebar to clear that page, or clear a section or all of your progress in Settings."})},
      ]}
      tryLinks={[
        {to: '/learning/courses/basics-of-quantum-information', label: translate({id: 'landing.progress.try.basics', message: 'Basics of quantum information'})},
        {to: '/learning/courses/utility-scale-quantum-computing', label: translate({id: 'landing.progress.try.utility', message: 'Utility-scale quantum computing'})},
        {to: '/learning/courses/quantum-chem-with-vqe', label: translate({id: 'landing.progress.try.vqe', message: 'Quantum chemistry with VQE'})},
      ]}
      related={landingLinks('progress')}
    />
  );
}
