import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import Field from '../components/Field';
import MfaChallengeForm from '../components/MfaChallengeForm';
import GoogleSignInButton from '../components/GoogleSignInButton';
import { useAuth } from '../context/AuthContext';
import { Brand, ThemeToggle } from '../lib/ui';
import { homeFor } from '../lib/paths';
import { ApiError, errMsg } from '../services';

/**
 * Login page.
 *  Step 1: username + password  → POST /accounts/login/
 *    - tokens returned  → profile is loaded and the user is sent to the dashboard of their role
 *    - mfa_required     → show the authenticator form (NOT logged in yet)
 *  Step 2: challenge + 6-digit code → POST /accounts/login/
 */
export default function Login() {
  const { user, login, verifyMfa, googleLogin } = useAuth();
  const registered = (useLocation().state as { registered?: boolean } | null)?.registered === true;

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errs, setErrs] = useState<{ username?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const [mfa, setMfa] = useState<{ challenge: string; detail: string; qrCode?: string; isSetup?: boolean } | null>(null);
  const [mfaError, setMfaError] = useState('');

  // Already signed in → redirect
  if (user) return <Navigate to={homeFor(user.role)} replace />;

  // ── Password login ────────────────────────────────────────────────────────
  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (busy) return;
    const name = username.trim();
    const e: typeof errs = {};
    if (!name) e.username = 'Enter your email or username.';
    if (!password) e.password = 'Enter your password.';
    setErrs(e);
    if (Object.keys(e).length) return;

    setBusy(true);
    try {
      const r = await login(name.includes('@') ? name.toLowerCase() : name, password);
      if (r.kind === 'mfa') {
        setMfa({
          challenge: r.challenge,
          detail: r.detail,
          qrCode: r.qrCode,
          isSetup: r.isSetup,
        });
        setMfaError('');
      }
    } catch (x) {
      setErrs({ form: errMsg(x) });
    } finally { setBusy(false); }
  };

  const submitCode = async (code: string) => {
    if (!mfa) return;
    setBusy(true); setMfaError('');
    try {
      await verifyMfa(mfa.challenge, code);
    } catch (x) {
      const m = errMsg(x);
      if (x instanceof ApiError && (x.status === 429 || /challenge/i.test(m))) {
        setMfa(null); setPassword(''); setErrs({ form: m });
      } else {
        setMfaError(m);
      }
    } finally { setBusy(false); }
  };

  return (
    <div className="au" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 16, right: 16 }}><ThemeToggle /></div>
      <Link className="lg" to="/"><Brand /></Link>

      {mfa ? (
        <MfaChallengeForm
          detail={mfa.detail}
          qrCode={mfa.qrCode}
          isSetup={mfa.isSetup}
          busy={busy}
          error={mfaError}
          onSubmit={submitCode}
          onBack={() => { setMfa(null); setPassword(''); setMfaError(''); }}
        />
      ) : (
        <form className="card" onSubmit={submit} noValidate>
          <h1>Welcome back</h1>
          <p className="mu">Sign in to verify and manage certificates.</p>
          {registered && <div className="bn" role="status">Account created. Please sign in.</div>}
          <Field id="username" label="Email or username" value={username} onChange={setUsername} error={errs.username} autoComplete="username" />
          <Field id="pw" label="Password" type="password" value={password} onChange={setPassword} error={errs.password} autoComplete="current-password" />
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4, marginBottom: 2 }}>
            <Link to="/forgot-password" style={{ fontSize: '13px', textDecoration: 'none' }}>
              Forgot Password?
            </Link>
          </div>
          {errs.form && <p className="fe" role="alert">{errs.form}</p>}
          <button className="btn" style={{ width: '100%', marginTop: 14 }} disabled={busy}>{busy ? 'Please wait…' : 'Sign in'}</button>

          <div style={{ display: 'flex', alignItems: 'center', margin: '16px 0 10px 0' }}>
            <div style={{ flex: 1, borderTop: '1px solid var(--border, #e2e8f0)' }} />
            <span style={{ padding: '0 10px', fontSize: '11px', color: 'var(--muted, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              or continue with
            </span>
            <div style={{ flex: 1, borderTop: '1px solid var(--border, #e2e8f0)' }} />
          </div>

          <GoogleSignInButton
            disabled={busy}
            text="signin_with"
            onSuccess={async (cred) => {
              setBusy(true);
              try {
                await googleLogin(cred);
              } catch (x) {
                setErrs({ form: errMsg(x) });
              } finally {
                setBusy(false);
              }
            }}
            onError={(msg) => setErrs({ form: msg })}
          />

          <p className="mu" style={{ textAlign: 'center', marginTop: 16 }}>
            New here? <Link to="/register">Create account</Link> · <Link to="/">Home</Link>
          </p>
        </form>
      )}
    </div>
  );
}
