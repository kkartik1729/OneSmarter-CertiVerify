import { useEffect, useRef, useState } from 'react';
import { certificateService } from '../services';
import ZoomableCertificateViewer from './ZoomableCertificateViewer';

interface Props {
  certificateId: string | number;
  alt: string;
  className?: string;
  onClick?: () => void;
  onError?: () => void;
  zoomable?: boolean;
  onClose?: () => void;
  thumbnail?: boolean;
}

type CachedImage = { promise: Promise<string>; url?: string; users: number; timer?: ReturnType<typeof setTimeout> };
const imageUrls = new Map<string, CachedImage>();

function acquireImage(certificateId: string | number, thumbnail: boolean) {
  const key = `${certificateId}:${thumbnail ? 'thumb-320' : 'full'}`;
  let entry = imageUrls.get(key);
  if (!entry) {
    const next: CachedImage = {
      users: 0,
      promise: certificateService.imageBlob(certificateId, thumbnail ? 320 : undefined).then((blob) => {
        const url = URL.createObjectURL(blob);
        next.url = url;
        return url;
      }).catch((error) => {
        imageUrls.delete(key);
        throw error;
      }),
    };
    entry = next;
    imageUrls.set(key, entry);
  }
  if (entry.timer) clearTimeout(entry.timer);
  entry.users += 1;
  const acquired = entry;
  return {
    promise: acquired.promise,
    release: () => {
      acquired.users -= 1;
      if (acquired.users === 0) {
        acquired.timer = setTimeout(() => {
          if (acquired.users !== 0) return;
          if (acquired.url) URL.revokeObjectURL(acquired.url);
          imageUrls.delete(key);
        }, 30_000);
      }
    },
  };
}

/** Loads a protected certificate image with the bearer token, never a tokenized URL. */
export default function AuthenticatedCertificateImage({ certificateId, alt, className, onClick, onError, zoomable = false, onClose, thumbnail = false }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const onErrorRef = useRef(onError);

  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  useEffect(() => {
    let active = true;
    const image = acquireImage(certificateId, thumbnail);
    setSrc(null);
    image.promise.then((url) => {
        if (active) setSrc(url);
      })
      .catch(() => {
        if (active) onErrorRef.current?.();
      });
    return () => {
      active = false;
      image.release();
    };
  }, [certificateId, thumbnail]);

  if (!src) return null;
  if (zoomable) return <ZoomableCertificateViewer src={src} alt={alt} onClose={onClose ?? (() => undefined)} />;
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick();
        }
      } : undefined}
    />
  );
}
