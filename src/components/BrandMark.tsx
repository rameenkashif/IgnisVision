import './BrandMark.css';

interface BrandMarkProps {
  size?: number;
}

export function BrandMark({ size = 40 }: BrandMarkProps) {
  return (
    <div className="brand-mark" style={{ width: size, height: size, fontSize: size * 0.4 }}>
      IV
    </div>
  );
}
