import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { api, unwrap } from '../../api/client';
import { ApiError } from '../../api/errors';
import { errorMessage } from '../../i18n';
import { nextStep } from '../../lib/session';
import { useAuth } from '../../stores/auth';
import { OnboardLayout } from './OnboardLayout';

export function ChangePassword() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuth((s) => s.user)!;
  const setUser = useAuth((s) => s.setUser);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (next !== confirm) return setError(t('changePassword.mismatch'));
    setBusy(true);
    setError(null);
    try {
      await unwrap(
        api.POST('/api/v1/auth/change-password', {
          body: { current_password: current, new_password: next },
        }),
      );
      const updated = { ...user, must_change_password: false };
      setUser(updated);
      navigate(nextStep(updated), { replace: true });
    } catch (err) {
      setError(errorMessage(err instanceof ApiError ? err.code : undefined));
      setBusy(false);
    }
  }

  const field = (
    id: string,
    label: string,
    value: string,
    set: (v: string) => void,
    ac: string,
  ) => (
    <div className="fg">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="password"
        dir="ltr"
        autoComplete={ac}
        value={value}
        onChange={(e) => set(e.target.value)}
      />
    </div>
  );

  return (
    <OnboardLayout>
      <div className="onboard-brand">
        <div>
          <h1>{t('changePassword.title')}</h1>
          <p>{t('changePassword.rules')}</p>
        </div>
      </div>
      <form className="onboard-form" onSubmit={onSubmit} noValidate>
        {user.must_change_password && (
          <p style={{ fontSize: 12.5, color: 'rgba(255,255,255,.7)', marginBlockEnd: 14 }}>
            {t('changePassword.subtitle')}
          </p>
        )}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        {field('current', t('changePassword.current'), current, setCurrent, 'current-password')}
        {field('new', t('changePassword.new'), next, setNext, 'new-password')}
        {field('confirm', t('changePassword.confirm'), confirm, setConfirm, 'new-password')}
        <button className="pill-btn" type="submit" disabled={busy || !current || !next || !confirm}>
          {t('changePassword.submit')}
        </button>
      </form>
    </OnboardLayout>
  );
}
