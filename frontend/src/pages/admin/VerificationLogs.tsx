import { useEffect, useState } from 'react';
import { ClipboardCheck, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import { verificationHistoryService, errMsg } from '../../services';
import type { VerificationAttemptItem } from '../../types';
import SearchInput from '../../components/SearchInput';
import FilterBar from '../../components/FilterBar';
import LoadingSkeleton from '../../components/LoadingSkeleton';
import EmptyState from '../../components/EmptyState';
import ErrorMessage from '../../components/ErrorMessage';

const outcomeFilters = [
  { label: 'All Lookups', value: 'ALL' },
  { label: 'Found & Verified', value: 'FOUND' },
  { label: 'Not Found', value: 'NOT_FOUND' },
];

export default function VerificationLogs() {
  const [logs, setLogs] = useState<VerificationAttemptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState('ALL');

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await verificationHistoryService.list();
      setLogs(data);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const filtered = logs.filter(l => {
    const matchesOutcome = outcomeFilter === 'ALL' || l.result === outcomeFilter;
    const q = search.toLowerCase().trim();
    const matchesSearch =
      !q ||
      l.certificate_number.toLowerCase().includes(q) ||
      (l.requested_by_username && l.requested_by_username.toLowerCase().includes(q));
    return matchesOutcome && matchesSearch;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            Verification Records & Audit Trail
          </h2>
        </div>
        <button
          type="button"
          onClick={loadLogs}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition shadow-sm w-fit"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Records</span>
        </button>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by certificate number or user..."
          className="max-w-md w-full"
        />
        <FilterBar
          options={outcomeFilters}
          selected={outcomeFilter}
          onSelect={setOutcomeFilter}
        />
      </div>

      {/* Main Table */}
      {loading ? (
        <LoadingSkeleton lines={6} height="h-12" />
      ) : error ? (
        <ErrorMessage message={error} onRetry={loadLogs} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Verification Records"
          description={
            search || outcomeFilter !== 'ALL'
              ? 'No verification logs match your filter criteria.'
              : 'No verification lookups have been logged yet.'
          }
          icon={ClipboardCheck}
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3.5 px-4">Attempt ID</th>
                  <th className="py-3.5 px-4">Queried Number</th>
                  <th className="py-3.5 px-4">Lookup Result</th>
                  <th className="py-3.5 px-4">Requested By</th>
                  <th className="py-3.5 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filtered.map(l => {
                  const isFound = l.result === 'FOUND' || l.result === 'VERIFIED';
                  return (
                    <tr
                      key={l.id}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                    >
                      <td className="py-3.5 px-4 font-mono text-slate-400">
                        #{l.id}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900 dark:text-white">
                        {l.certificate_number}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-semibold text-[11px] ${isFound
                              ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300'
                              : 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300'
                            }`}
                        >
                          {isFound ? (
                            <>
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Found in Database</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3" />
                              <span>Not Found</span>
                            </>
                          )}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 dark:text-slate-400">
                        {l.requested_by_username ? (
                          <span className="font-medium text-slate-800 dark:text-slate-200">
                            @{l.requested_by_username}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Public Anonymous Inquiry</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {new Date(l.created_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="py-3 px-4 bg-slate-50 dark:bg-slate-800/40 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 flex items-center justify-between">
            <span>Showing {filtered.length} of {logs.length} lookup records</span>
            <span>Recorded in PostgreSQL</span>
          </div>
        </div>
      )}
    </div>
  );
}
