import React from 'react';
import {translate} from '@docusaurus/Translate';

interface CodeAssistantAdmonitionProps {
  tagLine?: string;
  prompts?: string[];
}

/**
 * Stub for IBM's CodeAssistantAdmonition component.
 * IBM-specific feature — render as a subtle tip.
 */
export default function CodeAssistantAdmonition({ tagLine }: CodeAssistantAdmonitionProps) {
  return (
    <div
      style={{
        border: '1px solid var(--ifm-color-emphasis-200)',
        borderRadius: '6px',
        padding: '0.75rem 1rem',
        margin: '1rem 0',
        fontSize: '0.9rem',
        color: 'var(--ifm-color-content-secondary)',
      }}
    >
      {tagLine || translate({id: 'codeAssistant.defaultTagLine', message: 'Try Qiskit Code Assistant for help with this topic.', description: 'Default line of the Qiskit Code Assistant tip box; keep the product name'})}
    </div>
  );
}
