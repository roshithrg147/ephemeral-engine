import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Login } from '../../pages/Login';
import { Loader2 } from 'lucide-react';

export interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { authState } = useAuth();

  if (authState === 'initializing' || authState === 'authenticating') {
    return (
      <div
        data-testid="auth-loading-screen"
        className="min-h-screen bg-bg-dark flex flex-col items-center justify-center space-y-3 text-text-tertiary select-none"
      >
        <Loader2 className="w-8 h-8 animate-spin text-accent-blue" />
        <p className="text-sm font-medium">Resolving identity & PostgreSQL principal...</p>
      </div>
    );
  }

  if (authState !== 'authenticated') {
    return <Login />;
  }

  return <>{children}</>;
};
