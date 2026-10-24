import { CheckCircle2, XCircle, Calendar, Building, User, Award } from 'lucide-react';

interface VerificationResultProps {
  number: string;
  found: boolean;
  result: string;
  message: string;
  title?: string;
  issuer?: string;
  recipient?: string;
  issueDate?: string;
  timestamp?: string;
}

export default function VerificationResult({
  number,
  found,
  result,
  message,
  title,
  issuer,
  recipient,
  issueDate,
  timestamp,
}: VerificationResultProps) {
  const isSuccess = found && result === 'VERIFIED';
  const statusTitle = result === 'PENDING'
    ? 'Certificate Pending Review'
    : result === 'REJECTED'
      ? 'Certificate Rejected'
        : result === 'REVOKED'
          ? 'Certificate Revoked'
      : result === 'NOT_FOUND'
        ? 'Certificate Not Found'
        : 'Certificate Not Verified';

  return (
    <div
      className={`border rounded-2xl p-6 transition-all shadow-sm ${
        isSuccess
          ? 'bg-teal-50/50 dark:bg-teal-950/20 border-teal-200 dark:border-teal-800'
          : 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900'
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-200/60 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              isSuccess
                ? 'bg-teal-600 text-white shadow-teal-500/20 shadow-md'
                : 'bg-rose-600 text-white shadow-rose-500/20 shadow-md'
            }`}
          >
            {isSuccess ? (
              <CheckCircle2 className="w-7 h-7" />
            ) : (
              <XCircle className="w-7 h-7" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                {isSuccess ? 'Verified Authentic Certificate' : statusTitle}
              </h3>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  isSuccess
                    ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300'
                    : 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300'
                }`}
              >
                {result}
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              {message}
            </p>
          </div>
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 flex sm:flex-col items-center sm:items-end justify-between sm:justify-center">
          <span className="font-mono font-medium">{number}</span>
          {timestamp && <span>Checked: {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
        </div>
      </div>

      {isSuccess && (
        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-slate-900/80 p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              <Award className="w-4 h-4 text-teal-600 dark:text-teal-400" />
              <span>Certificate Title</span>
            </div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
              {title || 'Official Certificate'}
            </p>
          </div>

          <div className="bg-white dark:bg-slate-900/80 p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              <Building className="w-4 h-4 text-teal-600 dark:text-teal-400" />
              <span>Issuing Authority</span>
            </div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
              {issuer || 'Authorized Issuer'}
            </p>
          </div>

          <div className="bg-white dark:bg-slate-900/80 p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              <User className="w-4 h-4 text-teal-600 dark:text-teal-400" />
              <span>Recipient Name</span>
            </div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
              {recipient || 'Registered Holder'}
            </p>
          </div>

          <div className="bg-white dark:bg-slate-900/80 p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              <Calendar className="w-4 h-4 text-teal-600 dark:text-teal-400" />
              <span>Issue Date</span>
            </div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">
              {issueDate || 'Documented'}
            </p>
          </div>
        </div>
      )}

      {!isSuccess && (
        <div className="mt-4 p-4 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200/80 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-1">
          <p className="font-semibold text-slate-800 dark:text-slate-200">
            Why was this certificate not verified?
          </p>
          <p>
            {result === 'PENDING'
              ? 'This certificate exists but has not been approved yet.'
              : result === 'REJECTED'
                ? 'This certificate was rejected by the issuing authority.'
              : result === 'REVOKED'
                ? 'This certificate was revoked by the issuing authority.'
                : result === 'NOT_FOUND'
                  ? <>No record matching certificate number <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">{number}</code> was found in the registry.</>
                  : 'The registry does not currently confirm this certificate as verified.'}
          </p>
          <p>
            {result === 'PENDING' || result === 'REJECTED' || result === 'REVOKED' ? 'Contact the issuing authority for more information.' : 'Please double-check the spelling, letters, and hyphens or contact the issuing authority for assistance.'}
          </p>
        </div>
      )}
    </div>
  );
}
