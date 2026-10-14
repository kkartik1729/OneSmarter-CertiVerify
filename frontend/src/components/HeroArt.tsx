import { useMemo } from 'react';
const poly: [number, number][] = [[300, 30], [510, 100], [510, 320], [420, 470], [300, 590], [180, 470], [90, 320], [90, 100]];
const inside = (x: number, y: number) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const p = poly[i], q = poly[j]; if ((p[1] > y) !== (q[1] > y) && x < (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1]) + p[0]) c = !c; } return c; };
export default function HeroArt() {
  const { pts, lines } = useMemo(() => {
    let a = 7; const rnd = () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const pts: [number, number, number][] = []; while (pts.length < 460) { const x = 60 + rnd() * 480, y = 20 + rnd() * 590; if (inside(x, y)) pts.push([x, y, rnd()]); }
    const lines: [number, number, number, number][] = []; pts.slice(0, 170).forEach((p, i) => { for (let j = i + 1; j < pts.length && j < i + 40; j++) { const q = pts[j]; if (Math.hypot(p[0] - q[0], p[1] - q[1]) < 46) lines.push([p[0], p[1], q[0], q[1]]); } });
    return { pts, lines };
  }, []);
  return <svg viewBox="0 0 600 620" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    <defs><radialGradient id="gl"><stop offset="0" stopColor="#3B82F6" stopOpacity=".4" /><stop offset="1" stopColor="#3B82F6" stopOpacity="0" /></radialGradient></defs>
    <circle cx="300" cy="320" r="300" fill="url(#gl)" />
    <g stroke="#7DD3FC" strokeOpacity=".3" strokeWidth=".8">{lines.map((l, i) => <line key={i} x1={l[0]} y1={l[1]} x2={l[2]} y2={l[3]} />)}</g>
    {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={0.8 + p[2] * p[2] * 3.2} fill="#7DD3FC" opacity={0.35 + p[2] * 0.65} />)}
    <path d="M205 320l65 70 125-150" fill="none" stroke="#fff" strokeWidth="16" strokeLinecap="round" strokeLinejoin="round" opacity=".92" />
  </svg>;
}
