import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import type { User } from '../types';
import { ApiError, authService, mfaService, errMsg, profileService, type LoginResult } from '../services';
import { toast } from '../lib/ui';

interface AuthValue {
  /** Current profile from GET /accounts/me/ (null = signed out). */
  user: User | null;
  /** true while the stored session is being restored after a page load. */
  loading: boolean;
  /** Set when the session could not be restored because the server was unreachable. */
  bootError: string | null;
  login: (username: string, password: string) => Promise<LoginResult>;
  googleLogin: (idToken: string) => Promise<LoginResult>;
  verifyMfa: (challenge: string, code: string) => Promise<User>;
  recoverMfa: (challenge: string, code: string) => Promise<{ detail: string; success: boolean }>;
  register: typeof authService.register;
  verifyEmail: typeof authService.verifyEmail;
  resendVerification: typeof authService.resendVerification;
  setPassword: (password: string, passwordConfirm: string) => Promise<User>;
  reloadProfile: () => Promise<User | null>;
  logout: () => void;
  updateProfile: (p: { organization: string; phone: string }) => Promise<void>;
  retryRestore: () => void;
  hasSession: () => boolean;
}

const Ctx = createContext<AuthValue | null>(null);

export const useAuth = (): AuthValue => {
  const c = useContext(Ctx);
  if (!c) throw new Error('AuthProvider is missing');
  return c;
};

/** The ONE place that holds the session: tokens live in services/tokens.ts, the profile lives here. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUserState] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);
  const restoreCleanup = useRef<(() => void) | null>(null);

  const setUser = useCallback((u: User | null) => {
    setUserState(u);
  }, []);

  // Restore the session on page load (uses the stored tokens, refreshing the access token if needed).
  const restore = useCallback(() => {
    let live = true;
    setLoading(true);
    setBootError(null);
    authService
      .restore()
      .then(u => { if (live) setUser(u); })
      .catch(e => {
        if (!live) return;
        setUser(null);
        // Server down: keep the stored tokens and offer a retry. Anything else: the session is invalid.
        if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) setBootError(errMsg(e));
        else authService.logout();
      })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [setUser]);

  useEffect(() => {
    restoreCleanup.current = restore();
    return () => restoreCleanup.current?.();
  }, [restore]);

  // The API client fires this when the refresh token no longer works.
  useEffect(() => {
    const onExpired = () => {
      setUser(null);
      const message = 'Your session has expired. Please sign in again.';
      toast(message, 'er');
      navigate('/login', { replace: true, state: { message } });
    };
    window.addEventListener('auth:expired', onExpired);
    return () => window.removeEventListener('auth:expired', onExpired);
  }, [navigate, setUser]);

  const value = useMemo<AuthValue>(() => ({
    user,
    loading,
    bootError,
    login: async (username, password) => {
      const r = await authService.login(username, password);
      if (r.kind === 'success') setUser(r.user);
      return r;
    },
    googleLogin: async (idToken: string) => {
      const result = await authService.googleLogin(idToken);
      if (result.kind === 'success') setUser(result.user);
      return result;
    },
    verifyMfa: async (challenge, code) => {
      const u = await authService.verifyMfa(challenge, code);
      setUser(u);
      return u;
    },
    recoverMfa: async (challenge, code) => {
      const result = await mfaService.completeRecovery(challenge, code);
      return result;
    },
    register: authService.register,
    verifyEmail: async data => {
      const res = await authService.verifyEmail(data);
      if (authService.hasSession()) {
        try {
          const u = await authService.me();
          setUser(u);
        } catch {
          // Email verification is also available before the first login.
        }
      }
      return res;
    },
    resendVerification: authService.resendVerification,
    setPassword: async (pw, pc) => {
      const u = await authService.setPassword(pw, pc);
      setUser(u);
      return u;
    },
    reloadProfile: async () => {
      try {
        const u = await authService.me();
        setUser(u);
        return u;
      } catch {
        return null;
      }
    },
    logout: () => {
      authService.logout();
      setUser(null);
    },
    updateProfile: async p => {
      setUser(await profileService.update(p));
    },
    retryRestore: () => {
      restoreCleanup.current?.();
      restoreCleanup.current = restore();
    },
    hasSession: authService.hasSession,
  }), [user, loading, bootError, navigate, restore, setUser]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
