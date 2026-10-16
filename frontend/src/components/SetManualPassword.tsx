import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { KeyRound, CheckCircle2, AlertCircle, Mail, User as UserIcon, ShieldAlert, ArrowRight } from 'lucide-react';
import Field from './Field';
import { toast } from '../lib/ui';
import { errMsg } from '../services';

export default function SetManualPassword() {
  const { user, setPassword } = useAuth();
  const navigate = useNavigate();

  const [password, setLocalPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const score =
    (password.length >= 8 ? 1 : 0) +
    (/[a-z]/i.test(password) && /\d/.test(password) ? 1 : 0) +
    (password.length >= 12 ? 1 : 0);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!password) {
      setError('Please enter a new password.');
      return;
    }
    if (password.length < 8 || !/[a-z]/i.test(password) || !/\d/.test(password)) {
      setError('Password must contain at least 8 characters with letters and numbers.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setBusy(true);
    try {
      await setPassword(password, confirmPassword);
      setSuccess(true);
      setLocalPassword('');
      setConfirmPassword('');
      toast('Manual password set successfully. You can now log in using your password.');
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const hasPassword = user?.hasUsablePassword === true;
  const profilePath = user?.role === 'admin' ? '/admin/dashboard/profile' : '/user/dashboard/profile';

  return (
    <div
      id="set-password"
      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm text-left"
    >
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-teal-600 dark:text-teal-400" />
            <span>Set Up Manual Password</span>
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Create a local password for your account so you can sign in directly using your username or email
            in addition to Google Sign-In.
          </p>
        </div>
      </div>

      {hasPassword && !success && (
        <div className="mb-6 p-4 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200 flex items-start gap-3 text-xs">
          <CheckCircle2 className="w-5 h-5 text-teal-600 dark:text-teal-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-2">
            <p className="font-bold text-sm text-teal-950 dark:text-teal-100">
              Manual Password Is Active
            </p>
            <p className="text-teal-800 dark:text-teal-300 leading-relaxed">
              A manual password is configured for this account. You can sign in using your registered email/username
              and your password. If you ever need to change your password, please use the Forgot Password workflow from the login page.
            </p>
            <div className="pt-1">
              <button
                type="button"
                onClick={() => navigate(profilePath)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-medium text-xs transition"
              >
                <span>Return to Profile Settings</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200 flex items-start gap-3 text-xs">
          <CheckCircle2 className="w-5 h-5 text-teal-600 dark:text-teal-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-2">
            <p className="font-bold text-sm text-teal-950 dark:text-teal-100">
              Password Configured Successfully!
            </p>
            <p className="text-teal-800 dark:text-teal-300 leading-relaxed">
              Your manual password has been securely saved to the database. You can now use your registered
              email or username with this password to sign in.
            </p>
            <div className="pt-1">
              <button
                type="button"
                onClick={() => navigate(profilePath)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white font-medium text-xs transition"
              >
                <span>Return to Profile Settings</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 flex items-center gap-2.5 text-xs font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!hasPassword && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Read-only account username */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                Registered Username
              </label>
              <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm">
                <UserIcon className="w-4 h-4 text-slate-400" />
                <span>{user?.username || '—'}</span>
              </div>
            </div>

            {/* Read-only account email */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                Registered Email Address
              </label>
              <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm">
                <Mail className="w-4 h-4 text-slate-400" />
                <span>{user?.email || '—'}</span>
              </div>
            </div>
          </div>

          <div className="pt-2">
            <Field
              id="new-manual-password"
              label="New Password"
              type="password"
              value={password}
              onChange={setLocalPassword}
              autoComplete="new-password"
              placeholder="Enter at least 8 characters"
            />
            <div className="pm" style={{ marginTop: 8 }}>
              <i style={{ width: `${score * 33.3}%` }} />
            </div>
            <p className="n" style={{ fontSize: '11px', marginTop: 4 }}>
              At least 8 characters, with letters and numbers.
            </p>
          </div>

          <div>
            <Field
              id="confirm-manual-password"
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              autoComplete="new-password"
              placeholder="Re-enter your new password"
            />
          </div>

          <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-xs flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <span>
              Note: Once your manual password is set, future password logins will require two-factor authenticator
              app enrollment/verification. Google Sign-In will continue to work directly.
            </span>
          </div>

          <div className="flex justify-end pt-3 border-t border-slate-200 dark:border-slate-800">
            <button
              type="submit"
              disabled={busy || !password || !confirmPassword}
              className="btn"
              style={{ minWidth: 160 }}
            >
              {busy ? 'Setting Password…' : 'Set Password'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
