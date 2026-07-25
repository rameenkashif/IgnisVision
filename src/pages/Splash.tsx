import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LOGO_PATHS, LOGO_VIEWBOX } from '../components/logoPaths';
import './Splash.css';

const PHASES = [
  { at: 0, label: 'INITIALIZING_CORE' },
  { at: 350, label: 'TRACING_VECTOR_PATHS' },
  { at: 1450, label: 'RENDERING_ASSETS' },
  { at: 1950, label: 'SYNCING_SENSORS' },
  { at: 2300, label: 'READY_FOR_COMMAND.' },
];

const FILLING_AT = 1450;
const READY_AT = 2300;
const SETTLE_AT = 2650;
const NAVIGATE_AT = 4600;

const PARTICLES = Array.from({ length: 22 }, (_, i) => {
  const seed = i * 137.51;
  return {
    id: i,
    x: (seed * 7) % 100,
    y: (seed * 13) % 100,
    delay: (i * 0.37) % 3,
    size: i % 3 === 0 ? 2 : 1,
    warm: i % 4 === 0,
  };
});

export function Splash() {
  const navigate = useNavigate();
  const [label, setLabel] = useState(PHASES[0].label);
  const [pct, setPct] = useState(0);
  const [filling, setFilling] = useState(false);
  const [ready, setReady] = useState(false);
  const [settled, setSettled] = useState(false);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const timers = PHASES.map((p) => window.setTimeout(() => setLabel(p.label), p.at));
    timers.push(window.setTimeout(() => setFilling(true), FILLING_AT));
    timers.push(window.setTimeout(() => setReady(true), READY_AT));
    timers.push(window.setTimeout(() => setSettled(true), SETTLE_AT));
    const navTimer = window.setTimeout(() => navigate('/login'), NAVIGATE_AT);

    const start = performance.now();
    function tick(now: number) {
      const elapsed = now - start;
      if (elapsed < READY_AT) {
        setPct(Math.min(99, Math.round((elapsed / READY_AT) * 100)));
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setPct(100);
      }
    }
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(navTimer);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [navigate]);

  const stageClass =
    'splash' +
    (filling ? ' is-filling' : '') +
    (ready ? ' is-ready' : '') +
    (settled ? ' is-settled' : '');

  return (
    <div className={stageClass}>
      <div className="splash-particles">
        {PARTICLES.map((p) => (
          <span
            key={p.id}
            className={'particle' + (p.warm ? ' particle-warm' : '')}
            style={{
              left: p.x + '%',
              top: p.y + '%',
              width: p.size,
              height: p.size,
              animationDelay: p.delay + 's',
            }}
          />
        ))}
      </div>

      <div className="splash-stage">
        <div className="splash-logo-wrap">
          <div className="splash-flare" />
          <svg className="splash-logo" viewBox={LOGO_VIEWBOX}>
            <defs>
              <linearGradient id="splash-flame-grad" x1="20%" y1="0%" x2="80%" y2="100%">
                <stop offset="0%" stopColor="var(--thermal)" />
                <stop offset="100%" stopColor="#c73a17" />
              </linearGradient>
            </defs>
            <g className="logo-fill">
              <path d={LOGO_PATHS.flame} fill="url(#splash-flame-grad)" />
              <path d={LOGO_PATHS.flag} fill="#1b4332" />
              <path d={LOGO_PATHS.crescent} fill="#ede6dc" />
              <path d={LOGO_PATHS.star} fill="#ede6dc" />
              <path d={LOGO_PATHS.monogram} fill="#ede6dc" />
            </g>
            <g className="logo-trace" fill="none">
              <path className="lt lt-flame" d={LOGO_PATHS.flame} pathLength={1} />
              <path className="lt lt-flag" d={LOGO_PATHS.flag} pathLength={1} />
              <path className="lt lt-crescent" d={LOGO_PATHS.crescent} pathLength={1} />
              <path className="lt lt-star" d={LOGO_PATHS.star} pathLength={1} />
              <path className="lt lt-mono" d={LOGO_PATHS.monogram} pathLength={1} />
            </g>
          </svg>
        </div>

        <div className="splash-wordmark">
          <h1>
            <span className="w-ignis">IGNIS</span> <span className="w-vision">VISION</span>
          </h1>
          <p className="splash-tagline">DETECT. ALERT. SAVE.</p>
        </div>
      </div>

      <div className="splash-hud">
        <div className="hud-row">
          <div className="hud-left">
            <span className={'hud-label' + (ready ? ' hud-label-ready' : '')}>{label}</span>
            <span className="hud-cursor" />
          </div>
          <span className="hud-sector">SECTOR_04_ACTIVE</span>
        </div>
        <div className="hud-row hud-row-sub">
          <span className="hud-latency">CORE_LATENCY: 12ms</span>
          <span className={'hud-pct' + (pct >= 100 ? ' done' : '')}>{pct}%</span>
        </div>
        <div className="hud-progress">
          <div className="hud-progress-fill" style={{ width: pct + '%' }} />
        </div>
      </div>

      <button className="splash-skip" onClick={() => navigate('/login')}>
        Skip
      </button>
    </div>
  );
}
