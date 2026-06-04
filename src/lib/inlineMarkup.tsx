import React from 'react';

/**
 * Shared inline-markup helpers for component stubs.
 *
 * Upstream IBM Qiskit-documentation components receive STRING props (titles,
 * definitions, tooltips) that may carry inline markdown or HTML — `**bold**`,
 * `` `code` ``, `<em>…</em>` (and `<en>…</en>`, an upstream typo for `<em>`).
 *
 * Two rendering contexts need different handling:
 *   - JSX context (e.g. an AccordionItem <summary>): render the markup richly.
 *   - Attribute context (e.g. <abbr title=…> or CSS attr(data-tooltip)): the
 *     browser renders attributes as plain text, so markup would LEAK literally
 *     (`**bold**` shown verbatim). There we strip the markup to clean text.
 *
 * Centralizing both here keeps the patterns in one place so a stub never has to
 * choose between leaking markup and reinventing a parser.
 */

// Inline patterns IBM actually uses. Order matters only for the split below.
const INLINE_SPLIT = /(\*\*[^*]+\*\*|`[^`]+`|<em>[^<]+<\/em>)/g;

/** Normalize the upstream `<en>`/`</en>` typo to `<em>`/`</em>`. */
function normalizeEmTypo(text: string): string {
  return text.replace(/<\/?en>/g, (m) => (m === '<en>' ? '<em>' : '</em>'));
}

/**
 * Render inline markdown/HTML (`**bold**`, `` `code` ``, `<em>`) in a string
 * prop as JSX. Use in JSX contexts where rich rendering is possible.
 */
export function renderInlineMarkup(text: string): React.ReactNode {
  const parts = normalizeEmTypo(text).split(INLINE_SPLIT);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith('<em>') && part.endsWith('</em>')) return <em key={i}>{part.slice(4, -5)}</em>;
    return part;
  });
}

/**
 * Strip inline markdown/HTML from a string so it renders cleanly inside an HTML
 * attribute (title=, data-tooltip, aria-label, …) where markup cannot render and
 * would otherwise leak literally. `**bold**` → `bold`, `` `code` `` → `code`,
 * `<em>x</em>` → `x`.
 */
export function stripInlineMarkup(text: string): string {
  return normalizeEmTypo(text)
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/<em>([^<]+)<\/em>/g, '$1');
}
