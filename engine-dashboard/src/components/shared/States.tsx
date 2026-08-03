import React from 'react';
import { AlertCircle, WifiOff, XCircle } from 'lucide-react';

export function EmptyState({ message, icon: Icon }: { message: string, icon?: React.ElementType }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center h-full min-h-[200px]">
      {Icon && <Icon className="w-8 h-8 text-text-tertiary mb-3" />}
      <p className="text-sm text-text-secondary">{message}</p>
    </div>
  );
}

export function ErrorState({ title, message, onRetry }: { title: string, message: string, onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center p-6 text-center border border-message-error-bg bg-[rgba(221,68,68,0.05)] rounded-lg m-4">
      <XCircle className="w-8 h-8 text-status-error mb-3" />
      <h3 className="text-base font-medium text-text-primary mb-1">{title}</h3>
      <p className="text-sm text-text-secondary mb-4">{message}</p>
      {onRetry && (
        <button 
          onClick={onRetry}
          className="px-4 py-2 bg-surface-1 border border-border-strong rounded-md text-sm font-medium hover:bg-surface-2 transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
}

export function OfflineState() {
  return (
    <div className="flex items-center justify-center gap-2 p-3 bg-surface-2 border-b border-border-subtle text-sm text-text-secondary">
      <WifiOff className="w-4 h-4" />
      <span>You are offline. The dashboard will reconnect automatically when network is restored.</span>
    </div>
  );
}
