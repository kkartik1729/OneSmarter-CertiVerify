import type { VerificationAttemptItem } from '../types';
import { EP } from './endpoints';
import { http } from './http';
import { asList } from './mappers';
import { tokens } from './tokens';

export interface VerificationCheckResponse {
  certificate_number: string;
  found: boolean;
  verification_result: string;
  status: string;
  message: string;
  certificate?: {
    title: string;
    issuer: string;
    issue_date: string;
  };
}

export const verificationHistoryService = {
  list: async (): Promise<VerificationAttemptItem[]> => {
    const data = await http<unknown>('GET', EP.verificationHistory);
    return asList(data).map(r => ({
      id: Number(r.id),
      certificate_number: String(r.certificate_number ?? ''),
      result: (String(r.result ?? 'NOT_FOUND') as VerificationAttemptItem['result']),
      verification_result: String(
        r.verification_result ?? (r.result === 'VERIFIED' ? 'VERIFIED' : String(r.result ?? 'NOT_FOUND'))
      ),
      certificate_title: r.certificate_title ? String(r.certificate_title) : null,
      requested_by_username: r.requested_by_username ? String(r.requested_by_username) : null,
      created_at: String(r.created_at ?? ''),
    }));
  },

  check: async (certificateNumber: string): Promise<VerificationCheckResponse> => {
    const number = certificateNumber.trim().toUpperCase();
    return http<VerificationCheckResponse>(
      'POST',
      EP.verificationCheck,
      { certificate_number: number },
      Boolean(tokens.access)
    );
  },
};
