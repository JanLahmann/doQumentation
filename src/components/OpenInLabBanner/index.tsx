import { useState, useEffect, useRef } from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import {translate} from '@docusaurus/Translate';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import { detectJupyterConfig, getLabUrl, getBinderLabUrl, getColabUrl, openBinderLab } from '../../config/jupyter';
import { trackEvent } from '../../config/analytics';
import InfoIcon from '../InfoIcon';

interface OpenInLabBannerProps {
  notebookPath: string;
  description?: string;
}

// Short label shown inside the button while building (Binder)
const BINDER_PHASE_LABELS: Record<string, string> = {
  connecting: 'Connecting...',
  waiting:    'In queue...',
  fetching:   'Fetching...',
  building:   'Building...',
  pushing:    'Pushing...',
  built:      'Launching...',
  launching:  'Launching...',
  ready:      '',
  failed:     'Binder failed',
};

// Short label for CE phases
const CE_PHASE_LABELS: Record<string, string> = {
  connecting: 'Connecting...',
  launching:  'Starting...',
  ready:      '',
  failed:     'CE failed',
};

// Longer hint shown below the banner while building (Binder)
const BINDER_PHASE_HINTS: Record<string, string> = {
  connecting: 'Connecting to mybinder.org...',
  waiting:    'Waiting in queue...',
  fetching:   'Fetching repository (2–5 min)',
  building:   'Building Docker image (5–10 min)',
  pushing:    'Pushing image to registry (2–5 min)',
  built:      'Image ready — launching JupyterLab...',
  launching:  'Starting JupyterLab server (2–5 min)',
};

// CE hints — fast startup, minimal phases
const CE_PHASE_HINTS: Record<string, string> = {
  connecting: 'Connecting to Code Engine...',
  launching:  'Starting Jupyter server...',
};

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

/**
 * Page-level banner that links to the original .ipynb in JupyterLab and/or Colab.
 *
 * Environment-aware:
 * - RasQberry/Docker: opens local JupyterLab + Colab
 * - GitHub Pages: opens in Binder JupyterLab + Colab
 * - Custom server: opens configured JupyterLab + Colab
 * - Unknown: Colab only (always available)
 */
