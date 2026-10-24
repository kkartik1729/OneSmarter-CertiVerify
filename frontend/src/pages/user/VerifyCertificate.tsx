import { useState, type FormEvent } from 'react';
import { Search, Shield } from 'lucide-react';
import { verificationHistoryService, errMsg } from '../../services';
import type { VerificationCheckResponse } from '../../services';
import VerificationResult from '../../components/VerificationResult';

export default function VerifyCertificate() {
  const [certNumber, setCertNumber] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerificationCheckResponse | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    const query = certNumber.trim();
    if (!query) {
      setError('Please enter a certificate number to verify.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setCheckedAt(null);

    try {
      // Calls POST /api/verification/check/ which checks database & logs a persistent attempt
      const res = await verificationHistoryService.check(query);
      setResult(res);
      setCheckedAt(new Date().toISOString());
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">
          Verify Certificate Authenticity
        </h2>
      </div>

      {/* Verification Query Form */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm">
        <form onSubmit={handleVerify} className="space-y-4">
          <label htmlFor="verify-certificate-number" className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
            Certificate Number or Unique ID
          </label>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-5 h-5 absolute left-3.5 top-3 text-slate-400" />
              <input
                id="verify-certificate-number"
                type="text"
                required
                value={certNumber}
                onChange={e => setCertNumber(e.target.value)}
                placeholder="e.g. CERT-2026-98124 or OSC-2026-00125"
                className="w-full pl-11 pr-4 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !certNumber.trim()}
              className="px-6 py-2.5 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-50 rounded-xl shadow-sm transition flex items-center justify-center gap-2"
            >
              <Shield className="w-4 h-4" />
              <span>{loading ? 'Searching Database...' : 'Verify Now'}</span>
            </button>
          </div>

          {error && (
            <p className="text-xs text-rose-600 mt-2 font-medium">
              {error}
            </p>
          )}

        </form>
      </div>

      {/* Verification Outcome */}
      {result && (
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
      )}
    </div>
  );
}
