import { useEffect, useMemo, useRef, useState } from 'react';
import type { CertificateTemplate } from '../types';
import { templateService } from '../services/certificates';

const FIELDS = ['recipient_name', 'certificate_id', 'course_name', 'course_description', 'start_date', 'end_date', 'issue_date'];
type TextElement = { type: 'text'; text: string; x: number; y: number; width: number; fontSize: number; color: string; align: string; fontFamily?: string; bold?: boolean };
type Redaction = { x: number; y: number; width: number; height: number; color: string };

const previewFontFamily = (family?: string) => ({
  Arial: 'Arial, sans-serif',
  'DejaVu Sans': '"DejaVu Sans", Arial, sans-serif',
  Serif: '"DejaVu Serif", Georgia, serif',
  Monospace: '"DejaVu Sans Mono", Consolas, monospace',
}[family || 'Arial'] || 'Arial, sans-serif');

const keepCertificateIdPlaceholder = (previous: string, next: string) => {
  const identifierToken = /\{\{\s*(?:certificate_id|certificate_number)\s*\}\}/i;
  if (identifierToken.test(previous) && !identifierToken.test(next)) {
    return `${next.trimEnd()} {{ certificate_id }}`.trim();
  }
  return next;
};

const withCertificateIdLabel = (text: string) => {
  if (/^(?:certificate_id|certificate_number)$/i.test(text.trim())) {
    return 'Certificate ID: {{ certificate_id }}';
  }
  const hasIdentifier = /\{\{\s*(?:certificate_id|certificate_number)\s*\}\}/i.test(text);
  return hasIdentifier && !/^\s*Certificate\s+ID\s*:/i.test(text)
    ? `Certificate ID: ${text}`
    : text;
};

