import React from 'react';

interface CardGroupProps {
  children: React.ReactNode;
}

/**
 * Stub for IBM's CardGroup component.
 * Renders children in a responsive grid layout.
 */
export default function CardGroup({ children }: CardGroupProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: '1rem',
        margin: '1rem 0',
      }}
    >
      {children}
    </div>
  );
}
