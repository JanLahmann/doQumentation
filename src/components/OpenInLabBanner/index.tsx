import React from 'react';
import BrowserOnly from '@docusaurus/BrowserOnly';
import { detectJupyterConfig, getLabUrl, getBinderLabUrl } from '../../config/jupyter';

interface OpenInLabBannerProps {
  notebookPath: string;
}

/**
 * Page-level banner that links to the original .ipynb in JupyterLab.
 *
 * Environment-aware:
 * - RasQberry/Docker: opens local JupyterLab
 * - GitHub Pages: opens in Binder JupyterLab
 * - Custom server: opens configured JupyterLab
 */
export default function OpenInLabBanner({ notebookPath }: OpenInLabBannerProps) {
  return (
    <BrowserOnly>
      {() => {
        const config = detectJupyterConfig();

        // Build the URL based on environment
        let labUrl: string | null = null;
        if (config.labEnabled) {
          labUrl = getLabUrl(config, notebookPath);
        } else if (config.binderUrl) {
          labUrl = getBinderLabUrl(config, notebookPath);
        }

        if (!labUrl) return null;

        const label = config.binderUrl && !config.labEnabled
          ? 'Open in Binder JupyterLab'
          : 'Open in JupyterLab';

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
            }}
          >
            <span>&#128221;</span>
            <span>This page was generated from a Jupyter notebook.</span>
            <a
              href={labUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Opens the full Jupyter notebook for editing and advanced use"
              style={{
                marginLeft: 'auto',
                padding: '0.25rem 0.75rem',
                backgroundColor: 'var(--ifm-color-primary)',
                color: '#fff',
                borderRadius: '4px',
                fontWeight: 600,
                textDecoration: 'none',
                whiteSpace: 'nowrap',
              }}
            >
              {label} &#8599;
            </a>
          </div>
        );
      }}
    </BrowserOnly>
  );
}
