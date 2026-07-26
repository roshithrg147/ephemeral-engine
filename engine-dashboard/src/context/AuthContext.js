import React, { createContext, useCallback, useState } from 'react';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('sc-evm-auth-user');
    return saved ? JSON.parse(saved) : null;
  });
  const [idToken, setIdToken] = useState(() => localStorage.getItem('sc-evm-auth-token') || '');
  const [loading, setLoading] = useState(false);

  const login = useCallback(async (email = 'operator@example.com', password = '') => {
    setLoading(true);
    try {
      // Mock / Local Firebase authentication token generator for development & production fallback
      const mockUser = { uid: 'user_operator_001', email, displayName: email.split('@')[0] };
      const mockToken = `mock-firebase-token-${Date.now()}`;
      setUser(mockUser);
      setIdToken(mockToken);
      localStorage.setItem('sc-evm-auth-user', JSON.stringify(mockUser));
      localStorage.setItem('sc-evm-auth-token', mockToken);
      return true;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setIdToken('');
    localStorage.removeItem('sc-evm-auth-user');
    localStorage.removeItem('sc-evm-auth-token');
  }, []);

  const getAuthHeaders = useCallback((existingHeaders = {}) => {
    const headers = { ...existingHeaders };
    if (idToken) {
      headers.Authorization = `Bearer ${idToken}`;
    }
    return headers;
  }, [idToken]);

  return (
    <AuthContext.Provider value={{ user, idToken, loading, login, logout, getAuthHeaders }}>
      {children}
    </AuthContext.Provider>
  );
}
