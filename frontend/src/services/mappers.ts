/** Converts raw backend JSON into the UI types in ../types. */
import type { Cert, CertStatus, Course, CertificateTemplate, GenerationBatch, PublicRecord, User } from '../types';

type R = Record<string, unknown>;
const rec = (v: unknown): R => (v && typeof v === 'object' ? (v as R) : {});
const s = (v: unknown, d = ''): string => (v == null ? d : String(v));
const requiredNumber = (r: R, key: string): number => {
  const value = Number(r[key]);
  if (!Number.isFinite(value)) throw new Error(`Unexpected server response: ${key} must be a number.`);
  return value;
};
const requiredString = (r: R, key: string): string => {
  if (typeof r[key] !== 'string') throw new Error(`Unexpected server response: ${key} must be text.`);
  return r[key];
};
const requiredRecord = (value: unknown, resource: string): R => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Unexpected server response for ${resource}.`);
  }
  return value as R;
};

export function mapCourse(value: unknown): Course {
  const r = requiredRecord(value, 'course');
  return {
    id: requiredNumber(r, 'id'),
    name: requiredString(r, 'name'),
    title: requiredString(r, 'title'),
    issuer: requiredString(r, 'issuer'),
    start_date: requiredString(r, 'start_date'),
    end_date: requiredString(r, 'end_date'),
    created_by: typeof r.created_by === 'number' ? r.created_by : undefined,
    created_by_username: typeof r.created_by_username === 'string' ? r.created_by_username : undefined,
    created_at: typeof r.created_at === 'string' ? r.created_at : undefined,
    updated_at: typeof r.updated_at === 'string' ? r.updated_at : undefined,
  };
}

export function mapTemplate(value: unknown): CertificateTemplate {
  const r = requiredRecord(value, 'certificate template');
  const layout = r.layout_config && typeof r.layout_config === 'object' && !Array.isArray(r.layout_config)
    ? r.layout_config as Record<string, unknown>
    : {};
  return {
    id: requiredNumber(r, 'id'),
    name: requiredString(r, 'name'),
    image: s(r.image),
    image_url: typeof r.image_url === 'string' ? r.image_url : undefined,
    description: typeof r.description === 'string' ? r.description : undefined,
    layout_config: layout,
    file_format: typeof r.file_format === 'string' ? r.file_format : undefined,
    version: typeof r.version === 'number' ? r.version : undefined,
    uploaded_by: typeof r.uploaded_by === 'number' ? r.uploaded_by : undefined,
    uploaded_by_username: typeof r.uploaded_by_username === 'string' ? r.uploaded_by_username : undefined,
    created_at: typeof r.created_at === 'string' ? r.created_at : undefined,
    updated_at: typeof r.updated_at === 'string' ? r.updated_at : undefined,
  };
}

export function mapGenerationBatch(value: unknown): GenerationBatch {
  const r = requiredRecord(value, 'generation batch');
  const allowed = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'] as const;
  if (typeof r.status !== 'string' || !allowed.includes(r.status as typeof allowed[number])) {
    throw new Error('Unexpected server response: generation batch status is invalid.');
  }
  const count = (key: string) => requiredNumber(r, key);
  return {
    id: requiredNumber(r, 'id'),
    course: typeof r.course === 'number' ? r.course : null,
    course_name: typeof r.course_name === 'string' ? r.course_name : undefined,
    template: typeof r.template === 'number' ? r.template : null,
    template_name: typeof r.template_name === 'string' ? r.template_name : undefined,
    status: r.status as GenerationBatch['status'],
    total_rows: count('total_rows'),
    successful: count('successful'),
    failed: count('failed'),
    skipped_duplicates: count('skipped_duplicates'),
    emails_sent: count('emails_sent'),
    emails_failed: count('emails_failed'),
    error_report: Array.isArray(r.error_report) ? r.error_report as GenerationBatch['error_report'] : undefined,
    created_by: typeof r.created_by === 'number' ? r.created_by : undefined,
    created_by_username: typeof r.created_by_username === 'string' ? r.created_by_username : undefined,
    created_at: typeof r.created_at === 'string' ? r.created_at : undefined,
    completed_at: typeof r.completed_at === 'string' ? r.completed_at : undefined,
  };
}

/** DRF returns either a plain array or {results: []} when pagination is on. */
export const asList = (d: unknown): R[] =>
  (Array.isArray(d) ? d : Array.isArray(rec(d).results) ? (rec(d).results as unknown[]) : []).map(rec);

/** "ADMIN" / "admin" / " Admin " -> 'admin'. Anything else -> null (access is NOT granted). */
export const normaliseRole = (v: unknown): User['role'] | null => {
  const t = typeof v === 'string' ? v.trim().toUpperCase() : '';
  return t === 'ADMIN' ? 'admin' : t === 'USER' ? 'user' : null;
};

/** GET /accounts/me/ -> User. The role comes ONLY from the backend `role` field. */
export function mapUser(x: unknown): User {
  const r = rec(x);
  const role = normaliseRole(r.role);
  if (!role) throw new Error('Your account has no recognised role (expected USER or ADMIN), so access was not granted.');
  const full = `${s(r.first_name)} ${s(r.last_name)}`.trim();
  return {
    id: s(r.id),
    username: s(r.username),
    name: full || s(r.username, 'User'),
    email: s(r.email, s(r.username)),
    role,
    organization: s(r.organization),
    phone: s(r.phone),
    emailVerified: r.email_verified === true,
    mfaEnabled: r.mfa_enabled === true,
    hasUsablePassword: r.has_usable_password === true,
    isGoogleUser: r.is_google_user === true,
    hasUnclaimedCertificates: r.has_unclaimed_certificates === true,
  };
}

const statusOf = (v: unknown): CertStatus => {
  return s(v).trim().toUpperCase() || 'PENDING';
};

/** One certificate from /certificates/. */
export function mapCert(x: unknown): Cert {
  const r = rec(x);
  const file = s(r.file);
  return {
    key: s(r.id),
    id: s(r.id),
    number: s(r.certificate_number),
    title: s(r.title),
    issuer: s(r.issuer),
    recipient: s(r.recipient_name),
    recipientEmail: s(r.recipient_email) || undefined,
    recipient_email: s(r.recipient_email) || undefined,
    isClaimed: r.is_claimed === true,
    is_claimed: r.is_claimed === true,
    issued: s(r.issue_date).slice(0, 10),
    owner: s(r.owner_username),
    status: statusOf(r.status),
    reason: s(r.rejection_reason),
    course: typeof r.course === 'number' ? r.course : undefined,
    courseName: s(r.course_name) || undefined,
    startDate: s(r.start_date).slice(0, 10) || undefined,
    endDate: s(r.end_date).slice(0, 10) || undefined,
    generationBatch: typeof r.generation_batch === 'number' ? r.generation_batch : undefined,
    emailSent: r.email_sent === true,
    emailError: s(r.email_error) || undefined,
    imageUrl: typeof r.image_url === 'string' ? r.image_url : undefined,
    downloadUrl: typeof r.download_url === 'string' ? r.download_url : undefined,
    file: file || undefined,
    isPdf: /\.pdf($|\?)/i.test(file),
    hasPdf: r.has_pdf === true,
    pdfDownloadUrl: typeof r.pdf_download_url === 'string' ? r.pdf_download_url : undefined,
    sha: s(r.file_sha256),
    createdAt: s(r.created_at).slice(0, 10),
  };
}

/** Public lookup result from /certificates/verify/<number>/. */
export function mapPublicRecord(x: unknown): PublicRecord {
  const r = rec(x);
  return {
    number: s(r.certificate_number),
    title: s(r.title),
    issuer: s(r.issuer),
    recipient: s(r.recipient_name),
    issued: s(r.issue_date).slice(0, 10),
    status: statusOf(r.status),
  };
}
