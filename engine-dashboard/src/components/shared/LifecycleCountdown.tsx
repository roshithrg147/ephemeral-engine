import React from 'react';
import { useCountdown } from '../../hooks/useCountdown';
import { SessionTier } from '../../runtime/types';

export function StatusBadge({ 
  tier, 
  text, 
  dotOnly = false 
}: { 
  tier: SessionTier | 'offline' | 'error' | 'retrying'; 
  text?: string;
  dotOnly?: boolean;
}) {
  let colorClass = 'bg-status-healthy';
  if (tier === 'expiring_soon') colorClass = 'bg-status-expiring';
  if (tier === 'critical') colorClass = 'bg-status-critical';
  if (tier === 'expired' || tier === 'error') colorClass = 'bg-status-expired';
  if (tier === 'burning') colorClass = 'bg-status-burning animate-pulse-fast';
  if (tier === 'burned') colorClass = 'bg-status-burned';
  if (tier === 'offline') colorClass = 'bg-status-offline';
  if (tier === 'retrying') colorClass = 'bg-status-retrying';

  if (dotOnly) {
    return <span className={`w-2 h-2 rounded-full ${colorClass}`} aria-hidden="true" />;
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-border-subtle bg-surface-2">
      <span className={`w-2 h-2 rounded-full ${colorClass}`} aria-hidden="true" />
      <span className="text-[11px] font-medium tracking-wide text-text-secondary uppercase">
        {text || tier.replace('_', ' ')}
      </span>
    </div>
  );
}

export function LifecycleCountdown({ 
  expiresAt, 
  sessionId 
}: { 
  expiresAt: number; 
  sessionId: string;
}) {
  const { hours, minutes, seconds, tier, isExpired } = useCountdown(expiresAt);

  let formatted = '';
  if (isExpired) {
    formatted = '0:00';
  } else if (hours > 0) {
    formatted = `${hours}h ${minutes}m`;
  } else {
    formatted = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }

  return (
    <div 
      className="flex items-center gap-2" 
      aria-label={`Session expires in ${hours} hours and ${minutes} minutes. Status: ${tier}.`}
      data-testid={`countdown-display-${sessionId}`}
    >
      <StatusBadge tier={tier} dotOnly />
      <span className="font-mono text-xs text-text-primary w-[4ch]">
        {formatted}
      </span>
    </div>
  );
}
