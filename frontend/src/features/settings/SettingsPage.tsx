import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { LangSwitch } from '../../components/LangSwitch';
import { PageHeader } from '../../components/PageHeader';
import { signOut } from '../../lib/session';
import { useAuth } from '../../stores/auth';
import { usePrefs } from '../../stores/prefs';

function Toggle({
  id,
  checked,
  onChange,
}: {
  id: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      className={`chip ${checked ? 'ok' : ''}`}
      onClick={() => onChange(!checked)}
      style={{ cursor: 'pointer', minWidth: 56, justifyContent: 'center' }}
    >
      {checked ? t('common.on') : t('common.off')}
    </button>
  );
}

/** Per-user preferences. Admin-only system settings live under Administration (Phase 8). */
export function SettingsPage() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const prefs = usePrefs();

  const row = (label: string, control: React.ReactNode, hint?: string, id?: string) => (
    <div className="settings-row">
      <div>
        <label htmlFor={id}>{label}</label>
        {hint && <div className="hint">{hint}</div>}
      </div>
      {control}
    </div>
  );

  return (
    <>
      <PageHeader page="settings" />
      <div className="panel" style={{ marginBlockEnd: 14 }}>
        <div className="panel-body">
          {row(t('settings.language'), <LangSwitch />)}
          {row(
            t('settings.voice'),
            <Toggle
              id="voice"
              checked={prefs.voiceAlerts}
              onChange={(v) => prefs.set({ voiceAlerts: v })}
            />,
            t('settings.voiceHint'),
            'voice',
          )}
          {row(
            t('settings.sound'),
            <Toggle
              id="sound"
              checked={prefs.soundAlerts}
              onChange={(v) => prefs.set({ soundAlerts: v })}
            />,
            undefined,
            'sound',
          )}
          {row(
            t('settings.onboarding'),
            <Link className="btn" to="/onboarding?replay=1">
              {t('settings.replay')}
            </Link>,
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-head">
          <h2>{t('settings.account')}</h2>
        </div>
        <div className="panel-body">
          {row(
            t('settings.signedInAs', { name: user.full_name, role: t(`roles.${user.role}`) }),
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Link className="btn" to="/change-password">
                {t('settings.changePassword')}
              </Link>
              <button type="button" className="btn" onClick={() => void signOut()}>
                {t('common.signOut')}
              </button>
            </div>,
          )}
        </div>
      </div>
    </>
  );
}
