import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  History,
  FileStack,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Mail,
  Eye,
  ArrowRight,
  Download,
} from 'lucide-react';
import { generationService, errMsg } from '../../services';
import type { GenerationBatch } from '../../types';
import ErrorMessage from '../../components/ErrorMessage';
import LoadingSkeleton from '../../components/LoadingSkeleton';
import { useAccessibleDialog } from '../../lib/dialog';
import { downloadBlob } from '../../lib/download';

function csvCell(value: unknown): string {
  let text = String(value ?? '').replace(/"/g, '""');
  if (/^[\s\u0000-\u001f]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text}"`;
}

export default function GenerationHistory() {
  const [batches, setBatches] = useState<GenerationBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail Modal
  const [selectedBatch, setSelectedBatch] = useState<GenerationBatch | null>(null);
  const batchDialogRef = useAccessibleDialog(Boolean(selectedBatch), () => setSelectedBatch(null));
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchBatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await generationService.listBatches();
      setBatches(data);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  const downloadErrorReportCsv = (batch: GenerationBatch) => {
    if (!batch.error_report || batch.error_report.length === 0) return;
    const header = ['Row Number', 'Student Name', 'Student Email', 'Error Reason'].map(csvCell).join(',');
    const rows = batch.error_report.map(e => [e.row_number, e.student_name, e.student_email, e.error].map(csvCell).join(','));
    const blob = new Blob([[header, ...rows].join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `batch_${batch.id}_error_report.csv`);
  };

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 sm:p-8 text-white shadow-md border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight mt-2.5 flex items-center gap-3">
            <History className="w-7 h-7 text-indigo-400" />
            <span>Generation History & Batches</span>
          </h2>
          <p className="text-slate-300 text-sm mt-1 max-w-xl">
            Track certificate issuance, review errors and duplicates, and monitor email delivery status.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={fetchBatches}
            disabled={loading}
            className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition inline-flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/admin/dashboard/generate"
            className="px-4 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-sm font-semibold shadow-sm transition inline-flex items-center gap-2"
          >
            <FileStack className="w-4 h-4" />
            <span>+ New Bulk Batch</span>
          </Link>
        </div>
      </div>

      {error && <ErrorMessage message={error} onRetry={fetchBatches} />}
      {actionMessage && (
        <div className="p-4 rounded-xl bg-teal-50 dark:bg-teal-950/50 border border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200 text-xs font-medium flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-teal-600 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <LoadingSkeleton lines={5} height="h-16" />
      ) : batches.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-12 text-center space-y-4">
          <History className="w-12 h-12 text-slate-400 mx-auto" />
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">
            No Generation Batches Yet
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            When you run a bulk certificate generation job from a CSV roster, the batch records, successes, errors, and email status will appear here.
          </p>
          <Link
            to="/admin/dashboard/generate"
            className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs rounded-xl shadow-sm inline-flex items-center gap-2"
          >
            <span>Start First Batch</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 uppercase tracking-wider text-[11px] font-semibold">
                <tr>
                  <th className="py-3.5 px-4">Batch ID</th>
                  <th className="py-3.5 px-4">Course</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Total</th>
                  <th className="py-3.5 px-4 text-teal-600">Generated</th>
                  <th className="py-3.5 px-4 text-amber-600">Skipped</th>
                  <th className="py-3.5 px-4 text-rose-600">Failed</th>
                  <th className="py-3.5 px-4">Emails</th>
                  <th className="py-3.5 px-4">Created Date</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {batches.map((b) => (
                  <tr
                    key={b.id}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900 dark:text-white">
                      #{b.id}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800 dark:text-slate-200 max-w-xs truncate">
                      {b.course_name || '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[11px] font-semibold inline-flex items-center gap-1 ${b.status === 'COMPLETED'
                          ? 'bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300'
                          : b.status === 'PROCESSING'
                            ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-300 animate-pulse'
                            : 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300'
                          }`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-700 dark:text-slate-300">
                      {b.total_rows}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-teal-600 dark:text-teal-400">
                      {b.successful}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-amber-600 dark:text-amber-400">
                      {b.skipped_duplicates}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-rose-600 dark:text-rose-400">
                      {b.failed}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap text-[11px]">
                      {b.emails_sent} sent / {b.emails_failed} failed
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap text-[11px]">
                      {b.created_at ? new Date(b.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedBatch(b)}
                        className="px-2.5 py-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-400 rounded-lg transition inline-flex items-center gap-1"
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
        </div>
      )}

      {/* Batch Details Inspection Modal */}
      {selectedBatch && (
        <div ref={batchDialogRef} role="dialog" aria-modal="true" aria-label={`Batch ${selectedBatch.id} audit report`} tabIndex={-1} className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <History className="w-5 h-5 text-teal-600" />
                  <span>Batch #{selectedBatch.id} Audit Report</span>
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Course: {selectedBatch.course_name} · Completed: {selectedBatch.completed_at ? new Date(selectedBatch.completed_at).toLocaleString() : 'Processing'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedBatch(null)}
                aria-label="Close batch audit report"
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold"
              >
                ✕
              </button>
            </div>

            {/* Metrics Breakdown */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl">
                <span className="text-slate-500 block">Total Roster Rows</span>
                <span className="text-lg font-bold text-slate-900 dark:text-white mt-1 block">
                  {selectedBatch.total_rows}
                </span>
              </div>
              <div className="p-3 bg-teal-50 dark:bg-teal-950/60 rounded-xl">
                <span className="text-teal-700 dark:text-teal-300 block">Generated</span>
                <span className="text-lg font-bold text-teal-700 dark:text-teal-300 mt-1 block">
                  {selectedBatch.successful}
                </span>
              </div>
              <div className="p-3 bg-amber-50 dark:bg-amber-950/60 rounded-xl">
                <span className="text-amber-700 dark:text-amber-300 block">Skipped Dupes</span>
                <span className="text-lg font-bold text-amber-700 dark:text-amber-300 mt-1 block">
                  {selectedBatch.skipped_duplicates}
                </span>
              </div>
              <div className="p-3 bg-rose-50 dark:bg-rose-950/60 rounded-xl">
                <span className="text-rose-700 dark:text-rose-300 block">Failed Rows</span>
                <span className="text-lg font-bold text-rose-700 dark:text-rose-300 mt-1 block">
                  {selectedBatch.failed}
                </span>
              </div>
            </div>

            {/* Email delivery section */}
            <div className="p-4 bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-indigo-900 dark:text-indigo-200 font-semibold">
                  <Mail className="w-4 h-4 text-indigo-600" />
                  <span>Email Notification Delivery Status</span>
                </div>
                <span className="font-mono text-indigo-700 dark:text-indigo-300">
                  {selectedBatch.emails_sent} sent / {selectedBatch.emails_failed} failed
                </span>
              </div>
              <p className="text-slate-500 text-[11px]">
                Email notifications are sent safely using the configured SMTP backend. If SMTP is temporarily unavailable, certificates remain securely saved in PostgreSQL and can be retried.
              </p>
            </div>

            {/* Error report */}
            {selectedBatch.error_report && selectedBatch.error_report.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-xs text-rose-900 dark:text-rose-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-600" />
                    <span>Row Error & Skip Log ({selectedBatch.error_report.length})</span>
                  </h4>
                  <button
                    type="button"
                    onClick={() => downloadErrorReportCsv(selectedBatch)}
                    className="px-3 py-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5 text-rose-600" />
                    <span>Download CSV Report</span>
                  </button>
                </div>

                <div className="max-h-60 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/30 text-xs">
                  {selectedBatch.error_report.map((item, i) => (
                    <div key={i} className="py-2 flex items-center justify-between gap-4 text-[11px]">
                      <div>
                        <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                          Row #{item.row_number}:{' '}
                        </span>
                        <span>{item.student_name}</span>{' '}
                        <span className="text-slate-500">({item.student_email})</span>
                      </div>
                      <span className="text-rose-600 dark:text-rose-400 font-medium">
                        {item.error}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 bg-teal-50 dark:bg-teal-950/40 rounded-xl text-xs text-teal-800 dark:text-teal-200 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                <span>Zero row errors in this batch. All processed records were successful.</span>
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <Link
                to="/admin/dashboard/certificates"
                className="text-xs font-semibold text-teal-600 hover:underline"
              >
                View all issued certificates →
              </Link>
              <button
                type="button"
                onClick={() => setSelectedBatch(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold rounded-xl"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
