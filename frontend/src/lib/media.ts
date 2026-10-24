import { API_BASE } from '../services/http';

/**
 * Resolves a certificate image or download URL:
 * - Handles relative and absolute URLs correctly using the API base configuration.
 * - Prevents double '/media/' joining.
 * - Resolves media paths without putting credentials in URLs. Protected binary endpoints
 *   must be fetched through the authenticated API client and displayed as object URLs.
 */
export function resolveCertificateMediaUrl(
  rawUrl: string | null | undefined,
  _includeAuth = true
): string | null {
  if (!rawUrl) return null;
  let url = rawUrl.trim();
  if (!url) return null;

  // Backend origin (e.g. http://127.0.0.1:8000)
  const apiOrigin = API_BASE.replace(/\/api\/?$/, '');

  // If already absolute URL
  if (!/^https?:\/\//i.test(url)) {
    // Clean up duplicate leading slashes
    url = url.replace(/^\/+/, '/');
    url = `${apiOrigin}${url}`;
  }

  return url;
}
