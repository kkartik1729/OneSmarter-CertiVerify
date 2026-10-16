/** Converts raw backend JSON into the UI types in ../types. */
import type { Cert, CertStatus, PublicRecord, User } from '../types';

type R = Record<string, unknown>;
const rec = (v: unknown): R => (v && typeof v === 'object' ? (v as R) : {});
const s = (v: unknown, d = ''): string => (v == null ? d : String(v));

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
  };
}

const STATUSES: CertStatus[] = ['PENDING', 'VERIFIED', 'REJECTED'];
const statusOf = (v: unknown): CertStatus => {
  const t = s(v).toUpperCase() as CertStatus;
  return STATUSES.includes(t) ? t : 'PENDING';
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
    code: s(r.verification_code),
    sha: s(r.file_sha256),
    credentialUrl: typeof r.credential_url === 'string' ? r.credential_url : undefined,
    isCredentialUrlPublic: r.is_credential_url_public === true,
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
