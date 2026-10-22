import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { canAccess, homeFor } from '../../lib/nav';
import { nextStep } from '../../lib/session';
import { useAuth } from '../../stores/auth';

/** Signed in, password changed and onboarding done — otherwise send to the right step. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === 'unknown') return null;
  if (status !== 'authenticated' || !user) {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  }
  const step = nextStep(user);
  if (step === '/change-password' || step === '/language') return <Navigate to={step} replace />;
  return <>{children}</>;
}

/** Signed in, any onboarding state (used by the forced steps themselves). */
export function RequireSession({ children }: { children: ReactNode }) {
  const status = useAuth((s) => s.status);
  if (status === 'unknown') return null;
  if (status !== 'authenticated') return <Navigate to="/signin" replace />;
  return <>{children}</>;
}

export function RequireNav({ navKey, children }: { navKey: string; children: ReactNode }) {
  const user = useAuth((s) => s.user)!;
  return canAccess(user.role, navKey) ? <>{children}</> : <Forbidden />;
}

export function Forbidden() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user);
  return (
    <div className="empty-state" data-testid="forbidden">
      <div className="ic-circle" aria-hidden="true">
        ⛔
      </div>
      <h2>{t('forbidden.title')}</h2>
      <p>{t('forbidden.body')}</p>
      {user && (
        <Link className="btn" to={homeFor(user.role)} style={{ marginBlockStart: 18 }}>
          {t('notFound.home')}
        </Link>
      )}
    </div>
  );
}

export function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="empty-state">
      <div className="ic-circle" aria-hidden="true">
        ?
      </div>
      <h2>{t('notFound.title')}</h2>
      <p>{t('notFound.body')}</p>
      <Link className="btn" to="/" style={{ marginBlockStart: 18 }}>
        {t('notFound.home')}
      </Link>
    </div>
  );
}

export function RedirectHome() {
  const user = useAuth((s) => s.user);
  return <Navigate to={user ? nextStep(user) : '/signin'} replace />;
}
