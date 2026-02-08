import React from 'react';

interface CardProps {
  title?: string;
  description?: string;
  href?: string;
  linkText?: string;
  analyticsName?: string;
  children?: React.ReactNode;
}

/**
 * Stub for IBM's Card component used in guide index pages.
 * Renders as a styled link card.
 */
export default function Card({ title, description, href, linkText, children }: CardProps) {
  const content = (
    <div
      style={{
        border: '1px solid var(--ifm-color-emphasis-300)',
        borderRadius: '8px',
        padding: '1rem 1.25rem',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'border-color 0.2s',
      }}
    >
      {title && (
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '1rem' }}>
          {title}
        </div>
      )}
      {description && (
        <div style={{ fontSize: '0.9rem', color: 'var(--ifm-color-content-secondary)', flex: 1 }}>
          {description}
        </div>
      )}
      {children}
      {linkText && (
        <div style={{ marginTop: '0.75rem', fontSize: '0.9rem', color: 'var(--ifm-color-primary)' }}>
          {linkText} &rarr;
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <a href={href} style={{ textDecoration: 'none', color: 'inherit' }}>
        {content}
      </a>
    );
  }
  return content;
}
