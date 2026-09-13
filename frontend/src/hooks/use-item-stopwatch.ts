/**
 * Per-item review stopwatch (EP13 / C28).
 *
 * **The measurement travels in the save request, and is never the thing the delivery reads.**
 * The first review capability recorded sixty-four judgements and six timings, because its
 * stopwatch lived in component state and died with the tab — so the average its delivery
 * required does not exist for that session. The rule that repairs it is the shape of this hook:
 * `measure()` hands the caller a number to put in the request it was already making, and what
 * stays behind is a session counter for the reviewer's own benefit.
 *
 * Nothing here is authoritative. The published average is computed by the server from the
 * durations it persisted; the figures this hook exposes are a live indicator that a review has
 * not degraded into clicking through, and they vanish with the tab on purpose.
 */

import { useCallback, useRef, useState } from 'react';

export interface ItemStopwatch {
  /**
   * Milliseconds since the current item was opened, restarting the clock for the next one.
   *
   * Call this exactly once per judgement, and put the result in the request that records it.
   */
  measure: () => number;

  /** Restarts the clock without recording — the reviewer moved on without deciding. */
  reset: () => void;

  /** Items measured in this browser session. Display only. */
  reviewedInSession: number;

  /** Mean seconds per item in this session. Display only, never the delivered figure. */
  sessionAverageSeconds: number;
}

export function useItemStopwatch(): ItemStopwatch {
  const openedAt = useRef<number>(Date.now());
  const [reviewedInSession, setReviewedInSession] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);

  const measure = useCallback(() => {
    const spentMs = Date.now() - openedAt.current;
    openedAt.current = Date.now();
    setElapsedMs((current) => current + spentMs);
    setReviewedInSession((current) => current + 1);
    return spentMs;
  }, []);

  const reset = useCallback(() => {
    openedAt.current = Date.now();
  }, []);

  return {
    measure,
    reset,
    reviewedInSession,
    sessionAverageSeconds: reviewedInSession === 0 ? 0 : elapsedMs / reviewedInSession / 1000,
  };
}

export default useItemStopwatch;
