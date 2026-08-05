import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { LogIn, AlertTriangle, ShieldAlert, Cpu, Sparkles, Shield, Zap, Lock, Loader2 } from 'lucide-react';

export const Login: React.FC = () => {
  const { authState, error, signInWithGoogle, configValid } = useAuth();

  const isAuthenticating = authState === 'authenticating';

  return (
    <div className="relative min-h-screen bg-[#0a0c12] text-slate-100 flex flex-col items-center justify-center p-4 overflow-hidden select-none font-sans">
      {/* Background Animated Gradient Mesh & Glow Orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.25, 0.4, 0.25],
            x: [0, 30, 0],
            y: [0, -30, 0],
          }}
          transition={{
            duration: 12,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-indigo-600/30 blur-[120px]"
        />
        <motion.div
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.2, 0.35, 0.2],
            x: [0, -40, 0],
            y: [0, 40, 0],
          }}
          transition={{
            duration: 15,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-blue-600/30 blur-[140px]"
        />
        <motion.div
          animate={{
            scale: [1, 1.15, 1],
            opacity: [0.15, 0.3, 0.15],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-purple-600/20 blur-[160px]"
        />

        {/* Subtle Grid Pattern */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.8) 1px, transparent 0)`,
            backgroundSize: '24px 24px',
          }}
        />
      </div>

      {/* Main Container */}
      <div className="relative z-10 w-full max-w-md flex flex-col items-center space-y-6">
        {/* Animated Badge Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-medium backdrop-blur-md shadow-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
          <span>SC-EVM Autonomous Context Control Plane</span>
        </motion.div>

        {/* Hero Card */}
        <motion.div
          initial={{ opacity: 0, y: 25, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, type: 'spring', stiffness: 220, damping: 20 }}
          className="w-full bg-[#131724]/80 backdrop-blur-xl border border-slate-800/80 rounded-2xl p-8 shadow-[0_0_50px_rgba(79,126,240,0.12)] space-y-6 relative overflow-hidden"
        >
          {/* Top Border Accent Highlight */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-indigo-500 to-transparent opacity-80" />

          {/* Logo & Title */}
          <div className="text-center space-y-3">
            <motion.div
              whileHover={{ rotate: 5, scale: 1.05 }}
              className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 via-blue-500/10 to-purple-500/20 border border-indigo-500/30 text-indigo-400 shadow-inner mb-1"
            >
              <Cpu className="w-9 h-9 text-indigo-400" />
            </motion.div>
            <h1 className="text-3xl font-bold tracking-tight text-white bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
              Ephemeral Engine
            </h1>
            <p className="text-sm text-slate-400 leading-relaxed font-normal">
              Enterprise Dual-LLM Context Orchestration & Security Admission Gate
            </p>
          </div>

          {/* Error Banners */}
          <AnimatePresence mode="wait">
            {!configValid && (
              <motion.div
                key="config-error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                data-testid="config-error-banner"
                className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs space-y-1.5 backdrop-blur-sm"
              >
                <div className="flex items-center space-x-2 font-semibold text-rose-200">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>Configuration Error</span>
                </div>
                <p className="text-rose-300/90 leading-normal">
                  {error || 'Firebase client configuration is missing or invalid.'}
                </p>
              </motion.div>
            )}

            {error && configValid && error.includes('403') && (
              <motion.div
                key="forbidden-error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                data-testid="forbidden-error-banner"
                className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-300 text-xs space-y-1.5 backdrop-blur-sm"
              >
                <div className="flex items-center space-x-2 font-semibold text-amber-200">
                  <ShieldAlert className="w-4 h-4 shrink-0 text-amber-400" />
                  <span>Access Denied (403)</span>
                </div>
                <p className="text-amber-300/90 leading-normal">{error}</p>
              </motion.div>
            )}

            {error && configValid && !error.includes('403') && (
              <motion.div
                key="general-error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                data-testid="general-error-banner"
                className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs space-y-1.5 backdrop-blur-sm"
              >
                <div className="flex items-center space-x-2 font-semibold text-rose-200">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>Authentication Error</span>
                </div>
                <p className="text-rose-300/90 leading-normal">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Action Button & Sign In CTA */}
          <div className="space-y-4 pt-1">
            <motion.button
              whileHover={{ scale: configValid && !isAuthenticating ? 1.02 : 1 }}
              whileTap={{ scale: configValid && !isAuthenticating ? 0.98 : 1 }}
              data-testid="google-signin-btn"
              onClick={signInWithGoogle}
              disabled={!configValid || isAuthenticating}
              className="w-full relative group overflow-hidden flex items-center justify-center space-x-3 py-3.5 px-5 rounded-xl bg-gradient-to-r from-indigo-500 via-blue-600 to-indigo-600 hover:from-indigo-400 hover:to-blue-500 disabled:from-slate-800 disabled:to-slate-800 disabled:opacity-50 disabled:cursor-not-allowed font-semibold text-white text-base shadow-[0_0_25px_rgba(79,126,240,0.35)] transition-all duration-200 cursor-pointer border border-indigo-400/20"
            >
              {/* Button inner glow overlay */}
              <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />

              {isAuthenticating ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin text-white" />
                  <span className="text-white font-semibold">Connecting to Google...</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 fill-current text-white shrink-0" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                  </svg>
                  <span className="text-white font-semibold tracking-wide">Sign in with Google</span>
                </>
              )}
            </motion.button>

            {/* Feature Pills */}
            <div className="grid grid-cols-3 gap-2 pt-2 text-[11px] font-medium text-slate-400">
              <div className="flex items-center justify-center space-x-1 py-1.5 px-2 rounded-lg bg-slate-800/40 border border-slate-700/40 text-slate-300">
                <Zap className="w-3 h-3 text-indigo-400" />
                <span>Hybrid Search</span>
              </div>
              <div className="flex items-center justify-center space-x-1 py-1.5 px-2 rounded-lg bg-slate-800/40 border border-slate-700/40 text-slate-300">
                <Shield className="w-3 h-3 text-emerald-400" />
                <span>Zero-Trust</span>
              </div>
              <div className="flex items-center justify-center space-x-1 py-1.5 px-2 rounded-lg bg-slate-800/40 border border-slate-700/40 text-slate-300">
                <Lock className="w-3 h-3 text-blue-400" />
                <span>Firebase Auth</span>
              </div>
            </div>

            {/* Sub-footer Provider info */}
            <div className="text-center text-[11px] text-slate-500 space-y-0.5 pt-3 border-t border-slate-800/60">
              <p>Identity Provider: <span className="text-slate-400">Firebase Authentication (EphemeralAI)</span></p>
              <p>Security Boundary: <span className="text-slate-400">PostgreSQL OAuth & Admission Control</span></p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
};
