import React from 'react';
import { Activity, LayoutDashboard, MessageSquare, Orbit } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/chat', label: 'Workspace', icon: MessageSquare, end: false },
];

function NavigationLink({ item, mobile = false }) {
  const Icon = item.icon;
  return (
    <NavLink
      end={item.end}
      to={item.to}
      className={({ isActive }) => [
        mobile ? 'mobile-nav-link' : 'nav-link',
        isActive ? 'is-active' : '',
      ].filter(Boolean).join(' ')}
    >
      <Icon size={mobile ? 19 : 18} strokeWidth={1.8} aria-hidden="true" />
      <span>{item.label}</span>
    </NavLink>
  );
}

export default function Navigation({ connectionStatus }) {
  return (
    <>
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Orbit size={22} strokeWidth={1.8} />
          </span>
          <span>
            <strong>SC-EVM</strong>
            <small>Control plane</small>
          </span>
        </div>

        <nav className="sidebar-nav">
          <p className="nav-section-label">Workspace</p>
          {navItems.map((item) => <NavigationLink item={item} key={item.to} />)}
        </nav>

        <div className="sidebar-footer">
          <div className={`connection-card connection-${connectionStatus}`}>
            <Activity size={16} aria-hidden="true" />
            <span>
              <strong>
                {connectionStatus === 'online'
                  ? 'Backend connected'
                  : connectionStatus === 'connecting'
                    ? 'Connecting'
                    : 'Backend offline'}
              </strong>
              <small>Local control channel</small>
            </span>
            <span className="connection-dot" aria-hidden="true" />
          </div>
          <p>Ephemeral by design</p>
        </div>
      </aside>

      <nav className="mobile-nav" aria-label="Primary navigation">
        {navItems.map((item) => <NavigationLink item={item} key={item.to} mobile />)}
      </nav>
    </>
  );
}
