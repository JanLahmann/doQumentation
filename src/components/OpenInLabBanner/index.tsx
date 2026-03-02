import { useState } from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import { detectJupyterConfig, getLabUrl, getBinderLabUrl, getColabUrl, openBinderLab, getRawBinderUrl } from '../../config/jupyter';

interface OpenInLabBannerProps {
  notebookPath: string;
  description?: string;
}

const PHASE_LABELS: Record<string, string> = {
  connecting: 'Starting Binder (may take 1\u20132 min on first run)...',
  fetching: 'Fetching repo...',
  building: 'Building image (1\u20132 min on first run)...',
  pushing: 'Pushing image...',
  built: 'Image ready...',
  launching: 'Launching server...',
  ready: '',
  failed: 'Binder failed',
};

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

  return (
    <BrowserOnly>
      {() => {
        const config = detectJupyterConfig();

        // Build the Lab/Binder URL based on environment
        let labUrl: string | null = null;
        const isBinder = config.binderUrl && !config.labEnabled;
        if (config.labEnabled) {
          labUrl = getLabUrl(config, notebookPath);
        } else if (config.binderUrl) {
          labUrl = getBinderLabUrl(config, notebookPath, currentLocale);
        }

        const labLabel = isBinder ? 'Open in Binder JupyterLab' : 'Open in JupyterLab';
        const colabUrl = getColabUrl(notebookPath, currentLocale);
        const rawBinderUrl = isBinder ? getRawBinderUrl(config, notebookPath, currentLocale) : null;

        const handleBinderClick = (e: React.MouseEvent) => {
          if (!isBinder) return; // let non-Binder links work normally
          e.preventDefault();
          if (binderPhase && binderPhase !== 'failed') return; // build in progress
          setBinderPhase(null);
          openBinderLab(config, notebookPath, currentLocale, (phase) => {
            setBinderPhase(phase);
            if (phase === 'ready') {
              setTimeout(() => setBinderPhase(null), 1000);
            }
            if (phase === 'failed') {
              setTimeout(() => setBinderPhase(null), 3000);
            }
          });
        };

        const phaseText = binderPhase ? PHASE_LABELS[binderPhase] || binderPhase : null;

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
              <a
                href={colabUrl}
                target="_blank"
                rel="noopener noreferrer"
                title="Open notebook in Google Colab"
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
                Open in Colab &#8599;
              </a>
              {rawBinderUrl && (
                <a
                  href={rawBinderUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open the mybinder.org build page directly"
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
                  Launch Raw Binder &#8599;
                </a>
              )}
              {labUrl && (
                <a
                  href={labUrl}
                  target={isBinder ? '_blank' : 'binder-lab'}
                  onClick={handleBinderClick}
                  title="Opens the full Jupyter notebook for editing and advanced use"
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
                    opacity: (binderPhase && binderPhase !== 'ready' && binderPhase !== 'failed') ? 0.8 : 1,
                    cursor: (binderPhase && binderPhase !== 'ready' && binderPhase !== 'failed') ? 'wait' : 'pointer',
                  }}
                >
                  {phaseText || `${labLabel} \u2197`}
                </a>
              )}
            </div>
          </div>
        );
      }}
    </BrowserOnly>
  );
}
