/**
 * CodeBlock Theme Override
 * 
 * Optionally wraps Python code blocks with the ExecutableCode component
 * for interactive execution. This can be controlled via:
 * - metastring: ```python executable or ```python noexec
 * - Global setting in docusaurus.config.ts
 */

import React from 'react';
import OriginalCodeBlock from '@theme-original/CodeBlock';
import type { Props } from '@theme/CodeBlock';
import ExecutableCode from '../../components/ExecutableCode';

// Extract language from either the `language` prop or `className` (e.g. "language-python")
function getLanguage(props: Props): string | undefined {
  if (props.language) return props.language;
  if (props.className) {
    const match = props.className.match(/language-(\w+)/);
    if (match) return match[1];
  }
  return undefined;
}

// Check if code block should be executable
function shouldBeExecutable(props: Props): boolean {
  const { metastring } = props;
  const language = getLanguage(props);

  // Only Python code can be executable
  if (language !== 'python') {
    return false;
  }
  
  // Check metastring for explicit control
  if (metastring) {
    if (metastring.includes('noexec') || metastring.includes('no-exec')) {
      return false;
    }
    if (metastring.includes('executable') || metastring.includes('exec')) {
      return true;
    }
  }
  
  // Default: make Python code executable
  // Change this to `false` if you want opt-in behavior instead
  return true;
}

// Extract notebook path from metastring if present
// e.g., ```python notebook="tutorials/hello-world.ipynb"
function extractNotebookPath(metastring?: string): string | undefined {
  if (!metastring) return undefined;
  
  const match = metastring.match(/notebook=["']([^"']+)["']/);
  return match ? match[1] : undefined;
}

// Extract title from metastring if present
// e.g., ```python title="Create a Bell state"
function extractTitle(metastring?: string): string | undefined {
  if (!metastring) return undefined;
  
  const match = metastring.match(/title=["']([^"']+)["']/);
  return match ? match[1] : undefined;
}

export default function CodeBlockWrapper(props: Props): JSX.Element {
  const { children, metastring } = props;
  const language = getLanguage(props);

  // Only wrap if it should be executable
  if (shouldBeExecutable(props)) {
    // Extract the code content
    const code = typeof children === 'string'
      ? children
      : String(children);

    return (
      <ExecutableCode
        language={language}
        notebookPath={extractNotebookPath(metastring)}
        title={extractTitle(metastring)}
        showLineNumbers={!metastring?.includes('noLineNumbers')}
      >
        {code}
      </ExecutableCode>
    );
  }
  
  // Fall back to original CodeBlock
  return <OriginalCodeBlock {...props} />;
}
