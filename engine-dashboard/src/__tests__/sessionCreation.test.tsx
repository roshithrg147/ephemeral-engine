import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { RuntimeProvider, useRuntime } from '../runtime/RuntimeContext';
import { Sessions } from '../pages/Sessions';

// Mock localStorage if missing in node test environment
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    clear: () => {
      store = {};
    },
    removeItem: (key: string) => {
      delete store[key];
    },
  };
})();
Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
});

// Mock apiService to prevent network requests during unit tests
vi.mock('../runtime/apiService', () => ({
  fetchHealth: vi.fn().mockResolvedValue({ status: 'online' }),
  fetchSessionList: vi.fn().mockResolvedValue([]),
  fetchSessionHistory: vi.fn().mockResolvedValue([]),
  initializeSession: vi.fn().mockResolvedValue({ status: 'initialized' }),
  burnSession: vi.fn().mockResolvedValue({ status: 'burned' }),
}));

// Test helper component to invoke createSession programmatically
function SessionTester() {
  const { state, createSession, burnSession } = useRuntime();

  return (
    <div>
      <span data-testid="session-count">{Object.keys(state.sessions).length}</span>
      <span data-testid="active-session-id">{state.activeSessionId || 'none'}</span>
      <button
        data-testid="create-session-btn"
        onClick={async () => {
          await createSession('Test Custom Session', 'sess-custom123');
        }}
      >
        Create Session
      </button>
      {state.activeSessionId && (
        <button
          data-testid="burn-session-btn"
          onClick={async () => {
            await burnSession(state.activeSessionId!);
          }}
        >
          Burn Active
        </button>
      )}
    </div>
  );
}

describe('New Session Creation & UI Interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('creates a new session and sets it as active in RuntimeContext state', async () => {
    render(
      <RuntimeProvider>
        <SessionTester />
      </RuntimeProvider>
    );

    // Initial state: 0 sessions
    expect(screen.getByTestId('session-count')).toHaveTextContent('0');

    // Click create session
    await act(async () => {
      fireEvent.click(screen.getByTestId('create-session-btn'));
    });

    // Assert session count and active session ID
    expect(screen.getByTestId('session-count')).toHaveTextContent('1');
    expect(screen.getByTestId('active-session-id')).toHaveTextContent('sess-custom123');
  });

  it('renders Sessions page and triggers new session creation via top-right action', async () => {
    render(
      <RuntimeProvider>
        <Sessions />
      </RuntimeProvider>
    );

    // Find "New Session" button in Sessions header
    const newSessionBtn = screen.getByText('New Session');
    expect(newSessionBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(newSessionBtn);
    });

    // Header and filter elements should render cleanly
    expect(screen.getByText('Sessions')).toBeInTheDocument();
  });

  it('handles burning an active session and updating state', async () => {
    render(
      <RuntimeProvider>
        <SessionTester />
      </RuntimeProvider>
    );

    // Create session first
    await act(async () => {
      fireEvent.click(screen.getByTestId('create-session-btn'));
    });

    expect(screen.getByTestId('active-session-id')).toHaveTextContent('sess-custom123');

    // Burn session
    await act(async () => {
      fireEvent.click(screen.getByTestId('burn-session-btn'));
    });

    expect(screen.getByTestId('session-count')).toHaveTextContent('1');
  });
});
