/**
 * Profile review (EP13 / C28).
 *
 * Where a person judges what the extractor proposed about a piece, and where the two figures the
 * delivery asks for come from.
 *
 * **The criterion is fidelity to the source text, never the truth of the piece.** The system
 * holds no photographs and no visual embeddings, and the text of both the synthetic and the real
 * portions of the corpus was written by a language model — so "is this true of the piece?" is not
 * a question anybody here can answer. "Does the source text support this value?" is, and it is
 * precisely what the enrichment metrics claim to measure. That is why the product's full name and
 * description sit beside the values rather than behind a link: they are the evidence, not context.
 *
 * **The stratum decides the question.** Where every value already has a phrase behind it the span
 * check has asked "is the phrase present?" and answered yes, so the only defect a person can
 * still find is an omission — and there are measurably many. Asking "is it correct?" there is how
 * a reviewer confirms them away without reading the description to the end.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CheckCheck,
  Circle,
  FileText,
  Keyboard,
  RefreshCw,
  Target,
  Timer,
  Undo2,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { ThreeStateList } from '@/components/admin/three-state-list';
import { VocabularyField } from '@/components/admin/vocabulary-field';
import { CLOSED_VOCABULARIES } from '@/lib/materials-vocabulary';
import { useItemStopwatch } from '@/hooks/use-item-stopwatch';
import { REVIEW_SHORTCUTS, useReviewKeyboard } from '@/hooks/use-review-keyboard';
import { useVocabularyGaps } from '@/hooks/use-vocabulary-gaps';

import { profileReviewService } from '@/services/profile-review.service';
import type {
  EvidenceStratumCode,
  ListState,
  ProfileFieldName,
  ProfileReviewField,
  ProfileReviewItem,
  ProfileReviewMetrics,
  ProfileReviewQueue,
  RejectedProfiles,
} from '@/types/profile-review.types';

/** Field labels in the reviewer's language. The wire names stay as the API keys them. */
const FIELD_LABELS: Record<ProfileFieldName, string> = {
  piece_type: 'Tipo de pieza',
  materials: 'Materiales',
  stone_type: 'Piedra',
  size_label: 'Talla',
  color_tags: 'Color',
  style_tags: 'Estilo',
  occasion_tags: 'Ocasión',
};

const STRATUM_ORDER: EvidenceStratumCode[] = ['A', 'B', 'C'];

/** The values in force for one profile, as the reviewer is editing them. */
type Draft = Record<ProfileFieldName, string>;

/** Renders a field's value as the single text box the reviewer edits. */
const toText = (field: ProfileReviewField): string =>
  field.isList ? field.values.join(', ') : (field.value ?? '');

const draftOf = (item: ProfileReviewItem): Draft =>
  item.fields.reduce((draft, field) => {
    draft[field.field] = toText(field);
    return draft;
  }, {} as Draft);

/** Splits what the reviewer typed back into list elements. */
const toList = (raw: string): string[] =>
  raw
    .split(',')
    .map((value) => value.trim())
    .filter((value) => value.length > 0);

const blankToNull = (raw: string): string | null => (raw.trim() ? raw.trim() : null);

const formatRate = (rate: number | null): string =>
  rate === null ? 'sin medir' : `${rate.toLocaleString('es-ES')} %`;

