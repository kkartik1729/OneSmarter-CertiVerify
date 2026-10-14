import { useState, useEffect } from 'react';
import {
  X,
  Award,
  FileText,
  ExternalLink,
  Link2,
  Copy,
  CheckCheck,
  AlertTriangle,
  ShieldCheck,
} from 'lucide-react';
import type { Cert } from '../types';
import StatusBadge from './StatusBadge';
import { resolveCertificateMediaUrl } from '../lib/media';
import { getCredentialUrlInfo } from '../lib/credentialUrl';

interface CertificateDetailsProps {
  cert: Cert | null;
  onClose: () => void;
  initialLinkedInOpen?: boolean;
}

export default function CertificateDetails({
  cert,
  onClose,
  initialLinkedInOpen = false,
}: CertificateDetailsProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showLinkedIn, setShowLinkedIn] = useState(initialLinkedInOpen);

  useEffect(() => {
    if (initialLinkedInOpen) {
      setShowLinkedIn(true);
    }
  }, [initialLinkedInOpen]);

  if (!cert) return null;

  const { url: credentialUrl, isPublic, devFallbackUrl } = getCredentialUrlInfo(cert);

  const handleCopy = async () => {
    if (!isPublic || !credentialUrl) {
      return;
    }
    try {
      await navigator.clipboard.writeText(credentialUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch {
      // fallback: select + copy via execCommand
      const ta = document.createElement('textarea');
      ta.value = credentialUrl;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    }
  };

  const resolvedImg = resolveCertificateMediaUrl(cert.imageUrl || cert.file);
  const resolvedDownload = resolveCertificateMediaUrl(cert.downloadUrl || cert.imageUrl || cert.file);
  const resolvedPdf = resolveCertificateMediaUrl(cert.pdfDownloadUrl);

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
        {(cert.imageUrl || (cert.file && !cert.isPdf)) && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Official Generated Certificate:
              </span>
              {resolvedDownload && !imgFailed && (
                <a
                  href={resolvedDownload}
                  download={`certificate_${cert.number}.png`}
                  className="text-[11px] font-semibold text-teal-600 hover:underline flex items-center gap-1"
                >
                  <span>Download Image</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-950 flex items-center justify-center p-2 min-h-36">
              {resolvedImg && !imgFailed ? (
                <img
                  src={resolvedImg}
                  alt={cert.title}
                  className="max-h-72 w-auto object-contain rounded shadow"
                  onError={() => setImgFailed(true)}
                />
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
        {(cert.sha || cert.code) && (
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
        {(cert.hasPdf && resolvedPdf) ? (
          <div className="flex items-center justify-between p-3 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-xs">
            <div className="flex items-center gap-2 text-teal-800 dark:text-teal-300 font-medium">
              <FileText className="w-4 h-4 text-teal-600" />
              <span>Official Certificate PDF (PostgreSQL Stored)</span>
            </div>
            <a
              href={resolvedPdf}
              download
              className="inline-flex items-center gap-1 px-3 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition"
            >
              <span>Download PDF</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        ) : resolvedImg ? (
          <div className="flex items-center justify-between p-3 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-xs">
            <div className="flex items-center gap-2 text-teal-800 dark:text-teal-300 font-medium">
              <FileText className="w-4 h-4 text-teal-600" />
              <span>Attached Certificate Document</span>
            </div>
            <a
              href={resolvedImg}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition"
            >
              <span>View Document</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        ) : null}

        {/* ── Credential URL / LinkedIn Actions ── */}
        <div className="space-y-3">
          {/* Credential URL display or Configuration Warning */}
          {isPublic && credentialUrl ? (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-teal-600" />
                  Public HTTPS Credential URL (LinkedIn Verified):
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 bg-teal-100 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-md">
                  Active HTTPS
                </span>
              </div>
              <div className="flex items-center gap-2 p-3 bg-teal-50/40 dark:bg-teal-950/20 border border-teal-200 dark:border-teal-800/70 rounded-xl text-xs">
                <Link2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
                <span className="font-mono text-teal-900 dark:text-teal-200 truncate flex-1 font-medium select-all">
                  {credentialUrl}
                </span>
              </div>
            </div>
          ) : (
            <div className="p-3.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/80 rounded-xl text-xs space-y-2">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="space-y-1.5">
                  <p className="font-semibold text-amber-900 dark:text-amber-200 text-xs">
                    Public HTTPS Domain Required for LinkedIn
                  </p>
                  <p className="text-amber-800 dark:text-amber-300/90 leading-relaxed text-[11px]">
                    LinkedIn requires a publicly accessible HTTPS website domain. Development addresses (localhost) cannot be used for LinkedIn certification.
                  </p>
                  {devFallbackUrl && (
                    <div className="pt-1 text-[11px] text-slate-600 dark:text-slate-400">
                      <span className="text-slate-500 block mb-0.5 font-medium">Local development link (browser only):</span>
                      <span className="font-mono bg-white dark:bg-slate-900 px-2 py-1 rounded border border-slate-200 dark:border-slate-800 block truncate">
                        {devFallbackUrl}
                      </span>
                    </div>
                  )}
                  <p className="text-[10px] text-amber-800/90 dark:text-amber-400/90 pt-0.5">
                    💡 To generate a valid LinkedIn link: set <code className="bg-amber-100 dark:bg-amber-900/60 px-1 py-0.5 rounded font-mono font-bold">VITE_PUBLIC_FRONTEND_URL=https://your-domain.com</code> in frontend or <code className="bg-amber-100 dark:bg-amber-900/60 px-1 py-0.5 rounded font-mono font-bold">PUBLIC_FRONTEND_URL</code> in backend.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              id={`copy-credential-url-${cert.number}`}
              type="button"
              disabled={!isPublic}
              onClick={handleCopy}
              title={
                isPublic
                  ? 'Copy Credential URL'
                  : 'Copying disabled: LinkedIn requires a public HTTPS URL. Localhost cannot be used for LinkedIn.'
              }
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl border transition ${
                !isPublic
                  ? 'opacity-60 cursor-not-allowed bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500'
                  : copied
                  ? 'bg-teal-50 border-teal-200 text-teal-700 dark:bg-teal-950/40 dark:border-teal-800 dark:text-teal-300'
                  : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              {copied ? (
                <CheckCheck className="w-3.5 h-3.5" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
              <span>
                {copied
                  ? 'Copied!'
                  : isPublic
                  ? 'Copy Credential URL'
                  : 'Copy Credential URL (HTTPS Required)'}
              </span>
            </button>

            <button
              id={`linkedin-details-btn-${cert.number}`}
              type="button"
              onClick={() => setShowLinkedIn((v) => !v)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl border bg-[#0077B5] hover:bg-[#005f94] border-[#0077B5] text-white transition"
            >
              {/* LinkedIn SVG icon */}
              <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-current" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
              <span>{showLinkedIn ? 'Hide LinkedIn Details' : 'Add to LinkedIn'}</span>
            </button>
          </div>

          {/* LinkedIn Details panel */}
          {showLinkedIn && (
            <div className="border border-[#0077B5]/30 bg-blue-50/30 dark:bg-blue-950/20 rounded-xl p-4 space-y-4 text-xs">
              <div className="flex items-center gap-2 text-[#0077B5] dark:text-blue-400 font-semibold">
                <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current flex-shrink-0" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                <span>LinkedIn Licenses &amp; Certifications — Field Values</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {[
                  { label: 'Name', value: cert.title },
                  { label: 'Issuing Organization', value: 'OneSmarter, Inc.' },
                  { label: 'Issue Date', value: cert.issued },
                  { label: 'Credential ID', value: cert.number },
                  {
                    label: 'Credential URL',
                    value: isPublic && credentialUrl ? (
                      credentialUrl
                    ) : (
                      <span className="text-amber-600 dark:text-amber-400 text-[11px] font-normal italic">
                        ⚠️ Requires public HTTPS domain (Localhost disabled)
                      </span>
                    ),
                  },
                ].map(({ label, value }) => (
                  <div
                    key={label}
                    className="p-2.5 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700"
                  >
                    <span className="block text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-0.5">
                      {label}
                    </span>
                    <span className="font-medium text-slate-900 dark:text-white break-all">
                      {value}
                    </span>
                  </div>
                ))}
              </div>

              <div className="text-slate-600 dark:text-slate-400 space-y-1.5 leading-relaxed">
                <p className="font-semibold text-slate-700 dark:text-slate-300">
                  How to add to LinkedIn:
                </p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>
                    Go to your LinkedIn profile and click{' '}
                    <strong>Add profile section → Recommended → Licenses &amp; Certifications</strong>.
                  </li>
                  <li>
                    Fill in the fields above exactly as shown. For{' '}
                    <strong>Issuing Organization</strong> search for{' '}
                    <em>OneSmarter, Inc.</em>
                  </li>
                  <li>
                    Paste the <strong>Credential URL</strong> and <strong>Credential ID</strong>{' '}
                    in the corresponding fields.
                  </li>
                  <li>
                    Click <strong>Save</strong>. Recruiters can then click the credential URL to
                    verify your certificate instantly — no login or account creation required.
                  </li>
                </ol>
                {!isPublic && (
                  <div className="p-2 rounded bg-amber-100/60 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-amber-900 dark:text-amber-200 text-[11px]">
                    <strong>Note:</strong> LinkedIn requires a live public HTTPS website URL. Once your website is deployed, set <code className="font-mono">PUBLIC_FRONTEND_URL</code> in your server environment to automatically generate valid public LinkedIn credential links.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

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
