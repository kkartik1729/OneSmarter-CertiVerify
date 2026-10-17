import { useEffect, useRef, useState } from 'react';
import { certificateService } from '../services';

interface Props {
  certificateId: string | number;
  alt: string;
  className?: string;
  onClick?: () => void;
  onError?: () => void;
}

/** Loads a protected certificate image with the bearer token, never a tokenized URL. */
export default function AuthenticatedCertificateImage({ certificateId, alt, className, onClick, onError }: Props) {
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

  return src ? <img src={src} alt={alt} className={className} onClick={onClick} /> : null;
}
