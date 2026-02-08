import React from 'react';

interface IBMVideoProps {
  id: string;
  title?: string;
}

/**
 * Stub for IBM's IBMVideo component.
 * IBM videos aren't embeddable, so we show a placeholder card.
 */
export default function IBMVideo({ id, title }: IBMVideoProps) {
  return (
    <div
      style={{
        border: '1px solid var(--ifm-color-emphasis-300)',
        borderRadius: '8px',
        padding: '1.5rem',
        margin: '1rem 0',
        backgroundColor: 'var(--ifm-color-emphasis-100)',
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>
        &#9654;
      </div>
      <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
        {title || 'IBM Video'}
      </div>
      <div style={{ fontSize: '0.85rem', color: 'var(--ifm-color-content-secondary)' }}>
        Video available on the{' '}
        <a
          href="https://quantum.cloud.ibm.com/learning"
          target="_blank"
          rel="noopener noreferrer"
        >
          IBM Quantum Learning platform
        </a>
      </div>
    </div>
  );
}
