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
}

/** Loads a protected certificate image with the bearer token, never a tokenized URL. */
export default function AuthenticatedCertificateImage({ certificateId, alt, className, onClick, onError, zoomable = false, onClose }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const onErrorRef = useRef(onError);

  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setSrc(null);
    certificateService.imageBlob(certificateId)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (active) setSrc(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(() => {
        if (active) onErrorRef.current?.();
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [certificateId]);

  if (!src) return null;
  if (zoomable) return <ZoomableCertificateViewer src={src} alt={alt} onClose={onClose ?? (() => undefined)} />;
  return <img src={src} alt={alt} className={className} onClick={onClick} />;
}
