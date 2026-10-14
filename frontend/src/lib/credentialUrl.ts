/**
 * Utility for resolving, validating, and formatting LinkedIn Credential URLs.
 *
 * LinkedIn strictly requires a publicly accessible HTTPS URL.
 * Localhost, 127.0.0.1, private LAN IPs, and non-HTTPS schemes are rejected by
 * LinkedIn with the message: "Please provide a valid URL."
 *
 * This utility guarantees:
 * 1. Never generates a LinkedIn link using localhost, 127.0.0.1, or private LAN IPs.
 * 2. Uses the configured public HTTPS domain from VITE_PUBLIC_FRONTEND_URL or backend.
 * 3. In production, if running under an HTTPS public domain, falls back to window.location.origin.
 * 4. Normalizes slashes and ensures standard URL formatting.
 * 5. If no public HTTPS domain is configured, provides a clear warning and disables copying.
 */

const PRIVATE_HOST_RE =
  /^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|::1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|.*\.local|.*\.internal|.*\.test)$/i;

const PLACEHOLDER_KEYWORDS = [
  'your-deployed-domain',
  'your_deployed_domain',
  'your-production-domain',
  'example.com',
  'placeholder',
];

/**
 * Validates whether a candidate string is a real, public HTTPS URL.
 */
export function isPublicHttpsUrl(candidate: string | null | undefined): boolean {
  if (!candidate || typeof candidate !== 'string') return false;
  const trimmed = candidate.trim();
  if (!trimmed.toLowerCase().startsWith('https://')) return false;

  for (const kw of PLACEHOLDER_KEYWORDS) {
    if (trimmed.toLowerCase().includes(kw)) {
      return false;
    }
  }

  try {
    const url = new URL(trimmed);
    const hostname = url.hostname.toLowerCase();
    if (!hostname) return false;
    if (PRIVATE_HOST_RE.test(hostname)) return false;
    // Must contain a dot to be a valid domain name
    if (!hostname.includes('.')) return false;
    return true;
  } catch {
    return false;
  }
}

/**
 * Gets the configured public HTTPS frontend base URL.
 * Checks environment variable VITE_PUBLIC_FRONTEND_URL first.
 * If running on a deployed public HTTPS website in production, uses window.location.origin.
 * Returns null if running on localhost / non-HTTPS without a public URL configured.
 */
export function getPublicFrontendBase(): string | null {
  // 1. Check explicit frontend environment variable
  const envUrl = import.meta.env.VITE_PUBLIC_FRONTEND_URL || import.meta.env.VITE_FRONTEND_URL;
  if (isPublicHttpsUrl(envUrl)) {
    return envUrl.trim().replace(/\/+$/, '');
  }

  // 2. Check current browser location if in production public HTTPS
  if (typeof window !== 'undefined' && window.location?.origin) {
    const origin = window.location.origin;
    if (isPublicHttpsUrl(origin)) {
      return origin.trim().replace(/\/+$/, '');
    }
  }

  return null;
}

export interface CredentialUrlResult {
  /** The full absolute HTTPS credential URL, or null if no public domain is configured. */
  url: string | null;
  /** True when a valid public HTTPS URL could be constructed. */
  isPublic: boolean;
  /** Development fallback URL (e.g. on localhost) for local testing only. */
  devFallbackUrl: string | null;
  /** Clear human-readable warning message when isPublic is false. */
  warning: string | null;
}

/**
 * Resolves the credential URL information for a certificate.
 */
export function getCredentialUrlInfo(cert: {
  number: string;
  credentialUrl?: string | null;
  isCredentialUrlPublic?: boolean;
}): CredentialUrlResult {
  const cleanNumber = (cert.number || '').trim().toUpperCase();

  // 1. If backend returned a verified public HTTPS URL
  if (cert.isCredentialUrlPublic && cert.credentialUrl && isPublicHttpsUrl(cert.credentialUrl)) {
    return {
      url: cert.credentialUrl,
      isPublic: true,
      devFallbackUrl: null,
      warning: null,
    };
  }

  // 2. Check frontend-configured public HTTPS domain
  const publicBase = getPublicFrontendBase();
  if (publicBase && cleanNumber) {
    const url = `${publicBase}/verify-certificate/${encodeURIComponent(cleanNumber)}`;
    return {
      url,
      isPublic: true,
      devFallbackUrl: null,
      warning: null,
    };
  }

  // 3. Fallback when running in local development / private network
  const devOrigin = typeof window !== 'undefined' ? window.location.origin.replace(/\/+$/, '') : 'http://localhost:5173';
  const devFallbackUrl = cleanNumber ? `${devOrigin}/verify-certificate/${encodeURIComponent(cleanNumber)}` : null;

  return {
    url: null,
    isPublic: false,
    devFallbackUrl,
    warning:
      'LinkedIn requires a publicly accessible HTTPS URL. Localhost and private development addresses are rejected by LinkedIn. Configure VITE_PUBLIC_FRONTEND_URL (in frontend/.env) or PUBLIC_FRONTEND_URL (in backend/.env) with your deployed HTTPS domain to enable the LinkedIn credential link.',
  };
}
