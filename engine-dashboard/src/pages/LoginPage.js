import React, { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, LogIn, ShieldAlert } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';

export default function LoginPage() {
  const { login, loading } = useContext(AuthContext);
  const [email, setEmail] = useState('operator@example.com');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await login(email);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Authentication failed');
    }
  };

  return (
    <div className="login-page-wrapper" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
      <div className="dialog-card" style={{ maxWidth: '420px', width: '100%', padding: '2rem' }}>
        <div className="dialog-icon dialog-icon-primary">
          <Lock size={24} />
        </div>
        <h2 className="dialog-title" style={{ marginTop: '1rem' }}>SC-EVM Control Plane</h2>
        <p className="dialog-description">Sign in with Firebase or Google SSO to access session state and metrics.</p>

        {error && (
          <div className="toast" style={{ position: 'static', margin: '1rem 0', background: 'var(--color-danger-bg, #fee2e2)', color: 'var(--color-danger, #dc2626)' }}>
            <ShieldAlert size={16} /> <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="field-group">
            <label htmlFor="login-email">Account Email</label>
            <input
              id="login-email"
              type="email"
              className="text-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="button button-primary" disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
            <LogIn size={16} />
            {loading ? 'Authenticating…' : 'Sign In to Control Plane'}
          </button>
        </form>
      </div>
    </div>
  );
}
