import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './Splash.css';

const FALLBACK_MS = 8000;

export function Splash() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    function goToLogin() {
      if (doneRef.current) return;
      doneRef.current = true;
      navigate('/login');
    }

    const video = videoRef.current;
    video?.addEventListener('ended', goToLogin);

    // Safety fallback in case the video fails to load or play.
    const fallback = window.setTimeout(goToLogin, FALLBACK_MS);

    return () => {
      video?.removeEventListener('ended', goToLogin);
      clearTimeout(fallback);
    };
  }, [navigate]);

  return (
    <div className="splash">
      <video ref={videoRef} className="splash-video" autoPlay muted playsInline>
        <source src="/ignis-vision-splash.mp4" type="video/mp4" />
      </video>
      <button className="splash-skip" onClick={() => navigate('/login')}>
        Skip ›
      </button>
    </div>
  );
}
