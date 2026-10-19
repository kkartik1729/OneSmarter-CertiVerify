import { useState } from 'react';
import { Check, Copy, ExternalLink, X } from 'lucide-react';
import type { Cert } from '../types';
import { isPublicHttpsUrl } from '../lib/credentialUrl';

export const LINKEDIN_ADD_CERTIFICATION_URL =
  'https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME';

function formatIssueDate(value: string): string {
  if (!value) return '—';
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(date);
}

export default function LinkedInCredentialDialog({
  cert,
  onClose,
}: {
  cert: Cert | null;
  onClose: () => void;
}) {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [copyError, setCopyError] = useState(false);

  if (!cert) return null;

  const fields = [
    { label: 'Name', value: cert.title },
    { label: 'Issuing Organization', value: cert.issuer || 'OneSmarter, Inc.' },
    { label: 'Issue Date', value: formatIssueDate(cert.issued) },
    { label: 'Credential ID', value: cert.number },
    ...(cert.credentialUrl && cert.isCredentialUrlPublic && isPublicHttpsUrl(cert.credentialUrl)
      ? [{ label: 'Credential URL', value: cert.credentialUrl }]
      : []),
  ];
  const hasPublicCredentialUrl = Boolean(
    cert.isCredentialUrlPublic && cert.credentialUrl && isPublicHttpsUrl(cert.credentialUrl),
  );

  const copyField = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(label);
      setCopyError(false);
      window.setTimeout(() => setCopiedField(null), 1800);
    } catch {
      setCopyError(true);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/60 p-3 sm:p-5"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="linkedin-dialog-title"
        className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl dark:border-slate-700 dark:bg-slate-900 sm:p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="linkedin-dialog-title" className="text-lg font-bold text-slate-900 dark:text-white">
              Add certificate to LinkedIn
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              {hasPublicCredentialUrl
                ? 'LinkedIn opens its certification form without prefilled details. Copy the values below into that form, review them, and save the certificate yourself.'
                : 'Review the certificate details below. LinkedIn sharing will be available once the site has a public HTTPS address.'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close LinkedIn certificate details"
            className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-slate-800 dark:hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {!hasPublicCredentialUrl && (
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
            A public HTTPS domain is required before this certificate can be added to LinkedIn. The credential URL will be available after the site is deployed with its public HTTPS address.
          </p>
        )}

        <div className="mt-5 space-y-2.5">
          {fields.map(({ label, value }) => (
            <div key={label} className="flex min-w-0 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
                <p className="mt-1 break-all text-sm font-medium text-slate-900 dark:text-slate-100">{value}</p>
              </div>
              <button
                type="button"
                onClick={() => void copyField(label, value)}
                aria-label={`Copy ${label}`}
                className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 hover:border-teal-300 hover:text-teal-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:text-teal-300"
              >
                {copiedField === label ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copiedField === label ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          ))}
        </div>

        {copyError && (
          <p role="alert" className="mt-3 text-xs text-rose-600 dark:text-rose-400">
            Clipboard access failed. Select and copy the field value manually.
          </p>
        )}

        <div className="mt-5 flex flex-col-reverse justify-end gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Close
          </button>
          {hasPublicCredentialUrl && (
            <a
              href={LINKEDIN_ADD_CERTIFICATION_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#0A66C2] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#004182]"
            >
              Open LinkedIn form
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </section>
    </div>
  );
}
