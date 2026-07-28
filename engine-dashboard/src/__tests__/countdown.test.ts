import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useCountdown } from '../hooks/useCountdown';

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns healthy tier when > 30 mins remaining', () => {
    const expiresAt = Date.now() + 60 * 60 * 1000; // 1 hr
    const { result } = renderHook(() => useCountdown(expiresAt));
    
    expect(result.current.tier).toBe('healthy');
    expect(result.current.isExpired).toBe(false);
  });

  it('returns expiring_soon when <= 30 mins remaining', () => {
    const expiresAt = Date.now() + 25 * 60 * 1000; // 25 mins
    const { result } = renderHook(() => useCountdown(expiresAt));
    
    expect(result.current.tier).toBe('expiring_soon');
  });

  it('returns critical when <= 5 mins remaining', () => {
    const expiresAt = Date.now() + 4 * 60 * 1000; // 4 mins
    const { result } = renderHook(() => useCountdown(expiresAt));
    
    expect(result.current.tier).toBe('critical');
  });

  it('returns expired when diff is 0 or negative', () => {
    const expiresAt = Date.now() - 1000; // -1s
    const { result } = renderHook(() => useCountdown(expiresAt));
    
    expect(result.current.tier).toBe('expired');
    expect(result.current.isExpired).toBe(true);
    expect(result.current.hours).toBe(0);
    expect(result.current.minutes).toBe(0);
    expect(result.current.seconds).toBe(0);
  });

  it('updates over time', () => {
    const start = Date.now();
    const expiresAt = start + 2000; // 2s
    const { result } = renderHook(() => useCountdown(expiresAt));
    
    expect(result.current.seconds).toBe(2);
    
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    
    expect(result.current.seconds).toBe(1);
    
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    
    expect(result.current.seconds).toBe(0);
    expect(result.current.isExpired).toBe(true);
  });
});
