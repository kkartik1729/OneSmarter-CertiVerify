import { useEffect, useState } from 'react';
import { History, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import { verificationHistoryService, errMsg } from '../../services';
import type { VerificationAttemptItem } from '../../types';
import SearchInput from '../../components/SearchInput';
import LoadingSkeleton from '../../components/LoadingSkeleton';
import EmptyState from '../../components/EmptyState';
import ErrorMessage from '../../components/ErrorMessage';

export default function VerificationHistory() {
  const [history, setHistory] = useState<VerificationAttemptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const loadHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await verificationHistoryService.list();
      setHistory(data);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const filtered = history.filter(item => {
    const q = search.toLowerCase().trim();
    return !q || item.certificate_number.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            My Verification History
          </h2>
        </div>
        <button
          type="button"
          onClick={loadHistory}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition shadow-sm w-fit"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh History</span>
        </button>
      </div>

      <div className="flex items-center justify-between">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Filter by certificate number..."
          className="max-w-md w-full"
        />
      </div>

      {loading ? (
        <LoadingSkeleton lines={5} height="h-12" />
      ) : error ? (
        <ErrorMessage message={error} onRetry={loadHistory} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No History Found"
          description={
            search
              ? 'No verification queries match your search filter.'
              : 'You have not performed any certificate verification lookups yet.'
          }
          icon={History}
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3.5 px-4">Search ID</th>
                  <th className="py-3.5 px-4">Certificate Number Searched</th>
                  <th className="py-3.5 px-4">Registry Outcome</th>
                  <th className="py-3.5 px-4">Date & Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filtered.map(item => {
                  const isFound = item.result === 'FOUND' || item.result === 'VERIFIED';
                  return (
                    <tr
                      key={item.id}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                    >
                      <td className="py-3.5 px-4 font-mono text-slate-400">
                        #{item.id}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900 dark:text-white">
                        {item.certificate_number}
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
                      <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="py-3 px-4 bg-slate-50 dark:bg-slate-800/40 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 flex items-center justify-between">
            <span>Showing {filtered.length} of {history.length} lookup searches</span>
            <span>Persisted in PostgreSQL</span>
          </div>
        </div>
      )}
    </div>
  );
}
