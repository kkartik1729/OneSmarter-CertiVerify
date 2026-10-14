import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, QrCode } from 'lucide-react';

interface Props {
  detail: string;
  qrCode?: string;
  isSetup?: boolean;
  busy: boolean;
  error: string;
  onSubmit: (code: string) => void;
  onBack: () => void;
}

/** Login step 2: Google / Microsoft Authenticator QR setup or 6-digit TOTP verification. */
export default function MfaChallengeForm({ detail, qrCode, isSetup, busy, error, onSubmit, onBack }: Props) {
  const [code, setCode] = useState('');
  const [local, setLocal] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    if (!/^\d{6}$/.test(code.trim())) {
      return setLocal('Enter the six-digit code from Google or Microsoft Authenticator.');
    }
    setLocal('');
    onSubmit(code.trim());
  };

  return (
    <form className="card w-full max-w-md mx-auto text-left" onSubmit={submit} noValidate>
      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center flex-shrink-0">
          <ShieldCheck className="w-6 h-6 text-teal-600" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
            {isSetup || qrCode ? 'Set Up Authenticator App' : 'Two-Factor Authentication'}
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {isSetup || qrCode ? 'Step 2 of 2: Security Enrollment' : 'Step 2 of 2: Identity Verification'}
          </p>
        </div>
      </div>

      <p className="text-xs text-slate-600 dark:text-slate-300 mt-2 mb-4 leading-relaxed">
        {detail || (isSetup || qrCode
          ? 'Scan this QR code with Google Authenticator or Microsoft Authenticator, then enter the 6-digit code to complete login.'
          : 'Enter the six-digit code from Google Authenticator or Microsoft Authenticator to access your dashboard.')}
      </p>

      {qrCode && (
        <div className="my-4 p-4 bg-white rounded-2xl border border-slate-200 text-center shadow-sm w-fit mx-auto">
          <img
            src={qrCode}
            alt="Authenticator Provisioning QR Code"
            className="w-48 h-48 mx-auto rounded-lg object-contain"
          />
          <p className="text-[11px] text-slate-500 font-medium mt-2 flex items-center justify-center gap-1.5">
            <QrCode className="w-3.5 h-3.5 text-slate-400" />
            <span>Scan with Google Authenticator or Microsoft Authenticator</span>
          </p>
        </div>
      )}

      <div className="space-y-1.5 my-3">
        <label
          htmlFor="mfa-code"
          className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
        >
          6-Digit Authenticator Code
        </label>
        <input
          id="mfa-code"
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
        {local && <p className="text-xs text-rose-600 font-medium" role="alert">{local}</p>}
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 text-xs font-medium my-2">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={busy || code.trim().length !== 6}
        className="w-full mt-4 py-2.5 px-4 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-sm transition flex items-center justify-center gap-2"
      >
        <span>{busy ? 'Verifying Code…' : 'Verify & Enter Dashboard'}</span>
      </button>

      <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col items-center gap-2 text-center">
        <Link
          to="/mfa-recovery"
          className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 font-medium hover:underline"
        >
          Lost access to your authenticator? Recover your account
        </Link>
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline"
        >
          ← Back to username & password
        </button>
      </div>
    </form>
  );
}
