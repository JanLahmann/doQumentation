/**
 * Docusaurus Client Module — Onboarding Tips
 *
 * Shows contextual tips for first-time visitors on content pages.
 * Auto-completes after 3 page visits or manual dismiss.
 * Registered in docusaurus.config.ts as a clientModule.
 */

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
    <button class="dq-onboarding-tip__dismiss" title="Dismiss" aria-label="Dismiss tip">&times;</button>
  `;

  const dismissBtn = tip.querySelector('.dq-onboarding-tip__dismiss');
  if (dismissBtn) {
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
    if (count > 3) {
      removeTip();
      return;
    }

    // Choose tip based on page content
    const hasCode = document.querySelector('.executable-code');
    const message = hasCode
      ? 'Click <strong>Run</strong> on any code block to execute it. The first run starts a free Jupyter kernel (1\u20132 min). Configure IBM Quantum credentials or simulator mode in <a href="/jupyter-settings">Settings</a>.'
      : 'Your progress is tracked automatically \u2014 visited pages show \u2713 in the sidebar. Explore <a href="/jupyter-settings">Settings</a> to configure code execution.';

    createTip(message);
  }, 300);
}
