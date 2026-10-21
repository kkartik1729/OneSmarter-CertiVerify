import { useState } from 'react';
import {
  X,
  Award,
  FileText,
  ExternalLink,
} from 'lucide-react';
import type { Cert } from '../types';
import StatusBadge from './StatusBadge';
import AuthenticatedCertificateImage from './AuthenticatedCertificateImage';
import { certificateService } from '../services';
import { downloadBlob } from '../lib/download';

interface CertificateDetailsProps {
  cert: Cert | null;
  onClose: () => void;
  userDashboard?: boolean;
}

export default function CertificateDetails({
  cert,
  onClose,
  userDashboard = false,
}: CertificateDetailsProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expandedImage, setExpandedImage] = useState(false);

  if (!cert) return null;

  const hasImage = Boolean(cert.imageUrl || (cert.file && !cert.isPdf));
  const hasPdf = Boolean(cert.hasPdf && cert.pdfDownloadUrl);

  const downloadCertificate = async (pdf: boolean) => {
    setActionError(null);
    try {
      const blob = pdf ? await certificateService.pdfBlob(cert.key) : await certificateService.imageBlob(cert.key);
      downloadBlob(blob, `certificate_${cert.number}.${pdf ? 'pdf' : 'png'}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Certificate download failed.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-xl space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 border border-teal-200 dark:border-teal-800">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Certificate Details
              </h3>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                {cert.number}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Title</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.title}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Course Name</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.courseName || cert.title}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Recipient Name</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.recipient}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Issuing Authority</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.issuer}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Course Dates</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.startDate && cert.endDate ? `${cert.startDate} to ${cert.endDate}` : cert.issued}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Issue Date</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.issued}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Owner Account</span>
            <span className="font-semibold text-slate-900 dark:text-white text-sm block">
              {cert.owner || '—'}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
            <span className="text-slate-500 block mb-1">Current Status</span>
            <div className="mt-1">
              <StatusBadge status={cert.status} />
            </div>
          </div>
        </div>

        {/* Certificate Image Preview */}
        {hasImage && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Official Generated Certificate:
              </span>
              {!imgFailed && (
                <button
                  type="button"
                  onClick={() => downloadCertificate(false)}
                  className="text-[11px] font-semibold text-teal-600 hover:underline flex items-center gap-1"
                >
                  <span>Download Image</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              )}
            </div>
            <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-950 flex items-center justify-center p-2 min-h-36">
              {!imgFailed ? (
                <button type="button" onClick={() => setExpandedImage(true)} className="max-h-72 max-w-full cursor-zoom-in" aria-label="Open certificate viewer">
                  <AuthenticatedCertificateImage
                    certificateId={cert.key}
                    alt={cert.title}
                    className="mx-auto block max-h-72 max-w-full w-auto rounded object-contain shadow"
                    onError={() => setImgFailed(true)}
                  />
                </button>
              ) : (
                <div className="text-center p-6 text-slate-400">
                  <Award className="w-8 h-8 mx-auto text-teal-500 mb-2 opacity-60" />
                  <p className="text-xs text-slate-300">Image file unavailable on storage</p>
                  <p className="text-[11px] text-slate-500 mt-1">Certificate record #{cert.number} is verified in PostgreSQL</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SHA and verification codes */}
        {!userDashboard && (cert.sha || cert.code) && (
          <div className="p-3.5 rounded-xl bg-slate-100/70 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-2 text-xs">
            {cert.sha && (
              <div>
                <span className="text-slate-500 block text-[11px] font-medium">
                  SHA-256 Checksum:
                </span>
                <span className="font-mono text-slate-800 dark:text-slate-300 break-all select-all">
                  {cert.sha}
                </span>
              </div>
            )}
            {cert.code && (
              <div>
                <span className="text-slate-500 block text-[11px] font-medium">
                  Security Code:
                </span>
                <span className="font-mono text-slate-800 dark:text-slate-300">
                  {cert.code}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Document link if uploaded or stored in DB */}
        {!userDashboard && (hasPdf ? (
          <div className="flex items-center justify-between p-3 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-xs">
            <div className="flex items-center gap-2 text-teal-800 dark:text-teal-300 font-medium">
              <FileText className="w-4 h-4 text-teal-600" />
              <span>Official Certificate PDF (PostgreSQL Stored)</span>
            </div>
            <button
              type="button"
              onClick={() => downloadCertificate(true)}
              className="inline-flex items-center gap-1 px-3 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition"
            >
              <span>Download PDF</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        ) : hasImage ? (
          <div className="flex items-center justify-between p-3 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-xs">
            <div className="flex items-center gap-2 text-teal-800 dark:text-teal-300 font-medium">
              <FileText className="w-4 h-4 text-teal-600" />
              <span>Attached Certificate Document</span>
            </div>
            <button
              type="button"
              onClick={() => setExpandedImage(true)}
              className="inline-flex items-center gap-1 px-3 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition"
            >
              <span>View Document</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        ) : null)}
        {actionError && <p role="alert" className="text-xs text-rose-700 dark:text-rose-300">{actionError}</p>}
        {expandedImage && (
          <AuthenticatedCertificateImage certificateId={cert.key} alt={cert.title} zoomable onClose={() => setExpandedImage(false)} />
        )}

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
