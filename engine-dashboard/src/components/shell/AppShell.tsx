import React, { ReactNode } from 'react';
import { StatusBar } from './StatusBar';
import { NavBar } from './NavBar';
import { useRuntime } from '../../runtime/RuntimeContext';
import { OfflineState } from '../shared/States';

export function AppShell({ children }: { children: ReactNode }) {
  const { state } = useRuntime();

  return (
    <div className="h-screen w-full flex flex-col bg-canvas text-text-primary overflow-hidden">
      <StatusBar />
      
      {state.connectionState === 'offline' && <OfflineState />}
      
      {state.authStatus === 'expired' && (
        <div className="bg-status-expiring bg-opacity-10 border-b border-[rgba(240,168,50,0.3)] p-2 text-center text-sm text-[#d98918]">
          Your auth token has expired. Reconnect to continue. Active sessions are safe.
        </div>
      )}
      
      <div className="flex-1 flex overflow-hidden">
        <NavBar />
        <main className="flex-1 overflow-hidden relative">
          {children}
        </main>
      </div>
    </div>
  );
}
