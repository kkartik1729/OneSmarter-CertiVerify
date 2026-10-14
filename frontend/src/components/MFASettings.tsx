import { ShieldCheck, CheckCircle2, Lock } from 'lucide-react';

export default function MFASettings() {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-teal-600 dark:text-teal-400" />
            <span>Two-Factor Authentication (TOTP)</span>
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Mandatory security flow: Google Authenticator OTP verification is required immediately after login.
          </p>
        </div>
      </div>

      <div className="mt-4 p-4 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200 flex items-start gap-3">
        <CheckCircle2 className="w-5 h-5 text-teal-600 dark:text-teal-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <p className="font-bold text-sm text-teal-950 dark:text-teal-100 flex items-center gap-1.5">
            <span>Google Authenticator Verification Active</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] uppercase font-semibold bg-teal-200/80 dark:bg-teal-800 text-teal-900 dark:text-teal-100">
              Enforced on Login
            </span>
          </p>
          <p className="text-teal-800 dark:text-teal-300 leading-relaxed">
            Every time you sign in to CertiVerify, you are required to complete Google Authenticator 6-digit TOTP verification before being granted access to your dashboard.
          </p>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <Lock className="w-4 h-4 text-slate-400" />
        <span>Authentication tokens are never issued until two-factor verification succeeds.</span>
      </div>
    </div>
  );
}
