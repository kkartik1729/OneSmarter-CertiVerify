import { useEffect, useState, type ReactNode } from 'react';
import { errMsg } from '../services';
export interface AsyncState<T> { data?: T; error?: string; loading: boolean; reload: () => void }
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [st, setSt] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true }), [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true; setSt(p => ({ data: p.data, loading: true }));
    fn().then(d => { if (live) setSt({ data: d, loading: false }); }).catch(e => { if (live) setSt({ error: errMsg(e), loading: false }); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...st, reload: () => setTick(t => t + 1) };
}
export function Load<T>({ s, children }: { s: AsyncState<T>; children: (d: T) => ReactNode }) {
  if (s.error) return <div className="card em" role="alert"><p>{s.error}</p>{!/not implemented/.test(s.error) && <button className="btn g s" onClick={s.reload}>Retry</button>}</div>;
  if (s.data === undefined) return <div className="card sk" aria-busy="true" aria-label="Loading"><div /><div /><div /></div>;
  return <>{children(s.data)}</>;
}
