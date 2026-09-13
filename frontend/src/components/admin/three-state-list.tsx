/**
 * Three states per list, never two (EP13 / C18b → C28).
 *
 * A list that was computed and came back empty and one that could not be computed look identical
 * once only the rows are drawn, and on a screen whose subject is catalogue quality "nothing to
 * review" reads as "nothing is wrong" — the conclusion these screens exist to establish with
 * evidence rather than assert by accident. It is the exact shape in which the C17 risk
 * materialised: a degraded path that looked correct.
 *
 * Extracted here because two screens need it. The components below are the ones the family
 * review screen already carried, moved rather than rewritten, so its rendered output is
 * unchanged.
 */

import { CheckCircle2, CloudOff } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';

/** The three states a list can be in. */
export type ListState = 'loading' | 'loaded' | 'unavailable';

/**
 * A list that is unavailable, said plainly.
 *
 * Deliberately not a spinner and not an empty table. The whole point is that this cannot be
 * mistaken for "there is nothing here".
 */
export function Unavailable({ reason }: { reason: string }) {
  return (
    <Alert variant="destructive">
      <CloudOff className="size-4" />
      <AlertTitle>No se ha podido calcular</AlertTitle>
      <AlertDescription>
        {reason} Esto <strong>no</strong> significa que no haya nada que revisar: significa que no
        se sabe.
      </AlertDescription>
    </Alert>
  );
}

/** A list that was computed and came back with nothing, said just as plainly. */
export function EmptyButComputed({ children }: { children: React.ReactNode }) {
  return (
    <Alert>
      <CheckCircle2 className="size-4" />
      <AlertTitle>Sin hallazgos</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

export interface ThreeStateListProps {
  /** Which of the three states the list is in. */
  state: ListState;
  /** Why it could not be computed. Shown only in the unavailable state. */
  reason?: string;
  /** Whether the loaded list came back with nothing. */
  isEmpty?: boolean;
  /** What to say when it did. */
  emptyMessage?: React.ReactNode;
  /** The rows, rendered only when the list loaded with something in it. */
  children?: React.ReactNode;
}

/**
 * Renders one list in whichever of its three states it is in.
 *
 * The caller cannot reach the rows without passing through the state, which is what makes
 * repeating C17 awkward rather than merely discouraged.
 */
export function ThreeStateList({
  state,
  reason,
  isEmpty = false,
  emptyMessage,
  children,
}: ThreeStateListProps) {
  if (state === 'loading') {
    return <Skeleton className="h-40 w-full" />;
  }

  if (state === 'unavailable') {
    return <Unavailable reason={reason ?? 'No se ha podido calcular la lista.'} />;
  }

  if (isEmpty) {
    return <EmptyButComputed>{emptyMessage}</EmptyButComputed>;
  }

  return <>{children}</>;
}

export default ThreeStateList;
