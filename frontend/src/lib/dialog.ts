import { useEffect, useRef } from 'react';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/** Adds initial focus, Escape handling, a tab loop, and focus restoration to an open modal. */
export function useAccessibleDialog(open: boolean, onClose: () => void) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const first = dialog.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? dialog).focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE))
        .filter(item => item.getClientRects().length > 0);
      if (!items.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === firstItem || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && (document.activeElement === lastItem || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        firstItem.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open]);

  return dialogRef;
}
