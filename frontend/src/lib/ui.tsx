import { useEffect, useState, type ReactNode } from 'react';
import type { Kind } from '../types';
import { useTheme } from './theme';
const P: Record<string, string> = {
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/>', upload: '<path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v4h16v-4"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>', search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21h4"/>', user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/>', home: '<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  chart: '<path d="M4 20V4m0 16h16M8 16v-5m4 5V8m4 8v-3"/>', alert: '<path d="M12 3l10 18H2zM12 10v5m0 3v.01"/>', out: '<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M16 8l4 4-4 4M20 12H9"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-4 3-6 7-6s7 2 7 6M17 5a3.5 3.5 0 0 1 0 6m2 3c2 1 3 3 3 6"/>', db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 2 4 3 8 3s8-1 8-3V5M4 12c0 2 4 3 8 3s8-1 8-3"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>', phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M19 5l-1.5 1.5m-11 11L5 19"/>', moon: '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
};
export const Icon = ({ n }: { n: string }) => <svg className="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" dangerouslySetInnerHTML={{ __html: P[n] }} />;
const SYM: Record<Kind, string> = { ok: '✓', wn: '!', er: '✕', in: 'i', mu: '•' };
export const Badge = ({ k, children }: { k: Kind; children: ReactNode }) => <span className={`b ${k}`}>{SYM[k]} {children}</span>;
export const Stat = ({ label, value }: { label: string; value: ReactNode }) => <div className="card"><div className="sv">{value}</div><div className="sl">{label}</div></div>;
export const toast = (m: string, k: 'ok' | 'er' = 'ok') => window.dispatchEvent(new CustomEvent('toast', { detail: { m, k } }));
export function Toaster() {
  const [t, setT] = useState<{ m: string; k: string } | null>(null);
  useEffect(() => { let id = 0; const h = (e: Event) => { setT((e as CustomEvent).detail); clearTimeout(id); id = window.setTimeout(() => setT(null), 3500); }; window.addEventListener('toast', h); return () => window.removeEventListener('toast', h); }, []);
  return <div id="toast" aria-live={t?.k === 'er' ? 'assertive' : 'polite'}>{t && <div className={`tt2 ${t.k}`} role={t.k === 'er' ? 'alert' : 'status'}>{t.m}</div>}</div>;
}
export const ask = (msg: string) => new Promise<boolean>(res => {
  const d = document.createElement('dialog'), f = document.createElement('form'), p = document.createElement('p'), r = document.createElement('div');
  f.method = 'dialog'; p.textContent = msg; r.className = 'row'; r.style.justifyContent = 'flex-end';
  ['Cancel', 'Confirm'].forEach((l, i) => { const b = document.createElement('button'); b.className = i ? 'btn d' : 'btn g'; b.value = i ? 'y' : 'n'; b.textContent = l; r.append(b); });
  f.append(p, r); d.append(f); document.body.append(d); d.showModal(); d.onclose = () => { res(d.returnValue === 'y'); d.remove(); };
});
export const askText = (msg: string) => new Promise<string | null>(res => {
  const d = document.createElement('dialog'), f = document.createElement('form'), p = document.createElement('p'), input = document.createElement('input'), r = document.createElement('div');
  f.method = 'dialog'; p.textContent = msg; input.type = 'text'; input.required = true; input.className = 'f-inp'; input.style.width = '100%'; input.style.margin = '8px 0';
  r.className = 'row'; r.style.justifyContent = 'flex-end';
  ['Cancel', 'Submit'].forEach((l, i) => { const b = document.createElement('button'); b.className = i ? 'btn' : 'btn g'; b.value = i ? 'y' : 'n'; b.textContent = l; r.append(b); });
  f.append(p, input, r); d.append(f); document.body.append(d); d.showModal(); input.focus();
  d.onclose = () => { res(d.returnValue === 'y' ? input.value : null); d.remove(); };
});
export const Brand = () => <><span className="m"><Icon n="shield" /></span>OneSmarter CertiVerify</>;
export function ThemeToggle() {
  const { theme, toggle } = useTheme(), next = theme === 'dark' ? 'light' : 'dark';
  return <button type="button" className="ib2" onClick={toggle} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`} style={{ cursor: 'pointer' }}><Icon n={theme === 'dark' ? 'sun' : 'moon'} /></button>;
}
