import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useReducedMotion } from '../hooks/useReducedMotion';

describe('useReducedMotion', () => {
  it('matches prefers-reduced-motion media query', () => {
    // Mock matchMedia
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });
});
