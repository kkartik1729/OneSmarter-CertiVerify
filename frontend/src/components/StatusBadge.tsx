import { Badge } from '../lib/ui';
import type { CertStatus, Kind } from '../types';

export const STATUS_LABEL: Record<CertStatus, string> = { VERIFIED: 'Verified', PENDING: 'Pending review', REJECTED: 'Rejected' };
const KIND: Record<CertStatus, Kind> = { VERIFIED: 'ok', PENDING: 'wn', REJECTED: 'er' };

/** Coloured badge for a certificate status (same for users and admins). */
export default function StatusBadge({ status }: { status: CertStatus }) {
  return <Badge k={KIND[status]}>{STATUS_LABEL[status]}</Badge>;
}
