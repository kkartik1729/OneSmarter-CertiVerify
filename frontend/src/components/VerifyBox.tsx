import { useState, type FormEvent } from 'react';
import { verificationHistoryService, errMsg } from '../services';
import type { VerificationCheckResponse } from '../services';
import VerificationResult from './VerificationResult';
import { Shield } from 'lucide-react';

export default function VerifyBox({ record }: { record?: boolean } = {}) {
  const [id, setId] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<VerificationCheckResponse | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr('');
    const query = id.trim();
    if (!query) {
      setErr('Please enter a Certificate ID.');
      return;
    }
    setBusy(true);
    setResult(null);
    setCheckedAt(null);
    try {
      const res = await verificationHistoryService.check(query);
      setResult(res);
      setCheckedAt(new Date().toISOString());
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="w-full text-left">
      <form onSubmit={submit} noValidate className="space-y-3">
        <label htmlFor="vid" className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
          Certificate ID or Number
        </label>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            id="vid"
            value={id}
            onChange={e => setId(e.target.value)}
            placeholder="e.g. CERT-2026-98124"
            autoComplete="off"
            aria-invalid={!!err}
            className="flex-1 px-4 py-2.5 text-sm bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 font-mono"
          />
          <button
            type="submit"
            disabled={busy || !id.trim()}
            className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-sm transition flex items-center justify-center gap-2"
          >
            <Shield className="w-4 h-4" />
            <span>{busy ? 'Verifying...' : 'Verify'}</span>
          </button>
        </div>
        {err && <p className="text-xs text-rose-600 font-medium" role="alert">{err}</p>}
      </form>

      {result && (
        <div className="mt-4" aria-live="polite">
          <VerificationResult
            number={result.certificate_number}
            found={result.found}
            result={result.verification_result}
            message={result.message}
            title={result.certificate?.title}
            issuer={result.certificate?.issuer}
            issueDate={result.certificate?.issue_date}
            timestamp={checkedAt ?? undefined}
          />
        </div>
      )}
    </div>
  );
}
