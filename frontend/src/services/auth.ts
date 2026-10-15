import type { User } from '../types';
import { EP } from './endpoints';
import { http } from './http';
import { mapUser } from './mappers';
import { tokens } from './tokens';

/** Step 1 of login either finishes (tokens + profile) or asks for the Google Authenticator code. */
export type LoginResult =
  | { kind: 'success'; user: User }
  | { kind: 'mfa'; challenge: string; detail: string; qrCode?: string; secret?: string; isSetup?: boolean };

interface LoginResponse {
  access?: unknown;
  refresh?: unknown;
  mfa_required?: unknown;
  mfa_setup_required?: unknown;
  challenge?: unknown;
  qr_code?: unknown;
  secret?: unknown;
  detail?: unknown;
  user?: unknown;
}

/** Saves the tokens, then loads the profile. If the profile fails (or has no valid role) the tokens are discarded. */
async function finishLogin(d: LoginResponse): Promise<User> {
  if (typeof d.access !== 'string' || typeof d.refresh !== 'string') throw new Error('Unexpected response from the server. Please try again.');
  tokens.set(d.access, d.refresh);
  try {
    if (d.user) {
      try {
        return mapUser(d.user);
      } catch {
        // Fall back to fetching me() if payload was partial
      }
    }
    return await authService.me();
  } catch (e) {
    tokens.clear();
    throw e;
  }
}

let restoreInFlight: Promise<User | null> | null = null;

export const authService = {
  /** POST /accounts/login/ {username, password} */
  async login(username: string, password: string): Promise<LoginResult> {
    const d = await http<LoginResponse>('POST', EP.login, { username, password }, false);
    if (d.mfa_required === true) {
      // An MFA challenge is NOT a login: no tokens exist yet.
      if (typeof d.challenge !== 'string' || !d.challenge) throw new Error('Unexpected response from the server. Please try again.');
      return {
        kind: 'mfa',
        challenge: d.challenge,
        detail: typeof d.detail === 'string' ? d.detail : 'Enter your Google Authenticator code.',
        qrCode: typeof d.qr_code === 'string' ? d.qr_code : undefined,
        secret: typeof d.secret === 'string' ? d.secret : undefined,
        isSetup: d.mfa_setup_required === true,
      };
    }
    return { kind: 'success', user: await finishLogin(d) };
  },

  /** POST /accounts/login/ {challenge, code}  (login step 2) */
  async verifyMfa(challenge: string, code: string): Promise<User> {
    const d = await http<LoginResponse>('POST', EP.login, { challenge, code }, false);
    return finishLogin(d);
  },

  /** POST /accounts/google-login/ {id_token} - Directly authenticates via trusted Google OAuth without extra MFA prompt */
  async googleLogin(idToken: string): Promise<User> {
    const d = await http<LoginResponse>('POST', EP.googleLogin, { id_token: idToken }, false);
    return finishLogin(d);
  },

  /** POST /accounts/register/. The backend returns NO tokens, so the user must sign in afterwards. */
  async register(p: { username: string; email: string; first_name: string; last_name: string; password: string; password_confirm: string }): Promise<void> {
    await http('POST', EP.register, p, false);
  },

  /** POST /accounts/verify-email/ {email, otp, token} */
  async verifyEmail(data: { email?: string; otp?: string; token?: string }): Promise<{ detail: string; claimedCount: number; claimedCertificates: string[] }> {
    const res = await http<{ detail?: string; claimed_count?: number; claimed_certificate_numbers?: string[] }>(
      'POST',
      EP.verifyEmail,
      data,
      false,
    );
    return {
      detail: typeof res.detail === 'string' ? res.detail : 'Email verified successfully.',
      claimedCount: Number(res.claimed_count || 0),
      claimedCertificates: Array.isArray(res.claimed_certificate_numbers) ? res.claimed_certificate_numbers : [],
    };
  },

  /** POST /accounts/resend-verification/ {email} */
  async resendVerification(email: string): Promise<string> {
    const res = await http<{ detail?: string }>('POST', EP.resendVerification, { email }, false);
    return typeof res.detail === 'string' ? res.detail : 'Verification code sent to your email.';
  },

  /** GET /accounts/me/ (role is read from this response only). */
  async me(): Promise<User> {
    return mapUser(await http<unknown>('GET', EP.me));
  },

  /** Restores the session after a page reload. Returns null when there are no stored tokens. Shares in-flight request. */
  async restore(): Promise<User | null> {
    if (!tokens.has()) return null;
    if (restoreInFlight) return restoreInFlight;
    restoreInFlight = authService.me().finally(() => {
      restoreInFlight = null;
    });
    return restoreInFlight;
  },

  logout(): void {
    tokens.clear();
  },
};

export const profileService = {
  /** PATCH /accounts/me/ — the backend only accepts phone and organization. */
  async update(p: { organization: string; phone: string }): Promise<User> {
    return mapUser(await http<unknown>('PATCH', EP.me, p));
  },
};

