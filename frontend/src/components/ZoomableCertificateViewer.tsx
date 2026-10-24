import { useEffect, useRef, useState, type MouseEvent, type PointerEvent } from 'react';
import { createPortal } from 'react-dom';
import { Maximize2, X, ZoomIn, ZoomOut } from 'lucide-react';

interface Props {
  src: string;
  alt: string;
  onClose: () => void;
}

interface Point {
  x: number;
  y: number;
}

interface FitSize {
  width: number;
  height: number;
}

const MIN_ZOOM = 1;
const MAX_ZOOM = 6;

function clampZoom(value: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
}

function distance(a: Point, b: Point) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/** Full-screen image viewer that initially fits the complete certificate. */
export default function ZoomableCertificateViewer({ src, alt, onClose }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const imageRef = useRef<HTMLImageElement>(null);
  const pointersRef = useRef(new Map<number, Point>());
  const gestureRef = useRef<{
    kind: 'pan' | 'pinch';
    startPoint?: Point;
    lastPoint?: Point;
    startZoom: number;
    startOffset: Point;
    startDistance?: number;
    startMidpoint?: Point;
  } | null>(null);
  const lastTapRef = useRef<{ at: number; point: Point } | null>(null);
  const lastTouchDoubleTapRef = useRef(0);
  const [fitSize, setFitSize] = useState<FitSize | null>(null);
  const [zoom, setZoom] = useState(MIN_ZOOM);
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 });
  const [imageFailed, setImageFailed] = useState(false);

  const fitToScreen = () => {
    const viewport = viewportRef.current;
    const image = imageRef.current;
    if (!viewport || !image?.naturalWidth || !image.naturalHeight) return;
    const available = viewport.getBoundingClientRect();
    const fit = Math.min(
      available.width / image.naturalWidth,
      available.height / image.naturalHeight,
      1,
    );
    setFitSize({
      width: Math.max(1, image.naturalWidth * fit),
      height: Math.max(1, image.naturalHeight * fit),
    });
    setZoom(MIN_ZOOM);
    setOffset({ x: 0, y: 0 });
    pointersRef.current.clear();
    gestureRef.current = null;
  };

  useEffect(() => {
    setImageFailed(false);
    setFitSize(null);
    setZoom(MIN_ZOOM);
    setOffset({ x: 0, y: 0 });
  }, [src]);

  useEffect(() => {
    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = priorOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const recalculate = () => fitToScreen();
    const observer = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(recalculate)
      : null;
    observer?.observe(viewport);
    window.addEventListener('resize', recalculate);
    window.addEventListener('orientationchange', recalculate);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', recalculate);
      window.removeEventListener('orientationchange', recalculate);
    };
  }, [src]);

  const getPoint = (event: { currentTarget: HTMLDivElement; clientX: number; clientY: number }): Point => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const centerOffsetForZoom = (point: Point, nextZoom: number) => {
    const viewport = viewportRef.current;
    if (!viewport) return { x: 0, y: 0 };
    const bounds = viewport.getBoundingClientRect();
    const fromCenter = { x: point.x - bounds.width / 2, y: point.y - bounds.height / 2 };
    const imagePoint = { x: (fromCenter.x - offset.x) / zoom, y: (fromCenter.y - offset.y) / zoom };
    return {
      x: fromCenter.x - imagePoint.x * nextZoom,
      y: fromCenter.y - imagePoint.y * nextZoom,
    };
  };

  const clampOffset = (candidate: Point, scale = zoom): Point => {
    const viewport = viewportRef.current;
    if (!viewport || !fitSize || scale <= MIN_ZOOM) return { x: 0, y: 0 };
    const bounds = viewport.getBoundingClientRect();
    const maxX = Math.max(0, (fitSize.width * scale - bounds.width) / 2);
    const maxY = Math.max(0, (fitSize.height * scale - bounds.height) / 2);
    return {
      x: Math.min(maxX, Math.max(-maxX, candidate.x)),
      y: Math.min(maxY, Math.max(-maxY, candidate.y)),
    };
  };

  const toggleZoomAt = (point: Point) => {
    const nextZoom = zoom > MIN_ZOOM ? MIN_ZOOM : 2;
    setOffset(nextZoom === MIN_ZOOM ? { x: 0, y: 0 } : clampOffset(centerOffsetForZoom(point, nextZoom), nextZoom));
    setZoom(nextZoom);
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest('button')) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = getPoint(event);
    const now = Date.now();
    const previousTap = lastTapRef.current;
    if (event.pointerType === 'touch' && previousTap && now - previousTap.at < 320 && distance(point, previousTap.point) < 24) {
      toggleZoomAt(point);
      lastTouchDoubleTapRef.current = now;
      lastTapRef.current = null;
      return;
    }
    if (event.pointerType === 'touch') lastTapRef.current = { at: now, point };

    pointersRef.current.set(event.pointerId, point);
    const points = [...pointersRef.current.values()];
    if (points.length >= 2) {
      const center = midpoint(points[0], points[1]);
      gestureRef.current = {
        kind: 'pinch',
        startZoom: zoom,
        startOffset: offset,
        startDistance: Math.max(1, distance(points[0], points[1])),
        startMidpoint: center,
      };
    } else {
      gestureRef.current = {
        kind: 'pan',
        startZoom: zoom,
        startOffset: offset,
        startPoint: point,
        lastPoint: point,
      };
    }
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!pointersRef.current.has(event.pointerId)) return;
    event.preventDefault();
    pointersRef.current.set(event.pointerId, getPoint(event));
    const points = [...pointersRef.current.values()];
    const gesture = gestureRef.current;
    if (!gesture) return;

    if (points.length >= 2 && gesture.kind === 'pinch' && gesture.startDistance && gesture.startMidpoint) {
      const nextZoom = clampZoom(gesture.startZoom * (distance(points[0], points[1]) / gesture.startDistance));
      const viewport = viewportRef.current;
      if (!viewport) return;
      const bounds = viewport.getBoundingClientRect();
      const startCenter = {
        x: gesture.startMidpoint.x - bounds.width / 2,
        y: gesture.startMidpoint.y - bounds.height / 2,
      };
      const currentCenter = {
        x: midpoint(points[0], points[1]).x - bounds.width / 2,
        y: midpoint(points[0], points[1]).y - bounds.height / 2,
      };
      if (nextZoom === MIN_ZOOM) {
        setOffset({ x: 0, y: 0 });
        setZoom(nextZoom);
        return;
      }
      const imagePoint = {
        x: (startCenter.x - gesture.startOffset.x) / gesture.startZoom,
        y: (startCenter.y - gesture.startOffset.y) / gesture.startZoom,
      };
      setOffset(clampOffset({
        x: currentCenter.x - imagePoint.x * nextZoom,
        y: currentCenter.y - imagePoint.y * nextZoom,
      }, nextZoom));
      setZoom(nextZoom);
    } else if (points.length === 1 && gesture.kind === 'pan' && gesture.lastPoint && zoom > MIN_ZOOM) {
      const point = points[0];
      const lastPoint = gesture.lastPoint;
      setOffset(current => clampOffset({ x: current.x + point.x - lastPoint.x, y: current.y + point.y - lastPoint.y }));
      gesture.lastPoint = point;
    }
  };

  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    pointersRef.current.delete(event.pointerId);
    const remaining = [...pointersRef.current.values()];
    if (remaining.length === 1) {
      gestureRef.current = {
        kind: 'pan',
        startZoom: zoom,
        startOffset: offset,
        startPoint: remaining[0],
        lastPoint: remaining[0],
      };
    } else if (remaining.length === 0) {
      gestureRef.current = null;
    }
  };

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const handleWheel = (event: globalThis.WheelEvent) => {
      event.preventDefault();
      const nextZoom = clampZoom(zoom * (event.deltaY < 0 ? 1.15 : 1 / 1.15));
      if (nextZoom === MIN_ZOOM) setOffset({ x: 0, y: 0 });
      else {
        const point = getPoint({ currentTarget: viewport, clientX: event.clientX, clientY: event.clientY });
        setOffset(clampOffset(centerOffsetForZoom(point, nextZoom), nextZoom));
      }
      setZoom(nextZoom);
    };
    viewport.addEventListener('wheel', handleWheel, { passive: false });
    return () => viewport.removeEventListener('wheel', handleWheel);
  }, [zoom, offset, fitSize]);

  const adjustZoom = (factor: number) => {
    const nextZoom = clampZoom(zoom * factor);
    if (nextZoom === MIN_ZOOM) setOffset({ x: 0, y: 0 });
    setZoom(nextZoom);
  };

  return createPortal(
    <div ref={dialogRef} tabIndex={-1} className="fixed inset-0 z-[70] flex flex-col bg-slate-950 text-white overscroll-none px-3 pt-[calc(env(safe-area-inset-top)+0.5rem)] pb-[calc(env(safe-area-inset-bottom)+0.5rem)]" role="dialog" aria-modal="true" aria-label="Certificate viewer">
      <header className="flex h-12 shrink-0 items-center justify-between gap-3">
        <span className="min-w-0 truncate text-sm font-semibold">{alt}</span>
        <button type="button" onClick={onClose} className="rounded-lg p-2 text-white/80 hover:bg-white/10 hover:text-white" aria-label="Close certificate viewer">
          <X className="h-5 w-5" />
        </button>
      </header>

      <div
        ref={viewportRef}
        className="relative flex min-h-0 flex-1 touch-none select-none items-center justify-center overflow-hidden overscroll-contain"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onDoubleClick={(event: MouseEvent<HTMLDivElement>) => {
          if (Date.now() - lastTouchDoubleTapRef.current < 500) return;
          toggleZoomAt(getPoint(event));
        }}
        onContextMenu={(event) => event.preventDefault()}
        style={{ touchAction: 'none' }}
      >
        {!imageFailed ? (
          <img
            ref={imageRef}
            src={src}
            alt={alt}
            draggable={false}
            onLoad={fitToScreen}
            onError={() => setImageFailed(true)}
            style={{
              width: fitSize?.width ?? 'auto',
              height: fitSize?.height ?? 'auto',
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
              transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${zoom})`,
              transformOrigin: 'center',
              willChange: 'transform',
            }}
          />
        ) : (
          <p className="px-6 text-center text-sm text-white/70">The certificate image could not be loaded.</p>
        )}
      </div>

      <footer className="flex h-14 shrink-0 items-center justify-center gap-2">
        <button type="button" onClick={() => adjustZoom(1 / 1.25)} className="rounded-lg p-2 hover:bg-white/10" aria-label="Zoom out"><ZoomOut className="h-5 w-5" /></button>
        <span className="w-14 text-center text-xs tabular-nums text-white/75">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => adjustZoom(1.25)} className="rounded-lg p-2 hover:bg-white/10" aria-label="Zoom in"><ZoomIn className="h-5 w-5" /></button>
        <button type="button" onClick={fitToScreen} className="ml-2 inline-flex items-center gap-2 rounded-lg bg-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/15"><Maximize2 className="h-4 w-4" />Fit to Screen</button>
      </footer>
    </div>,
    document.body,
  );
}
