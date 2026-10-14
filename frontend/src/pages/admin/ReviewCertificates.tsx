import { useEffect, useState } from 'react';
import { Award, Eye, RefreshCw } from 'lucide-react';
import { certificateService, errMsg } from '../../services';
import type { Cert } from '../../types';
import StatusBadge from '../../components/StatusBadge';
import SearchInput from '../../components/SearchInput';
import FilterBar from '../../components/FilterBar';
import CertificateDetails from '../../components/CertificateDetails';
import LoadingSkeleton from '../../components/LoadingSkeleton';
import EmptyState from '../../components/EmptyState';
import ErrorMessage from '../../components/ErrorMessage';

const filterOptions = [
  { label: 'All Certificates', value: 'ALL' },
  { label: 'Verified', value: 'VERIFIED' },
  { label: 'Pending Review', value: 'PENDING' },
  { label: 'Rejected', value: 'REJECTED' },
];

export default function ReviewCertificates() {
  const [certs, setCerts] = useState<Cert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('ALL');
  const [selectedCert, setSelectedCert] = useState<Cert | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await certificateService.list();
      setCerts(data);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filtered = certs.filter(c => {
    const matchesFilter = filter === 'ALL' || c.status === filter;
    const q = search.toLowerCase().trim();
    const matchesSearch =
      !q ||
      c.number.toLowerCase().includes(q) ||
      c.title.toLowerCase().includes(q) ||
      c.issuer.toLowerCase().includes(q) ||
      c.recipient.toLowerCase().includes(q) ||
      (c.owner && c.owner.toLowerCase().includes(q));
    return matchesFilter && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            Manage Certificate Records
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Browse, inspect, and verify certificates stored in PostgreSQL.
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition shadow-sm w-fit"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by ID, title, recipient, issuer..."
          className="max-w-md w-full"
        />
        <FilterBar
          options={filterOptions}
          selected={filter}
          onSelect={setFilter}
        />
      </div>

      {/* Main Table / Content */}
      {loading ? (
        <LoadingSkeleton lines={6} height="h-12" />
      ) : error ? (
        <ErrorMessage message={error} onRetry={loadData} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Certificates Found"
          description={
            search || filter !== 'ALL'
              ? 'No certificates match your search query or filter criteria.'
              : 'No certificates have been submitted to PostgreSQL yet.'
          }
          icon={Award}
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3.5 px-4">Certificate ID</th>
                  <th className="py-3.5 px-4">Title</th>
                  <th className="py-3.5 px-4">Recipient</th>
                  <th className="py-3.5 px-4">Issuer</th>
                  <th className="py-3.5 px-4">Issue Date</th>
                  <th className="py-3.5 px-4">Owner</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filtered.map(c => (
                  <tr
                    key={c.key}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                  >
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-900 dark:text-white">
                      {c.number}
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-800 dark:text-slate-200 max-w-xs truncate">
                      {c.title}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 dark:text-slate-400">
                      {c.recipient}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 dark:text-slate-400">
                      {c.issuer}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {c.issued}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 font-mono text-[11px]">
                      {c.owner || '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedCert(c)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-400 rounded-lg transition"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="py-3 px-4 bg-slate-50 dark:bg-slate-800/40 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 flex items-center justify-between">
            <span>Showing {filtered.length} of {certs.length} certificates</span>
            <span>PostgreSQL Data Source</span>
          </div>
        </div>
      )}

      {/* Modal Inspector */}
      <CertificateDetails
        cert={selectedCert}
        onClose={() => setSelectedCert(null)}
      />
    </div>
  );
}
