import React from 'react';

interface LaunchExamButtonProps {
  href: string;
}

/**
 * Stub for IBM's LaunchExamButton component.
 * Renders a styled external link to the IBM Training exam page.
 */
export default function LaunchExamButton({ href }: LaunchExamButtonProps) {
  return (
    <div style={{ margin: '1.5rem 0' }}>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'inline-block',
          padding: '0.75rem 1.5rem',
          backgroundColor: 'var(--ifm-color-primary)',
          color: '#fff',
          borderRadius: '4px',
          fontWeight: 600,
          textDecoration: 'none',
          fontSize: '1rem',
        }}
      >
        Launch exam &#8599;
      </a>
    </div>
  );
}
