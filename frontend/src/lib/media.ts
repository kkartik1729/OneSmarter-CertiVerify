import { API_BASE } from '../services/http';
import { tokens } from '../services/tokens';

/**
 * Resolves a certificate image or download URL:
 * - Handles relative and absolute URLs correctly using the API base configuration.
 * - Prevents double '/media/' joining.
 * - Attaches authentication token for protected certificate endpoints so browser <img> tags load without 401.
 */
export function resolveCertificateMediaUrl(
  rawUrl: string | null | undefined,
  includeAuth = true
): string | null {
  if (!rawUrl) return null;
  let url = rawUrl.trim();
  if (!url) return null;

  // Backend origin (e.g. http://127.0.0.1:8000 or http://localhost:8005)
  const apiOrigin = API_BASE.replace(/\/api\/?$/, '');

  // If already absolute URL
  if (!/^https?:\/\//i.test(url)) {
    // Clean up duplicate leading slashes
    url = url.replace(/^\/+/, '/');
    url = `${apiOrigin}${url}`;
  }

  // If authenticated and this is a protected certificate endpoint or media URL, append token
  if (includeAuth && tokens.access && (url.includes('/api/certificates/') || url.includes('/media/certificates/'))) {
    if (!url.includes('token=')) {
      const sep = url.includes('?') ? '&' : '?';
      url = `${url}${sep}token=${encodeURIComponent(tokens.access)}`;
    }
  }

  return url;
}
