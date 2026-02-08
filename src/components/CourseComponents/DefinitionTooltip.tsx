import React from 'react';

interface DefinitionTooltipProps {
  definition: string;
  children: React.ReactNode;
}

/**
 * Stub for IBM's DefinitionTooltip component.
 * Renders as <abbr> with a native browser tooltip.
 */
export default function DefinitionTooltip({ definition, children }: DefinitionTooltipProps) {
  return (
    <abbr
      title={definition}
      style={{
        textDecoration: 'underline dotted',
        textUnderlineOffset: '2px',
        cursor: 'help',
      }}
    >
      {children}
    </abbr>
  );
}
