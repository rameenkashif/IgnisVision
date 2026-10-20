import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../stores/auth';
import { useUi } from '../stores/ui';
import { signOut } from './session';

const HEARTBEAT_EVERY_MS = 60_000;
const WARN_BEFORE_S = 60;
const EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const;

/**
 * Client half of the 30-minute idle rule (SRS §5.3.1; server half in auth_sessions.py).
 * Interaction → heartbeat (throttled). keepAlive (live/capture of an active incident) →
 * heartbeat regardless. Idle past the limit and not in an active incident → sign out.
 * Returns seconds left when inside the warning window, else null.
 */
export function useIdleTimer(): { secondsLeft: number | null; stayActive: () => void } {
  const idleTimeoutS = useAuth((s) => s.idleTimeoutS);
  const lastInteraction = useRef(Date.now());
  const lastBeat = useRef(0);
  const inActiveIncident = useRef(false);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const beat = useCallback(async () => {
    lastBeat.current = Date.now();
    const { data } = await api.POST('/api/v1/auth/heartbeat').catch(() => ({ data: undefined }));
    if (data) inActiveIncident.current = data.in_active_incident;
  }, []);

  const stayActive = useCallback(() => {
    lastInteraction.current = Date.now();
    setSecondsLeft(null);
    void beat();
  }, [beat]);

  useEffect(() => {
    const onActivity = () => {
      lastInteraction.current = Date.now();
    };
    EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
    void beat();

    const tick = window.setInterval(() => {
      const now = Date.now();
      const keepAlive = useUi.getState().keepAlive;
      const interactedSinceBeat = lastInteraction.current > lastBeat.current;
      if (now - lastBeat.current >= HEARTBEAT_EVERY_MS && (interactedSinceBeat || keepAlive)) {
        void beat();
      }
      if (keepAlive || inActiveIncident.current) {
        setSecondsLeft(null);
        return;
      }
      const left = Math.round(idleTimeoutS - (now - lastInteraction.current) / 1000);
      if (left <= 0) {
        window.clearInterval(tick);
        void signOut('idle_timeout');
      } else {
        setSecondsLeft(left <= WARN_BEFORE_S ? left : null);
      }
    }, 1000);

    return () => {
      EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
      window.clearInterval(tick);
    };
  }, [beat, idleTimeoutS]);

  return { secondsLeft, stayActive };
}
