import { useEffect, useState, type FormEvent } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { certificateService, adminUsersService, errMsg, ApiError } from '../services';
import type { Cert, AdminUser } from '../types';
import { toast } from '../lib/ui';

interface CertificateFormProps {
  onSuccess?: (newCert: Cert) => void;
}

export default function CertificateForm({ onSuccess }: CertificateFormProps) {
  const [number, setNumber] = useState('');
  const [title, setTitle] = useState('');
  const [issuer, setIssuer] = useState('');
  const [recipient, setRecipient] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10));
  const [file, setFile] = useState<File | null>(null);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [successCert, setSuccessCert] = useState<Cert | null>(null);

  useEffect(() => {
    let active = true;
    setLoadingUsers(true);
    adminUsersService
      .list()
      .then(list => {
        if (active) setUsers(list);
      })
      .catch(err => {
        console.error('Failed to load registered accounts for certificate ownership:', err);
      })
      .finally(() => {
        if (active) setLoadingUsers(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    if (!number.trim() || !title.trim() || !issuer.trim() || !recipient.trim() || !issueDate) {
      setError('Please fill in all required fields.');
      return;
    }

    if (!ownerId) {
      setError('Please select an existing registered user account to assign this certificate to.');
      setFieldErrors({ owner_id: 'Please select an owner account.' });
      return;
    }

    setLoading(true);
    try {
      const created = await certificateService.create({
        number: number.trim(),
        title: title.trim(),
        issuer: issuer.trim(),
        recipient: recipient.trim(),
        issued: issueDate,
        owner_id: ownerId,
        file: file ?? undefined,
      });

      setSuccessCert(created);
      toast('Certificate successfully created and recorded in database.');
      if (onSuccess) onSuccess(created);

      // Reset form
      setNumber('');
      setTitle('');
      setIssuer('');
      setRecipient('');
      setOwnerId('');
      setFile(null);
    } catch (err) {
      if (err instanceof ApiError && err.fields) {
        setFieldErrors(err.fields);
      }
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">
          Register New Certificate
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Store an authentic certificate in PostgreSQL and assign it to a registered user account.
        </p>
      </div>

      {successCert && (
        <div className="mb-6 p-4 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-300 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-teal-600 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold">Certificate #{successCert.number} registered!</p>
              <p className="text-xs text-teal-700 dark:text-teal-400">
                Issued to {successCert.recipient} ({successCert.owner}) by {successCert.issuer}.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSuccessCert(null)}
            className="text-xs underline text-teal-700 hover:text-teal-900"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Certificate Number */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Certificate Number / Unique ID *
            </label>
            <input
              type="text"
              required
              value={number}
              onChange={e => setNumber(e.target.value)}
              placeholder="e.g. CERT-2026-98124"
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600"
            />
            {fieldErrors.certificate_number && (
              <p className="text-xs text-rose-600 mt-1">{fieldErrors.certificate_number}</p>
            )}
          </div>

          {/* Certificate Title */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Certificate Title *
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Advanced Cybersecurity Professional"
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600"
            />
            {fieldErrors.title && (
              <p className="text-xs text-rose-600 mt-1">{fieldErrors.title}</p>
            )}
          </div>

          {/* Recipient Name */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Recipient Full Name *
            </label>
            <input
              type="text"
              required
              value={recipient}
              onChange={e => setRecipient(e.target.value)}
              placeholder="e.g. John Doe"
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600"
            />
            {fieldErrors.recipient_name && (
              <p className="text-xs text-rose-600 mt-1">{fieldErrors.recipient_name}</p>
            )}
          </div>

          {/* Assigned Owner Account Dropdown */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Assigned Account (Registered User) *
            </label>
            <select
              required
              value={ownerId}
              onChange={e => setOwnerId(e.target.value)}
              disabled={loadingUsers}
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 disabled:opacity-50"
            >
              <option value="">
                {loadingUsers ? 'Loading registered accounts...' : 'Select a registered user account...'}
              </option>
              {users.map(u => {
                const fullName = `${u.first_name || ''} ${u.last_name || ''}`.trim();
                const label = fullName
                  ? `${fullName} (${u.email || u.username})`
                  : `${u.username}${u.email ? ` (${u.email})` : ''}`;
                return (
                  <option key={u.id} value={u.id}>
                    {label}
                  </option>
                );
              })}
            </select>
            {(fieldErrors.owner_id || fieldErrors.owner) && (
              <p className="text-xs text-rose-600 mt-1">{fieldErrors.owner_id || fieldErrors.owner}</p>
            )}
          </div>

          {/* Issuer */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Issuing Organization *
            </label>
            <input
              type="text"
              required
              value={issuer}
              onChange={e => setIssuer(e.target.value)}
              placeholder="e.g. OneSmarter Global Academy"
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600"
            />
            {fieldErrors.issuer && (
              <p className="text-xs text-rose-600 mt-1">{fieldErrors.issuer}</p>
            )}
          </div>

          {/* Issue Date */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Issue Date *
            </label>
            <input
              type="date"
              required
              value={issueDate}
              onChange={e => setIssueDate(e.target.value)}
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600"
            />
            {fieldErrors.issue_date && (
              <p className="text-xs text-rose-600 mt-1">{fieldErrors.issue_date}</p>
            )}
          </div>

          {/* File Upload (Optional) */}
          <div className="sm:col-span-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Certificate Document (Optional PDF / Image)
            </label>
            <div className="relative border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-teal-500 dark:hover:border-teal-500 rounded-xl p-3 text-center transition cursor-pointer bg-slate-50 dark:bg-slate-800/40">
              <input
                type="file"
                accept=".pdf,image/*"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="flex items-center justify-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                {file ? (
                  <>
                    <FileText className="w-4 h-4 text-teal-600" />
                    <span className="font-semibold text-teal-700 dark:text-teal-400 truncate max-w-[200px]">
                      {file.name}
                    </span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4 text-slate-400" />
                    <span>Choose or drag a PDF / image file</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-slate-200 dark:border-slate-800">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-50 rounded-xl shadow-sm transition flex items-center gap-2"
          >
            {loading ? 'Submitting to PostgreSQL...' : 'Register Certificate'}
          </button>
        </div>
      </form>
    </div>
  );
}
