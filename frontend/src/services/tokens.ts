/**
 * Token storage.
 * Access + refresh tokens live in memory and are mirrored to sessionStorage so that a page
 * reload keeps the session (sessionStorage is cleared when the tab closes).
 * Tokens are never logged.
 */
const KEY = 'cv-session';

interface Pair { access: string; refresh: string }

function read(): Pair | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<Pair> | null;
    if (p && typeof p.access === 'string' && typeof p.refresh === 'string') return { access: p.access, refresh: p.refresh };
  } catch {
    /* storage unavailable or corrupt: treat as signed out */
  }
  return null;
}

let pair: Pair | null = read();

function write() {
  try {
    if (pair) sessionStorage.setItem(KEY, JSON.stringify(pair));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the session then lasts until reload */
  }
}

export const tokens = {
  get access(): string | null { return pair?.access ?? null; },
  get refresh(): string | null { return pair?.refresh ?? null; },
  has: (): boolean => pair !== null,
  set(access: string, refresh: string) { pair = { access, refresh }; write(); },
  clear() { pair = null; write(); },
};
