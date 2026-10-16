/** Backend URLs, relative to VITE_API_BASE_URL (for example http://127.0.0.1:8000/api). */
export const EP = {
  // accounts
  login: '/accounts/login/',
  setPassword: '/accounts/set-password/',
  googleLogin: '/accounts/google-login/',
  register: '/accounts/register/',
  verifyEmail: '/accounts/verify-email/',
  resendVerification: '/accounts/resend-verification/',
  refresh: '/accounts/token/refresh/',
  me: '/accounts/me/',
  mfaSetup: '/accounts/mfa/setup/',
  mfaConfirm: '/accounts/mfa/confirm/',
  mfaRecoveryRequest: '/accounts/mfa/recovery/request/',
  mfaRecoveryConfirm: '/accounts/mfa/recovery/confirm/',
  mfaRecoveryComplete: '/accounts/mfa/recovery/complete/',
  passwordResetRequest: '/accounts/password-reset/request/',
  passwordResetValidate: '/accounts/password-reset/validate/',
  passwordResetVerify: '/accounts/password-reset/verify/',
  passwordResetComplete: '/accounts/password-reset/complete/',
  adminUsers: '/accounts/admin/users/',
  adminUser: (id: string | number) => `/accounts/admin/users/${id}/`,
  // certificates
  certificates: '/certificates/',
  certificate: (id: string | number) => `/certificates/${encodeURIComponent(String(id))}/`,
  certificateImage: (id: string | number, download = false) =>
    `/certificates/${encodeURIComponent(String(id))}/image/${download ? '?download=true' : ''}`,
  review: (id: string | number) => `/certificates/${encodeURIComponent(String(id))}/review/`,
  verify: (num: string) => `/certificates/verify/${encodeURIComponent(num)}/`,
  retryEmail: (id: string | number) => `/certificates/${encodeURIComponent(String(id))}/retry-email/`,

  // course management
  courses: '/certificates/courses/',
  course: (id: string | number) => `/certificates/courses/${encodeURIComponent(String(id))}/`,

  // certificate templates
  templates: '/certificates/templates/',
  template: (id: string | number) => `/certificates/templates/${encodeURIComponent(String(id))}/`,

  // generation workflows
  csvTemplate: '/certificates/generate/csv-template/',
  validateCsv: '/certificates/generate/validate-csv/',
  bulkGenerate: '/certificates/generate/bulk/',
  singleGenerate: '/certificates/generate/single/',
  previewCertificate: '/certificates/generate/preview/',
  batches: '/certificates/generate/batches/',
  batch: (id: string | number) => `/certificates/generate/batches/${encodeURIComponent(String(id))}/`,
  // verification
  verificationCheck: '/verification/check/',
  verificationHistory: '/verification/history/',
  // dashboard
  dashboard: '/dashboard/',
  // audit
  auditLogs: '/audit/logs/',
} as const;
