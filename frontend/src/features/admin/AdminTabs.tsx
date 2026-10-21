import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

const TABS = ['users', 'scenarios', 'settings', 'status', 'audit'] as const;

/** Administration sections (HANDOFF §11). Scenarios arrive in Phase 7, the rest in Phase 8. */
export function AdminTabs() {
  const { t } = useTranslation();
  return (
    <nav className="admin-tabs" aria-label={t('pages.admin.title')}>
      {TABS.map((k) => (
        <NavLink
          key={k}
          to={`/admin/${k}`}
          className={({ isActive }) => (isActive ? 'active' : undefined)}
        >
          {t(`admin.tabs.${k}`)}
        </NavLink>
      ))}
    </nav>
  );
}