/** Positions reusable text layers over the template preview in normalized coordinates. */
export default function TemplateLayoutEditor({ template, onClose, onSaved }: {
  template: CertificateTemplate; onClose: () => void; onSaved: (template: CertificateTemplate) => void;
}) {
  const original = useMemo(() => Array.isArray(template.layout_config?.elements)
    ? (template.layout_config.elements as TextElement[]).map((item) => ({ ...item, text: withCertificateIdLabel(item.text) }))
    : [], [template]);
  const [elements, setElements] = useState<TextElement[]>(original.map((element) => ({ ...element })));
  const [redactions, setRedactions] = useState<Redaction[]>(Array.isArray(template.layout_config?.redactions) ? template.layout_config.redactions as Redaction[] : []);
  const [selected, setSelected] = useState(0);
  const [selectedRedaction, setSelectedRedaction] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [placementText, setPlacementText] = useState<string | null>(null);
  const [fontScale, setFontScale] = useState(1);
  const imageRef = useRef<HTMLImageElement>(null);
  const dragRef = useRef<{ kind: 'text' | 'redaction'; index: number; startX: number; startY: number; pointerX: number; pointerY: number; width: number; height: number } | null>(null);

  useEffect(() => {
    const image = imageRef.current;
    if (!image) return;
    const updateScale = () => {
      if (image.naturalWidth > 0) setFontScale(image.getBoundingClientRect().width / image.naturalWidth);
    };
    updateScale();
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(updateScale) : null;
    observer?.observe(image);
    window.addEventListener('resize', updateScale);
    return () => { observer?.disconnect(); window.removeEventListener('resize', updateScale); };
  }, [template.image_url, template.image]);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const nextX = (item: { width: number }) => Math.max(0, Math.min(1 - item.width, drag.startX + (event.clientX - drag.pointerX) / drag.width));
      const nextY = Math.max(0, Math.min(1, drag.startY + (event.clientY - drag.pointerY) / drag.height));
      if (drag.kind === 'text') setElements((items) => items.map((item, i) => i === drag.index ? { ...item, x: nextX(item), y: nextY } : item));
      else setRedactions((items) => items.map((item, i) => i === drag.index ? { ...item, x: nextX(item), y: nextY } : item));
    };
    const onUp = () => { dragRef.current = null; };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
  }, []);

  const place = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!placementText) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    if (placementText === '__cover__') {
      setSelectedRedaction(redactions.length);
      setRedactions((items) => [...items, { x, y, width: .32, height: .065, color: '#ffffff' }]);
    } else {
      const newElement = { type: 'text' as const, text: placementText, x, y, width: .56, fontSize: 28, color: '#202020', align: 'center', fontFamily: 'Arial' };
      setSelectedRedaction(null);
      setSelected(elements.length);
      setElements((items) => [...items, newElement]);
    }
    setPlacementText(null);
  };

  const beginDrag = (event: React.PointerEvent<HTMLDivElement>, kind: 'text' | 'redaction', index: number) => {
    if (placementText) return;
    event.preventDefault();
    event.stopPropagation();
    if (kind === 'text') { setSelected(index); setSelectedRedaction(null); }
    else setSelectedRedaction(index);
    const bounds = event.currentTarget.parentElement?.getBoundingClientRect();
    if (!bounds || !bounds.width || !bounds.height) return;
    const item = kind === 'text' ? elements[index] : redactions[index];
    dragRef.current = { kind, index, startX: item.x, startY: item.y, pointerX: event.clientX, pointerY: event.clientY, width: bounds.width, height: bounds.height };
  };
  const save = async () => {
    setSaving(true); setError('');
    try {
      const updated = await templateService.saveLayout(template.id, { ...(template.layout_config || {}), elements, redactions });
      onSaved(updated); onClose();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save template layout.'); }
    finally { setSaving(false); }
  };
  const active = elements[selected];
  return <div className="fixed inset-0 z-[80] bg-slate-950/80 p-3 sm:p-6 overflow-auto" role="dialog" aria-modal="true" aria-label={`Edit ${template.name} layout`}>
    <div className="mx-auto max-w-6xl rounded-2xl bg-white dark:bg-slate-900 shadow-2xl overflow-hidden">
      <header className="flex items-center justify-between gap-3 p-4 border-b border-slate-200 dark:border-slate-700">
        <div><h2 className="font-bold text-lg text-slate-900 dark:text-white">Template layout · {template.name}</h2><p className="text-xs text-slate-500 dark:text-slate-400">Drag text layers to position them. Changes are saved per template.</p></div>
        <button className="px-3 py-2 rounded-lg border border-slate-300 text-slate-800 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-800" onClick={onClose}>Close</button>
      </header>
      <div className="grid lg:grid-cols-[1fr_280px] gap-4 p-4">
        <div className="max-h-[72vh] overflow-auto bg-slate-100 dark:bg-slate-800 p-3 rounded-xl">
          <div className={`relative mx-auto w-fit max-w-full select-none ${placementText ? 'cursor-crosshair' : ''}`} style={{ lineHeight: 0 }} onClick={place}>
            <img ref={imageRef} src={template.image_url || template.image} alt={`${template.name} page preview`} onLoad={() => { const image = imageRef.current; if (image?.naturalWidth) setFontScale(image.getBoundingClientRect().width / image.naturalWidth); }} className="block max-h-[68vh] max-w-full object-contain" draggable={false} />
            {redactions.map((cover, index) => <div key={`cover-${index}`} onPointerDown={(event) => beginDrag(event, 'redaction', index)} className={`absolute cursor-move border border-dashed ${selectedRedaction === index ? 'border-amber-600' : 'border-transparent hover:border-amber-400'}`} style={{ left: `${cover.x * 100}%`, top: `${cover.y * 100}%`, width: `${cover.width * 100}%`, height: `${cover.height * 100}%`, background: cover.color }} />)}
            {elements.map((item, index) => <div key={index} onPointerDown={(event) => beginDrag(event, 'text', index)}
              className={`absolute cursor-move border border-dashed px-1 py-0.5 whitespace-nowrap ${selected === index ? 'border-blue-600 bg-blue-100/40' : 'border-transparent hover:border-blue-400'}`}
              style={{ left: `${item.x * 100}%`, top: `${item.y * 100}%`, width: `${item.width * 100}%`, fontSize: `${Math.max(1, item.fontSize * fontScale)}px`, fontFamily: previewFontFamily(item.fontFamily), lineHeight: 1.15, color: item.color, fontWeight: item.bold ? 700 : 400, textAlign: item.align as CanvasTextAlign }}>
              {item.text.replace(/\{\{\s*([\w]+)\s*\}\}/g, (_, key) => ({ recipient_name: 'Alex Morgan', student_name: 'Alex Morgan', certificate_id: 'OSCV-YYYY-XXXXXXXX', certificate_number: 'OSCV-YYYY-XXXXXXXX', course_name: 'Sample Course', course_description: 'Completion description', start_date: '01/07/2026', end_date: '01/10/2026', issue_date: '16/10/2026' } as Record<string, string>)[key] || key)}
            </div>)}
          </div>
        </div>
        <aside className="space-y-3 text-sm text-slate-800 dark:text-slate-100">
          <div className="font-semibold">Choose a field, then click its position</div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Certificate ID preview: OSCV-YYYY-XXXXXXXX. The real unique ID and year are inserted when a certificate is generated.</p>
          <div className="flex flex-wrap gap-1">{FIELDS.map((field) => {
            const fieldText = field === 'certificate_id' ? 'Certificate ID: {{ certificate_id }}' : `{{ ${field} }}`;
            return <button key={field} onClick={() => setPlacementText(fieldText)} className={`rounded-md border px-2 py-1 text-xs text-slate-800 dark:text-slate-100 ${placementText === fieldText ? 'border-blue-600 bg-blue-50 dark:bg-blue-950' : 'border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800'}`}>{field}</button>;
          })}</div>
          <button onClick={() => setPlacementText('New text')} className="rounded-md bg-slate-100 px-3 py-2 text-slate-800 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700">Place text</button>
          <button onClick={() => setPlacementText('__cover__')} className="ml-2 rounded-md bg-amber-50 px-3 py-2 text-amber-900 hover:bg-amber-100 dark:bg-amber-950 dark:text-amber-200 dark:hover:bg-amber-900">Cover printed text</button>
          {placementText && <p className="text-xs text-blue-700 dark:text-blue-300">Click on the certificate to {placementText === '__cover__' ? 'place a cover area' : `place ${placementText}`}.</p>}
          {selectedRedaction !== null && redactions[selectedRedaction] && <div className="space-y-2 border-t pt-3 dark:border-slate-700">
            <p className="font-medium">Cover area settings</p>
            <label className="block">Width<input type="range" min=".03" max=".9" step=".005" className="w-full" value={redactions[selectedRedaction].width} onChange={(e) => setRedactions((items) => items.map((x, i) => i === selectedRedaction ? { ...x, width: Number(e.target.value) } : x))} /></label>
            <label className="block">Height<input type="range" min=".01" max=".25" step=".005" className="w-full" value={redactions[selectedRedaction].height} onChange={(e) => setRedactions((items) => items.map((x, i) => i === selectedRedaction ? { ...x, height: Number(e.target.value) } : x))} /></label>
            <label className="block">Cover color<input type="color" className="ml-2 align-middle" value={redactions[selectedRedaction].color} onChange={(e) => setRedactions((items) => items.map((x, i) => i === selectedRedaction ? { ...x, color: e.target.value } : x))} /></label>
            <button className="text-red-600" onClick={() => { setRedactions((items) => items.filter((_, i) => i !== selectedRedaction)); setSelectedRedaction(null); }}>Delete cover</button>
          </div>}
          {active && selectedRedaction === null && <div className="space-y-2 border-t pt-3 dark:border-slate-700">
            <label className="block">Text<input className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100" value={active.text} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, text: keepCertificateIdPlaceholder(x.text, e.target.value) } : x))} /></label>
            <label className="block">Font size (template image px)<input type="number" min="8" max="120" className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100" value={active.fontSize} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, fontSize: Number(e.target.value) || 8 } : x))} /></label>
            <label className="block">Font family<select className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100" value={active.fontFamily || 'Arial'} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, fontFamily: e.target.value } : x))}><option>Arial</option><option>DejaVu Sans</option><option>Serif</option><option>Monospace</option></select></label>
            <label className="block">Color<input type="color" className="ml-2 align-middle" value={active.color} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, color: e.target.value } : x))} /></label>
            <label className="block">Width<input type="range" min=".15" max=".9" step=".01" className="w-full" value={active.width} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, width: Number(e.target.value) } : x))} /></label>
            <label className="block">Alignment<select className="mt-1 w-full rounded border p-2 text-slate-900" value={active.align} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, align: e.target.value } : x))}><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select></label>
            <label className="inline-flex items-center gap-2"><input type="checkbox" checked={!!active.bold} onChange={(e) => setElements((items) => items.map((x, i) => i === selected ? { ...x, bold: e.target.checked } : x))} />Bold</label>
            <button className="text-red-600" onClick={() => { setElements((items) => items.filter((_, i) => i !== selected)); setSelected(0); }}>Delete selected layer</button>
          </div>}
          <p className="text-xs text-amber-700 dark:text-amber-400">Cover regions are reversible layout masks applied only to generated output; the source template remains unchanged. Match the cover color to its local background. Flattened or scanned artwork is not directly editable.</p>
          {error && <p className="text-red-600 dark:text-red-400" role="alert">{error}</p>}
          <button disabled={saving} onClick={save} className="w-full rounded-lg bg-blue-600 px-3 py-2 font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60">{saving ? 'Saving…' : 'Save layout'}</button>
        </aside>
      </div>
    </div>
  </div>;
}
