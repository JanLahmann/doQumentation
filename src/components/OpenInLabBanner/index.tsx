import BrowserOnly from '@docusaurus/BrowserOnly';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import { detectJupyterConfig, getLabUrl, getBinderLabUrl, getColabUrl } from '../../config/jupyter';

interface OpenInLabBannerProps {
  notebookPath: string;
  description?: string;
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
  return (
    <BrowserOnly>
      {() => {
        const config = detectJupyterConfig();

        // Build the Lab/Binder URL based on environment
        let labUrl: string | null = null;
        if (config.labEnabled) {
          labUrl = getLabUrl(config, notebookPath);
        } else if (config.binderUrl) {
          labUrl = getBinderLabUrl(config, notebookPath);
        }

        const labLabel = config.binderUrl && !config.labEnabled
          ? 'Open in Binder JupyterLab'
          : 'Open in JupyterLab';

        const colabUrl = getColabUrl(notebookPath, currentLocale);

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
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
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
              {labUrl && (
                <a
                  href={labUrl}
                  target="binder-lab"
                  rel="noopener noreferrer"
                  title="Opens the full Jupyter notebook for editing and advanced use"
                  style={{
                    padding: '0.25rem 0.75rem',
                    backgroundColor: 'var(--ifm-color-primary)',
                    color: '#fff',
                    borderRadius: '4px',
                    fontWeight: 600,
                    textDecoration: 'none',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {labLabel} &#8599;
                </a>
              )}
            </div>
          </div>
        );
      }}
    </BrowserOnly>
  );
}
