/**
 * Docusaurus Client Module — Onboarding Tips
 *
 * Shows contextual tips for first-time visitors on content pages.
 * Auto-completes after 3 page visits or manual dismiss.
 * Registered in docusaurus.config.ts as a clientModule.
 */

import {translate} from '@docusaurus/Translate';
import {
  isOnboardingCompleted,
  completeOnboarding,
  incrementOnboardingVisits,
} from '../config/preferences';

const TIP_ID = 'dq-onboarding-tip';

function removeTip(): void {
  document.getElementById(TIP_ID)?.remove();
}

function createTip(message: string): void {
  // Remove any existing tip first
  removeTip();

  const tip = document.createElement('div');
  tip.id = TIP_ID;
  tip.className = 'dq-onboarding-tip';
  tip.innerHTML = `
    <span>${message}</span>
    <button class="dq-onboarding-tip__dismiss">&times;</button>
  `;

  const dismissBtn = tip.querySelector('.dq-onboarding-tip__dismiss');
  if (dismissBtn) {
    // Set as properties, not in the HTML string, so a quote in a translation
    // cannot break the attribute.
    dismissBtn.setAttribute('title', translate({id: 'onboarding.dismiss', message: 'Dismiss', description: 'Tooltip of the button that closes the onboarding tip'}));
    dismissBtn.setAttribute('aria-label', translate({id: 'onboarding.dismissAria', message: 'Dismiss tip', description: 'Screen-reader label of the button that closes the onboarding tip'}));
    dismissBtn.addEventListener('click', () => {
      completeOnboarding();
      removeTip();
    });
  }

  // Insert at the top of the doc content area
  const target = document.querySelector('.theme-doc-markdown');
  if (target && target.firstChild) {
    target.insertBefore(tip, target.firstChild);
  }
}

function isContentPage(path: string): boolean {
  return path !== '/' && path !== '/jupyter-settings';
}

export function onRouteDidUpdate({ location }: { location: Location }): void {
  // Small delay to let the page render
  setTimeout(() => {
    if (isOnboardingCompleted()) {
      removeTip();
      return;
    }

    if (!isContentPage(location.pathname)) {
      removeTip();
      return;
    }

    const count = incrementOnboardingVisits();
    if (count > 2) {
      removeTip();
      return;
    }

    // Choose tip based on page content
    const hasCode = document.querySelector('.executable-code');
    const message = hasCode
      ? translate({
          id: 'onboarding.tip.run',
          message: 'Click <strong>Run</strong> on any code block to execute it live \u2014 no setup needed.',
          description: 'Onboarding tip on pages with runnable code; keep the <strong> tags and the word Run as the button shows it',
        })
      : translate({
          id: 'onboarding.tip.progress',
          message: 'Your progress is tracked automatically \u2014 visited pages show \u2713 in the sidebar.',
          description: 'Onboarding tip on pages without code',
        });

    createTip(message);
  }, 300);
}
