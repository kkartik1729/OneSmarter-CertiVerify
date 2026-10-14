import { useMemo, useState, type ReactNode } from 'react';
/** q = cell texts joined by "|" (used for search, filter and sorting). */
export interface Row { c: ReactNode[]; q: string }
export default function DataTable({ heads, rows, filters, size = 6 }: { heads: string[]; rows: Row[]; filters?: string[]; size?: number }) {
  const [q, setQ] = useState(''), [f, setF] = useState(''), [pg, setPg] = useState(0), [sort, setSort] = useState<[number, 1 | -1]>([-1, 1]);
  const rs = useMemo(() => {
    const t = q.toLowerCase(), g = f.toLowerCase();
    const r = rows.filter(x => { const s = x.q.toLowerCase(); return s.includes(t) && (!g || s.includes(g)); });
    return sort[0] < 0 ? r : [...r].sort((a, b) => (a.q.split('|')[sort[0]] ?? '').localeCompare(b.q.split('|')[sort[0]] ?? '') * sort[1]);
  }, [rows, q, f, sort]);
  const pages = Math.max(1, Math.ceil(rs.length / size)), cur = Math.min(pg, pages - 1);
  return <div>
    <div className="tt"><label className="sr" htmlFor="tq">Search</label><input id="tq" type="search" placeholder="Search…" value={q} onChange={e => { setQ(e.target.value); setPg(0); }} />
      {filters && <select aria-label="Filter" value={f} onChange={e => { setF(e.target.value); setPg(0); }}><option value="">All</option>{filters.map(x => <option key={x}>{x}</option>)}</select>}</div>
    <div className="tw"><table><thead><tr>{heads.map((h, i) => <th key={i} onClick={() => setSort([i, sort[0] === i ? (-sort[1] as 1 | -1) : 1])}>{h}</th>)}</tr></thead>
      <tbody>{rs.slice(cur * size, cur * size + size).map((r, i) => <tr key={i}>{r.c.map((x, j) => <td key={j}>{x}</td>)}</tr>)}{!rs.length && <tr><td colSpan={heads.length} className="em">No matching records.</td></tr>}</tbody></table></div>
    <div className="pgr"><span>{rs.length} result{rs.length === 1 ? '' : 's'} · Page {cur + 1}/{pages}</span>
      <button className="btn g s" disabled={cur === 0} onClick={() => setPg(cur - 1)}>Prev</button><button className="btn g s" disabled={cur >= pages - 1} onClick={() => setPg(cur + 1)}>Next</button></div>
  </div>;
}
