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
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  const [search, setSearch] = useState('');
  const [selectedCert, setSelectedCert] = useState<Cert | null>(null);
  const [openLinkedIn, setOpenLinkedIn] = useState(false);

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">
            My Certificates
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Certificates associated with your account in PostgreSQL.
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
            <table className="w-full text-left text-xs">
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
                            className="w-16 h-11 object-cover rounded-md border border-slate-200 dark:border-slate-700 shadow-xs cursor-pointer hover:opacity-90 transition"
                            onClick={() => setSelectedCert(c)}
                            onError={() => setFailedImages(prev => ({ ...prev, [c.key]: true }))}
                          />
                        ) : (
                          <div
                            className="w-16 h-11 bg-slate-100 dark:bg-slate-800 rounded-md border border-slate-200 dark:border-slate-700 flex flex-col items-center justify-center text-slate-400 cursor-pointer"
                            onClick={() => setSelectedCert(c)}
                            title={isImageFailed ? "Certificate image file missing on server" : c.title}
                          >
                            <Award className="w-5 h-5 text-teal-600" />
                            {isImageFailed && (
                              <span className="text-[9px] text-rose-500 font-semibold leading-none mt-0.5">Missing</span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900 dark:text-white">
                        {c.number}
                      </td>
                      <td className="py-3.5 px-4 max-w-xs">
                        <p className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                          {c.title}
                        </p>
                        <p className="text-[11px] text-teal-600 dark:text-teal-400 truncate mt-0.5">
                          {c.courseName || c.issuer}
                        </p>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 dark:text-slate-400">
                        {c.recipient}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap text-[11px]">
                        {c.startDate && c.endDate ? `${c.startDate} → ${c.endDate}` : '—'}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap text-[11px]">
                        {c.issued}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1.5 justify-end">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedCert(c);
                              setOpenLinkedIn(false);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-teal-600 hover:text-teal-700 bg-teal-50 dark:bg-teal-950/60 dark:text-teal-400 rounded-lg transition"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>View</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedCert(c);
                              setOpenLinkedIn(true);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-[#0077B5] hover:text-[#005f94] bg-blue-50 hover:bg-blue-100/80 dark:bg-blue-950/60 dark:hover:bg-blue-900/60 dark:text-blue-300 rounded-lg transition"
                            title="LinkedIn Credential Details & Verification Link"
                          >
                            <svg viewBox="0 0 24 24" className="w-3 h-3 fill-current" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                            <span>LinkedIn</span>
                          </button>
                          {rawDownload && !isImageFailed && (
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  const blob = c.hasPdf ? await certificateService.pdfBlob(c.key) : await certificateService.imageBlob(c.key);
                                  downloadBlob(blob, `certificate_${c.number}.${c.hasPdf ? 'pdf' : 'png'}`);
                                } catch {
                                  setFailedImages(prev => ({ ...prev, [c.key]: true }));
                                }
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-lg transition"
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
        onClose={() => {
          setSelectedCert(null);
          setOpenLinkedIn(false);
        }}
        initialLinkedInOpen={openLinkedIn}
      />
    </div>
  );
}
