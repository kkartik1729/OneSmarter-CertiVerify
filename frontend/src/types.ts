export type Role = 'user' | 'admin';
export type CertStatus = 'PENDING' | 'VERIFIED' | 'REJECTED' | 'REVOKED' | (string & {});
export type Kind = 'ok' | 'wn' | 'er' | 'in' | 'mu';

export interface User {
  id?: string;
  username?: string;
  name: string;
  email: string;
  role: Role;
  organization?: string;
  phone?: string;
  isStaff?: boolean;
  isSuperuser?: boolean;
  dateJoined?: string;
  mfaEnabled?: boolean;
  emailVerified?: boolean;
  hasUsablePassword?: boolean;
  isGoogleUser?: boolean;
  hasUnclaimedCertificates?: boolean;
}

export interface AdminUser {
  id: number | string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: 'ADMIN' | 'USER';
  date_joined: string;
  mfa_enabled?: boolean;
  email_verified?: boolean;
  phone?: string;
  organization?: string;
}

export interface Cert {
  key: string;
  id?: string;
  number: string;
  title: string;
  issuer: string;
  recipient: string;
  recipientEmail?: string;
  recipient_email?: string;
  isClaimed?: boolean;
  is_claimed?: boolean;
  issued: string;
  owner: string;
  status: CertStatus;
  reason?: string;
  course?: number;
  courseName?: string;
  startDate?: string;
  endDate?: string;
  generationBatch?: number;
  emailSent?: boolean;
  emailError?: string;
  imageUrl?: string;
  downloadUrl?: string;
  file?: string;        // legacy filesystem path
  isPdf?: boolean;
  pdf?: boolean;
  hasPdf?: boolean;        // true when PDF is stored in PostgreSQL
  pdfDownloadUrl?: string; // URL to download the PostgreSQL-stored PDF
  code?: string;
  sha?: string;
  createdAt?: string;
}

export interface Course {
  id: number;
  name: string;
  title: string;
  issuer: string;
  start_date: string;
  end_date: string;
  created_by?: number;
  created_by_username?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CertificateTemplate {
  id: number;
  name: string;
  image: string;
  image_url?: string;
  description?: string;
  layout_config?: Record<string, any>;
  file_format?: string;
  version?: number;
  uploaded_by?: number;
  uploaded_by_username?: string;
  created_at?: string;
  updated_at?: string;
}

export interface GenerationBatch {
  id: number;
  course: number | null;
  course_name?: string;
  template: number | null;
  template_name?: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  total_rows: number;
  successful: number;
  failed: number;
  skipped_duplicates: number;
  emails_sent: number;
  emails_failed: number;
  error_report?: Array<{
    row_number: number | string;
    student_name: string;
    student_email: string;
    error: string;
  }>;
  created_by?: number;
  created_by_username?: string;
  created_at?: string;
  completed_at?: string;
}

export interface CSVValidationRow {
  row_number: number;
  student_name: string;
  student_email: string;
  course_name: string;
  start_date: string;
  end_date: string;
  issue_date: string;
  user_id: number | null;
  has_account?: boolean;
  is_valid: boolean;
  errors: string[];
}

export interface CSVValidationResult {
  total_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  is_valid: boolean;
  rows: CSVValidationRow[];
  batch_defaults?: {
    course_name: string;
    start_date: string;
    end_date: string;
    issue_date: string;
  };
}

export interface NewCert {
  file?: File;
  title: string;
  number: string;
  issuer: string;
  recipient: string;
  issued: string;
  owner_id?: number | string;
}

export interface PublicRecord {
  number: string;
  title: string;
  issuer: string;
  recipient: string;
  issued: string;
  status: CertStatus;
}

export interface Trusted {
  id: string;
  title: string;
  org: string;
  name: string;
  issued: string;
  src: string;
}

export interface Verification {
  kind: Kind;
  title: string;
  detail: string;
  record?: PublicRecord | Trusted;
  id?: string;
  found?: boolean;
  certificate?: {
    title: string;
    issuer: string;
    issue_date: string;
  };
}

export interface VerificationAttemptItem {
  id: number;
  certificate_number: string;
  result: 'FOUND' | 'NOT_FOUND' | 'VERIFIED' | 'REJECTED';
  verification_result?: string;
  certificate_title?: string | null;
  requested_by_username: string | null;
  created_at: string;
}

export interface DashboardStats {
  role: 'ADMIN' | 'USER';
  statistics: {
    total: number;
    verified: number;
    pending: number;
    rejected: number;
  };
  recent_certificates: Array<{
    id: number;
    certificate_number: string;
    title: string;
    issuer: string;
    recipient_name: string;
    status: CertStatus;
    created_at: string;
  }>;
  admin_stats?: {
    total_users: number;
    total_certificates: number;
    total_verification_attempts: number;
    successful_verifications: number;
    unsuccessful_verifications: number;
    certificate_trend: Array<{ date: string; count: number }>;
    verification_trend: Array<{ date: string; total: number; found: number; not_found: number }>;
    issuer_breakdown: Array<{ issuer: string; count: number }>;
    recent_verifications: Array<{
      id: number;
      certificate_number: string;
      result: string;
      created_at: string;
      requested_by: string | null;
    }>;
  };
}

export interface HistoryItem {
  id: string;
  at: string;
  title: string;
  kind: Kind;
}

export interface Notif {
  text: string;
  when: string;
  read: boolean;
  to: string;
}

export interface DemoUser {
  name: string;
  email: string;
  role: Role;
  joined: string;
  active: boolean;
}

export interface LogRow {
  id: string;
  at: string;
  title: string;
  kind: Kind;
  ms: number;
}
