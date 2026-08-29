/**
 * Assisted Search Panel (EP14 / C16)
 *
 * The operator describes a piece in their own words and gets back what their shop actually
 * carries, at the price the catalog holds right now. The backend decides everything: this page
 * never re-sorts, never re-filters and never recomputes stock or price.
 *
 * Two rules govern the interaction and are easy to break by accident:
 *
 * 1. **A search is issued only when the operator asks for one.** Never on typing. The candidate
 *    cache is keyed on the whole query string, so no prefix can hit it: a debounced field would
 *    charge several query embeddings per query, of which at most one would be read, and would
 *    exhaust the per-user request budget in five or six searches.
 * 2. **Nothing is shown that the system has not asserted.** The retriever's match reasons are
 *    the constant `["vector"]` until C21, and the variant label is null until C18. Neither is
 *    faked; the row degrades instead.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Search, Sparkles, Info } from 'lucide-react';
import { toast } from 'sonner';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

import { AssistedSearchResultRow } from '@/components/sales/assisted-search-result-row';
import { useAuth } from '@/providers/auth-provider';
import { aiSearchService } from '@/services/ai-search.service';
import * as pointOfSaleService from '@/services/point-of-sale.service';
import {
  EXAMPLE_QUERIES,
  MATERIAL_OPTIONS,
  PIECE_TYPE_OPTIONS,
} from '@/lib/materials-vocabulary';
import { ROUTES } from '@/routing/routes';
import type {
  AssistedSearchResponse,
  AssistedSearchResult,
} from '@/types/ai-search.types';
import type { PointOfSale } from '@/types/point-of-sale.types';

const PAGE_SIZE = 10;

/** Everything the panel can be showing, once a search has settled. */
type PanelState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'answered'; response: AssistedSearchResponse }
  | { kind: 'rate-limited' }
  | { kind: 'forbidden' }
  | { kind: 'invalid'; errors: string[] }
  | { kind: 'error'; message: string };

