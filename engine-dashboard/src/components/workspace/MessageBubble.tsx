import React from 'react';
import { Message } from '../../runtime/types';
import { AlertTriangle, XCircle, Copy, Check } from 'lucide-react';
import { StreamingIndicator } from './StreamingIndicator';
import { FormattedMarkdown } from './FormattedMarkdown';

export function MessageBubble({ message }: { message: Message }) {
  const [copied, setCopied] = React.useState(false);

  const rawText = message.content || message.streamBuffer || '';

  const handleCopy = () => {
    navigator.clipboard.writeText(rawText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (message.role === 'system') {
    return (
      <div className="flex justify-center my-4" data-testid={`message-${message.id}`}>
        <div className="bg-message-system-bg text-message-system-fg px-4 py-2 rounded-lg text-[11px] font-mono italic max-w-2xl text-center border border-border-subtle">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.role === 'warning' || message.role === 'error') {
    const isError = message.role === 'error';
    const Icon = isError ? XCircle : AlertTriangle;
    return (
      <div className={`my-4 p-3 rounded-lg border flex gap-3 max-w-3xl mx-auto
        ${isError ? 'bg-message-error-bg text-message-error-fg border-[rgba(221,68,68,0.3)]' : 'bg-message-warning-bg text-message-warning-fg border-[rgba(240,168,50,0.3)]'}
      `} data-testid={`message-${message.id}`}>
        <Icon className="w-5 h-5 flex-none mt-0.5" />
        <div className="flex-1 text-sm whitespace-pre-wrap">
          {message.content}
          {isError && (
            <div className="mt-2 text-xs opacity-80 underline cursor-pointer">
              Retry request
            </div>
          )}
        </div>
      </div>
    );
  }

  const isUser = message.role === 'user';
  
  return (
    <div 
      className={`my-4 flex ${isUser ? 'justify-end' : 'justify-start'}`}
      data-testid={`message-${message.id}`}
    >
      <div 
        className={`relative group max-w-3xl flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}
      >
        <div className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide px-1">
          {message.role}
        </div>
        
        <div className={`
          px-4 py-3 rounded-xl border text-[14px] leading-relaxed w-full min-w-[180px]
          ${isUser 
            ? 'bg-message-user-bg text-message-user-fg border-border-default rounded-tr-sm' 
            : 'bg-message-assistant-bg text-message-assistant-fg border-border-subtle rounded-tl-sm shadow-sm'
          }
          ${message.cancelled ? 'opacity-60 line-through' : ''}
        `}>
          {rawText ? <FormattedMarkdown content={rawText} /> : (message.streaming && <StreamingIndicator />)}
          
          <button 
            onClick={handleCopy}
            className={`absolute top-6 ${isUser ? 'left-[-32px]' : 'right-[-32px]'} p-1 rounded-md bg-surface-2 border border-border-default text-text-tertiary opacity-0 group-hover:opacity-100 hover:text-text-primary transition-all`}
            aria-label="Copy text"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-status-healthy" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>

        {!isUser && (message.tokenCount || message.latencyMs) && (
          <div className="text-[10px] font-mono text-text-tertiary px-1 flex gap-3">
            {message.tokenCount && <span>{message.tokenCount} tokens</span>}
            {message.latencyMs && <span>{message.latencyMs}ms</span>}
          </div>
        )}
      </div>
    </div>
  );
}
