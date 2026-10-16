import { useState, useCallback, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import Field from '../components/Field';
import MfaChallengeForm from '../components/MfaChallengeForm';
import GoogleSignInButton from '../components/GoogleSignInButton';
import LoadingScreen from '../components/LoadingScreen';
import { useAuth } from '../context/AuthContext';
import { Brand, ThemeToggle } from '../lib/ui';
import { homeFor } from '../lib/paths';
import { ApiError, errMsg, tokens } from '../services';

/**
 * Login page.
 *  Step 1: username + password  → POST /accounts/login/
 *    - tokens returned  → profile is loaded and the user is sent to the dashboard of their role
 *    - mfa_required     → show the authenticator form (NOT logged in yet)
 *  Step 2: challenge + 6-digit code → POST /accounts/login/
 */
export default function Login() {
  const { user, loading, login, verifyMfa, googleLogin } = useAuth();
  const navigate = useNavigate();
  const locState = (useLocation().state as { registered?: boolean; verified?: boolean; message?: string } | null);
  const registered = locState?.registered === true;
  const verified = locState?.verified === true;
  const infoMsg = locState?.message;

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errs, setErrs] = useState<{ username?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const [mfa, setMfa] = useState<{ challenge: string; detail: string; qrCode?: string; secret?: string; isSetup?: boolean } | null>(null);
  const [mfaError, setMfaError] = useState('');

  // While restoring an existing stored session, show loading screen to prevent UI flash
  if (loading && tokens.has()) return <LoadingScreen />;

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
          secret: r.secret,
          isSetup: r.isSetup,
        });
        setMfaError('');
      } else if (r.kind === 'success') {
        navigate(homeFor(r.user.role), { replace: true });
      }
    } catch (x) {
      setErrs({ form: errMsg(x) });
    } finally { setBusy(false); }
  };

  const submitCode = async (code: string) => {
    if (!mfa) return;
    setBusy(true); setMfaError('');
    try {
      const u = await verifyMfa(mfa.challenge, code);
      navigate(homeFor(u.role), { replace: true });
    } catch (x) {
      const m = errMsg(x);
      if (x instanceof ApiError && (x.status === 429 || /challenge/i.test(m))) {
        setMfa(null); setPassword(''); setErrs({ form: m });
      } else {
        setMfaError(m);
      }
    } finally { setBusy(false); }
  };

  const handleGoogleSuccess = useCallback(async (cred: string) => {
    setBusy(true);
    try {
      const u = await googleLogin(cred);
      navigate(homeFor(u.role), { replace: true });
    } catch (x) {
      setErrs({ form: errMsg(x) });
    } finally {
      setBusy(false);
    }
  }, [googleLogin, navigate]);

  const handleGoogleError = useCallback((msg: string) => {
    setErrs({ form: msg });
  }, []);

  return (
    <div className="au" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 16, right: 16 }}><ThemeToggle /></div>
      <Link className="lg" to="/"><Brand /></Link>

      {mfa ? (
        <MfaChallengeForm
          detail={mfa.detail}
          qrCode={mfa.qrCode}
          secret={mfa.secret}
          isSetup={mfa.isSetup}
          busy={busy}
          error={mfaError}
          onSubmit={submitCode}
          onBack={() => { setMfa(null); setPassword(''); setMfaError(''); }}
        />
      ) : (
        <form className="card" onSubmit={submit} noValidate>
          <h1>Welcome back</h1>
          {registered && (
            <div className="bn" role="status">
              {infoMsg || 'Account created successfully! Please sign in to complete two-factor authentication setup.'}
            </div>
          )}
          {verified && (
            <div
              className="bn"
              style={{
                background: 'color-mix(in srgb, var(--ok, #34D399) 15%, transparent)',
                color: 'var(--ok, #34D399)',
                border: '1px solid color-mix(in srgb, var(--ok, #34D399) 30%, transparent)',
              }}
              role="status"
            >
              Email verified successfully! Please sign in.
            </div>
          )}
          {infoMsg && !registered && !verified && <div className="bn" role="status">{infoMsg}</div>}
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
            <div style={{ flex: 1, borderTop: '1px solid var(--bd, #1F2D45)' }} />
            <span style={{ padding: '0 10px', fontSize: '11px', color: 'var(--t2, #9FB0C8)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              or continue with
            </span>
            <div style={{ flex: 1, borderTop: '1px solid var(--bd, #1F2D45)' }} />
          </div>

          <GoogleSignInButton
            disabled={busy}
            text="signin_with"
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
          />

          <p className="mu" style={{ textAlign: 'center', marginTop: 16 }}>
            New here? <Link to="/register">Create account</Link> · <Link to="/">Home</Link>
          </p>
        </form>
      )}
    </div>
  );
}
