/**
 * Keyboard operation of a review queue (EP13 / C28).
 *
 * Shared by the two review screens on purpose. A reviewer who moves between families and
 * profiles should meet one set of keys rather than two, and having two consumers is what makes
 * extracting this a generalisation rather than an anticipation.
 *
 * **Inert while focus is inside a text-editing field.** Otherwise typing the word "aro" into a
 * variant label would approve the row, reject it and advance — and the reviewer would not
 * necessarily notice which of those happened.
 */

import { useEffect } from 'react';

export interface ReviewKeyboardHandlers {
  /** Approve the current item. */
  onApprove?: () => void;
  /** Reject the current item. */
  onReject?: () => void;
  /** Move to the next item. */
  onNext?: () => void;
  /** Move to the previous item. */
  onPrevious?: () => void;
  /** Persist what is pending. */
  onSave?: () => void;
  /** Off while a dialog owns the keyboard, or while a save is in flight. */
  enabled?: boolean;
}

/** The bindings, exported so a screen can show its own legend without restating them. */
export const REVIEW_SHORTCUTS = [
  { keys: 'A', description: 'Aprobar' },
  { keys: 'R', description: 'Rechazar' },
  { keys: 'J / ↓', description: 'Siguiente' },
  { keys: 'K / ↑', description: 'Anterior' },
  { keys: 'Enter', description: 'Guardar' },
] as const;

/**
 * Whether the event came from somewhere the reviewer is typing.
 *
 * Covers the editable host as well as the obvious fields: a rich-text cell is a text-editing
 * field even though its tag name is a div, and a shortcut that fires inside one is the same
 * defect with a less obvious cause.
 */
function isTextEntry(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;

  if (target.isContentEditable) return true;

  const tag = target.tagName.toLowerCase();
  if (tag === 'textarea' || tag === 'select') return true;

  if (tag === 'input') {
    const type = (target as HTMLInputElement).type.toLowerCase();
    // Buttons and checkboxes are inputs that nobody types into, and a reviewer who has just
    // clicked one still expects the next keystroke to work.
    return !['button', 'checkbox', 'radio', 'submit', 'reset', 'file'].includes(type);
  }

  return false;
}

export function useReviewKeyboard({
  onApprove,
  onReject,
  onNext,
  onPrevious,
  onSave,
  enabled = true,
}: ReviewKeyboardHandlers): void {
  useEffect(() => {
    if (!enabled) return;

    const handle = (event: KeyboardEvent) => {
      // A modifier means the keystroke belongs to the browser or the operating system.
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTextEntry(event.target)) return;

      const actions: Record<string, (() => void) | undefined> = {
        a: onApprove,
        r: onReject,
        j: onNext,
        arrowdown: onNext,
        k: onPrevious,
        arrowup: onPrevious,
        enter: onSave,
      };

      const action = actions[event.key.toLowerCase()];
      if (!action) return;

      event.preventDefault();
      action();
    };

    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, [onApprove, onReject, onNext, onPrevious, onSave, enabled]);
}

export default useReviewKeyboard;
