import { useEffect, useState, type FormEvent } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { ShieldAlert, ShieldCheck, QrCode, ArrowLeft, CheckCircle2 } from 'lucide-react';
import Field from '../components/Field';
import { useAuth } from '../context/AuthContext';
import { Brand, ThemeToggle } from '../lib/ui';
import { homeFor } from '../lib/paths';
import { mfaService, errMsg } from '../services';

export default function MfaRecovery() {
  const { user, recoverMfa } = useAuth();
  const [searchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get('token') || '';

  // Mode: 'request' (enter email), 'confirm' (scan QR and enter code), or 'success'
  const [mode, setMode] = useState<'request' | 'confirm' | 'success'>(tokenFromUrl ? 'confirm' : 'request');

  // Request state
  const [email, setEmail] = useState('');
  const [requestSent, setRequestSent] = useState(false);
  const [requestMessage, setRequestMessage] = useState('');
  const [requestBusy, setRequestBusy] = useState(false);
  const [requestError, setRequestError] = useState('');

  // Confirm state
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(Boolean(tokenFromUrl));
  const [confirmError, setConfirmError] = useState('');
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [challenge, setChallenge] = useState('');
  const [code, setCode] = useState('');
  const [codeError, setCodeError] = useState('');

  // When tokenFromUrl is present, validate token and fetch new QR code.
  // All hooks MUST be declared before any early return (Rules of Hooks).
  useEffect(() => {
    if (!tokenFromUrl) return;

    let isMounted = true;
    setConfirmLoading(true);
    setConfirmError('');

    mfaService
      .confirmRecovery(tokenFromUrl)
      .then(res => {
        if (!isMounted) return;
        setQrCode(res.qr);
        setSecret(res.secret);
        setChallenge(res.challenge);
        setMode('confirm');
      })
      .catch(err => {
        if (!isMounted) return;
        setConfirmError(errMsg(err));
        setMode('confirm');
      })
      .finally(() => {
        if (isMounted) setConfirmLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [tokenFromUrl]);

  // If already authenticated, redirect to role home (AFTER all hooks)
  if (user) {
    return <Navigate to={homeFor(user.role)} replace />;
  }

  const handleRequestSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setRequestError('Enter a valid registered email address.');
      return;
    }

    setRequestBusy(true);
    setRequestError('');
    try {
      const msg = await mfaService.requestRecovery(cleanEmail.toLowerCase());
      setRequestMessage(msg);
      setRequestSent(true);
    } catch (err) {
      setRequestError(errMsg(err));
    } finally {
      setRequestBusy(false);
    }
  };

  const handleCompleteSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (confirmBusy) return;
    if (!/^\d{6}$/.test(code.trim())) {
      setCodeError('Enter the six-digit code from your authenticator app.');
      return;
    }

    setCodeError('');
    setConfirmBusy(true);
    try {
      // Re-enrolls authenticator and completes recovery
      await recoverMfa(challenge, code.trim());
      setMode('success');
    } catch (err) {
      setCodeError(errMsg(err));
    } finally {
      setConfirmBusy(false);
    }
  };

  return (
    <div className="au" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 16, right: 16 }}>
        <ThemeToggle />
      </div>
      <Link className="lg" to="/">
        <Brand />
      </Link>

      {mode === 'request' && (
        <form className="card w-full max-w-md mx-auto text-left" onSubmit={handleRequestSubmit} noValidate>
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center flex-shrink-0">
              <ShieldAlert className="w-6 h-6 text-teal-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
                MFA Account Recovery
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Restore access if you lost your authenticator device
              </p>
            </div>
          </div>

          {requestSent ? (
            <div className="space-y-4 my-4">
              <div className="p-4 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-teal-600 dark:text-teal-400 flex-shrink-0 mt-0.5" />
                <div className="text-xs space-y-1">
                  <p className="font-semibold text-sm text-teal-950 dark:text-teal-100">
                    Recovery Instructions Dispatched
                  </p>
                  <p className="text-teal-800 dark:text-teal-300 leading-relaxed">
                    {requestMessage ||
                      'If an account with that email exists, an MFA recovery link has been sent to your email address.'}
                  </p>
                  <p className="text-teal-700 dark:text-teal-400 text-[11px] mt-2">
                    Please check your inbox (and spam folder) and open the secure recovery link within 15 minutes.
                  </p>
                </div>
              </div>

              <div className="pt-2 text-center space-y-2">
                <button
                  type="button"
                  onClick={() => {
                    setRequestSent(false);
                    setEmail('');
                    setRequestError('');
                  }}
                  className="text-xs text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 underline block mx-auto"
                >
                  Send to a different email address
                </button>
                <Link
                  to="/login"
                  className="text-xs font-semibold text-teal-600 hover:text-teal-700 dark:text-teal-400 inline-flex items-center gap-1.5"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to Sign In</span>
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-3 mt-3">
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                Enter the email address registered with your account. We will send a secure single-use link allowing
                you to enroll a new Google Authenticator or Microsoft Authenticator app.
              </p>

              <Field
                id="recovery-email"
                label="Registered Email Address"
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@example.com"
                autoComplete="email"
                error={requestError}
              />

              <button
                type="submit"
                disabled={requestBusy}
                className="btn w-full mt-2"
                style={{ width: '100%' }}
              >
                <span>{requestBusy ? 'Sending link…' : 'Send Recovery Link'}</span>
              </button>

              <p className="mu" style={{ textAlign: 'center', marginTop: 16 }}>
                Remembered your authenticator? <Link to="/login">Back to Sign in</Link>
              </p>
            </div>
          )}
        </form>
      )}

      {/* Mode: Confirm and Re-enroll */}
      {mode === 'confirm' && (
        <div className="card w-full max-w-md mx-auto text-left">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center flex-shrink-0">
              <ShieldCheck className="w-6 h-6 text-teal-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
                Re-enroll Authenticator
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Set up a new authenticator to complete account recovery
              </p>
            </div>
          </div>

          {confirmLoading ? (
            <div className="py-8 text-center text-xs text-slate-500 dark:text-slate-400 space-y-2">
              <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p>Validating recovery link…</p>
            </div>
          ) : confirmError ? (
            <div className="space-y-4 my-3">
              <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 text-xs">
                {confirmError}
              </div>
              <div className="text-center space-y-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setMode('request');
                    setConfirmError('');
                  }}
                  className="btn w-full"
                  style={{ width: '100%' }}
                >
                  Request a New Recovery Link
                </button>
                <Link
                  to="/login"
                  className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline block pt-2"
                >
                  ← Back to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleCompleteSubmit} className="space-y-4 mt-3" noValidate>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                Scan this new QR code with Google Authenticator or Microsoft Authenticator, then enter the 6-digit code
                below to re-activate two-factor authentication.
              </p>

              {qrCode && (
                <div className="my-3 p-4 bg-white rounded-2xl border border-slate-200 text-center shadow-sm w-fit mx-auto">
                  <img
                    src={qrCode}
                    alt="New Authenticator QR Code"
                    className="w-48 h-48 mx-auto rounded-lg object-contain"
                  />
                  <p className="text-[11px] text-slate-500 font-medium mt-2 flex items-center justify-center gap-1.5">
                    <QrCode className="w-3.5 h-3.5 text-slate-400" />
                    <span>Scan in Google or Microsoft Authenticator</span>
                  </p>
                </div>
              )}

              {secret && (
                <div className="text-center p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                    Manual Entry Key
                  </p>
                  <p className="font-mono text-xs text-slate-800 dark:text-slate-200 font-semibold tracking-wider select-all mt-0.5">
                    {secret}
                  </p>
                </div>
              )}

              <div className="space-y-1.5">
                <label
                  htmlFor="recovery-otp"
                  className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
                >
                  6-Digit Authenticator Code
                </label>
                <input
                  id="recovery-otp"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  autoFocus
                  className="w-full font-mono text-center tracking-widest text-2xl px-4 py-3 bg-slate-50 dark:bg-slate-800/90 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 shadow-inner"
                />
                {codeError && (
                  <p className="text-xs text-rose-600 font-medium" role="alert">
                    {codeError}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={confirmBusy || code.trim().length !== 6}
                className="btn w-full"
                style={{ width: '100%' }}
              >
                <span>{confirmBusy ? 'Verifying & Re-enrolling…' : 'Confirm & Activate Authenticator'}</span>
              </button>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline"
                >
                  ← Back to Sign In
                </Link>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Mode: Recovery Success */}
      {mode === 'success' && (
        <div className="card w-full max-w-md mx-auto text-left">
          <div className="text-center py-4 space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-teal-500/10 text-teal-600 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8 text-teal-600" />
            </div>

            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              Authenticator Re-enrolled Successfully
            </h1>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed max-w-xs mx-auto">
              Your multi-factor authentication enrollment has been restored. You can now sign in using your account credentials and your new authenticator app.
            </p>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-left text-xs space-y-1.5">
              <p className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-teal-600 flex-shrink-0" />
                <span>Two-Factor Authentication Active</span>
              </p>
              <p className="text-slate-600 dark:text-slate-400 leading-normal">
                Next time you sign in, enter your registered email and password, then supply the 6-digit code generated by your newly configured authenticator app.
              </p>
            </div>

            <Link
              to="/login"
              className="btn w-full inline-flex mt-2"
              style={{ width: '100%' }}
            >
              Back to Sign In
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
