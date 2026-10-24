import { useEffect, useState } from 'react';
import { Award, Eye, RefreshCw, Download } from 'lucide-react';
import { certificateService, errMsg } from '../../services';
import type { Cert } from '../../types';
import StatusBadge from '../../components/StatusBadge';
import SearchInput from '../../components/SearchInput';
import CertificateDetails from '../../components/CertificateDetails';
import LoadingSkeleton from '../../components/LoadingSkeleton';
import EmptyState from '../../components/EmptyState';
import ErrorMessage from '../../components/ErrorMessage';
import AuthenticatedCertificateImage from '../../components/AuthenticatedCertificateImage';
import { downloadBlob } from '../../lib/download';

export default function MyCertificates() {
  const [certs, setCerts] = useState<Cert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  const [search, setSearch] = useState('');
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
    const q = search.toLowerCase().trim();
    return (
      !q ||
      c.number.toLowerCase().includes(q) ||
      c.title.toLowerCase().includes(q) ||
      c.issuer.toLowerCase().includes(q) ||
      c.recipient.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {downloadError && <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">{downloadError}</p>}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            My Certificates
          </h2>
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

      <div className="flex items-center justify-between">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search my certificates..."
          className="max-w-md w-full"
        />
      </div>

      {loading ? (
        <LoadingSkeleton lines={5} height="h-12" />
      ) : error ? (
        <ErrorMessage message={error} onRetry={loadData} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Certificates Found"
          description={
            search
              ? 'No certificates match your search query.'
              : 'You do not have any certificates registered yet.'
          }
          icon={Award}
        />
      ) : (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] table-fixed text-left text-xs xl:min-w-0">
              <colgroup>
                <col className="w-[8%]" />
                <col className="w-[11%]" />
                <col className="w-[15%]" />
                <col className="w-[10%]" />
                <col className="w-[14%]" />
                <col className="w-[10%]" />
                <col className="w-[8%]" />
                <col className="w-[24%]" />
              </colgroup>
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3.5 px-4">Thumbnail</th>
                  <th className="py-3.5 px-4">Certificate ID</th>
                  <th className="py-3.5 px-4">Title & Course</th>
                  <th className="py-3.5 px-4">Recipient</th>
                  <th className="py-3.5 px-4">Course Dates</th>
                  <th className="py-3.5 px-4">Issue Date</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filtered.map(c => {
                  const rawThumb = c.imageUrl || (c.file && !c.isPdf ? c.file : null);
                  const rawDownload = c.downloadUrl || (c.hasPdf && c.pdfDownloadUrl ? c.pdfDownloadUrl : c.imageUrl || c.file);
                  const isImageFailed = failedImages[c.key] === true;

                  return (
                    <tr
                      key={c.key}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                    >
                      <td className="py-3 px-4">
                        {rawThumb && !isImageFailed ? (
                          <AuthenticatedCertificateImage
                            certificateId={c.key}
                            alt={c.title}
                            thumbnail
                            className="w-16 h-11 object-cover rounded-md border border-slate-200 dark:border-slate-700 shadow-xs cursor-pointer hover:opacity-90 transition"
                            onClick={() => setSelectedCert(c)}
                            onError={() => setFailedImages(prev => ({ ...prev, [c.key]: true }))}
                          />
                        ) : (
                          <button
                            type="button"
                            aria-label={`Open certificate details for ${c.title}`}
                            className="w-16 h-11 bg-slate-100 dark:bg-slate-800 rounded-md border border-slate-200 dark:border-slate-700 flex flex-col items-center justify-center text-slate-400 cursor-pointer"
                            onClick={() => setSelectedCert(c)}
                            title={isImageFailed ? "Certificate image file missing on server" : c.title}
                          >
                            <Award className="w-5 h-5 text-teal-600" />
                            {isImageFailed && (
                              <span className="text-[9px] text-rose-500 font-semibold leading-none mt-0.5">Missing</span>
                            )}
                          </button>
                        )}
                      </td>
                      <td className="py-3.5 px-3 font-mono font-medium text-slate-900 dark:text-white break-all">
                        {c.number}
                      </td>
                      <td className="py-3.5 px-3 min-w-0">
                        <p className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                          {c.title}
                        </p>
                        <p className="text-[11px] text-teal-600 dark:text-teal-400 truncate mt-0.5">
                          {c.courseName || c.issuer}
                        </p>
                      </td>
                      <td className="py-3.5 px-3 text-slate-600 dark:text-slate-400 break-words">
                        {c.recipient}
                      </td>
                      <td className="py-3.5 px-3 text-slate-500 dark:text-slate-400 text-[11px] break-words">
                        {c.startDate && c.endDate ? `${c.startDate} → ${c.endDate}` : '—'}
                      </td>
                      <td className="py-3.5 px-3 text-slate-500 dark:text-slate-400 text-[11px] whitespace-nowrap">
                        {c.issued}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3.5 px-2 whitespace-nowrap">
                        <div className="flex flex-nowrap items-center justify-end gap-1">
                          <button
                            type="button"
                              aria-label={`Open certificate details for ${c.title}`}
                            onClick={() => setSelectedCert(c)}
                            className="inline-flex shrink-0 items-center gap-1 px-2 py-1 text-[11px] font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-400 rounded-lg transition"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>View</span>
                          </button>
                          {rawDownload && !isImageFailed && (
                            <button
                              type="button"
                              onClick={async () => {
                                setDownloadError(null);
                                try {
                                  const blob = c.hasPdf ? await certificateService.pdfBlob(c.key) : await certificateService.imageBlob(c.key);
                                  downloadBlob(blob, `certificate_${c.number}.${c.hasPdf ? 'pdf' : 'png'}`);
                                } catch (err) {
                                  setDownloadError(errMsg(err));
                                }
                              }}
                              className="inline-flex shrink-0 items-center gap-1 px-2 py-1 text-[11px] font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-lg transition"
                              title="Download Certificate"
                            >
                              <Download className="w-3.5 h-3.5 text-teal-600" />
                              <span>Download</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="py-3 px-4 bg-slate-50 dark:bg-slate-800/40 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 flex items-center justify-between">
            <span>Showing {filtered.length} of {certs.length} records</span>
            <span>Private User Records</span>
          </div>
        </div>
      )}

      <CertificateDetails
        cert={selectedCert}
        onClose={() => setSelectedCert(null)}
        userDashboard
      />
    </div>
  );
}
