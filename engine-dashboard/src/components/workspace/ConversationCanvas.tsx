import React from 'react';
import { useRuntime } from '../../runtime/RuntimeContext';
import { selectActiveSession } from '../../runtime/selectors';
import { useAutoScroll } from '../../hooks/useAutoScroll';
import { MessageBubble } from './MessageBubble';
import { ArrowDown } from 'lucide-react';

export function ConversationCanvas() {
  const { state } = useRuntime();
  const session = selectActiveSession(state);
  
  const messages = session?.messages || [];
  
  // We use auto scroll hook
  // We want to re-evaluate scroll position when messages array changes or when streamBuffer updates
  // A stringified rep of the last message's length is a good proxy for streaming updates
  const lastMsgLength = messages.length > 0 
    ? (messages[messages.length-1].content?.length || 0) + (messages[messages.length-1].streamBuffer?.length || 0)
    : 0;

  const { scrollRef, showJumpButton, scrollToBottom } = useAutoScroll([messages.length, lastMsgLength]);

  if (!session) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-text-tertiary">
        <div className="w-16 h-16 border-2 border-dashed border-border-default rounded-full flex items-center justify-center mb-4">
          +
        </div>
        <p>Select a session or create a new one to begin.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col relative overflow-hidden bg-canvas">
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 lg:p-8 pb-24 scroll-smooth"
      >
        <div className="max-w-3xl mx-auto w-full">
          {messages.length === 0 ? (
            <div className="text-center text-sm text-text-tertiary mt-20">
              No messages yet.
            </div>
          ) : (
            messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}
        </div>
      </div>
      
      {showJumpButton && (
        <button 
          onClick={scrollToBottom}
          data-testid="jump-to-latest-button"
          className="absolute bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 bg-surface-2/90 backdrop-blur border border-border-strong rounded-full shadow-lg text-xs font-medium text-text-primary hover:bg-surface-1 flex items-center gap-2 transition-all animate-in slide-in-from-bottom-5"
        >
          Jump to latest <ArrowDown className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
