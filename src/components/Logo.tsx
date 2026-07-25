import { LOGO_PATHS, LOGO_VIEWBOX } from './logoPaths';
import './Logo.css';

const ASPECT = 220 / 325;

interface LogoProps {
  height?: number;
  glow?: boolean;
  className?: string;
}

export function Logo({ height = 56, glow = false, className = '' }: LogoProps) {
  return (
    <svg
      className={`iv-logo${glow ? ' iv-logo-glow' : ''} ${className}`}
      viewBox={LOGO_VIEWBOX}
      style={{ height, width: height * ASPECT }}
      aria-label="Ignis Vision"
      role="img"
    >
      <defs>
        <linearGradient id="iv-flame-grad" x1="20%" y1="0%" x2="80%" y2="100%">
          <stop offset="0%" stopColor="var(--thermal)" />
          <stop offset="100%" stopColor="#c73a17" />
        </linearGradient>
      </defs>
      <path d={LOGO_PATHS.flame} fill="url(#iv-flame-grad)" />
      <path d={LOGO_PATHS.flag} fill="#1b4332" />
      <path d={LOGO_PATHS.crescent} fill="#ede6dc" />
      <path d={LOGO_PATHS.star} fill="#ede6dc" />
      <path d={LOGO_PATHS.monogram} fill="#ede6dc" />
    </svg>
  );
}
