import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Award,
  Users,
  Search,
  CheckCircle2,
  XCircle,
  ArrowRight,
  TrendingUp,
  Building,
  FileStack,
  Sparkles,
  Download,
  History,
  UploadCloud,
  Eye,
  AlertTriangle,
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import { StatCardSkeleton } from '../../components/LoadingSkeleton';
import ErrorMessage from '../../components/ErrorMessage';
import StatusBadge from '../../components/StatusBadge';
import { dashboardService, generationService, errMsg } from '../../services';
import type { DashboardStats } from '../../types';

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await dashboardService.get();
      setData(res);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={fetchStats} title="Failed to load admin metrics" />;
  }

  const adminStats = data?.admin_stats;
  const stats = data?.statistics;
  const recentCerts = data?.recent_certificates ?? [];
  const recentVerifies = adminStats?.recent_verifications ?? [];

  // Calculate real verification success rate
  const totalAttempts = adminStats?.total_verification_attempts ?? 0;
  const successfulLookups = adminStats?.successful_verifications ?? 0;
  const unsuccessfulLookups = adminStats?.unsuccessful_verifications ?? 0;
  const successRate = totalAttempts > 0 ? Math.round((successfulLookups / totalAttempts) * 100) : 0;

  return (
    <div className="space-y-8">
      {/* Top Welcome Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-md border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <span className="text-teal-400 font-semibold text-xs tracking-wider uppercase bg-teal-950/60 border border-teal-800/80 px-2.5 py-1 rounded-full">
            Enterprise Security Core
          </span>
          <h2 className="text-2xl font-bold tracking-tight mt-2.5">
            Admin System Overview
          </h2>
          <p className="text-slate-300 text-sm mt-1 max-w-xl">
            Live database telemetry backed by PostgreSQL. Real certificate issuance, user registration, and search verification analytics.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/admin/dashboard/generate"
            className="px-4 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold shadow-sm transition inline-flex items-center gap-2"
          >
            <FileStack className="w-4 h-4" />
            <span>Generate Bulk</span>
          </Link>
          <Link
            to="/admin/dashboard/generate-single"
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-sm transition inline-flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>Manual Generation</span>
          </Link>
        </div>
      </div>

      {/* Primary Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Certificates"
          value={adminStats?.total_certificates ?? stats?.total ?? 0}
          subtitle="Recorded in PostgreSQL"
          icon={Award}
          color="teal"
        />
        <StatCard
          title="Registered Users"
          value={adminStats?.total_users ?? 0}
          subtitle="Active system accounts"
          icon={Users}
          color="navy"
        />
        <StatCard
          title="Verification Lookups"
          value={totalAttempts}
          subtitle="Persistent search attempts"
          icon={Search}
          color="indigo"
        />
        <StatCard
          title="Lookup Success Rate"
          value={`${successRate}%`}
          subtitle={`${successfulLookups} successful of ${totalAttempts}`}
          icon={TrendingUp}
          trend={`${successRate}% match`}
          trendUp={successRate >= 50}
          color="emerald"
        />
      </div>

      {/* Secondary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Successful Verifications"
          value={successfulLookups}
          subtitle="Certificate found in database"
          icon={CheckCircle2}
          color="emerald"
        />
        <StatCard
          title="Unsuccessful Lookups"
          value={unsuccessfulLookups}
          subtitle="Number not found in database"
          icon={XCircle}
          color="rose"
        />
        <StatCard
          title="Issuing Authorities"
          value={adminStats?.issuer_breakdown?.length ?? 0}
          subtitle="Unique organizations logged"
          icon={Building}
          color="amber"
        />
      </div>

      {/* Certificate Generation & Distribution Suite */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <FileStack className="w-5 h-5 text-teal-600" />
              <span>Certificate Generation & Distribution Suite</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Bulk CSV roster processing, single issuance, graphics template preview, and distribution tracking
            </p>
          </div>
          <span className="text-[11px] font-semibold text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/60 border border-teal-200 dark:border-teal-800/60 px-2.5 py-1 rounded-full w-fit">
            Pillow Graphics Core
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-1">
          {/* 1. Bulk Generation */}
          <Link
            to="/admin/dashboard/generate"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-teal-500 dark:hover:border-teal-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-teal-50/40 dark:hover:bg-teal-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-teal-100 dark:bg-teal-900/60 text-teal-700 dark:text-teal-300">
                <FileStack className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-teal-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                Generate in Bulk
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Upload CSV roster, validate students & render certificates
              </p>
            </div>
          </Link>

          {/* 2. Generate Single */}
          <Link
            to="/admin/dashboard/generate-single"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-indigo-500 dark:hover:border-indigo-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300">
                <Sparkles className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                Generate Single Certificate
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Manual on-demand certificate without CSV upload
              </p>
            </div>
          </Link>

          {/* 3. Upload Template */}
          <Link
            to="/admin/dashboard/generate"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-emerald-500 dark:hover:border-emerald-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-emerald-50/40 dark:hover:bg-emerald-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300">
                <UploadCloud className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                Upload Certificate Template
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                PNG/JPEG official OneSmarter background template
              </p>
            </div>
          </Link>

          {/* 4. Preview Certificate */}
          <Link
            to="/admin/dashboard/generate"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-amber-500 dark:hover:border-amber-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-amber-50/40 dark:hover:bg-amber-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300">
                <Eye className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-amber-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                Preview Certificate
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Real-time image render with names, dates & seals
              </p>
            </div>
          </Link>

          {/* 5. View Generated Certificates */}
          <Link
            to="/admin/dashboard/certificates"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-cyan-500 dark:hover:border-cyan-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-cyan-50/40 dark:hover:bg-cyan-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-cyan-100 dark:bg-cyan-900/60 text-cyan-700 dark:text-cyan-300">
                <Award className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-cyan-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                View Generated Certificates
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                All issued records stored in PostgreSQL database
              </p>
            </div>
          </Link>

          {/* 6. View Generation History */}
          <Link
            to="/admin/dashboard/generation-history"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-violet-500 dark:hover:border-violet-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-violet-50/40 dark:hover:bg-violet-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-violet-100 dark:bg-violet-900/60 text-violet-700 dark:text-violet-300">
                <History className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-violet-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                View Generation History
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Past batch jobs, student rosters & timestamps
              </p>
            </div>
          </Link>

          {/* 7. Download CSV Template */}
          <a
            href={generationService.downloadCsvTemplateUrl()}
            download="certificate_upload_template.csv"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-teal-500 dark:hover:border-teal-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-teal-50/40 dark:hover:bg-teal-950/20 transition group flex flex-col justify-between space-y-3 text-left"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-teal-100 dark:bg-teal-900/60 text-teal-700 dark:text-teal-300">
                <Download className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-teal-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                Download CSV Template
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Standard columns: name, email, course, dates
              </p>
            </div>
          </a>

          {/* 8. View Failed Rows & Retry */}
          <Link
            to="/admin/dashboard/generation-history"
            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-rose-500 dark:hover:border-rose-500 bg-slate-50/50 dark:bg-slate-800/30 hover:bg-rose-50/40 dark:hover:bg-rose-950/20 transition group flex flex-col justify-between space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-rose-600 group-hover:translate-x-0.5 transition" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                Failed Rows & Email Retry
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Audit error logs & resend failed notifications
              </p>
            </div>
          </Link>
        </div>
      </div>

      {/* Recent Activity Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Certificates */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Recent Certificates
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Latest records added to the database
              </p>
            </div>
            <Link
              to="/admin/dashboard/certificates"
              className="text-xs font-semibold text-teal-600 hover:text-teal-700 dark:text-teal-400 flex items-center gap-1"
            >
              <span>View all</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {recentCerts.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">No certificates added yet.</p>
          ) : (
            <div className="max-h-72 overflow-y-auto overscroll-contain [scrollbar-color:#94a3b8_transparent] dark:[scrollbar-color:#64748b_transparent] divide-y divide-slate-100 dark:divide-slate-800">
              {recentCerts.map(c => (
                <div key={c.id} className="py-3 flex items-center justify-between gap-3 text-xs">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 dark:text-white truncate">
                      {c.title}
                    </p>
                    <p className="text-slate-500 font-mono text-[11px] mt-0.5 truncate">
                      {c.certificate_number} · {c.recipient_name}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <StatusBadge status={c.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Verification Activity */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Recent Verification Activity
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Live lookup history from public & authenticated users
              </p>
            </div>
            <Link
              to="/admin/dashboard/verifications"
              className="text-xs font-semibold text-teal-600 hover:text-teal-700 dark:text-teal-400 flex items-center gap-1"
            >
              <span>View all logs</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {recentVerifies.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">No verification attempts recorded yet.</p>
          ) : (
            <div className="max-h-72 overflow-y-auto overscroll-contain [scrollbar-color:#94a3b8_transparent] dark:[scrollbar-color:#64748b_transparent] divide-y divide-slate-100 dark:divide-slate-800">
              {recentVerifies.map(v => {
                const isFound = v.result === 'FOUND' || v.result === 'VERIFIED';
                return (
                  <div key={v.id} className="py-3 flex items-center justify-between gap-3 text-xs">
                    <div className="min-w-0">
                      <p className="font-mono font-medium text-slate-900 dark:text-white truncate">
                        {v.certificate_number}
                      </p>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        {v.requested_by ? `By ${v.requested_by}` : 'Public inquiry'} ·{' '}
                        {new Date(v.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full font-semibold text-[11px] flex items-center gap-1 flex-shrink-0 ${
                        isFound
                          ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300'
                          : 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300'
                      }`}
                    >
                      {isFound ? (
                        <>
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Found</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3 h-3" />
                          <span>Not Found</span>
                        </>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
