/**
 * PublicVerify — The public LinkedIn credential verification page.
 *
 * Accessible at:
 *   /verify-certificate/:certificateNumber   (LinkedIn credential URL format)
 *   /verify/:certificateNumber               (legacy alias)
 *   /verify-certificate                      (manual search form)
 *
 * Visitors do NOT need to log in or create an account.
 * The certificate number is read from the URL and verified automatically on mount.
 * If no number is in the URL, a manual search form is presented instead.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  Shield,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Search,
  Award,
  Building,
  Calendar,
  User,
  Hash,
  BookOpen,
  ArrowLeft,
  Loader2,
} from 'lucide-react';
import { EP } from '../services/endpoints';
import { API_BASE, http, ApiError } from '../services/http';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface PublicCertRecord {
  certificate_number: string;
  found: boolean;
  verification_result: string;
  status?: string;
  preview_url?: string | null;
  message: string;
  title?: string;
  issuer?: string;
  issue_date?: string;
  recipient_name?: string;
  course_name?: string;
  start_date?: string;
  end_date?: string;
}

type VerifyState =
  | { kind: 'idle' }
  | { kind: 'loading'; number: string }
  | { kind: 'verified'; data: PublicCertRecord }
  | { kind: 'not_found'; number: string }
  | { kind: 'error'; message: string; number: string };

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------
function formatDate(d: string | undefined): string {
  if (!d) return '';
  try {
    return new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return d;
  }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function PublicVerify() {
  const { certificateNumber: urlParam } = useParams<{ certificateNumber?: string }>();
  const [searchParams] = useSearchParams();

  // Seed the input from URL param or ?number= query param
  const seedNumber = (urlParam || searchParams.get('number') || '').trim().toUpperCase();

  const [inputValue, setInputValue] = useState(seedNumber);
  const [state, setState] = useState<VerifyState>({ kind: 'idle' });

  // ---------------------------------------------------------------------------
  // Verify against the public GET endpoint
  // ---------------------------------------------------------------------------
  const verify = async (number: string) => {
    const normalized = number.trim().toUpperCase();
    if (!normalized) return;

    setState({ kind: 'loading', number: normalized });
    try {
      const data = await http<PublicCertRecord>(
        'GET',
        EP.verify(normalized),
        undefined,
        false, // no auth token required
      );
      if (data.found) {
        setState({ kind: 'verified', data });
      } else {
        setState({ kind: 'not_found', number: normalized });
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setState({ kind: 'not_found', number: normalized });
      } else {
        const msg =
          e instanceof Error
            ? e.message
            : 'Verification is temporarily unavailable. Please try again later.';
        setState({ kind: 'error', message: msg, number: normalized });
      }
    }
  };

  // Auto-verify when a certificate number is present in the URL
  useEffect(() => {
    if (seedNumber) {
      verify(seedNumber);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedNumber]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    verify(inputValue);
  };

  const handleReset = () => {
    setInputValue('');
    setState({ kind: 'idle' });
    window.history.replaceState({}, '', '/verify-certificate');
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 flex flex-col">
      {/* ── Header ── */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center shadow">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900 dark:text-white leading-none">
                OneSmarter CertiVerify
              </p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                Public Certificate Verification
              </p>
            </div>
          </div>
          <Link
            to="/login"
            className="text-xs font-semibold text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 transition"
          >
            Sign in →
          </Link>
        </div>
      </header>

      {/* ── Body ── */}
      <main className="flex-1 max-w-4xl mx-auto px-4 py-10 w-full space-y-8">
        {/* Hero */}
        <div className="text-center space-y-2">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Certificate Verification
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-xl mx-auto">
            Instantly verify any certificate issued by OneSmarter, Inc. against the live
            PostgreSQL registry. No account or login required.
          </p>
        </div>

        {/* ── Search form ── */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Enter Credential ID / Certificate Number
            </label>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
                <input
                  id="public-cert-number-input"
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value.toUpperCase())}
                  placeholder="e.g. OSCV-2026-001234"
                  className="w-full pl-10 pr-4 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 font-mono transition"
                  autoFocus={!seedNumber}
                />
              </div>
              <button
                id="public-verify-btn"
                type="submit"
                disabled={state.kind === 'loading' || !inputValue.trim()}
                className="px-6 py-2.5 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-50 rounded-xl shadow transition flex items-center justify-center gap-2 min-w-[120px]"
              >
                {state.kind === 'loading' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Checking…</span>
                  </>
                ) : (
                  <>
                    <Shield className="w-4 h-4" />
                    <span>Verify</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-[11px] text-slate-400">
              Enter the Credential ID exactly as printed on the certificate or as shown in the LinkedIn
              Licenses &amp; Certifications section.
            </p>
          </form>
        </div>

        {/* ── Loading state ── */}
        {state.kind === 'loading' && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-10 shadow-sm flex flex-col items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-teal-50 dark:bg-teal-950/40 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-teal-600 animate-spin" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                Searching PostgreSQL registry…
              </p>
              <p className="text-xs text-slate-500 mt-1 font-mono">{state.number}</p>
            </div>
          </div>
        )}

        {/* ── VERIFIED ── */}
        {state.kind === 'verified' && (
          <VerifiedCard data={state.data} onReset={handleReset} />
        )}

        {/* ── NOT FOUND ── */}
        {state.kind === 'not_found' && (
          <NotFoundCard number={state.number} onReset={handleReset} />
        )}

        {/* ── API ERROR ── */}
        {state.kind === 'error' && (
          <ErrorCard message={state.message} number={state.number} onReset={handleReset} />
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="text-center text-[11px] text-slate-400 dark:text-slate-600 py-6 border-t border-slate-200 dark:border-slate-800">
        © {new Date().getFullYear()} OneSmarter, Inc. · CertiVerify Public Verification Portal
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Field({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  if (!value) return null;
  return (
    <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl p-3.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
        <Icon className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
        <span>{label}</span>
      </div>
      <p className="text-sm font-semibold text-slate-900 dark:text-white">{value}</p>
    </div>
  );
}

function VerifiedCard({
  data,
  onReset,
}: {
  data: PublicCertRecord;
  onReset: () => void;
}) {
  const isVerified = data.verification_result === 'VERIFIED';
  return (
    <div className={`${isVerified ? 'bg-teal-50/50 dark:bg-teal-950/20 border-teal-200 dark:border-teal-800' : 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800'} border rounded-2xl p-6 shadow-sm space-y-5`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl ${isVerified ? 'bg-teal-600 shadow-teal-500/20' : 'bg-amber-500 shadow-amber-500/20'} flex items-center justify-center shadow-md flex-shrink-0`}>
            {isVerified ? <CheckCircle2 className="w-7 h-7 text-white" /> : <AlertTriangle className="w-7 h-7 text-white" />}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {isVerified ? 'Verified Certificate' : 'Certificate Not Verified'}
              </h2>
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${isVerified ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300' : 'bg-amber-100 text-amber-900 dark:bg-amber-900/50 dark:text-amber-200'}`}>
                {data.verification_result || data.status || 'NOT_VERIFIED'}
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              {data.message}
            </p>
          </div>
        </div>
        <span className="text-xs font-mono font-medium text-slate-500 dark:text-slate-400 flex-shrink-0">
          {data.certificate_number}
        </span>
      </div>

      {data.verification_result === 'VERIFIED' && data.preview_url && (
        <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white">
          <img
            src={`${API_BASE.replace(/\/+$/, '')}${data.preview_url}`}
            alt={`Certificate ${data.certificate_number}`}
            className="block h-auto w-full object-contain"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        </div>
      )}

      {/* Fields grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Field icon={Award} label="Certificate Title" value={data.title || ''} />
        <Field icon={Building} label="Issuing Organization" value={data.issuer || ''} />
        <Field icon={Hash} label="Credential ID" value={data.certificate_number} />
        {data.recipient_name && (
          <Field icon={User} label="Recipient Name" value={data.recipient_name} />
        )}
        {data.course_name && (
          <Field icon={BookOpen} label="Course / Program" value={data.course_name} />
        )}
        <Field icon={Calendar} label="Issue Date" value={formatDate(data.issue_date)} />
        {data.start_date && (
          <Field icon={Calendar} label="Course Start Date" value={formatDate(data.start_date)} />
        )}
        {data.end_date && (
          <Field icon={Calendar} label="Course End Date" value={formatDate(data.end_date)} />
        )}
      </div>

      {/* Disclaimer */}
      <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 leading-relaxed">
        <span className="font-semibold text-slate-700 dark:text-slate-300">
          Verification Note:&nbsp;
        </span>
        This result confirms that certificate number{' '}
        <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">
          {data.certificate_number}
        </code>{' '}
        exists in the OneSmarter-CertiVerify database. Database presence does not independently
        verify that a separate screenshot, edited image, or copied document has not been altered.
        Always request the original credential URL directly from the certificate holder.
      </div>

      {/* Reset */}
      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-teal-600 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Verify another certificate
      </button>
    </div>
  );
}

function NotFoundCard({ number, onReset }: { number: string; onReset: () => void }) {
  return (
    <div className="bg-rose-50/40 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900 rounded-2xl p-6 shadow-sm space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-rose-600 flex items-center justify-center shadow-md shadow-rose-500/20 flex-shrink-0">
          <XCircle className="w-7 h-7 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              Certificate Not Verified
            </h2>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300">
              NOT_FOUND
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
            No matching certificate record was found in the OneSmarter-CertiVerify database.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
        <p>
          The certificate number{' '}
          <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">{number}</code>{' '}
          does not match any issued record in our registry.
        </p>
        <p>
          Please double-check the spelling, letters, and hyphens. If you believe this is an error,
          contact the issuing authority.
        </p>
      </div>

      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-teal-600 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Try a different certificate number
      </button>
    </div>
  );
}

function ErrorCard({
  message,
  number,
  onReset,
}: {
  message: string;
  number: string;
  onReset: () => void;
}) {
  return (
    <div className="bg-amber-50/40 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 rounded-2xl p-6 shadow-sm space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl bg-amber-500 flex items-center justify-center shadow-md shadow-amber-500/20 flex-shrink-0">
          <AlertTriangle className="w-7 h-7 text-white" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">
            Verification Unavailable
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
            The verification service did not respond. This is <strong>not</strong> a confirmed
            result.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-3 text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
        <p>
          Verification is temporarily unavailable. Please try again later.
        </p>
        {number && (
          <p>
            Queried number:{' '}
            <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">{number}</code>
          </p>
        )}
        {message && <p className="text-amber-700 dark:text-amber-400">{message}</p>}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-teal-600 transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Try again
      </button>
    </div>
  );
}
