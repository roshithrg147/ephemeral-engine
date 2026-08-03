import React, { useEffect } from 'react';
import { useLocation } from 'wouter';
import { useRuntime } from '../runtime/RuntimeContext';
import { SessionRail } from '../components/workspace/SessionRail';
import { ConversationCanvas } from '../components/workspace/ConversationCanvas';
import { Composer } from '../components/workspace/Composer';
import { Inspector } from '../components/workspace/Inspector';

export function Workspace() {
  const { state, dispatch } = useRuntime();
  
  // Minimal query param parsing (since wouter doesn't give us search params directly in the hook)
  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const sessionId = searchParams.get('session');
    
    if (sessionId && state.sessions[sessionId] && state.activeSessionId !== sessionId) {
      dispatch({ type: 'SESSION_SELECTED', sessionId });
    }
  }, [dispatch, state.sessions, state.activeSessionId]);

  return (
    <div className="h-full flex flex-col md:flex-row overflow-hidden relative">
      <SessionRail />
      
      <div className="flex-1 flex flex-col min-w-0">
        <ConversationCanvas />
        <Composer />
      </div>
      
      <Inspector />
    </div>
  );
}
