import { useTranslation } from 'react-i18next';
import { Link, Outlet, useMatches } from 'react-router-dom';
import { CamIndicator, ConnIndicator } from '../../components/Indicators';
import { LangSwitch } from '../../components/LangSwitch';
import { Sidebar } from '../../components/Sidebar';
import { useIdleTimer } from '../../lib/idle-timer';
import { useOnline } from '../../lib/online';
import { useUi } from '../../stores/ui';

export type RouteHandle = { help?: string; camera?: boolean };

function useHandle(): RouteHandle {
  const matches = useMatches();
  return matches.reduce<RouteHandle>((acc, m) => ({ ...acc, ...(m.handle as RouteHandle) }), {});
}

/** Every signed-in screen: sidebar + language switch, help, connection and camera
 * indicators (SRS §3.1.2). */
export function AppShell() {
  const { t } = useTranslation();
  const handle = useHandle();
  const online = useOnline();
  const setMobileNav = useUi((s) => s.setMobileNav);
  const { secondsLeft, stayActive } = useIdleTimer();
  const helpTopic = handle.help ?? 'getting-started';

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        <div className="app">
          <header className="shell-header">
            <button
              type="button"
              className="icon-btn menu-btn"
              onClick={() => setMobileNav(true)}
              aria-label={t('shell.openMenu')}
              aria-controls="sidebar"
            >
              ☰
            </button>
            <div className="spacer" />
            {handle.camera && <CamIndicator />}
            <ConnIndicator />
            <LangSwitch />
            <Link
              to={`/help/${helpTopic}`}
              className="icon-btn"
              aria-label={t('shell.help')}
              title={t('shell.help')}
              data-testid="help-button"
            >
              ?
            </Link>
          </header>
          {!online && (
            <div className="banner bad" role="alert">
              {t('shell.offlineBanner')}
            </div>
          )}
          {secondsLeft !== null && (
            <div className="banner warn" role="alert">
              <span>{t('shell.idleWarning', { seconds: secondsLeft })}</span>
              <button type="button" className="btn" onClick={stayActive}>
                {t('shell.staySignedIn')}
              </button>
            </div>
          )}
          <Outlet />
        </div>
      </main>
    </div>
  );
}