export default function ProfileReviewPage() {
  const [queueState, setQueueState] = useState<ListState>('loading');
  const [queueReason, setQueueReason] = useState('');
  const [queue, setQueue] = useState<ProfileReviewQueue | null>(null);

  const [rejectedState, setRejectedState] = useState<ListState>('loading');
  const [rejectedReason, setRejectedReason] = useState('');
  const [rejected, setRejected] = useState<RejectedProfiles | null>(null);

  const [metricsState, setMetricsState] = useState<ListState>('loading');
  const [metricsReason, setMetricsReason] = useState('');
  const [metrics, setMetrics] = useState<ProfileReviewMetrics | null>(null);

  const [stratum, setStratum] = useState<EvidenceStratumCode | 'all'>('all');
  const [cursor, setCursor] = useState(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);

  const [selected, setSelected] = useState<string[]>([]);
  const [bulkField, setBulkField] = useState<ProfileFieldName>('color_tags');

  const stopwatch = useItemStopwatch();

  // Findings, not corrections. A term the vocabulary lacks could not have been produced by the
  // extractor, so it never reaches the rate — it feeds the change that widens the list.
  const gaps = useVocabularyGaps();

  const loadQueue = useCallback(
    async (which: EvidenceStratumCode | 'all', signal?: AbortSignal) => {
      setQueueState('loading');
      const outcome = await profileReviewService.getQueue(
        which === 'all' ? {} : { stratum: which },
        signal,
      );

      if (outcome.state === 'unavailable') {
        setQueue(null);
        setQueueReason(outcome.reason);
        setQueueState('unavailable');
        return;
      }

      setQueue(outcome.queue);
      setQueueState('loaded');
    },
    [],
  );

  const loadRejected = useCallback(async (signal?: AbortSignal) => {
    setRejectedState('loading');
    const outcome = await profileReviewService.getRejected(1, 50, signal);

    if (outcome.state === 'unavailable') {
      setRejected(null);
      setRejectedReason(outcome.reason);
      setRejectedState('unavailable');
      return;
    }

    setRejected(outcome.rejected);
    setRejectedState('loaded');
  }, []);

  const loadMetrics = useCallback(async (signal?: AbortSignal) => {
    setMetricsState('loading');
    const outcome = await profileReviewService.getMetrics(signal);

    if (outcome.state === 'unavailable') {
      setMetrics(null);
      setMetricsReason(outcome.reason);
      setMetricsState('unavailable');
      return;
    }

    setMetrics(outcome.metrics);
    setMetricsState('loaded');
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadQueue(stratum, controller.signal);
    return () => controller.abort();
  }, [loadQueue, stratum]);

  useEffect(() => {
    const controller = new AbortController();
    void loadRejected(controller.signal);
    void loadMetrics(controller.signal);
    return () => controller.abort();
  }, [loadRejected, loadMetrics]);

  const items = useMemo(() => queue?.items ?? [], [queue]);
  const current = items[cursor];

  /** What the design asked for, and what has been judged against it. */
  const quotaTotal = useMemo(
    () => (queue?.strata ?? []).reduce((total, row) => total + row.quota, 0),
    [queue],
  );
  const reviewedTotal = metrics?.profilesReviewedByHuman ?? 0;

  // The draft follows the cursor, and the clock restarts with it. Both have to move together:
  // a stopwatch that kept running across a change of item would attribute one reviewer's
  // hesitation to the next row.
  useEffect(() => {
    setDraft(current ? draftOf(current) : null);
    stopwatch.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.productId]);

  useEffect(() => {
    setCursor(0);
    setSelected([]);
  }, [stratum, queue?.seed]);

  const save = useCallback(
    async (verdict: 'approved' | 'rejected') => {
      if (!current || !draft || saving) return;

      // Measured here and sent **in this request**. Accumulating it in screen state is how the
      // previous review capability recorded sixty-four judgements and six durations.
      const reviewDurationMs = stopwatch.measure();

      setSaving(true);
      try {
        const result = await profileReviewService.recordReview({
          productId: current.productId,
          verdict,
          reviewDurationMs,
          pieceType: blankToNull(draft.piece_type ?? ''),
          materials: toList(draft.materials ?? ''),
          stoneType: blankToNull(draft.stone_type ?? ''),
          sizeLabel: blankToNull(draft.size_label ?? ''),
          colorTags: toList(draft.color_tags ?? ''),
          styleTags: toList(draft.style_tags ?? ''),
          occasionTags: toList(draft.occasion_tags ?? ''),
        });

        toast.success(
          result.correctedFields === 0
            ? 'Revisado sin correcciones.'
            : `Revisado con ${result.correctedFields} corrección(es).`,
        );

        // Dropped from the page as soon as it is judged. Reviewing moves the profile's origin to
        // human, so the server has already stopped offering it — leaving it on screen would show
        // a queue that no longer exists and, once the page ran out, look like the end of the
        // batch when there are hundreds left.
        // Computed here rather than read back out of the state updater. React does not promise
        // to run an updater synchronously, so reading a value assigned inside one is a race:
        // it reported an empty page, refetched, and put the reviewer back on the item they had
        // just judged.
        const remaining = items.filter((item) => item.productId !== current.productId);

        setQueue((previous) =>
          previous
            ? {
                ...previous,
                items: remaining,
                totalCount: Math.max(previous.totalCount - 1, 0),
              }
            : previous,
        );

        // Only when the page is spent, never mid-page: a refetch reorders what is left, and a
        // reviewer who loses their place in the middle of a run stops trusting the screen.
        if (remaining.length === 0) {
          await loadQueue(stratum);
          setCursor(0);
        } else {
          setCursor((index) => Math.min(index, remaining.length - 1));
        }

        void loadMetrics();
      } catch {
        toast.error('No se ha podido guardar la revisión.');
      } finally {
        setSaving(false);
      }
    },
    [current, draft, items, loadMetrics, loadQueue, saving, stopwatch, stratum],
  );

  useReviewKeyboard({
    onApprove: () => void save('approved'),
    onReject: () => void save('rejected'),
    onNext: () => setCursor((index) => Math.min(index + 1, items.length - 1)),
    onPrevious: () => setCursor((index) => Math.max(index - 1, 0)),
    onSave: () => void save('approved'),
    enabled: queueState === 'loaded' && items.length > 0 && !saving,
  });

  /**
   * Bulk approval is only offered inside one stratum.
   *
   * The bound lives in the interface as well as on the server. Unbounded, this is how the batch
   * stops containing any evidence: a stratum approved wholesale yields a correction rate of zero
   * that says nothing about the extractor, and the delivery loses the figure it exists to produce.
   */
  const bulkAvailable = stratum !== 'all' && selected.length > 0;

  const approveInBulk = useCallback(async () => {
    if (stratum === 'all' || selected.length === 0) return;

    try {
      const result = await profileReviewService.bulkApprove({
        fields: [bulkField],
        stratum,
        productIds: selected,
      });
      toast.success(
        `${result.approved} perfil(es) aprobados en «${FIELD_LABELS[result.field]}» ` +
          `dentro del estrato ${result.stratum}. Sin tiempo medido, como corresponde.`,
      );
      setSelected([]);
      void loadQueue(stratum);
      void loadMetrics();
    } catch {
      toast.error('No se ha podido aprobar en masa.');
    }
  }, [bulkField, loadMetrics, loadQueue, selected, stratum]);

  const restore = useCallback(
    async (productId: string) => {
      try {
        await profileReviewService.restoreRejected(productId);
        toast.success('Perfil devuelto a aprobado.');
        void loadRejected();
        void loadMetrics();
      } catch {
        toast.error('No se ha podido devolver el perfil a aprobado.');
      }
    },
    [loadMetrics, loadRejected],
  );

  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Revisión de perfiles de IA</h1>
          <p className="text-muted-foreground text-sm">
            Juzgar si el <strong>texto del producto respalda</strong> cada valor propuesto. No si
            es cierto de la pieza: no hay fotos en el sistema y eso no se puede comprobar aquí.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1">
            <Timer className="size-3" />
            {metrics
              ? metrics.averageReviewSeconds !== null
                ? `${metrics.timedReviews} cronometrado(s) · ${metrics.averageReviewSeconds} s de media`
                : `${metrics.profilesReviewedByHuman} revisado(s) · sin tiempos medidos`
              : '—'}
            {stopwatch.reviewedInSession > 0 &&
              ` · ${stopwatch.reviewedInSession} en esta sesión ` +
                `(${stopwatch.sessionAverageSeconds.toFixed(1)} s)`}
          </Badge>

          {/* Progress against the quota, because the queue advances rather than ends. A profile
              a person judges leaves the universe the batch is drawn from, so the next one takes
              its place and the screen would happily offer a four-hundredth item. The quota is
              the design's sample size, so it has to be visible or it is not a sample size. */}
          {metrics && queue && (
            <Badge
              variant={reviewedTotal >= quotaTotal ? 'primary' : 'outline'}
              title="Revisados por estrato frente a la cuota del diseño"
            >
              <Target className="size-3" />
              {queue.strata
                .map((stratumRow) => {
                  const done =
                    metrics.strata.find((row) => row.stratum === stratumRow.stratum)
                      ?.profilesReviewed ?? 0;
                  return `${stratumRow.stratum} ${done}/${stratumRow.quota}`;
                })
                .join(' · ')}
              {reviewedTotal >= quotaTotal && ' · lote completo'}
            </Badge>
          )}

          {queue && (
            /* The seed is on screen so the session can name the batch it produced. A figure
               whose sample cannot be reconstructed is a figure nobody can check. */
            <Badge variant="outline" title="Semilla del muestreo">
              semilla: {queue.seed}
            </Badge>
          )}

          <Badge variant="outline" className="gap-1" title="Atajos de teclado">
            <Keyboard className="size-3" />
            {REVIEW_SHORTCUTS.map((s) => `${s.keys} ${s.description}`).join(' · ')}
          </Badge>

          <Button variant="outline" size="sm" onClick={() => void loadQueue(stratum)}>
            <RefreshCw className="size-4" />
            Recalcular
          </Button>
        </div>
      </div>

      <Tabs defaultValue="queue">
        <TabsList>
          <TabsTrigger value="queue">
            Cola{queueState === 'loaded' ? ` (${queue?.totalCount ?? 0})` : ''}
          </TabsTrigger>
          <TabsTrigger value="rejected">
            Rechazados{rejectedState === 'loaded' ? ` (${rejected?.totalCount ?? 0})` : ''}
          </TabsTrigger>
          <TabsTrigger value="gaps">Huecos de vocabulario ({gaps.gaps.length})</TabsTrigger>
          <TabsTrigger value="metrics">Métricas</TabsTrigger>
        </TabsList>

        {/* ── The queue ────────────────────────────────────────────────────────────────── */}
        <TabsContent value="queue" className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Lote estratificado</CardTitle>
              <CardDescription>
                El estrato decide la pregunta. Donde toda la evidencia está en el texto, lo único
                que queda por encontrar es lo que <strong>falta</strong>.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ThreeStateList
                state={queueState}
                reason={queueReason}
                isEmpty={items.length === 0}
                emptyMessage="No queda ningún perfil sin revisar en este estrato."
              >
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={stratum === 'all' ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setStratum('all')}
                  >
                    Todos
                  </Button>
                  {STRATUM_ORDER.map((code) => {
                    const summary = queue?.strata.find((s) => s.stratum === code);
                    return (
                      <Button
                        key={code}
                        variant={stratum === code ? 'primary' : 'outline'}
                        size="sm"
                        onClick={() => setStratum(code)}
                      >
                        {code} · {summary?.label ?? '—'}
                        {summary ? ` (${summary.drawn}/${summary.corpusSize})` : ''}
                        {summary?.exhausted ? ' · agotado' : ''}
                      </Button>
                    );
                  })}
                </div>
              </ThreeStateList>
            </CardContent>
          </Card>

          {current && draft && (
            <Card>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                  <span>{current.name}</span>
                  <Badge variant="outline">{current.sku}</Badge>
                  <Badge variant="secondary">
                    Estrato {current.stratum} · por {FIELD_LABELS[current.stratumDecidingField]}
                  </Badge>
                  <Badge>{current.question}</Badge>
                  <span className="text-muted-foreground text-xs">
                    {cursor + 1} de {items.length}
                  </span>
                </CardTitle>
                <CardDescription>
                  <span className="flex items-start gap-2">
                    <FileText className="mt-0.5 size-4 shrink-0" />
                    {current.hasDescription ? (
                      <span>{current.description}</span>
                    ) : (
                      /* Stated, never left as a gap. A blank where the evidence should be reads
                         as "nothing worth saying"; what it means is that the reviewer has less to
                         judge against than usual, and they need to know that. */
                      <span className="italic">
                        Este producto <strong>no tiene descripción</strong>. Solo se puede juzgar
                        contra su nombre.
                      </span>
                    )}
                  </span>
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Campo</TableHead>
                      <TableHead>Propuesto</TableHead>
                      <TableHead>En vigor</TableHead>
                      <TableHead className="text-right">Confianza</TableHead>
                      <TableHead>Procedencia</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {current.fields.map((field) => (
                      <TableRow
                        key={field.field}
                        data-pending-review={field.pendingReview ? 'true' : undefined}
                        className={field.pendingReview ? 'bg-amber-50/60' : undefined}
                      >
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-1">
                            {FIELD_LABELS[field.field]}
                            {field.pendingReview && (
                              /* Sensitive and inferred: the hybrid policy needs a person for
                                 exactly these. A size read off a SKU by a regex is not marked,
                                 because re-reading it would spend attention on a certainty. */
                              <Badge variant="destructive" className="text-[10px]">
                                pendiente de revisión
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground font-mono text-xs">
                          {field.isList
                            ? field.proposedValues.join(', ') || '—'
                            : (field.proposedValue ?? '—')}
                        </TableCell>
                        <TableCell>
                          {CLOSED_VOCABULARIES[field.field] ? (
                            <VocabularyField
                              field={field.field}
                              label={FIELD_LABELS[field.field]}
                              options={CLOSED_VOCABULARIES[field.field]}
                              isList={field.isList}
                              values={toList(draft[field.field] ?? '')}
                              onChange={(next) =>
                                setDraft((previous) =>
                                  previous
                                    ? { ...previous, [field.field]: next.join(', ') }
                                    : previous,
                                )
                              }
                              onGap={(term) => {
                                gaps.record(field.field, term, current.sku);
                                toast.success(
                                  `Anotado «${term}» como hueco de ${FIELD_LABELS[field.field]}. `
                                    + 'No cuenta como corrección.',
                                );
                              }}
                              gaps={gaps.termsFor(field.field, current.sku)}
                              onRemoveGap={(term) =>
                                gaps.withdraw(field.field, term, current.sku)
                              }
                            />
                          ) : (
                            /* Free text, and only here. The size label is the one field the
                               extractor produces from a deterministic rule, and the rule emits
                               ring sizes and chain lengths the vocabulary never contained — the
                               corpus carries twenty distinct labels against twelve terms. A
                               closed list would make a size of 17 unrecordable. */
                            <Input
                              aria-label={FIELD_LABELS[field.field]}
                              value={draft[field.field] ?? ''}
                              onChange={(event) =>
                                setDraft((previous) =>
                                  previous
                                    ? { ...previous, [field.field]: event.target.value }
                                    : previous,
                                )
                              }
                              placeholder="vacío"
                            />
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {field.confidence.toLocaleString('es-ES')}
                        </TableCell>
                        <TableCell>
                          <Badge variant={field.source === 'rule' ? 'secondary' : 'outline'}>
                            {field.source === 'rule' ? 'regla' : 'inferido'}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <div className="flex flex-wrap items-center gap-2">
                  <Button disabled={saving} onClick={() => void save('approved')}>
                    <CheckCheck className="size-4" />
                    Aprobar y siguiente
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={saving}
                    onClick={() => void save('rejected')}
                  >
                    Rechazar
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setCursor((index) => Math.max(index - 1, 0))}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      setCursor((index) => Math.min(index + 1, items.length - 1))
                    }
                  >
                    Siguiente
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── Bulk approval, bounded in the interface as well as on the server ────────── */}
          <Card>
            <CardHeader>
              <CardTitle>Aprobación masiva</CardTitle>
              <CardDescription>
                Un solo campo, dentro de un solo estrato. Sin ese límite el lote se aprueba entero
                y la tasa de corrección deja de decir nada del extractor.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {stratum === 'all' ? (
                <p className="text-muted-foreground text-sm">
                  Elige un estrato arriba para poder aprobar en masa.
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="flex flex-col gap-1">
                      <Label htmlFor="bulk-field">Campo</Label>
                      <select
                        id="bulk-field"
                        className="border-input h-9 rounded-md border px-3 text-sm"
                        value={bulkField}
                        onChange={(event) =>
                          setBulkField(event.target.value as ProfileFieldName)
                        }
                      >
                        {(Object.keys(FIELD_LABELS) as ProfileFieldName[]).map((field) => (
                          <option key={field} value={field}>
                            {FIELD_LABELS[field]}
                          </option>
                        ))}
                      </select>
                    </div>
                    <Button disabled={!bulkAvailable} onClick={() => void approveInBulk()}>
                      Aprobar {selected.length} perfil(es) en estrato {stratum}
                    </Button>
                    <span className="text-muted-foreground text-xs">
                      La aprobación masiva no registra tiempo, y así se reporta.
                    </span>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-10" />
                        <TableHead>Producto</TableHead>
                        <TableHead>Valor propuesto</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map((item) => (
                        <TableRow key={item.productId}>
                          <TableCell>
                            <Checkbox
                              aria-label={`Seleccionar ${item.name}`}
                              checked={selected.includes(item.productId)}
                              onCheckedChange={(checked) =>
                                setSelected((current) =>
                                  checked
                                    ? [...current, item.productId]
                                    : current.filter((id) => id !== item.productId),
                                )
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <div className="font-medium">{item.name}</div>
                            <div className="text-muted-foreground text-xs">{item.sku}</div>
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {valueOf(item, bulkField)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── The rejected, asked the opposite question ─────────────────────────────────── */}
        <TabsContent value="rejected">
          <Card>
            <CardHeader>
              <CardTitle>{rejected?.question ?? '¿Hay algún rechazo incorrecto?'}</CardTitle>
              <CardDescription>
                La pregunta está invertida a propósito: casi todos son artículos de regalo
                correctamente rechazados, y no consumen cuota de ningún estrato.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ThreeStateList
                state={rejectedState}
                reason={rejectedReason}
                isEmpty={(rejected?.items.length ?? 0) === 0}
                emptyMessage="No hay perfiles rechazados."
              >
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Producto</TableHead>
                      <TableHead>Tipo de pieza</TableHead>
                      <TableHead>Materiales</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rejected?.items.map((item) => (
                      <TableRow key={item.productId}>
                        <TableCell>
                          <div className="font-medium">{item.name}</div>
                          <div className="text-muted-foreground text-xs">
                            {item.hasDescription ? item.description : 'Sin descripción'}
                          </div>
                        </TableCell>
                        <TableCell>{valueOf(item, 'piece_type')}</TableCell>
                        <TableCell>{valueOf(item, 'materials')}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void restore(item.productId)}
                          >
                            <Undo2 className="size-4" />
                            Devolver a aprobado
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </ThreeStateList>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Vocabulary gaps: findings, deliberately outside the rate ──────────────────── */}
        <TabsContent value="gaps">
          <Card>
            <CardHeader>
              <CardTitle>Términos que el vocabulario no tiene</CardTitle>
              <CardDescription>
                <strong>No son correcciones del extractor</strong>: no podía producirlos. Contarlos
                en la tasa reportaría la cobertura del vocabulario como error del modelo, que son
                dos cosas distintas y se arreglan de forma distinta. Ampliar el vocabulario no cabe
                en este change —la confianza se calcula contra él, así que añadir un término mueve
                productos de estrato y el lote dejaría de ser el mismo—, así que esta lista es la
                evidencia que justifica hacerlo en el siguiente.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {gaps.gaps.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  Todavía no has anotado ninguno.
                </p>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Campo</TableHead>
                        <TableHead>Término</TableHead>
                        <TableHead>SKU</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {gaps.gaps.map((gap, index) => (
                        <TableRow key={`${gap.field}-${gap.term}-${gap.sku}`}>
                          <TableCell>{FIELD_LABELS[gap.field as ProfileFieldName]}</TableCell>
                          <TableCell className="font-mono">{gap.term}</TableCell>
                          <TableCell className="font-mono text-xs">{gap.sku}</TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="outline"
                              size="sm"
                              aria-label={`Quitar ${gap.term}`}
                              onClick={() => gaps.remove(index)}
                            >
                              Quitar
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        void navigator.clipboard?.writeText(gaps.asMarkdown());
                        toast.success('Tabla copiada. Pégala en el informe de implementación.');
                      }}
                    >
                      Copiar como tabla
                    </Button>
                    <span className="text-muted-foreground text-xs">
                      Se guardan en este navegador, así que cerrar la pestaña no los pierde.
                    </span>
                  </div>

                  <pre className="bg-muted overflow-x-auto rounded-md p-3 text-xs">
                    {gaps.asMarkdown()}
                  </pre>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── The figures ──────────────────────────────────────────────────────────────── */}
        <TabsContent value="metrics" className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Tiempos</CardTitle>
              <CardDescription>
                Dos poblaciones separadas. Mezclar la que se cronometró con la que no se puede
                cronometrar produce una media que no describe ninguna de las dos.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ThreeStateList state={metricsState} reason={metricsReason}>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Figure
                    label="Revisadas con cronómetro"
                    value={`${metrics?.timedReviews ?? 0}`}
                    detail={
                      metrics?.averageReviewSeconds !== null &&
                      metrics?.averageReviewSeconds !== undefined
                        ? `${metrics.averageReviewSeconds} s de media ` +
                          `(${metrics.minReviewSeconds}–${metrics.maxReviewSeconds} s)`
                        : /* Never a zero. A zero asserts an instantaneous review, which is a
                             claim; an absence reports that nothing was measured. */
                          'sin tiempos medidos'
                    }
                  />
                  <Figure
                    label="Aprobadas en masa"
                    value={`${metrics?.bulkApprovedReviews ?? 0}`}
                    detail="sin tiempo, por diseño"
                  />
                  <Figure
                    label="Revisadas por una persona"
                    value={`${metrics?.profilesReviewedByHuman ?? 0}`}
                    detail={`de ${metrics?.profilesTotal ?? 0} · ${formatRate(
                      metrics?.reviewedShare ?? null,
                    )} del corpus`}
                  />
                </div>
              </ThreeStateList>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tasa de corrección</CardTitle>
              <CardDescription>
                El total va ponderado por el tamaño real de cada estrato en el catálogo: los
                estratos se muestrean a ritmos muy distintos a propósito, así que un total sin
                ponderar describe la muestra y no el catálogo.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ThreeStateList state={metricsState} reason={metricsReason}>
                <div className="flex flex-col gap-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Figure
                      label="Ponderada por el catálogo"
                      value={formatRate(metrics?.weightedCorrectionRate ?? null)}
                      detail="la cifra que describe el catálogo"
                    />
                    <Figure
                      label="Sobre la muestra"
                      value={formatRate(metrics?.sampleCorrectionRate ?? null)}
                      detail={`${metrics?.fieldsCorrected ?? 0} de ${
                        metrics?.fieldsReviewed ?? 0
                      } juicios de campo`}
                    />
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Estrato</TableHead>
                        <TableHead className="text-right">En el corpus</TableHead>
                        <TableHead className="text-right">Revisados</TableHead>
                        <TableHead className="text-right">Tasa</TableHead>
                        <TableHead className="text-right">Adiciones</TableHead>
                        <TableHead className="text-right">Retiradas</TableHead>
                        <TableHead className="text-right">Sustituciones</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {metrics?.strata.map((row) => (
                        <TableRow key={row.stratum}>
                          <TableCell>
                            {row.stratum} · {row.label}
                          </TableCell>
                          <TableCell className="text-right font-mono">{row.corpusSize}</TableCell>
                          <TableCell className="text-right font-mono">
                            {row.profilesReviewed}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatRate(row.correctionRate)}
                          </TableCell>
                          <TableCell className="text-right font-mono">{row.additions}</TableCell>
                          <TableCell className="text-right font-mono">{row.removals}</TableCell>
                          <TableCell className="text-right font-mono">
                            {row.substitutions}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Campo</TableHead>
                        <TableHead className="text-right">Revisados</TableHead>
                        <TableHead className="text-right">Corregidos</TableHead>
                        <TableHead className="text-right">Tasa ponderada</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {metrics?.fields.map((row) => (
                        <TableRow key={row.field}>
                          <TableCell>{FIELD_LABELS[row.field]}</TableCell>
                          <TableCell className="text-right font-mono">{row.reviewed}</TableCell>
                          <TableCell className="text-right font-mono">{row.corrected}</TableCell>
                          <TableCell className="text-right font-mono">
                            {formatRate(row.weightedCorrectionRate)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </ThreeStateList>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** One figure with what it is and what qualifies it. */
function Figure({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border p-4">
      <span className="text-muted-foreground flex items-center gap-1 text-xs">
        <Circle className="size-2 fill-current" />
        {label}
      </span>
      <span className="text-2xl font-semibold">{value}</span>
      <span className="text-muted-foreground text-xs">{detail}</span>
    </div>
  );
}

/** The value in force for one field of one item, rendered for a read-only cell. */
function valueOf(item: ProfileReviewItem, field: ProfileFieldName): string {
  const found = item.fields.find((candidate) => candidate.field === field);
  if (!found) return '—';
  return (found.isList ? found.values.join(', ') : found.value) || '—';
}
