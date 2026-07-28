import React from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../hooks/useTheme';
import { Sun, Moon, LogOut, User as UserIcon } from 'lucide-react';
import { StatusBadge, LifecycleCountdown } from '../shared/LifecycleCountdown';
import { selectActiveSession } from '../../runtime/selectors';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      data-testid="theme-toggle"
      onClick={toggleTheme}
      className="p-1.5 rounded-md hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus-ring"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
}

export function StatusBar() {
  const { state } = useRuntime();
  const { user, authState, signOutUser } = useAuth();
  const activeSession = selectActiveSession(state);

  return (
    <header className="h-[36px] flex-none flex items-center justify-between px-4 border-b border-border-subtle bg-surface-1 select-none">
      <div className="flex items-center gap-4">
        <h1 className="text-[14px] font-semibold tracking-tight text-text-primary">
          Ephemeral Engine
        </h1>
        
        <div className="flex items-center gap-2 border-l border-border-subtle pl-4" aria-live="polite">
          <div data-testid="status-bar-connection">
            <StatusBadge 
              tier={state.connectionState === 'connected' ? 'healthy' : state.connectionState === 'offline' ? 'offline' : 'retrying'} 
              text={state.connectionState.replace('_', ' ')}
            />
          </div>
          <div data-testid="status-bar-backend">
            <StatusBadge 
              tier={state.backendStatus === 'operational' ? 'healthy' : 'error'} 
              text={`backend: ${state.backendStatus}`}
            />
          </div>
          {authState !== 'authenticated' && (
            <div data-testid="status-bar-auth">
              <StatusBadge tier="error" text={`auth: ${authState}`} />
            </div>
          )}
          {state.modelStatus !== 'available' && (
            <div data-testid="status-bar-model">
              <StatusBadge 
                tier={state.modelStatus === 'rate_limited' ? 'expiring_soon' : 'error'} 
                text={`model: ${state.modelStatus}${state.modelRetryCountdown ? ` (retry in ${state.modelRetryCountdown}s)` : ''}`}
              />
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {activeSession && activeSession.tier !== 'burned' && (
          <div className="flex items-center gap-2 border-r border-border-subtle pr-3">
            <span className="text-xs text-text-secondary">active session:</span>
            <LifecycleCountdown expiresAt={activeSession.expiresAt} sessionId={activeSession.id} />
          </div>
        )}

        {user && (
          <div className="flex items-center gap-2 border-r border-border-subtle pr-3 text-xs text-text-secondary">
            {user.photoURL ? (
              <img src={user.photoURL} alt="" className="w-4 h-4 rounded-full" />
            ) : (
              <UserIcon className="w-3.5 h-3.5 text-text-tertiary" />
            )}
            <span data-testid="user-display-name" className="font-medium text-text-primary">
              {user.displayName || user.email}
            </span>
            <button
              data-testid="signout-button"
              onClick={() => signOutUser()}
              className="ml-1 p-1 hover:bg-surface-2 rounded text-text-tertiary hover:text-status-error transition-colors"
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <ThemeToggle />
      </div>
    </header>
  );
}
