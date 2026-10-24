import { EP } from './endpoints';
import { tokens } from './tokens';

const RAW = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? (import.meta.env.VITE_API_URL as string | undefined) ?? '').trim().replace(/\/+$/, '');
/** Base URL of the API; existing `/api` and versioned `/api/vN` paths are preserved. */
export const API_BASE = RAW ? (/\/api(?:\/v\d+)?$/.test(RAW) ? RAW : `${RAW}/api`) : '/api';
const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || 15000;

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

/** status 0 = the server could not be reached (network error or timeout). */
export class ApiError extends Error {
  constructor(public status: number, message: string, public fields: Record<string, string> = {}) {
    super(message);
  }
}

const firstText = (v: unknown): string => (typeof v === 'string' ? v : Array.isArray(v) && typeof v[0] === 'string' ? v[0] : '');

/** Turns a DRF error body into an ApiError: `detail` for general errors, `fields` for per-field errors. */
function buildError(status: number, data: unknown): ApiError {
  const fields: Record<string, string> = {};
  let message = '';
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const o = data as Record<string, unknown>;
    message = firstText(o.detail) || firstText(o.message) || firstText(o.non_field_errors);
    for (const [k, v] of Object.entries(o)) {
      if (k === 'detail' || k === 'message' || k === 'non_field_errors') continue;
      const t = firstText(v);
      if (t) fields[k] = t;
    }
    const first = Object.entries(fields)[0];
    if (!message && first) message = `${first[0].replace(/_/g, ' ')}: ${first[1]}`;
  }
  if (!message) message = status >= 500 ? 'Server error. Please try again.' : status === 401 ? 'Your session is not valid.' : 'Request failed.';
  return new ApiError(status, message, fields);
}

interface Raw { ok: boolean; status: number; data: unknown }

/** One HTTP call. Throws ApiError(0) only when the server cannot be reached. */
async function request(method: Method, path: string, body: unknown, withAuth: boolean, timeoutMs = TIMEOUT_MS): Promise<Raw> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  const isForm = body instanceof FormData;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  if (withAuth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  try {
    const res = await fetch(API_BASE + path, {
      method,
      headers,
      signal: ctl.signal,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = null; }
    }
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    throw new ApiError(
      0,
      e instanceof DOMException && e.name === 'AbortError'
        ? 'The request timed out. The server may be unavailable.'
        : 'Network error: cannot reach the server. Check that the backend is running and VITE_API_BASE_URL is correct.',
    );
  } finally {
    clearTimeout(timer);
  }
}

/** Clears the session and tells the app (AuthContext) to send the user to /login. */
function expireSession() {
  // Clearing first makes concurrent failed requests emit only one expiry event.
  if (!tokens.has()) return;
  tokens.clear();
  window.dispatchEvent(new Event('auth:expired'));
}

let inflight: Promise<boolean> | null = null;

/**
 * Exchanges the refresh token for a new access token.
 * Parallel callers share ONE request, so there are never two refreshes at once.
 * Resolves false when the refresh token is invalid/expired; throws on network/server errors.
 */
function refreshAccessToken(): Promise<boolean> {
  if (inflight) return inflight;
  const refresh = tokens.refresh;
  if (!refresh) return Promise.resolve(false);
  inflight = (async () => {
    const res = await request('POST', EP.refresh, { refresh }, false);
    if (res.status === 400 || res.status === 401) return false;
    if (!res.ok) throw buildError(res.status, res.data);
    const d = res.data as { access?: unknown; refresh?: unknown } | null;
    if (!d || typeof d.access !== 'string') return false;
    tokens.set(d.access, typeof d.refresh === 'string' ? d.refresh : refresh);
    return true;
  })().finally(() => { inflight = null; });
  return inflight;
}

/**
 * The single API client used by every service.
 * withAuth=false is for login / register / refresh (no Bearer header, no refresh-and-retry).
 * On a 401 it refreshes once and retries once; if that fails the session is cleared. No loops.
 */
export async function http<T>(method: Method, path: string, body?: unknown, withAuth = true, timeoutMs = TIMEOUT_MS): Promise<T> {
  let res = await request(method, path, body, withAuth, timeoutMs);
  if (withAuth && res.status === 401) {
    const refreshed = tokens.refresh ? await refreshAccessToken() : false;
    if (refreshed) res = await request(method, path, body, true, timeoutMs);
    if (!refreshed || res.status === 401) expireSession();
  }
  if (!res.ok) throw buildError(res.status, res.data);
  return res.data as T;
}

/** Fetch an authenticated image/PDF response while preserving the shared refresh behavior. */
export async function httpBlob(path: string): Promise<Blob> {
  const fetchBlob = async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      return await fetch(API_BASE + path, {
        headers: tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {},
        signal: controller.signal,
      });
    } catch (error) {
      throw new ApiError(
        0,
        error instanceof DOMException && error.name === 'AbortError'
          ? 'The request timed out. The server may be unavailable.'
          : 'Network error: cannot reach the server.',
      );
    } finally {
      clearTimeout(timer);
    }
  };
  let response = await fetchBlob();
  if (response.status === 401) {
    const refreshed = tokens.refresh ? await refreshAccessToken() : false;
    if (refreshed) response = await fetchBlob();
    if (!refreshed || response.status === 401) expireSession();
  }
  if (!response.ok) {
    const text = await response.text();
    let data: unknown = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
    throw buildError(response.status, data);
  }
  const blob = await response.blob();
  return blob;
}
