import { useEffect, useRef, useState } from 'react';
import { errMsg } from '../services';

interface GoogleSignInButtonProps {
  onSuccess: (credential: string) => Promise<void>;
  onError: (err: string) => void;
  disabled?: boolean;
  text?: 'signin_with' | 'signup_with' | 'continue_with';
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: any) => void;
          renderButton: (parent: HTMLElement, options: any) => void;
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
  const containerRef = useRef<HTMLDivElement>(null);
  const [loadingScript, setLoadingScript] = useState(true);
  const [busy, setBusy] = useState(false);

  const clientId =
    (import.meta.env.VITE_GOOGLE_CLIENT_ID as string) ||
    '668146604297-onesmarter-certiverify.apps.googleusercontent.com';

  useEffect(() => {
    let scriptEl = document.querySelector('script[src="https://accounts.google.com/gsi/client"]') as HTMLScriptElement;

    const initGsi = () => {
      setLoadingScript(false);
      if (!window.google?.accounts?.id || !containerRef.current) return;

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (response: { credential?: string }) => {
          if (!response?.credential) {
            onError('No Google credential returned.');
            return;
          }
          setBusy(true);
          try {
            await onSuccess(response.credential);
          } catch (err) {
            onError(errMsg(err));
          } finally {
            setBusy(false);
          }
        },
      });

      // Clear container and render official GIS button
      containerRef.current.innerHTML = '';
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: 'outline',
        size: 'large',
        width: 320,
        text,
        shape: 'pill',
        logo_alignment: 'left',
      });
    };

    if (window.google?.accounts?.id) {
      initGsi();
    } else {
      if (!scriptEl) {
        scriptEl = document.createElement('script');
        scriptEl.src = 'https://accounts.google.com/gsi/client';
        scriptEl.async = true;
        scriptEl.defer = true;
        document.head.appendChild(scriptEl);
      }
      scriptEl.addEventListener('load', initGsi);
    }
  }, [clientId, onSuccess, onError, text]);

  return (
    <div className="w-full flex flex-col items-center justify-center my-2">
      <div
        ref={containerRef}
        style={{
          minHeight: 40,
          display: 'flex',
          justifyContent: 'center',
          opacity: disabled || busy ? 0.6 : 1,
          pointerEvents: disabled || busy ? 'none' : 'auto',
        }}
      >
        {loadingScript && (
          <div className="text-xs text-slate-400 py-2">Loading Google Sign-In…</div>
        )}
      </div>
      {busy && <p className="text-xs text-teal-600 mt-1">Verifying Google identity…</p>}
    </div>
  );
}
