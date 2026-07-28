import React from 'react';
import { useAuth } from '../context/AuthContext';
import { LogIn, AlertTriangle, ShieldAlert, Cpu } from 'lucide-react';

export const Login: React.FC = () => {
  const { authState, error, signInWithGoogle, configValid } = useAuth();

  const isAuthenticating = authState === 'authenticating';

  return (
    <div className="min-h-screen bg-bg-dark flex items-center justify-center p-4 text-text-primary">
      <div className="w-full max-w-md bg-card-bg border border-border-color rounded-xl p-8 shadow-2xl space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-accent-blue/10 text-accent-blue mb-2">
            <Cpu className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Ephemeral Engine</h1>
          <p className="text-sm text-text-tertiary">
            Phase 2 Authentication Gateway & Control Plane
          </p>
        </div>

        {!configValid && (
          <div
            data-testid="config-error-banner"
            className="p-4 rounded-lg bg-status-error/10 border border-status-error/30 text-status-error text-xs space-y-1"
          >
            <div className="flex items-center space-x-2 font-semibold">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Configuration Error</span>
            </div>
            <p>{error || 'Firebase client configuration is missing or invalid.'}</p>
          </div>
        )}

        {error && configValid && error.includes('403') && (
          <div
            data-testid="forbidden-error-banner"
            className="p-4 rounded-lg bg-status-warning/10 border border-status-warning/30 text-status-warning text-xs space-y-1"
          >
            <div className="flex items-center space-x-2 font-semibold">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>Access Denied (403)</span>
            </div>
            <p>{error}</p>
          </div>
        )}

        {error && configValid && !error.includes('403') && (
          <div
            data-testid="general-error-banner"
            className="p-4 rounded-lg bg-status-error/10 border border-status-error/30 text-status-error text-xs space-y-1"
          >
            <div className="flex items-center space-x-2 font-semibold">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Authentication Error</span>
            </div>
            <p>{error}</p>
          </div>
        )}

        <div className="space-y-4 pt-2">
          <button
            data-testid="google-signin-btn"
            onClick={signInWithGoogle}
            disabled={!configValid || isAuthenticating}
            className="w-full flex items-center justify-center space-x-3 py-3 px-4 rounded-lg bg-accent-blue hover:bg-accent-blue/90 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-white transition-all shadow-md"
          >
            <LogIn className="w-5 h-5" />
            <span>{isAuthenticating ? 'Connecting to Google...' : 'Sign in with Google'}</span>
          </button>

          <div className="text-center text-xs text-text-tertiary space-y-1 pt-2">
            <p>Identity Provider: Firebase Authentication (EphemeralAI)</p>
            <p>Authoritative Policy: PostgreSQL Security Engine</p>
          </div>
        </div>
      </div>
    </div>
  );
};
