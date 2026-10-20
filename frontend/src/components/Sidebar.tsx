import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation } from 'react-router-dom';
import { GROUPS, initials, navFor } from '../lib/nav';
import { signOut } from '../lib/session';
import { useAuth } from '../stores/auth';
import { useUi } from '../stores/ui';
import { BrandMark } from './BrandMark';

export function Sidebar() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const { sidebarCollapsed, toggleSidebar, mobileNavOpen, setMobileNav } = useUi();
  const location = useLocation();
  const items = navFor(user.role);

  useEffect(() => setMobileNav(false), [location.pathname, setMobileNav]);

  const cls = ['sidebar', sidebarCollapsed && 'collapsed', mobileNavOpen && 'open']
    .filter(Boolean)
    .join(' ');

  return (
    <>
      <div className={`scrim${mobileNavOpen ? ' show' : ''}`} onClick={() => setMobileNav(false)} />
      <aside className={cls} id="sidebar" aria-label={t('app.name')}>
        <div className="side-head">
          <BrandMark />
          <div className="brand-text">
            <h1>IGNIS VISION</h1>
            <p>{t('app.org')}</p>
          </div>
          <button
            type="button"
            className="side-toggle"
            onClick={toggleSidebar}
            aria-label={sidebarCollapsed ? t('shell.expand') : t('shell.collapse')}
            aria-expanded={!sidebarCollapsed}
          >
            <span className="flip">{sidebarCollapsed ? '⇥' : '⇤'}</span>
          </button>
        </div>
        <nav className="side-nav" data-testid="side-nav">
          {GROUPS.map((group) => {
            const groupItems = items.filter((i) => i.group === group);
            if (!groupItems.length) return null;
            return (
              <div key={group} role="group" aria-label={t(`nav.groups.${group}`)}>
                <div className="side-group-label">{t(`nav.groups.${group}`)}</div>
                {groupItems.map((item) => (
                  <NavLink
                    key={item.key}
                    to={item.path}
                    end={item.path === '/trainer'}
                    className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                    title={sidebarCollapsed ? t(`nav.${item.key}`) : undefined}
                    data-nav={item.key}
                  >
                    <span className="ic" aria-hidden="true">
                      {item.icon}
                    </span>
                    <span className="lbl">{t(`nav.${item.key}`)}</span>
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="side-foot">
          <div className="avatar" aria-hidden="true">
            {initials(user.full_name)}
          </div>
          <div className="who">
            <div className="name">{user.full_name}</div>
            <div className="role">{t(`roles.${user.role}`)}</div>
          </div>
          <button
            type="button"
            className="signout"
            onClick={() => void signOut()}
            title={t('common.signOut')}
          >
            <span aria-hidden="true">⏻</span>{' '}
            <span className="signout-label">{t('common.signOut')}</span>
          </button>
        </div>
      </aside>
    </>
  );
}