export function AssistedSalesSearchPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';

  /**
   * One search episode per visit to the panel.
   *
   * The episode exists so the reformulations of a visit are not counted as abandoned queries,
   * and reformulations happen inside a visit. Two visits that each end in a selection are two
   * legitimate episodes with nothing to group between them.
   */
  const searchSessionId = useRef(crypto.randomUUID());

  /**
   * Guards against out-of-order responses: submit, change shop, submit again, and the first
   * response could otherwise land last and overwrite the second.
   */
  const requestSeq = useRef(0);

  const [query, setQuery] = useState('');
  const [materials, setMaterials] = useState<string[]>([]);
  const [category, setCategory] = useState<string>('');
  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);
  const [pointOfSaleId, setPointOfSaleId] = useState<string>('');
  const [loadingPos, setLoadingPos] = useState(true);
  const [state, setState] = useState<PanelState>({ kind: 'idle' });
  const [showFunnel, setShowFunnel] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const all = await pointOfSaleService.getPointsOfSale();
        // Only active ones: the endpoint refuses an inactive point of sale for every role, so
        // offering one would be offering a guaranteed error.
        const active = all.filter((pos) => pos.isActive);
        setPointsOfSale(active);
        if (active.length > 0) {
          setPointOfSaleId(active[0].id);
        }
      } catch {
        toast.error('No se pudieron cargar los puntos de venta');
      } finally {
        setLoadingPos(false);
      }
    };
    load();
  }, []);

  const runSearch = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !pointOfSaleId) return;

      const seq = ++requestSeq.current;
      setState({ kind: 'loading' });

      const outcome = await aiSearchService.search({
        query: trimmed,
        pointOfSaleId,
        pageSize: PAGE_SIZE,
        searchSessionId: searchSessionId.current,
        materials,
        category: category || undefined,
      });

      // A response that is no longer the current one is dropped rather than rendered.
      if (seq !== requestSeq.current) return;

      switch (outcome.kind) {
        case 'ok':
          setState({ kind: 'answered', response: outcome.response });
          break;
        case 'rate-limited':
          setState({ kind: 'rate-limited' });
          break;
        case 'forbidden':
          setState({ kind: 'forbidden' });
          break;
        case 'invalid':
          setState({ kind: 'invalid', errors: outcome.errors });
          break;
        default:
          setState({ kind: 'error', message: outcome.message });
      }
    },
    [pointOfSaleId, materials, category],
  );

  const handleSubmit = () => runSearch(query);

  const handleExample = (example: string) => {
    setQuery(example);
    // Fills the field *and* searches, in one act: the example is there to teach what can be
    // asked, and making the operator press again would waste the lesson.
    runSearch(example);
  };

  const toggleMaterial = (value: string) => {
    // Toggling never searches: each change of filter is a different cache key, so three toggles
    // would be three charged query embeddings.
    setMaterials((prev) =>
      prev.includes(value) ? prev.filter((m) => m !== value) : [...prev, value],
    );
  };

  const clearFilters = () => {
    setMaterials([]);
    setCategory('');
  };

  const handlePointOfSaleChange = (value: string) => {
    setPointOfSaleId(value);
    // Cleared rather than re-run: another shop is another assortment, and re-running here would
    // charge an embedding the operator did not ask for.
    setState({ kind: 'idle' });
    requestSeq.current += 1;
  };

  const handleSelect = (result: AssistedSearchResult) => {
    const searchEventId =
      state.kind === 'answered' ? state.response.searchEventId ?? undefined : undefined;

    // Reported at the instant of the click and deliberately not awaited: the server stamps the
    // moment, and a telemetry failure must never block the operator or surface as an error.
    // A null identifier means telemetry did not persist, and the report is skipped in silence.
    if (searchEventId) {
      void aiSearchService.reportSelection(searchEventId, result.productId);
    }

    navigate(ROUTES.SALES.NEW, {
      state: { productId: result.productId, searchEventId },
    });
  };

  const hasFilters = materials.length > 0 || category !== '';

  const response = state.kind === 'answered' ? state.response : null;
  const shortPage =
    response !== null && response.results.length > 0 && response.results.length < PAGE_SIZE;

  const posName = useMemo(
    () => pointsOfSale.find((pos) => pos.id === pointOfSaleId)?.name ?? '',
    [pointsOfSale, pointOfSaleId],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link to={ROUTES.SALES.ROOT} aria-label="Volver a ventas">
            <ArrowLeft className="size-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Buscar con ayuda</h1>
          <p className="text-muted-foreground">
            Describe la pieza con tus palabras y te enseño lo que hay en tu tienda
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4 pt-6">
          {pointsOfSale.length > 1 || isAdmin ? (
            <div className="space-y-2">
              <Label htmlFor="assisted-pos">Punto de venta</Label>
              <Select value={pointOfSaleId} onValueChange={handlePointOfSaleChange}>
                <SelectTrigger id="assisted-pos" className="w-full sm:w-72">
                  <SelectValue placeholder="Selecciona un punto de venta" />
                </SelectTrigger>
                <SelectContent>
                  {pointsOfSale.map((pos) => (
                    <SelectItem key={pos.id} value={pos.id}>
                      {pos.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="assisted-query">¿Qué busca el cliente?</Label>
            <div className="flex gap-2">
              <Input
                id="assisted-query"
                placeholder="Un anillo de plata para regalar..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSubmit();
                }}
                disabled={loadingPos}
              />
              <Button
                onClick={handleSubmit}
                disabled={!query.trim() || !pointOfSaleId || state.kind === 'loading'}
              >
                <Search className="mr-2 size-4" />
                Buscar
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Prueba con:</span>
            {EXAMPLE_QUERIES.map((example) => (
              <Button
                key={example}
                variant="outline"
                size="sm"
                onClick={() => handleExample(example)}
              >
                <Sparkles className="mr-1.5 size-3.5" />
                {example}
              </Button>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Materiales</Label>
              {hasFilters ? (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  Quitar filtros
                </Button>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {MATERIAL_OPTIONS.map((option) => {
                const selected = materials.includes(option.value);
                return (
                  <Button
                    key={option.value}
                    type="button"
                    variant={selected ? 'primary' : 'outline'}
                    size="sm"
                    aria-pressed={selected}
                    onClick={() => toggleMaterial(option.value)}
                  >
                    {option.label}
                  </Button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="assisted-category">Tipo de pieza</Label>
            <Select value={category || 'all'} onValueChange={(v) => setCategory(v === 'all' ? '' : v)}>
              <SelectTrigger id="assisted-category" className="w-full sm:w-72">
                <SelectValue placeholder="Cualquiera" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Cualquiera</SelectItem>
                {PIECE_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {state.kind === 'loading' ? (
        <div className="space-y-3" data-testid="assisted-search-loading">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : null}

      {state.kind === 'rate-limited' ? (
        <Alert variant="warning">
          <AlertTitle>Demasiadas búsquedas seguidas</AlertTitle>
          <AlertDescription>
            Espera unos segundos y vuelve a intentarlo.
          </AlertDescription>
        </Alert>
      ) : null}

      {state.kind === 'forbidden' ? (
        <Alert variant="destructive">
          <AlertTitle>No tienes acceso a esta tienda</AlertTitle>
          <AlertDescription>
            Selecciona un punto de venta que tengas asignado.
          </AlertDescription>
        </Alert>
      ) : null}

      {state.kind === 'invalid' ? (
        <Alert variant="destructive">
          <AlertTitle>La búsqueda no es válida</AlertTitle>
          <AlertDescription>{state.errors.join(' ')}</AlertDescription>
        </Alert>
      ) : null}

      {state.kind === 'error' ? (
        <Alert variant="destructive">
          <AlertTitle>No se pudo completar la búsqueda</AlertTitle>
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      ) : null}

      {response ? (
        <div className="space-y-4">
          {/* Degraded or switched off. The response cannot tell those apart — telemetry can, the
              API cannot — and for the operator the sentence is the same either way. */}
          {!response.aiAvailable ? (
            <Alert variant="warning">
              <AlertTitle>Búsqueda asistida no disponible</AlertTitle>
              <AlertDescription>
                Estos resultados vienen de la búsqueda por texto.
              </AlertDescription>
            </Alert>
          ) : null}

          {response.results.length === 0 && response.aiAvailable && response.lowConfidence ? (
            <Alert>
              <AlertTitle>No he encontrado nada que encaje</AlertTitle>
              <AlertDescription>
                Prueba a describirlo de otra forma.
              </AlertDescription>
            </Alert>
          ) : null}

          {response.results.length === 0 &&
          response.aiAvailable &&
          !response.lowConfidence &&
          response.candidatesReturned > 0 ? (
            <Alert>
              <AlertTitle>Nada de esto está en tu tienda</AlertTitle>
              <AlertDescription>
                Encontré {response.candidatesReturned} piezas parecidas, pero ninguna está
                disponible en {posName || 'este punto de venta'}.
                {hasFilters ? ' Prueba a quitar los filtros.' : ''}
              </AlertDescription>
            </Alert>
          ) : null}

          {response.results.length === 0 &&
          response.aiAvailable &&
          !response.lowConfidence &&
          response.candidatesReturned === 0 ? (
            <Alert>
              <AlertTitle>Sin resultados</AlertTitle>
              <AlertDescription>Prueba a describirlo de otra forma.</AlertDescription>
            </Alert>
          ) : null}

          {response.results.length === 0 && !response.aiAvailable ? (
            <Alert>
              <AlertTitle>Sin resultados</AlertTitle>
              <AlertDescription>
                La búsqueda por texto tampoco ha encontrado nada en tu tienda.
              </AlertDescription>
            </Alert>
          ) : null}

          {/* Rendered in the order received. No sort(): the rank is the measurement of retrieval
              quality, and re-sorting would make it measure this page instead. */}
          {response.results.map((result) => (
            <AssistedSearchResultRow
              key={result.productId}
              result={result}
              aiAvailable={response.aiAvailable}
              onSelect={handleSelect}
            />
          ))}

          {/* A short page is the frequent case where assortment coverage is low. Left unsaid it
              reads as the system being unable to search, when the shop simply does not carry it. */}
          {shortPage ? (
            <p className="text-sm text-muted-foreground" data-testid="assisted-search-short-page">
              {response.results.length} resultados en {posName || 'esta tienda'} ·{' '}
              {response.candidatesReturned} candidatos considerados
            </p>
          ) : null}

          {isAdmin ? (
            <div data-testid="assisted-search-funnel">
              <Button variant="ghost" size="sm" onClick={() => setShowFunnel((v) => !v)}>
                <Info className="mr-1.5 size-3.5" />
                Embudo de recuperación
              </Button>
              {showFunnel ? (
                <div className="mt-2 flex flex-wrap gap-2 text-sm text-muted-foreground">
                  <Badge variant="secondary" appearance="outline">
                    Candidatos: {response.candidatesReturned}
                  </Badge>
                  <Badge variant="secondary" appearance="outline">
                    Supervivientes: {response.survivedHydration}
                  </Badge>
                  <Badge variant="secondary" appearance="outline">
                    Mostrados: {response.results.length}
                  </Badge>
                  {response.searchEventId ? (
                    <Badge variant="secondary" appearance="outline">
                      Evento: {response.searchEventId}
                    </Badge>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default AssistedSalesSearchPage;