export default function OpenInLabBanner({ notebookPath, description }: OpenInLabBannerProps) {
  const { i18n: { currentLocale } } = useDocusaurusContext();
  const [binderPhase, setBinderPhase] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [showCacheMissWarning, setShowCacheMissWarning] = useState(false);
  const buildStartRef = useRef<number | null>(null);

  const isActive = !!binderPhase && binderPhase !== 'ready' && binderPhase !== 'failed';

  // Elapsed timer — runs while a build is in progress
  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(() => {
      if (buildStartRef.current !== null) {
        setElapsedSeconds(Math.floor((Date.now() - buildStartRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [isActive]);

  return (
    <BrowserOnly>
      {() => {
        const config = detectJupyterConfig();
        const isCodeEngine = config.environment === 'code-engine';
        const usesRemoteSession = (config.environment === 'github-pages' && !!config.binderUrl) || isCodeEngine;
        const phaseLabels = isCodeEngine ? CE_PHASE_LABELS : BINDER_PHASE_LABELS;
        const phaseHintMap = isCodeEngine ? CE_PHASE_HINTS : BINDER_PHASE_HINTS;

        let labUrl: string | null = null;
        if (config.labEnabled) {
          labUrl = getLabUrl(config, notebookPath);
        } else if (config.binderUrl) {
          labUrl = getBinderLabUrl(config, notebookPath, currentLocale);
        }

        const colabUrl = getColabUrl(notebookPath, currentLocale);

        const handleBinderClick = (e: React.MouseEvent) => {
          trackEvent('Binder Launch', { notebook: notebookPath, page: window.location.pathname });
          // CE with labEnabled: direct link works, no SSE needed
          if (config.labEnabled) return;
          if (!usesRemoteSession) return;
          e.preventDefault();
          if (binderPhase && binderPhase !== 'failed') return;

          buildStartRef.current = Date.now();
          setElapsedSeconds(0);
          setShowCacheMissWarning(false);
          setBinderPhase(null);

          openBinderLab(config, notebookPath, currentLocale, (phase) => {
            setBinderPhase(phase);
            // Entering 'building' means no warm cache — show warning immediately
            if (phase === 'building') {
              setShowCacheMissWarning(true);
            }
            if (phase === 'ready') {
              setTimeout(() => {
                setBinderPhase(null);
                setShowCacheMissWarning(false);
                setElapsedSeconds(0);
                buildStartRef.current = null;
              }, 1000);
            }
            if (phase === 'failed') {
              setTimeout(() => {
                setBinderPhase(null);
                setShowCacheMissWarning(false);
              }, 3000);
            }
          });
        };

        const phaseLabel = binderPhase ? (phaseLabels[binderPhase] ?? binderPhase) : null;
        const hint = isActive ? (phaseHintMap[binderPhase!] ?? null) : null;
        const backendSuffix = isCodeEngine ? ' (IBM Cloud)' : usesRemoteSession ? ' (Binder)' : '';
        const buttonText = isActive
          ? `${phaseLabel} ${formatElapsed(elapsedSeconds)}`
          : phaseLabel || `JupyterLab${backendSuffix} \u2197`;

        return (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.5rem 0.75rem',
              marginBottom: '1rem',
              border: '1px solid var(--ifm-color-emphasis-300)',
              borderRadius: '6px',
              backgroundColor: 'var(--ifm-color-emphasis-100)',
              fontSize: '0.875rem',
              flexWrap: 'wrap',
            }}
          >
            <span>&#128221;</span>
            <span>{description || 'This page was generated from a Jupyter notebook.'}</span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>Open in:<InfoIcon tooltip={translate({id: 'openInLab.info.openIn', message: 'JupyterLab: full notebook editor with all packages pre-installed. Colab: Google\'s free cloud notebooks (requires a Google account).'})} position="below" /></span>
              {labUrl && (
                <a
                  href={labUrl}
                  target={usesRemoteSession ? '_blank' : 'binder-lab'}
                  onClick={handleBinderClick}
                  title={isCodeEngine
                    ? 'JupyterLab via Code Engine — fast serverless kernel'
                    : 'JupyterLab via Binder — full notebook editing environment'
                  }
                  style={{
                    padding: '0.25rem 0.75rem',
                    backgroundColor: binderPhase === 'failed'
                      ? 'var(--ifm-color-danger)'
                      : 'var(--ifm-color-primary)',
                    color: '#fff',
                    borderRadius: '4px',
                    fontWeight: 600,
                    textDecoration: 'none',
                    whiteSpace: 'nowrap',
                    opacity: isActive ? 0.8 : 1,
                    cursor: isActive ? 'wait' : 'pointer',
                  }}
                >
                  {buttonText}
                </a>
              )}
              <a
                href={colabUrl}
                target="_blank"
                rel="noopener noreferrer"
                title="Google Colab — run in the cloud, no setup needed"
                onClick={() => trackEvent('Colab Open', { notebook: notebookPath, page: window.location.pathname })}
                style={{
                  padding: '0.25rem 0.75rem',
                  border: '1px solid var(--ifm-color-primary)',
                  color: 'var(--ifm-color-primary)',
                  borderRadius: '4px',
                  fontWeight: 600,
                  textDecoration: 'none',
                  whiteSpace: 'nowrap',
                }}
              >
                Colab &#8599;
              </a>
              <a
                href="/about/code-modifications"
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--ifm-color-emphasis-500)',
                  textDecoration: 'none',
                  whiteSpace: 'nowrap',
                  alignSelf: 'center',
                }}
                title="See what doQumentation modifies in exported notebooks"
              >
                What&apos;s modified?
              </a>
            </div>
            {isActive && (
              <div style={{ width: '100%', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                {showCacheMissWarning ? (
                  <span style={{ color: 'var(--ifm-color-warning-dark, #b45309)' }}>
                    ⚠ Cache not warmed — total build time 10–25 min. Use the <strong>Colab</strong> button above, or come back later.
                  </span>
                ) : hint ? (
                  <span style={{ color: 'var(--ifm-color-emphasis-600)' }}>{hint}</span>
                ) : null}
              </div>
            )}
          </div>
        );
      }}
    </BrowserOnly>
  );
}
