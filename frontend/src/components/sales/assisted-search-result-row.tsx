/**
 * Assisted Search Result Row (EP14 / C16)
 *
 * A component of its own from day one, on purpose: C36 adds the generated pitch, the citations
 * and the family disambiguation, and it should extend this row rather than rewrite the page.
 */

import { Package } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getImageUrl } from '@/lib/image-url';
import type { AssistedSearchResult } from '@/types/ai-search.types';

/**
 * Where the result came from, as the operator reads it.
 *
 * A lookup rather than a conditional so that a later origin — the lexical branch of C21 — is a
 * new entry here instead of a change to the row. An unknown key falls back rather than throwing.
 */
const ORIGIN_LABELS: Record<string, string> = {
  assisted: 'Coincidencia semántica',
  lexical: 'Búsqueda por texto',
};

export function originLabel(origin: string): string {
  return ORIGIN_LABELS[origin] ?? 'Resultado';
}

/** The retriever's name for the semantic branch. `assisted` is the operator's name for it. */
const VECTOR_REASON = 'vector';
const LEXICAL_REASON = 'lexical';

/**
 * Which origin this result has, from its own match reasons — never from whether the assisted
 * path served the response.
 *
 * The distinction matters the moment the embedding provider fails: C21 serves the lexical
 * branch alone with HTTP 200, so a response-wide badge would print "semantic match" over
 * results no semantic search produced. Claiming a capability that did not run is the lie the
 * per-result badge exists to prevent.
 *
 * No match reasons at all means no retriever ran: the search was answered by the .NET side's
 * own degraded text search, which is a text search and says so. A reason this panel does not
 * know falls back to the neutral label rather than guessing.
 */
export function resultOrigin(matchReasons: readonly string[]): string {
  if (matchReasons.includes(VECTOR_REASON)) return 'assisted';
  if (matchReasons.length === 0 || matchReasons.includes(LEXICAL_REASON)) return LEXICAL_REASON;
  return matchReasons[0];
}

/** Which retriever answered the whole search, as far as the results can testify. */
export type SearchOrigin = 'assisted' | 'service-lexical' | 'legacy-lexical' | 'unknown';

/**
 * Which mode the search actually fell into, derived from the results themselves.
 *
 * The browser never talks to the AI service and the response carries no mode field, so this
 * is read from provenance rather than asserted. Three outcomes are distinguishable and worth
 * distinguishing, because the middle one is invisible otherwise:
 *
 * - `assisted` — at least one result came from the semantic branch, so the fused path ran.
 * - `service-lexical` — the AI service answered, but nothing came from the semantic branch.
 *   That is the embedding provider having failed: HTTP 200, results on screen, and the panel
 *   would look perfectly healthy while the capability the screen is named after did not run.
 * - `legacy-lexical` — the assisted path did not serve at all and the .NET side's own text
 *   search answered. Switched off and unavailable arrive identically here, on purpose.
 *
 * With no results there is no provenance to read, so the mode is `unknown` and nothing is
 * claimed about it. That case is already covered by the empty-state messages.
 */
export function searchOrigin(
  results: readonly { matchReasons: string[] }[],
  aiAvailable: boolean,
): SearchOrigin {
  if (!aiAvailable) return 'legacy-lexical';
  if (results.length === 0) return 'unknown';
  return results.some((item) => item.matchReasons.includes(VECTOR_REASON))
    ? 'assisted'
    : 'service-lexical';
}

const euro = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });

interface AssistedSearchResultRowProps {
  result: AssistedSearchResult;
  onSelect: (result: AssistedSearchResult) => void;
}

export function AssistedSearchResultRow({ result, onSelect }: AssistedSearchResultRowProps) {
  const photoUrl = getImageUrl(result.primaryPhotoUrl ?? undefined);

  return (
    <Card data-testid="assisted-search-result">
      <CardContent className="flex items-center gap-4 p-4">
        <div className="relative size-20 shrink-0 overflow-hidden rounded-md bg-muted">
          {photoUrl ? (
            <img src={photoUrl} alt={result.name} className="size-full object-cover" />
          ) : (
            <div className="flex size-full items-center justify-center">
              <Package className="size-8 text-muted-foreground/50" />
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate font-medium">{result.name}</p>
            {/* Rendered only when it exists. C18 populates it; until then there is no size to
                show, and inventing one would be worse than leaving the gap. */}
            {result.variantLabel ? (
              <Badge variant="secondary" appearance="outline">
                Talla {result.variantLabel}
              </Badge>
            ) : null}
          </div>

          <p className="text-sm text-muted-foreground">{result.sku}</p>

          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="info" appearance="light">
              {originLabel(resultOrigin(result.matchReasons))}
            </Badge>
            {/* Closes the loop with the quick filters: you filter by silver and you can see that
                the piece is silver. The raw match reasons are still deliberately not rendered:
                since C21 they carry real provenance, but `vector` and `lexical` are engineering
                vocabulary and the badge above is their translation. */}
            {result.materials.map((material) => (
              <Badge key={material} variant="secondary" appearance="outline">
                {material}
              </Badge>
            ))}
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <p className="font-semibold">{euro.format(result.price)}</p>

          {result.hasStock ? (
            <span className="text-sm text-muted-foreground">
              {result.quantityAtPointOfSale} en tienda
            </span>
          ) : (
            /* Kept and marked, never hidden: "we carry it, we are out of it" is an answer that
               can still save a sale. Marked by text as well as colour. */
            <Badge variant="warning" appearance="light">
              Sin existencias
            </Badge>
          )}

          <Button size="sm" onClick={() => onSelect(result)}>
            Seleccionar para venta
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default AssistedSearchResultRow;
