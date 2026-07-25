import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BrandMark } from '../components/BrandMark';
import './Splash.css';

const AUTO_ADVANCE_MS = 2600;

export function Splash() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => navigate('/login'), AUTO_ADVANCE_MS);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="splash">
      <div className="splash-mark">
        <BrandMark size={72} />
      </div>
      <h1 className="splash-title">
        <span>IGNIS</span> <span>VISION</span>
      </h1>
      <p className="splash-tagline">AI FIRE INTELLIGENCE</p>
      <div className="splash-bar">
        <div className="splash-bar-fill" />
      </div>
      <button className="splash-skip" onClick={() => navigate('/login')}>
        Skip
      </button>
    </div>
  );
}
