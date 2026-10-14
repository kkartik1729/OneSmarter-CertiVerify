export { ApiError, API_BASE } from './http';
export { authService, profileService, mfaService, passwordResetService } from './auth';
export type { LoginResult } from './auth';
export { certificateService, verificationService, courseService, templateService, generationService } from './certificates';
export { dashboardService } from './dashboard';
export { adminUsersService } from './users';
export { verificationHistoryService } from './verification';
export type { VerificationCheckResponse } from './verification';

/** Safe message for any thrown error or response. */
export const errMsg = (e: unknown): string => {
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  return 'An unexpected error occurred. Please try again.';
};
