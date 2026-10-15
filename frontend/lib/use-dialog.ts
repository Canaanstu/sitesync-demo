'use client';

import {useEffect, useRef, useState} from 'react';

// Shared behavior only: retain each screen's existing dialog markup and layout.
export function useDialog(key: string, onClose: () => void, busy = false) {
  const ref = useRef<HTMLElement>(null);
  const [working, setWorking] = useState(false);
  const latest = useRef({onClose, busy});
  latest.current = {onClose, busy: busy || working};
  const dirty = useRef(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const armed = useRef(false);
  function markDirty() { dirty.current = true; armed.current = false; setConfirmDiscard(false); }
  function markClean() { dirty.current = false; armed.current = false; setConfirmDiscard(false); }
  function requestClose() {
    if (latest.current.busy) return;
    if (dirty.current && !armed.current) {
      armed.current = true;
      setConfirmDiscard(true);
      return;
    }
    latest.current.onClose();
  }
  useEffect(() => {
    if (!key || !ref.current) return;
    markClean();
    const dialog = ref.current;
    const opener = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]'
    )).filter(el => el.getClientRects().length > 0 && !el.closest('[disabled]'));
    dialog.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        // Escape must never be the second, destructive confirmation.
        if (latest.current.busy) return;
        if (dirty.current) { armed.current = true; setConfirmDiscard(true); }
        else latest.current.onClose();
      }
      if (event.key === 'Tab') {
        const items = focusable(), first = items[0], last = items[items.length - 1];
        if (!first) { event.preventDefault(); dialog.focus(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
          event.preventDefault(); first.focus();
        }
      }
    }
    function containFocus(event: FocusEvent) {
      if (!dialog.contains(event.target as Node)) dialog.focus();
    }
    document.addEventListener('keydown', keydown);
    document.addEventListener('focusin', containFocus);
    return () => {
      document.removeEventListener('keydown', keydown);
      document.removeEventListener('focusin', containFocus);
      document.body.style.overflow = previousOverflow;
      if (opener?.isConnected) opener.focus();
    };
  }, [key]);
  return {ref, markDirty, markClean, requestClose, confirmDiscard, working, setWorking,
    backdrop: () => { if (!dirty.current && !latest.current.busy) latest.current.onClose(); }};
}
