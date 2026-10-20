import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { homeFor } from '../../lib/nav';
import { stepsFor } from '../../lib/onboarding';
import { completeOnboarding } from '../../lib/session';
import { useAuth } from '../../stores/auth';
import { OnboardLayout } from './OnboardLayout';

const ICONS: Record<string, string> = {
  welcome: '◉',
  disclaimer: '⚠',
  live: '◉',
  capture: '●',
  analysis: '✎',
  reports: '☰',
  trainer: '▶',
  admin: '◈',
  controls: '?',
};

/** Walkthrough tailored to the role (SRS §3.1.2). Replayable from Settings (?replay=1). */
export function Onboarding() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const user = useAuth((s) => s.user)!;
  const steps = stepsFor(user.role);
  const [i, setI] = useState(0);
  const [busy, setBusy] = useState(false);
  const step = steps[i]!;
  const last = i === steps.length - 1;

  async function finish() {
    setBusy(true);
    try {
      if (!user.onboarding_completed) await completeOnboarding();
    } finally {
      navigate(params.get('replay') ? '/settings' : homeFor(user.role), { replace: true });
    }
  }

  return (
    <OnboardLayout wide>
      <div className="onboard-form" data-testid="onboarding">
        <div className="walk-step" aria-live="polite">
          <div className="ic" aria-hidden="true">
            {ICONS[step]}
          </div>
          <h2>{t(`onboarding.steps.${step}.title`)}</h2>
          <p>{t(`onboarding.steps.${step}.body`)}</p>
        </div>
        <div className="walk-dots" aria-label={`${i + 1} / ${steps.length}`}>
          {steps.map((s, n) => (
            <span key={s} className={n === i ? 'on' : undefined} />
          ))}
        </div>
        <div className="walk-actions">
          {i > 0 ? (
            <button type="button" className="pill-btn ghost" onClick={() => setI(i - 1)}>
              {t('common.back')}
            </button>
          ) : (
            <button
              type="button"
              className="pill-btn ghost"
              onClick={() => void finish()}
              disabled={busy}
            >
              {t('common.skip')}
            </button>
          )}
          <button
            type="button"
            className="pill-btn"
            onClick={() => (last ? void finish() : setI(i + 1))}
            disabled={busy}
          >
            {last ? t('common.finish') : t('common.next')}
          </button>
        </div>
      </div>
    </OnboardLayout>
  );
}