export const mfaService = {
  /** POST /accounts/mfa/setup/ -> QR code (PNG data URL). */
  async setup(): Promise<{ qr: string; message: string }> {
    const d = await http<{ qr_code?: unknown; message?: unknown }>('POST', EP.mfaSetup, {});
    const qr = typeof d.qr_code === 'string' ? d.qr_code : '';
    if (!qr.startsWith('data:image/png;base64,')) throw new Error('The server did not return a valid QR code.');
    return { qr, message: typeof d.message === 'string' ? d.message : '' };
  },

  /** POST /accounts/mfa/confirm/ {code} */
  async confirm(code: string): Promise<string> {
    const d = await http<{ detail?: unknown }>('POST', EP.mfaConfirm, { code });
    return typeof d.detail === 'string' ? d.detail : 'Authenticator MFA enabled.';
  },

  /** POST /accounts/mfa/recovery/request/ {email} */
  async requestRecovery(email: string): Promise<string> {
    const d = await http<{ detail?: unknown }>('POST', EP.mfaRecoveryRequest, { email }, false);
    return typeof d.detail === 'string' ? d.detail : 'Recovery instructions have been sent to your email address.';
  },

  /** POST /accounts/mfa/recovery/confirm/ {token} */
  async confirmRecovery(token: string): Promise<{ qr: string; secret: string; challenge: string; detail: string; email?: string }> {
    const d = await http<{ qr_code?: unknown; secret?: unknown; challenge?: unknown; detail?: unknown; email?: unknown }>(
      'POST',
      EP.mfaRecoveryConfirm,
      { token },
      false,
    );
    const qr = typeof d.qr_code === 'string' ? d.qr_code : '';
    const challenge = typeof d.challenge === 'string' ? d.challenge : '';
    const secret = typeof d.secret === 'string' ? d.secret : '';
    if (!qr.startsWith('data:image/png;base64,') || !challenge) {
      throw new Error('Invalid recovery response from the server.');
    }
    return {
      qr,
      secret,
      challenge,
      detail: typeof d.detail === 'string' ? d.detail : 'Scan the new QR code to re-enroll your authenticator.',
      email: typeof d.email === 'string' ? d.email : undefined,
    };
  },

  /** POST /accounts/mfa/recovery/complete/ {challenge, code} */
  async completeRecovery(challenge: string, code: string): Promise<{ detail: string; success: boolean }> {
    const d = await http<{ detail?: unknown; success?: unknown }>(
      'POST',
      EP.mfaRecoveryComplete,
      { challenge, code },
      false,
    );
    return {
      detail:
        typeof d.detail === 'string'
          ? d.detail
          : 'MFA recovery complete. Your new authenticator has been enrolled and activated.',
      success: true,
    };
  },
};

export const passwordResetService = {
  /** POST /accounts/password-reset/request/ {email} */
  async requestReset(email: string): Promise<string> {
    const d = await http<{ detail?: unknown }>('POST', EP.passwordResetRequest, { email }, false);
    return typeof d.detail === 'string'
      ? d.detail
      : 'If an account exists with that email, a password reset link has been sent.';
  },

  /** Alias requestOtp -> requestReset for backward compatibility */
  async requestOtp(email: string): Promise<string> {
    return this.requestReset(email);
  },

  /** POST /accounts/password-reset/validate/ {token} */
  async validateToken(token: string): Promise<{ valid: boolean; email?: string; detail: string }> {
    const d = await http<{ valid?: unknown; email?: unknown; detail?: unknown }>(
      'POST',
      EP.passwordResetValidate,
      { token },
      false,
    );
    return {
      valid: Boolean(d.valid),
      email: typeof d.email === 'string' ? d.email : undefined,
      detail: typeof d.detail === 'string' ? d.detail : 'Password reset link is valid.',
    };
  },

  /** POST /accounts/password-reset/verify/ {email, otp} */
  async verifyOtp(email: string, otp: string): Promise<{ resetToken: string; detail: string }> {
    const d = await http<{ reset_token?: unknown; detail?: unknown }>(
      'POST',
      EP.passwordResetVerify,
      { email, otp },
      false,
    );
    const resetToken = typeof d.reset_token === 'string' ? d.reset_token : '';
    if (!resetToken) {
      throw new Error('Verification failed. Invalid response from server.');
    }
    return {
      resetToken,
      detail: typeof d.detail === 'string' ? d.detail : 'Verification code accepted.',
    };
  },

  /** POST /accounts/password-reset/complete/ {token, password, password_confirm} */
  async completeReset(token: string, password: string, passwordConfirm: string): Promise<string> {
    const d = await http<{ detail?: unknown }>(
      'POST',
      EP.passwordResetComplete,
      {
        token,
        reset_token: token,
        password,
        password_confirm: passwordConfirm,
      },
      false,
    );
    return typeof d.detail === 'string'
      ? d.detail
      : 'Your password has been changed successfully. Please sign in.';
  },
};


