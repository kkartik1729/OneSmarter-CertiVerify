import { Badge } from '../lib/ui';
import type { CertStatus, Kind } from '../types';

export const STATUS_LABEL: Partial<Record<CertStatus, string>> = {
  VERIFIED: 'Verified',
  PENDING: 'Pending review',
  REJECTED: 'Rejected',
  REVOKED: 'Revoked',
  NOT_VERIFIED: 'Not verified',
};

/** Coloured badge for a certificate status (same for users and admins). */
export default function StatusBadge({ status }: { status: CertStatus }) {
  const kind: Kind = status === 'VERIFIED' ? 'ok' : status === 'PENDING' ? 'wn' : 'er';
  const label = STATUS_LABEL[status] || status.toLowerCase().replace(/(^|_)\w/g, (part) => part.toUpperCase()).replace(/_/g, ' ');
  return <Badge k={kind}>{label}</Badge>;
}
