import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Award, ShieldCheck, History, ArrowRight, Search, Eye, Download, AlertTriangle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { certificateService, verificationHistoryService, errMsg } from '../../services';
import type { Cert, VerificationAttemptItem } from '../../types';
import StatCard from '../../components/StatCard';
import { StatCardSkeleton } from '../../components/LoadingSkeleton';
import StatusBadge from '../../components/StatusBadge';
import CertificateDetails from '../../components/CertificateDetails';
import ErrorMessage from '../../components/ErrorMessage';
import { toast } from '../../lib/ui';

export default function UserDashboard() {
  const { user, verifyEmail, resendVerification } = useAuth();
  const [certs, setCerts] = useState<Cert[]>([]);
  const [verifications, setVerifications] = useState<VerificationAttemptItem[]>([]);
  const [selectedCert, setSelectedCert] = useState<Cert | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Email verification state
  const [otp, setOtp] = useState('');
  const [verifyingEmail, setVerifyingEmail] = useState(false);
  const [resendingCode, setResendingCode] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [cList, vList] = await Promise.all([
        certificateService.list(),
        verificationHistoryService.list(),
      ]);
      setCerts(cList);
      setVerifications(vList);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-100 dark:bg-slate-800 rounded-2xl animate-pulse" />
          <div className="h-64 bg-slate-100 dark:bg-slate-800 rounded-2xl animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadData} />;
  }

  // Consistent Verified Records metric: count distinct authentic certificate numbers found in user's lookup queries
  const verifiedCount = new Set(
    verifications
      .filter(v => v.result === 'FOUND' || v.result === 'VERIFIED')
      .map(v => v.certificate_number.trim().toUpperCase())
  ).size;

  const recentCerts = certs.slice(0, 5);
  const recentLookups = verifications.slice(0, 5);

  const handleVerifyEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp.trim()) {
      setVerifyError('Please enter the 6-digit verification code.');
      return;
    }
    setVerifyingEmail(true);
    setVerifyError(null);
    try {
      const res = await verifyEmail({ email: user?.email, otp: otp.trim() });
      toast(
        res.claimedCount > 0
          ? `Email verified! ${res.claimedCount} certificate(s) linked to your account.`
          : 'Email verified successfully!'
      );
      setOtp('');
      await loadData();
    } catch (err) {
      setVerifyError(errMsg(err));
    } finally {
      setVerifyingEmail(false);
    }
  };

  const handleResend = async () => {
    if (!user?.email) return;
    setResendingCode(true);
    setVerifyError(null);
    try {
      const msg = await resendVerification(user.email);
      toast(msg);
    } catch (err) {
      setVerifyError(errMsg(err));
    } finally {
      setResendingCode(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Email Verification Required Banner — only display when unclaimed certificates genuinely exist */}
      {user && user.emailVerified === false && user.hasUnclaimedCertificates === true && (
        <div className="p-5 sm:p-6 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-amber-950 dark:text-amber-200">
                  Email Verification Required to Claim Issued Certificates
                </h4>
                <p className="text-xs text-amber-800/90 dark:text-amber-300/80 mt-1 max-w-xl">
                  Your registered email <span className="font-semibold">{user.email}</span> is not verified yet.
                  Enter the 6-digit code sent to your inbox to link any previously issued certificates.
                </p>
                {verifyError && (
                  <p className="text-xs font-semibold text-rose-600 dark:text-rose-400 mt-2">
                    {verifyError}
                  </p>
                )}
              </div>
            </div>

            <form onSubmit={handleVerifyEmail} className="flex flex-wrap items-center gap-2.5">
              <input
                type="text"
                placeholder="6-digit code"
                maxLength={6}
                value={otp}
                onChange={e => setOtp(e.target.value)}
                className="w-32 px-3 py-2 text-center text-sm font-mono tracking-widest bg-white dark:bg-slate-900 border border-amber-300 dark:border-amber-700/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500 text-slate-900 dark:text-white"
              />
              <button
                type="submit"
                disabled={verifyingEmail || !otp.trim()}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold shadow-sm transition disabled:opacity-50"
              >
                {verifyingEmail ? 'Verifying…' : 'Verify & Link'}
              </button>
              <button
                type="button"
                onClick={handleResend}
                disabled={resendingCode}
                className="px-3 py-2 text-xs font-medium text-amber-800 dark:text-amber-300 hover:underline disabled:opacity-50"
              >
                {resendingCode ? 'Sending…' : 'Resend code'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-teal-950 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-md border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <span className="text-teal-400 font-semibold text-xs tracking-wider uppercase bg-teal-950/60 border border-teal-800/80 px-2.5 py-1 rounded-full">
            Credential Portal
          </span>
          <h2 className="text-2xl font-bold tracking-tight mt-2.5">
            Welcome, {user?.name || user?.username}
          </h2>
          <p className="text-slate-300 text-sm mt-1 max-w-xl">
            Access your authenticated certificate records, inspect verification validity, or look up credentials in the registry.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/user/dashboard/verify"
            className="px-4 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold shadow-sm transition inline-flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            <span>Verify an ID</span>
          </Link>
          <Link
            to="/user/dashboard/certificates"
            className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition inline-flex items-center gap-2"
          >
            <span>My Certificates</span>
          </Link>
        </div>
      </div>

      {/* User Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="My Certificates"
          value={certs.length}
          subtitle="Accessible to your account"
          icon={Award}
          color="teal"
        />
        <StatCard
          title="Verified Records"
          value={verifiedCount}
          subtitle="Distinct credentials verified by your searches"
          icon={ShieldCheck}
          color="emerald"
        />
        <StatCard
          title="Verification Searches"
          value={verifications.length}
          subtitle="Lookup queries performed by you"
          icon={History}
          color="indigo"
        />
      </div>

      {/* Recent Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Certificates */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Recent Certificates
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Credentials issued and assigned to your profile
              </p>
            </div>
            <Link
              to="/user/dashboard/certificates"
              className="text-xs font-semibold text-teal-600 hover:text-teal-700 dark:text-teal-400 flex items-center gap-1"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {recentCerts.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">No certificates in your account.</p>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {recentCerts.map(c => (
                <div key={c.key} className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900 dark:text-white truncate">
                      {c.title}
                    </p>
                    <p className="text-slate-500 font-mono text-[11px] mt-0.5 truncate">
                      {c.number} · {c.issuer} {c.issued ? `· ${c.issued}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <StatusBadge status={c.status} />
                    <button
                      type="button"
                      onClick={() => setSelectedCert(c)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-400 rounded-lg transition"
                      title="View Details"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>View</span>
                    </button>
                    {c.hasPdf && c.pdfDownloadUrl ? (
                      <a
                        href={c.pdfDownloadUrl}
                        download
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 rounded-lg transition"
                        title="Download PDF"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>PDF</span>
                      </a>
                    ) : c.file ? (
                      <a
                        href={c.file}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 rounded-lg transition"
                        title="Download File"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>File</span>
                      </a>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Verification History */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Recent Verification Searches
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Certificate lookups executed by your account
              </p>
            </div>
            <Link
              to="/user/dashboard/history"
              className="text-xs font-semibold text-teal-600 hover:text-teal-700 dark:text-teal-400 flex items-center gap-1"
            >
              <span>View history</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {recentLookups.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">No lookup queries recorded yet.</p>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {recentLookups.map(v => {
                const isFound = v.result === 'FOUND' || v.result === 'VERIFIED';
                return (
                  <div key={v.id} className="py-3 flex items-center justify-between gap-3 text-xs">
                    <div className="min-w-0">
                      <p className="font-mono font-medium text-slate-900 dark:text-white truncate">
                        {v.certificate_number}
                      </p>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        {new Date(v.created_at).toLocaleString()}
                      </p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full font-semibold text-[11px] flex-shrink-0 ${
                        isFound
                          ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300'
                          : 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300'
                      }`}
                    >
                      {isFound ? 'Found' : 'Not Found'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Modal Inspector */}
      <CertificateDetails
        cert={selectedCert}
        onClose={() => setSelectedCert(null)}
      />
    </div>
  );
}
