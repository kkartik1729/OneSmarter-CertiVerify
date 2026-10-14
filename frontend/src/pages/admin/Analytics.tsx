import { useEffect, useState } from 'react';
import { Award, Users, Search, TrendingUp, RefreshCw } from 'lucide-react';
import { dashboardService, errMsg } from '../../services';
import type { DashboardStats } from '../../types';
import StatCard from '../../components/StatCard';
import { StatCardSkeleton } from '../../components/LoadingSkeleton';
import AnalyticsChart from '../../components/AnalyticsChart';
import ErrorMessage from '../../components/ErrorMessage';

export default function Analytics() {
  const [data, setData] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = async () => {
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
    loadAnalytics();
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
        <div className="h-64 bg-slate-100 dark:bg-slate-800 rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadAnalytics} title="Failed to load analytics" />;
  }

  const adminStats = data?.admin_stats;
  const totalAttempts = adminStats?.total_verification_attempts ?? 0;
  const successfulLookups = adminStats?.successful_verifications ?? 0;
  const unsuccessfulLookups = adminStats?.unsuccessful_verifications ?? 0;
  const successRate = totalAttempts > 0 ? Math.round((successfulLookups / totalAttempts) * 100) : 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            System Analytics & Reports
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Aggregated audit telemetry and lookup trends computed directly from PostgreSQL.
          </p>
        </div>
        <button
          type="button"
          onClick={loadAnalytics}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition shadow-sm w-fit"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Analytics</span>
        </button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Certificates"
          value={adminStats?.total_certificates ?? data?.statistics.total ?? 0}
          subtitle="Persistent certificate records"
          icon={Award}
          color="teal"
        />
        <StatCard
          title="Registered Users"
          value={adminStats?.total_users ?? 0}
          subtitle="Authorized accounts"
          icon={Users}
          color="navy"
        />
        <StatCard
          title="Total Verification Attempts"
          value={totalAttempts}
          subtitle={`${successfulLookups} found, ${unsuccessfulLookups} missing`}
          icon={Search}
          color="indigo"
        />
        <StatCard
          title="Verification Success Rate"
          value={`${successRate}%`}
          subtitle="Proportion of queries matched"
          icon={TrendingUp}
          trend={`${successRate}%`}
          trendUp={successRate >= 50}
          color="emerald"
        />
      </div>

      {/* Visual Recharts Charts */}
      <AnalyticsChart
        certTrends={adminStats?.certificate_trend ?? []}
        verifyTrends={adminStats?.verification_trend ?? []}
        issuerBreakdown={adminStats?.issuer_breakdown ?? []}
      />
    </div>
  );
}
