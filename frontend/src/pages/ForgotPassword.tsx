import { useState, useEffect, type FormEvent } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { KeyRound, CheckCircle2, ArrowLeft, Mail, RefreshCw, ShieldAlert, AlertCircle } from 'lucide-react';
import Field from '../components/Field';
import { useAuth } from '../context/AuthContext';
import { Brand, ThemeToggle } from '../lib/ui';
import { homeFor } from '../lib/paths';
import { passwordResetService, errMsg } from '../services';

type Step = 'email' | 'requested' | 'otp' | 'validating' | 'invalid_token' | 'password' | 'success';

export default function ForgotPassword() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get('token') || '';

  // Multi-step workflow state
  const [step, setStep] = useState<Step>(tokenFromUrl ? 'validating' : 'email');

  // Step 1: Email state
  const [email, setEmail] = useState('');
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');

  // Token validation state
  const [tokenError, setTokenError] = useState('');
  const [resendCooldown, setResendCooldown] = useState(60);
  const [resendBusy, setResendBusy] = useState(false);

  // Step 3: Password state
  const [resetToken, setResetToken] = useState(tokenFromUrl);
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordErrors, setPasswordErrors] = useState<{ password?: string; confirm?: string; form?: string }>({});

  // When tokenFromUrl is present, validate token with backend immediately
  useEffect(() => {
    if (!tokenFromUrl) return;

    let isMounted = true;
    setStep('validating');
    setTokenError('');

    passwordResetService
      .validateToken(tokenFromUrl)
      .then(res => {
        if (!isMounted) return;
        if (res.valid) {
          setResetToken(tokenFromUrl);
          setStep('password');
        } else {
          setTokenError(res.detail || 'This password reset link is invalid, expired, or has already been used.');
          setStep('invalid_token');
        }
      })
      .catch(err => {
        if (!isMounted) return;
        setTokenError(errMsg(err));
        setStep('invalid_token');
      });

    return () => {
      isMounted = false;
    };
  }, [tokenFromUrl]);

  // Cooldown countdown for resending reset link/code
  useEffect(() => {
    if (step !== 'requested' && step !== 'otp') return;
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown(prev => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [step, resendCooldown]);

  // If already logged in, redirect to user dashboard
  if (user) {
    return <Navigate to={homeFor(user.role)} replace />;
  }

  // --- Step 1: Request Password Reset Link ---
  const handleRequestSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setEmailError('Enter a valid registered email address.');
      return;
    }

    setEmailBusy(true);
    setEmailError('');
    try {
      const msg = await passwordResetService.requestReset(cleanEmail);
      setInfoMessage(msg);
      setResendCooldown(60);
      setStep('requested');
    } catch (err) {
      setEmailError(errMsg(err));
    } finally {
      setEmailBusy(false);
    }
  };

  // --- Resend link handler ---
  const handleResendLink = async () => {
    if (resendCooldown > 0 || resendBusy) return;
    const cleanEmail = email.trim().toLowerCase();
    setResendBusy(true);
    setEmailError('');
    try {
      const msg = await passwordResetService.requestReset(cleanEmail);
      setInfoMessage(msg);
      setResendCooldown(60);
    } catch (err) {
      setEmailError(errMsg(err));
    } finally {
      setResendBusy(false);
    }
  };

  // --- Step 3: Complete Password Reset ---
  const handlePasswordSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const errors: typeof passwordErrors = {};

    if (!password) {
      errors.password = 'Enter your new password.';
    } else if (password.length < 8) {
      errors.password = 'Password must be at least 8 characters long.';
    }

    if (!passwordConfirm) {
      errors.confirm = 'Confirm your new password.';
    } else if (password !== passwordConfirm) {
      errors.confirm = 'Passwords do not match.';
    }

    setPasswordErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setPasswordBusy(true);
    try {
      await passwordResetService.completeReset(resetToken, password, passwordConfirm);
      setStep('success');
    } catch (err) {
      setPasswordErrors({ form: errMsg(err) });
    } finally {
      setPasswordBusy(false);
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

      {/* VALIDATING TOKEN IN URL */}
      {step === 'validating' && (
        <div className="card w-full max-w-md mx-auto text-center py-8">
          <div className="w-8 h-8 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs text-slate-600 dark:text-slate-300">Validating password reset link…</p>
        </div>
      )}

      {/* INVALID OR EXPIRED TOKEN */}
      {step === 'invalid_token' && (
        <div className="card w-full max-w-md mx-auto text-left">
          <div className="flex items-center gap-2.5 mb-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-600 flex items-center justify-center flex-shrink-0">
              <AlertCircle className="w-6 h-6 text-rose-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
                Invalid or Expired Link
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Password reset link cannot be used
              </p>
            </div>
          </div>

          <div className="p-3.5 my-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 text-xs leading-relaxed">
            {tokenError ||
              'This password reset link is invalid, expired, or has already been used. Please request a new link.'}
          </div>

          <div className="space-y-2 mt-4">
            <button
              type="button"
              onClick={() => {
                setStep('email');
                setEmail('');
                setTokenError('');
              }}
              className="btn w-full"
              style={{ width: '100%' }}
            >
              Request a New Reset Link
            </button>
            <div className="text-center pt-2">
              <Link to="/login" className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 inline-flex items-center gap-1">
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Sign In</span>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* STEP 1: Enter Email */}
      {step === 'email' && (
        <form className="card w-full max-w-md mx-auto text-left" onSubmit={handleRequestSubmit} noValidate>
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center flex-shrink-0">
              <KeyRound className="w-6 h-6 text-teal-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
                Forgot Password
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Receive a secure reset link at your registered email
              </p>
            </div>
          </div>

          <p className="text-xs text-slate-600 dark:text-slate-300 mt-2 mb-3 leading-relaxed">
            Enter the email address registered with your OneSmarter CertiVerify account. We will send a secure single-use password reset link.
          </p>

          <Field
            id="reset-email"
            label="Registered Email Address"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@example.com"
            autoComplete="email"
            error={emailError}
          />

          <button
            type="submit"
            disabled={emailBusy}
            className="btn w-full mt-3"
            style={{ width: '100%' }}
          >
            <span>{emailBusy ? 'Sending reset link…' : 'Send Reset Link'}</span>
          </button>

          <p className="mu" style={{ textAlign: 'center', marginTop: 16 }}>
            Remembered your password? <Link to="/login">Back to Sign In</Link>
          </p>
        </form>
      )}

      {/* STEP 2: Request Submitted / Email Sent */}
      {step === 'requested' && (
        <div className="card w-full max-w-md mx-auto text-left">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center flex-shrink-0">
              <Mail className="w-6 h-6 text-teal-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
                Reset Link Sent
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Check your inbox to choose a new password
              </p>
            </div>
          </div>

          <div className="p-4 my-3 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200 flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-teal-600 dark:text-teal-400 flex-shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <p className="font-semibold text-sm text-teal-950 dark:text-teal-100">
                Password Reset Instructions Dispatched
              </p>
              <p className="text-teal-800 dark:text-teal-300 leading-relaxed">
                {infoMessage ||
                  'If an account with that email exists, a password reset link has been sent to your email address.'}
              </p>
              <p className="text-teal-700 dark:text-teal-400 text-[11px] mt-2">
                The link expires after <strong>15 minutes</strong> and can only be used once. Please check your spam folder if you do not see it.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 text-xs">
            <button
              type="button"
              onClick={() => {
                setStep('email');
                setEmail('');
                setEmailError('');
              }}
              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline"
            >
              Send to a different email
            </button>
            <button
              type="button"
              disabled={resendCooldown > 0 || resendBusy}
              onClick={handleResendLink}
              className="text-teal-600 dark:text-teal-400 font-medium disabled:opacity-50 inline-flex items-center gap-1 hover:underline"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${resendBusy ? 'animate-spin' : ''}`} />
              <span>{resendCooldown > 0 ? `Resend email (${resendCooldown}s)` : 'Resend email'}</span>
            </button>
          </div>

          <div className="text-center pt-3">
            <Link to="/login" className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 inline-flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Sign In</span>
            </Link>
          </div>
        </div>
      )}

      {/* STEP 3: Enter New Password */}
      {step === 'password' && (
        <form className="card w-full max-w-md mx-auto text-left" onSubmit={handlePasswordSubmit} noValidate>
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center flex-shrink-0">
              <KeyRound className="w-6 h-6 text-teal-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
                Set New Password
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Choose and confirm your new credentials
              </p>
            </div>
          </div>

          <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 mb-3 leading-relaxed">
            Enter and confirm your new password below. Ensure it is at least 8 characters long and contains a mix of letters and numbers.
          </p>

          <Field
            id="new-password"
            label="New Password"
            type="password"
            value={password}
            onChange={setPassword}
            error={passwordErrors.password}
            autoComplete="new-password"
          />

          <Field
            id="confirm-password"
            label="Confirm New Password"
            type="password"
            value={passwordConfirm}
            onChange={setPasswordConfirm}
            error={passwordErrors.confirm}
            autoComplete="new-password"
          />

          {passwordErrors.form && (
            <p className="fe" role="alert" style={{ marginTop: 6 }}>
              {passwordErrors.form}
            </p>
          )}

          <button
            type="submit"
            disabled={passwordBusy}
            className="btn w-full mt-4"
            style={{ width: '100%' }}
          >
            <span>{passwordBusy ? 'Updating Password…' : 'Save Password'}</span>
          </button>

          <div className="text-center pt-3">
            <Link to="/login" className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 inline-flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Sign In</span>
            </Link>
          </div>
        </form>
      )}

      {/* STEP 4: Reset Success */}
      {step === 'success' && (
        <div className="card w-full max-w-md mx-auto text-left">
          <div className="text-center py-4 space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-teal-500/10 text-teal-600 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8 text-teal-600" />
            </div>

            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              Password Changed Successfully
            </h1>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed max-w-xs mx-auto">
              Your OneSmarter CertiVerify account password has been updated. You can now sign in using your new password.
            </p>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-left text-xs space-y-1.5">
              <p className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-teal-600 flex-shrink-0" />
                <span>Security Notice</span>
              </p>
              <p className="text-slate-600 dark:text-slate-400 leading-normal">
                If Two-Factor Authentication (Google / Microsoft Authenticator) is enabled on your account, your authenticator OTP code will still be required when signing in.
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
