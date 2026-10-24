import { useState, useEffect, useRef, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { MailCheck, CheckCircle2, AlertCircle, ArrowRight } from 'lucide-react';
import Field from '../components/Field';
import { useAuth } from '../context/AuthContext';
import { Brand, ThemeToggle, toast } from '../lib/ui';
import { homeFor } from '../lib/paths';
import { errMsg } from '../services';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const go = useNavigate();
  const { user, verifyEmail, resendVerification } = useAuth();

  const queryEmail = searchParams.get('email') || '';
  const queryToken = searchParams.get('token') || '';
  const queryOtp = searchParams.get('otp') || '';

  const [email, setEmail] = useState(queryEmail || user?.email || '');
  const [otp, setOtp] = useState(queryOtp);
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ message: string; count: number } | null>(null);
  const autoVerifyStarted = useRef<string | null>(null);

  // Auto-verify if token is present in query parameters
  useEffect(() => {
    if (queryToken && autoVerifyStarted.current !== queryToken) {
      autoVerifyStarted.current = queryToken;
      setBusy(true);
      verifyEmail({ token: queryToken })
        .then(res => {
          setSuccess({
            message: res.detail,
            count: res.claimedCount,
          });
          toast(
            res.claimedCount > 0
              ? `Email verified! ${res.claimedCount} certificate(s) linked to your account.`
              : 'Email verified successfully!'
          );
        })
        .catch(err => {
          setError(errMsg(err));
        })
        .finally(() => setBusy(false));
    }
  }, [queryToken]);

  const handleSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (busy) return;
    const cleanEmail = email.trim().toLowerCase();
    const cleanOtp = otp.trim();

    if (!cleanEmail && !user) {
      setError('Please enter your email address.');
      return;
    }
    if (!/^\d{6}$/.test(cleanOtp)) {
      setError('Please enter the 6-digit verification code.');
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const res = await verifyEmail({ email: cleanEmail || user?.email, otp: cleanOtp });
      setSuccess({
        message: res.detail,
        count: res.claimedCount,
      });
      toast(
        res.claimedCount > 0
          ? `Email verified! ${res.claimedCount} certificate(s) linked to your account.`
          : 'Email verified successfully!'
      );
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    const cleanEmail = email.trim().toLowerCase() || user?.email;
    if (!cleanEmail) {
      setError('Enter your email address first to request a code.');
      return;
    }
    setResending(true);
    setError(null);
    try {
      const msg = await resendVerification(cleanEmail);
      toast(msg);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setResending(false);
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

      <div className="card">
        {success ? (
          <div className="text-center py-4 space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center">
              <CheckCircle2 className="w-7 h-7" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">Email Verified!</h1>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              {success.message}
            </p>
            {success.count > 0 && (
              <div className="p-3 bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 rounded-xl text-teal-800 dark:text-teal-300 text-xs font-semibold">
                🎉 {success.count} certificate{success.count > 1 ? 's' : ''} successfully linked to your account!
              </div>
            )}
            <div className="pt-2">
              <button
                type="button"
                onClick={() => go(user ? homeFor(user.role) : '/login', { state: { verified: true } })}
                className="btn inline-flex items-center justify-center gap-2"
                style={{ width: '100%' }}
              >
                <span>{user ? 'Go to Dashboard' : 'Sign in to Your Account'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            <div className="text-center mb-6">
              <div className="w-12 h-12 rounded-full bg-teal-100 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 mx-auto flex items-center justify-center mb-3">
                <MailCheck className="w-6 h-6" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">Verify Your Email</h1>
              <p className="mu text-xs mt-1">
                Enter the 6-digit code sent to your inbox to verify your email and link your issued certificates.
              </p>
            </div>

            {!user && (
              <Field
                id="email"
                label="Registered Email"
                type="email"
                value={email}
                onChange={setEmail}
                autoComplete="email"
              />
            )}

            <Field
              id="otp"
              label="6-Digit Verification Code"
              type="text"
              value={otp}
              onChange={value => setOtp(value.replace(/\D/g, '').slice(0, 6))}
              placeholder="e.g. 123456"
              autoComplete="one-time-code"
              inputMode="numeric"
              maxLength={6}
            />

            {error && (
              <div className="p-3 mb-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 flex items-center gap-2 text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              className="btn"
              style={{ width: '100%', marginTop: 14 }}
              disabled={busy || !/^\d{6}$/.test(otp)}
            >
              {busy ? 'Verifying…' : 'Verify & Claim Certificates'}
            </button>

            <div className="flex items-center justify-between mt-4 text-xs">
              <button
                type="button"
                onClick={handleResend}
                disabled={resending}
                className="text-teal-600 dark:text-teal-400 hover:underline disabled:opacity-50"
              >
                {resending ? 'Sending code…' : "Didn't receive a code? Resend"}
              </button>
              <Link to="/login" className="text-slate-500 hover:underline">
                Sign in
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
