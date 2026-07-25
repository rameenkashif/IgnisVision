import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useIncident } from '../state/IncidentContext';
import '../pages/dashboard/shared.css';
import './AppShell.css';

const NAV_GROUPS = [
  {
    label: 'Operations',
    items: [
      { to: 'live', icon: '◉', label: 'Live monitoring', badge: true },
      { to: 'demo', icon: '●', label: 'Camera demo' },
      { to: 'reports', icon: '☰', label: 'Incident reports' },
      { to: 'annotate', icon: '✎', label: 'Image analysis' },
      { to: 'team', icon: '☉', label: 'Team deployment' },
    ],
  },
  {
    label: 'Training',
    items: [{ to: 'sim', icon: '▶', label: 'Training simulator' }],
  },
  {
    label: 'System',
    items: [{ to: 'settings', icon: '⚙', label: 'Settings' }],
  },
];

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const { incident } = useIncident();

  return (
    <div className="shell">
      <div className={'sidebar' + (collapsed ? ' collapsed' : '')}>
        <div className="side-head">
          <Logo height={32} />
          <div className="brand-text">
            <h1>IGNIS VISION</h1>
            <p>AI fire intelligence</p>
          </div>
          <button className="side-toggle" onClick={() => setCollapsed((c) => !c)}>
            {collapsed ? '⇁' : '⇀'}
          </button>
        </div>

        <nav className="side-nav">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="side-group-label">{group.label}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
                >
                  <span className="ic">{item.icon}</span>
                  <span className="lbl">{item.label}</span>
                  {item.badge && incident && <span className="badge">1</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="side-foot">
          <div className="avatar">RI</div>
          <div className="who">
            <div className="name">Rimsha Irfan</div>
            <div className="role">Incident Commander</div>
          </div>
        </div>
      </div>

      <div className="main">
        <div className="app">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
