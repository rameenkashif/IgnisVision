import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate } from 'react-router-dom';
import { BrandMark } from '../../components/BrandMark';
import { ApiError } from '../../api/errors';
import { errorMessage } from '../../i18n';
import { nextStep, signIn } from '../../lib/session';
import { useAuth } from '../../stores/auth';
import { OnboardLayout } from './OnboardLayout';

export function SignIn() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { status, user, signedOutReason, clearReason } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === 'authenticated' && user && !busy) return <Navigate to={nextStep(user)} replace />;

  const notice =
    signedOutReason && i18n.exists(`signedOut.${signedOutReason}`)
      ? t(`signedOut.${signedOutReason}`)
      : signedOutReason
        ? errorMessage(signedOutReason)
        : null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    clearReason();
    try {
      const u = await signIn(username.trim(), password);
      navigate(nextStep(u), { replace: true });
    } catch (err) {
      setError(errorMessage(err instanceof ApiError ? err.code : undefined));
      setBusy(false);
    }
  }

  return (
    <OnboardLayout>
      <div className="onboard-brand">
        <BrandMark large />
        <div>
          <h1>{t('signin.title')}</h1>
          <p>{t('app.tagline')}</p>
        </div>
      </div>
      <form className="onboard-form" onSubmit={onSubmit} noValidate>
        {notice && !error && (
          <p className="error-text" role="status" style={{ color: 'var(--caution)' }}>
            {notice}
          </p>
        )}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <div className="fg">
          <label htmlFor="username">{t('signin.username')}</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            dir="ltr"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div className="fg">
          <label htmlFor="password">{t('signin.password')}</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            dir="ltr"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button className="pill-btn" type="submit" disabled={busy || !username || !password}>
          {busy ? t('signin.submitting') : t('signin.submit')}
        </button>
      </form>
      <div className="onboard-foot-link">{t('signin.foot')}</div>
    </OnboardLayout>
  );
}
