import './styles.css';
import { stripInlineMarkup } from '@site/src/lib/inlineMarkup';

interface InfoIconProps {
  tooltip: string;
  position?: 'above' | 'below';
}

export default function InfoIcon({ tooltip, position = 'above' }: InfoIconProps) {
  // The tooltip is rendered via CSS `content: attr(data-tooltip)`, which shows
  // plain text — strip any inline markdown/HTML so it never leaks literally.
  const text = stripInlineMarkup(tooltip);
  // A focusable <button> with the tooltip text as its accessible name, so
  // keyboard + screen-reader users can reach the info that the CSS :hover/:focus
  // tooltip shows. type="button" prevents form submission; the ⓘ glyph is
  // aria-hidden because the button's aria-label carries the meaning.
  return (
    <button
      type="button"
      className={`dq-info-icon dq-info-icon--${position}`}
      data-tooltip={text}
      aria-label={text}
    >
      <span aria-hidden="true">&#9432;{/* ⓘ character */}</span>
    </button>
  );
}
