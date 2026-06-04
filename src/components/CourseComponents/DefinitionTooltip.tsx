import React from 'react';
import { stripInlineMarkup } from '@site/src/lib/inlineMarkup';

interface DefinitionTooltipProps {
  definition: string;
  children: React.ReactNode;
}

/**
 * Stub for IBM's DefinitionTooltip component.
 * Renders as <abbr> with a native browser tooltip. The `definition` prop can
 * carry inline markdown/HTML from upstream; a native title= attribute renders
 * as plain text, so strip the markup to avoid leaking literal `**…**`/`<em>`.
 */
export default function DefinitionTooltip({ definition, children }: DefinitionTooltipProps) {
  return (
    <abbr
      title={stripInlineMarkup(definition)}
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
