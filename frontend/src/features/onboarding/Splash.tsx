import { useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { nextStep } from '../../lib/session';
import { useAuth } from '../../stores/auth';

const SEEN_KEY = 'iv.splashSeen';
const MAX_MS = 8000;

function seen(): boolean {
  try {
    return sessionStorage.getItem(SEEN_KEY) === '1';
  } catch {
    return false;
  }
}

/** Plays once per browser session, then hands off to sign-in or the user's next step. */
export function Splash() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { status, user } = useAuth();
  const done = useRef(false);
  const reduceMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const finish = useCallback(() => {
    if (done.current) return;
    done.current = true;
    try {
      sessionStorage.setItem(SEEN_KEY, '1');
    } catch {
      /* ignore */
    }
    navigate(user ? nextStep(user) : '/signin', { replace: true });
  }, [navigate, user]);

  useEffect(() => {
    if (status === 'unknown') return;
    if (seen()) return finish();
    const timer = window.setTimeout(finish, reduceMotion ? 600 : MAX_MS);
    return () => window.clearTimeout(timer);
  }, [status, finish, reduceMotion]);

  if (seen()) return null;
  return (
    <div className="onboard-screen" data-testid="splash">
      {!reduceMotion && (
        <video src="/splash.mp4" autoPlay muted playsInline onEnded={finish} onError={finish} />
      )}
      <button type="button" className="splash-skip" onClick={finish}>
        {t('splash.skip')} ›
      </button>
    </div>
  );
}
