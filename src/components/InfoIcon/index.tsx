import './styles.css';

interface InfoIconProps {
  tooltip: string;
  position?: 'above' | 'below';
}

export default function InfoIcon({ tooltip, position = 'above' }: InfoIconProps) {
  return (
    <span className={`dq-info-icon dq-info-icon--${position}`} data-tooltip={tooltip}>
      &#9432;{/* ⓘ character */}
    </span>
  );
}
