import React, { useContext, useState } from 'react';
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Flame,
  LayoutDashboard,
  MessageSquare,
  Orbit,
  Plus,
  Sliders,
} from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { TelemetryContext } from '../App';

export default function Navigation({
  connectionStatus,
  onRequestCreateSession,
  onRequestBurnSession,
}) {
  const { sessionState, setSessionState } = useContext(TelemetryContext) || {};
  const [isContextsOpen, setIsContextsOpen] = useState(true);
  const navigate = useNavigate();

  const sessions = sessionState?.sessions || [];
  const activeSessionId = sessionState?.activeSessionId || '';

  const handleSelectSession = (sessionId) => {
    if (setSessionState) {
      setSessionState((previous) => ({
        ...previous,
        activeSessionId: sessionId,
      }));
    }
    navigate('/chat');
  };

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
          <p className="nav-section-label">Main Navigation</p>
          
          <NavLink
            end
            to="/"
            className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}
          >
            <LayoutDashboard size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>Overview</span>
          </NavLink>

          <div className="nav-section-wrap">
            <NavLink
              to="/chat"
              className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}
            >
              <MessageSquare size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>Workspace</span>
            </NavLink>

            {/* Collapsible Sub-Menu for ISOLATED CONTEXTS below Workspace */}
            <div className="sub-menu-container">
              <button
                type="button"
                className="sub-menu-toggle"
                onClick={() => setIsContextsOpen((prev) => !prev)}
                aria-expanded={isContextsOpen}
              >
                <div className="sub-menu-title">
                  {isContextsOpen ? (
                    <ChevronDown size={14} className="chevron-icon" />
                  ) : (
                    <ChevronRight size={14} className="chevron-icon" />
                  )}
                  <span>ISOLATED CONTEXTS</span>
                </div>
                <span className="sub-menu-badge">{sessions.length}</span>
              </button>

              {isContextsOpen && (
                <div className="sub-menu-content">
                  <button
                    type="button"
                    className="sub-menu-action-btn"
                    onClick={onRequestCreateSession}
                  >
                    <Plus size={14} />
                    <span>New Context</span>
                  </button>

                  <div className="context-item-list">
                    {sessions.map((sessionId) => {
                      const isActive = sessionId === activeSessionId;
                      return (
                        <div
                          key={sessionId}
                          className={`context-sub-item ${isActive ? 'is-active' : ''}`}
                          onClick={() => handleSelectSession(sessionId)}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSelectSession(sessionId);
                          }}
                        >
                          <span className={`status-dot ${isActive ? 'active-dot' : ''}`} />
                          <span className="context-item-name" title={sessionId}>
                            {sessionId}
                          </span>
                          {isActive && (
                            <button
                              type="button"
                              className="context-burn-btn"
                              title="Burn session context"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (onRequestBurnSession) onRequestBurnSession(sessionId);
                              }}
                            >
                              <Flame size={13} />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}
          >
            <Sliders size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>Settings</span>
          </NavLink>
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
        <NavLink
          end
          to="/"
          className={({ isActive }) => `mobile-nav-link ${isActive ? 'is-active' : ''}`}
        >
          <LayoutDashboard size={19} strokeWidth={1.8} aria-hidden="true" />
          <span>Overview</span>
        </NavLink>
        <NavLink
          to="/chat"
          className={({ isActive }) => `mobile-nav-link ${isActive ? 'is-active' : ''}`}
        >
          <MessageSquare size={19} strokeWidth={1.8} aria-hidden="true" />
          <span>Workspace</span>
        </NavLink>
        <NavLink
          to="/settings"
          className={({ isActive }) => `mobile-nav-link ${isActive ? 'is-active' : ''}`}
        >
          <Sliders size={19} strokeWidth={1.8} aria-hidden="true" />
          <span>Settings</span>
        </NavLink>
      </nav>
    </>
  );
}
