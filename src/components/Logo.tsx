import logoSrc from '../assets/ignis-vision-logo.png';
import './Logo.css';

const ASPECT = 696 / 967;

interface LogoProps {
  height?: number;
  glow?: boolean;
  className?: string;
}

export function Logo({ height = 56, glow = false, className = '' }: LogoProps) {
  return (
    <img
      src={logoSrc}
      alt="Ignis Vision"
      className={`iv-logo${glow ? ' iv-logo-glow' : ''} ${className}`}
      style={{ height, width: height * ASPECT }}
    />
  );
}
