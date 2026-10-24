import { useEffect, useRef, useState } from 'react';
import { errMsg } from '../services';

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => Promise<void>;
  onError: (err: string) => void;
  disabled?: boolean;
  text?: 'signin_with' | 'signup_with' | 'continue_with';
}

interface GoogleCredentialResponse { credential?: string }
interface GoogleInitializeConfig {
  client_id: string;
  callback: (response: GoogleCredentialResponse) => void;
}
interface GoogleButtonOptions {
  theme?: 'outline' | 'filled_blue' | 'filled_black';
  size?: 'large' | 'medium' | 'small';
  width?: number;
  text?: 'signin_with' | 'signup_with' | 'continue_with';
  shape?: 'rectangular' | 'pill' | 'circle' | 'square';
  logo_alignment?: 'left' | 'center';
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: GoogleInitializeConfig) => void;
          renderButton: (parent: HTMLElement, options: GoogleButtonOptions) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export default function GoogleSignInButton({
  onSuccess,
  onError,
  disabled = false,
  text = 'signin_with',
}: GoogleSignInButtonProps) {
  // Container dedicated ONLY to Google's rendered DOM.
  const containerRef = useRef<HTMLDivElement>(null);
  const [loadingScript, setLoadingScript] = useState(true);
  const [busy, setBusy] = useState(false);

  // Keep latest callbacks in refs to avoid re-triggering effects
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // Retrieve configured Google Client ID from environment variables
  const clientId = ((import.meta.env.VITE_GOOGLE_CLIENT_ID as string) || '').trim();
  const isConfigured = Boolean(clientId && !clientId.startsWith('YOUR_GOOGLE_CLIENT_ID'));

  useEffect(() => {
    if (!isConfigured) {
      setLoadingScript(false);
      return;
    }

    let isMounted = true;
    let scriptEl = document.querySelector('script[src="https://accounts.google.com/gsi/client"]') as HTMLScriptElement | null;

    const renderGsi = () => {
      if (!isMounted) return;

      if (!window.google?.accounts?.id || !containerRef.current) {
        setLoadingScript(false);
        return;
      }

      try {
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response: GoogleCredentialResponse) => {
            if (!response?.credential) {
              onErrorRef.current('No Google credential returned.');
              return;
            }
            if (!isMounted) return;
            setBusy(true);
            try {
              await onSuccessRef.current(response.credential);
            } catch (err) {
              if (isMounted) onErrorRef.current(errMsg(err));
            } finally {
              if (isMounted) setBusy(false);
            }
          },
        });

        if (containerRef.current) {
          containerRef.current.innerHTML = '';
          window.google.accounts.id.renderButton(containerRef.current, {
            theme: 'outline',
            size: 'large',
            width: 320,
            text,
            shape: 'pill',
            logo_alignment: 'left',
          });
        }
      } catch (e) {
        console.warn('Google Sign-In initialization notice:', e);
      } finally {
        if (isMounted) {
          setLoadingScript(false);
        }
      }
    };

    const handleScriptLoad = () => {
      renderGsi();
    };

    const handleScriptError = () => {
      if (!isMounted) return;
      console.warn('Google Sign-In client library could not be loaded from Google CDN.');
      setLoadingScript(false);
    };

    if (window.google?.accounts?.id) {
      renderGsi();
    } else {
      if (!scriptEl) {
        scriptEl = document.createElement('script');
        scriptEl.src = 'https://accounts.google.com/gsi/client';
        scriptEl.async = true;
        scriptEl.defer = true;
        document.head.appendChild(scriptEl);
      }
      scriptEl.addEventListener('load', handleScriptLoad);
      scriptEl.addEventListener('error', handleScriptError);
    }

    return () => {
      isMounted = false;
      if (scriptEl) {
        scriptEl.removeEventListener('load', handleScriptLoad);
        scriptEl.removeEventListener('error', handleScriptError);
      }
    };
  }, [clientId, isConfigured, text]);

  // If Google OAuth Client ID is not configured in .env, show an unconfigured button that guides the user
  if (!isConfigured) {
    return (
      <div className="w-full flex flex-col items-center justify-center my-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            onError(
              'Google Sign-In is not configured yet. Please configure VITE_GOOGLE_CLIENT_ID in your frontend .env file.'
            );
          }}
          className="w-[320px] max-w-full h-10 px-4 rounded-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 text-sm font-medium flex items-center justify-center gap-3 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition cursor-pointer"
        >
          <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>Sign in with Google</span>
        </button>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col items-center justify-center my-2">
      {loadingScript && (
        <div className="text-xs text-slate-400 py-2">Loading Google Sign-In…</div>
      )}
      <div
        ref={containerRef}
        style={{
          minHeight: loadingScript ? 0 : 40,
          display: loadingScript ? 'none' : 'flex',
          justifyContent: 'center',
          opacity: disabled || busy ? 0.6 : 1,
          pointerEvents: disabled || busy ? 'none' : 'auto',
        }}
      />
      {busy && <p className="text-xs text-teal-600 mt-1">Verifying Google identity…</p>}
    </div>
  );
}
