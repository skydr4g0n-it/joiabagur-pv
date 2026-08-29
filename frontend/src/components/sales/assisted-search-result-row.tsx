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

const euro = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });

interface AssistedSearchResultRowProps {
  result: AssistedSearchResult;
  /** Whether the assisted path served this search. Decides the origin badge. */
  aiAvailable: boolean;
  onSelect: (result: AssistedSearchResult) => void;
}

export function AssistedSearchResultRow({
  result,
  aiAvailable,
  onSelect,
}: AssistedSearchResultRowProps) {
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
              {originLabel(aiAvailable ? 'assisted' : 'lexical')}
            </Badge>
            {/* Closes the loop with the quick filters: you filter by silver and you can see that
                the piece is silver. The raw match reasons are deliberately not rendered — they
                are the constant "vector" for every result until C21. */}
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
