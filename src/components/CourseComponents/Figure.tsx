import React from 'react';

interface FigureProps {
  title?: string;
  children: React.ReactNode;
}

/**
 * Stub for IBM's Figure component.
 * Used in course notebooks for definitions, theorems, and other highlighted content.
 */
export default function Figure({ title, children }: FigureProps) {
  return (
    <div
      style={{
        border: '1px solid var(--ifm-color-emphasis-300)',
        borderRadius: '6px',
        margin: '1rem 0',
        overflow: 'hidden',
      }}
    >
      {title && (
        <div
          style={{
            padding: '0.5rem 0.75rem',
            backgroundColor: 'var(--ifm-color-emphasis-100)',
            borderBottom: '1px solid var(--ifm-color-emphasis-300)',
            fontWeight: 600,
            fontSize: '0.9rem',
          }}
        >
          {title}
        </div>
      )}
      <div style={{ padding: '0.75rem' }}>{children}</div>
    </div>
  );
}
