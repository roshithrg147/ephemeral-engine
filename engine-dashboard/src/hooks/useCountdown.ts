import { useState, useEffect } from 'react';
import { SessionTier } from '../runtime/types';

export function useCountdown(expiresAt: number) {
  const [now, setNow] = useState(Date.now());
  
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  
  const diff = Math.max(0, expiresAt - now);
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);
  const isExpired = diff <= 0;
  
  let tier: SessionTier = 'healthy';
  if (isExpired) tier = 'expired';
  else if (diff <= 5 * 60 * 1000) tier = 'critical';
  else if (diff <= 30 * 60 * 1000) tier = 'expiring_soon';
  
  return { hours, minutes, seconds, tier, isExpired };
}
