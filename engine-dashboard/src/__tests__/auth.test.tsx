import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { validateRuntimeConfig, RuntimeConfig } from '../lib/config';
import { initFirebaseClient, FirebaseInitResult, resetFirebaseInitCache } from '../lib/firebase';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { customFetch } from '../lib/customFetch';

// Mock firebase/auth
vi.mock('firebase/auth', () => {
  return {
    getAuth: vi.fn().mockReturnValue({}),
    GoogleAuthProvider: class {
      setCustomParameters = vi.fn();
    },
    setPersistence: vi.fn().mockResolvedValue(undefined),
    browserSessionPersistence: 'SESSION',
    onAuthStateChanged: vi.fn((_auth, callback) => {
      callback(null);
      return () => {};
    }),
    signInWithPopup: vi.fn(),
    signOut: vi.fn().mockResolvedValue(undefined),
  };
});

// Mock firebase/app
vi.mock('firebase/app', () => {
  return {
    getApps: vi.fn().mockReturnValue([]),
    getApp: vi.fn(),
    initializeApp: vi.fn().mockReturnValue({}),
  };
});

describe('Runtime Config Boundary (config.ts)', () => {
  it('validates required Firebase and API variables', () => {
    const validConfig: RuntimeConfig = {
      firebaseApiKey: 'test-api-key',
      firebaseAuthDomain: 'test.firebaseapp.com',
      firebaseProjectId: 'ephemeralai-a8bee',
      firebaseAppId: '1:123:web:abc',
      apiBaseUrl: '/api',
      isProduction: false,
    };
    const res = validateRuntimeConfig(validConfig);
    expect(res.valid).toBe(true);
    expect(res.errors).toHaveLength(0);
  });

  it('fails safely when required variables are missing or blank', () => {
    const invalidConfig: RuntimeConfig = {
      firebaseApiKey: '',
      firebaseAuthDomain: '   ',
      firebaseProjectId: 'ephemeralai-a8bee',
      firebaseAppId: '',
      apiBaseUrl: '/api',
      isProduction: false,
    };
    const res = validateRuntimeConfig(invalidConfig);
    expect(res.valid).toBe(false);
    expect(res.errors.length).toBeGreaterThanOrEqual(3);
  });

  it('detects placeholder configuration in production builds', () => {
    const prodPlaceholderConfig: RuntimeConfig = {
      firebaseApiKey: 'YOUR_API_KEY_HERE',
      firebaseAuthDomain: 'test.firebaseapp.com',
      firebaseProjectId: 'ephemeralai-a8bee',
      firebaseAppId: '1:123:web:abc',
      apiBaseUrl: '/api',
      isProduction: true,
    };
    const res = validateRuntimeConfig(prodPlaceholderConfig);
    expect(res.valid).toBe(false);
    expect(res.errors[0]).toContain('Production build detected placeholder string');
  });
});

describe('Firebase Client Initialization (firebase.ts)', () => {
  beforeEach(() => {
    resetFirebaseInitCache();
  });

  it('initializes Firebase client once with valid configuration', () => {
    const validValidation = {
      valid: true,
      config: {
        firebaseApiKey: 'test-key',
        firebaseAuthDomain: 'test.firebaseapp.com',
        firebaseProjectId: 'ephemeralai-a8bee',
        firebaseAppId: '1:123:web:abc',
        apiBaseUrl: '/api',
        isProduction: false,
      },
      errors: [],
    };

    const result = initFirebaseClient(validValidation);
    expect(result.configValid).toBe(true);
    expect(result.auth).toBeDefined();
    expect(result.googleProvider).toBeDefined();
  });
});

describe('AuthProvider & ProtectedRoute', () => {
  it('renders error screen when configuration is invalid', () => {
    const invalidInit: FirebaseInitResult = {
      configValid: false,
      errors: ['VITE_FIREBASE_API_KEY is required.'],
    };

    render(
      <AuthProvider initResult={invalidInit}>
        <ProtectedRoute>
          <div data-testid="protected-content">Protected App Content</div>
        </ProtectedRoute>
      </AuthProvider>
    );

    expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    expect(screen.getByTestId('config-error-banner')).toHaveTextContent(
      'VITE_FIREBASE_API_KEY is required.'
    );
  });

  it('renders unauthenticated Login page after auth observer initializes with null user', () => {
    const validInit: FirebaseInitResult = {
      configValid: true,
      errors: [],
      auth: {} as any,
      googleProvider: {} as any,
    };

    render(
      <AuthProvider initResult={validInit}>
        <ProtectedRoute>
          <div data-testid="protected-content">Protected Content</div>
        </ProtectedRoute>
      </AuthProvider>
    );

    expect(screen.getByTestId('google-signin-btn')).toBeInTheDocument();
  });
});

describe('customFetch & Bearer Token Authorization', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('attaches Authorization header if token is available', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'ok', data: ['session-1'] }),
    });
    global.fetch = mockFetch;

    const mockInit: FirebaseInitResult = {
      configValid: true,
      errors: [],
      auth: {} as any,
    };

    const FetchTester = () => {
      React.useEffect(() => {
        customFetch('/api/session/list');
      }, []);
      return <div>Tester</div>;
    };

    render(
      <AuthProvider initResult={mockInit}>
        <FetchTester />
      </AuthProvider>
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockFetch).toHaveBeenCalled();
  });

  it('handles 403 Forbidden without automatically signing out', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: () => Promise.resolve({ detail: 'Access denied - Account not admitted' }),
    });
    global.fetch = mockFetch;

    await expect(customFetch('/api/session/list')).rejects.toThrow('HTTP 403 Forbidden');
  });
});
