import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  signInWithPopup,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  setPersistence,
  browserSessionPersistence,
} from 'firebase/auth';
import { initFirebaseClient, FirebaseInitResult } from '../lib/firebase';
import { fetchSessionList } from '../runtime/apiService';

export type AuthState =
  | 'initializing'
  | 'unauthenticated'
  | 'authenticating'
  | 'authenticated'
  | 'signing_out'
  | 'error';

export interface SanitizedUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}

export interface AuthContextType {
  authState: AuthState;
  user: SanitizedUser | null;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signOutUser: () => Promise<void>;
  getIdToken: (forceRefresh?: boolean) => Promise<string | null>;
  setForbiddenState: (message?: string) => void;
  configValid: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

let currentGetTokenFn: ((forceRefresh?: boolean) => Promise<string | null>) | null = null;
let currentSetForbiddenFn: ((message?: string) => void) | null = null;
let currentSignOutFn: (() => Promise<void>) | null = null;
let currentRawUser: any = null;

export function getGlobalIdToken(forceRefresh = false): Promise<string | null> {
  if (currentGetTokenFn) {
    return currentGetTokenFn(forceRefresh);
  }
  return Promise.resolve(null);
}

export function notifyGlobalForbidden(message?: string): void {
  if (currentSetForbiddenFn) {
    currentSetForbiddenFn(message);
  }
}

export function triggerGlobalSignOut(): Promise<void> {
  if (currentSignOutFn) {
    return currentSignOutFn();
  }
  return Promise.resolve();
}

export interface AuthProviderProps {
  children: React.ReactNode;
  initResult?: FirebaseInitResult;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, initResult }) => {
  const firebase = useMemo(() => initResult || initFirebaseClient(), [initResult]);

  const [authState, setAuthState] = useState<AuthState>(
    firebase.configValid ? 'initializing' : 'error'
  );
  const [user, setUser] = useState<SanitizedUser | null>(null);
  const [error, setError] = useState<string | null>(
    firebase.errors.length > 0 ? firebase.errors.join(' ') : null
  );

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const getIdToken = useCallback(async (forceRefresh = false): Promise<string | null> => {
    if (!currentRawUser) return null;
    try {
      return await currentRawUser.getIdToken(forceRefresh);
    } catch (err: any) {
      console.error('Failed to retrieve Firebase ID token:', err);
      return null;
    }
  }, []);

  const setForbiddenState = useCallback((message?: string) => {
    if (!mountedRef.current) return;
    setAuthState('error');
    setError(message || 'Access denied (403): Account not admitted in PostgreSQL or lacks active tenant membership.');
  }, []);

  const signOutUser = useCallback(async () => {
    if (mountedRef.current) setAuthState('signing_out');
    if (firebase.auth) {
      try {
        await firebaseSignOut(firebase.auth);
      } catch (err: any) {
        console.error('Firebase Sign-Out error:', err);
      }
    }

    try {
      localStorage.removeItem('sc-evm-auth-token');
      sessionStorage.removeItem('sc-evm-auth-token');
    } catch {
      // Ignore browser storage removal errors
    }

    currentRawUser = null;
    if (mountedRef.current) {
      setUser(null);
      setAuthState('unauthenticated');
      setError(null);
    }
  }, [firebase]);

  useEffect(() => {
    currentGetTokenFn = getIdToken;
    currentSetForbiddenFn = setForbiddenState;
    currentSignOutFn = signOutUser;
    return () => {
      currentGetTokenFn = null;
      currentSetForbiddenFn = null;
      currentSignOutFn = null;
    };
  }, [getIdToken, setForbiddenState, signOutUser]);

  // Perform backend admission check against PostgreSQL
  const checkApplicationAdmission = useCallback(
    async (firebaseUser: any) => {
      currentRawUser = firebaseUser;
      if (mountedRef.current) setAuthState('authenticating');

      try {
        // Query /api/session/list to verify PostgreSQL identity resolution
        await fetchSessionList();

        if (!mountedRef.current) return;
        setUser({
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          displayName: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL,
        });
        setAuthState('authenticated');
        setError(null);
      } catch (err: any) {
        if (!mountedRef.current) return;
        console.error('Backend application admission check failed:', err);
        if (err?.status === 403 || err?.message?.includes('403')) {
          setAuthState('error');
          setError('Access denied (403): Google identity verified, but account is not admitted in PostgreSQL.');
        } else if (err?.status === 401 || err?.message?.includes('401')) {
          await signOutUser();
          setError('Session expired. Please sign in again.');
        } else {
          setAuthState('error');
          setError('Backend service unavailable during admission check. Please retry.');
        }
      }
    },
    [signOutUser]
  );

  useEffect(() => {
    if (!firebase.configValid || !firebase.auth) {
      setAuthState('error');
      setError(firebase.errors.join(' ') || 'Firebase configuration invalid');
      return;
    }

    const unsubscribe = onAuthStateChanged(
      firebase.auth,
      async (firebaseUser) => {
        if (firebaseUser) {
          await checkApplicationAdmission(firebaseUser);
        } else {
          currentRawUser = null;
          if (mountedRef.current) {
            setUser(null);
            setAuthState('unauthenticated');
          }
        }
      },
      (err) => {
        console.error('Firebase Auth state observer error:', err);
        currentRawUser = null;
        if (mountedRef.current) {
          setUser(null);
          setAuthState('error');
          setError(err.message || 'Firebase authentication state error');
        }
      }
    );

    return () => {
      unsubscribe();
    };
  }, [firebase, checkApplicationAdmission]);

  const signInWithGoogle = useCallback(async () => {
    if (!firebase.configValid || !firebase.auth || !firebase.googleProvider) {
      setAuthState('error');
      setError(firebase.errors.join(' ') || 'Firebase configuration invalid');
      return;
    }

    if (mountedRef.current) {
      setAuthState('authenticating');
      setError(null);
    }

    try {
      await setPersistence(firebase.auth, browserSessionPersistence);
      await signInWithPopup(firebase.auth, firebase.googleProvider);
    } catch (err: any) {
      if (!mountedRef.current) return;
      console.error('Google Sign-In popup error:', err);
      let userFriendlyMsg = 'Google Sign-In failed. Please try again.';
      const code = err?.code || '';

      if (code === 'auth/popup-closed-by-user') {
        userFriendlyMsg = 'Sign-in popup was closed before completing.';
      } else if (code === 'auth/popup-blocked') {
        userFriendlyMsg = 'Sign-in popup was blocked by your browser. Please allow popups for this site.';
      } else if (code === 'auth/network-request-failed') {
        userFriendlyMsg = 'Network connection failure during sign-in.';
      } else if (code === 'auth/unauthorized-domain') {
        userFriendlyMsg = 'Domain is not authorized in Firebase Console for Google sign-in.';
      } else if (code === 'auth/user-disabled') {
        userFriendlyMsg = 'Account has been disabled.';
      }

      setAuthState('unauthenticated');
      setError(userFriendlyMsg);
    }
  }, [firebase]);

  const contextValue: AuthContextType = {
    authState,
    user,
    error,
    signInWithGoogle,
    signOutUser,
    getIdToken,
    setForbiddenState,
    configValid: firebase.configValid,
  };

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
