/**
 * Family review (EP13 / C18b).
 *
 * The second place in this project where a person judges what the AI produced, and the first that
 * measures how long it takes them. Built as the shell C28 will reuse for profile review — only
 * what that change already specifies in writing is generalised here, nothing anticipated.
 *
 * **Three states per list, never two.** A list that was computed and came back empty and one that
 * could not be computed look identical once only the rows are drawn, and on a screen whose subject
 * is catalogue quality "nothing to review" reads as "nothing is wrong". That is the conclusion this
 * change exists to establish with evidence, and it is the exact shape in which the C17 risk
 * materialised — a degraded path that looked correct. The states are per list rather than per page
 * so that reviewing the families, which needs no vectors, stays usable while the audit does not.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CloudOff,
  Inbox,
  Pencil,
  RefreshCw,
  Timer,
  Trash2,
  Users,
  Wrench,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { familyReviewService } from '@/services/family-review.service';
import type {
  FamilyAudit,
  FamilyListItem,
  FamilyReviewOutcome,
  FamilyVerdict,
  FamilyDetail,
  FamilyReviewMetrics,
  ListState,
  RecordedVerdict,
} from '@/types/family-review.types';

/** Formats a similarity margin the way the reviewer reads it: three decimals, Spanish comma. */
const formatMargin = (value: number) =>
  value.toLocaleString('es-ES', { minimumFractionDigits: 3, maximumFractionDigits: 3 });

/**
 * A list that is unavailable, said plainly.
 *
 * Deliberately not a spinner and not an empty table. The whole point is that this cannot be
 * mistaken for "there is nothing here".
 */
function Unavailable({ reason }: { reason: string }) {
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
function EmptyButComputed({ children }: { children: React.ReactNode }) {
  return (
    <Alert>
      <CheckCircle2 className="size-4" />
      <AlertTitle>Sin hallazgos</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

export default function FamilyReviewPage() {
  const [auditState, setAuditState] = useState<ListState>('loading');
  const [auditReason, setAuditReason] = useState('');
  const [audit, setAudit] = useState<FamilyAudit | null>(null);

  const [familiesState, setFamiliesState] = useState<ListState>('loading');
  const [families, setFamilies] = useState<FamilyListItem[]>([]);
  const [familiesTotal, setFamiliesTotal] = useState(0);
  const [page, setPage] = useState(1);

  const [pending, setPending] = useState<FamilyVerdict[]>([]);
  const [saving, setSaving] = useState(false);

  // Judgements already recorded, and what the catalogue would need to change to honour them.
  // A verdict is not a membership: rejecting a member does not remove it, and confirming a
  // candidate does not add it. Without this list that gap is invisible, because the audit omits
  // judged pairs — so a decision nobody acted on stops appearing anywhere and reads as done.
  const [recorded, setRecorded] = useState<RecordedVerdict[]>([]);
  const [metrics, setMetrics] = useState<FamilyReviewMetrics | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [applying, setApplying] = useState<string | null>(null);

  // Per-item stopwatch. The average it produces is a delivery metric, and it is also the only
  // signal that a review has degraded into clicking through: a queue worked at two seconds an
  // item is not being read.
  const openedAt = useRef<number>(Date.now());
  const [reviewed, setReviewed] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);

  const loadAudit = useCallback(async (signal?: AbortSignal) => {
    setAuditState('loading');
    const outcome = await familyReviewService.getAudit(signal);

    if (outcome.state === 'unavailable') {
      setAudit(null);
      setAuditReason(outcome.reason);
      setAuditState('unavailable');
      return;
    }

    setAudit(outcome.audit);
    setAuditState('loaded');
  }, []);

  const loadFamilies = useCallback(async (nextPage: number, signal?: AbortSignal) => {
    setFamiliesState('loading');
    try {
      const result = await familyReviewService.listFamilies({ page: nextPage }, signal);
      setFamilies(result.items);
      setFamiliesTotal(result.totalCount);
      setFamiliesState('loaded');
    } catch {
      setFamiliesState('unavailable');
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadAudit(controller.signal);
    return () => controller.abort();
  }, [loadAudit]);

  const loadRecorded = useCallback(async (signal?: AbortSignal) => {
    try {
      const [verdicts, figures] = await Promise.all([
        familyReviewService.listVerdicts(signal),
        familyReviewService.getMetrics(signal),
      ]);
      setRecorded(verdicts);
      setMetrics(figures);
    } catch {
      // Left as it was rather than cleared: an empty list here would say "nothing pending",
      // which is the one thing a failed read must not claim on this screen.
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadFamilies(page, controller.signal);
    return () => controller.abort();
  }, [loadFamilies, page]);

  useEffect(() => {
    const controller = new AbortController();
    void loadRecorded(controller.signal);
    return () => controller.abort();
  }, [loadRecorded]);

  const actionable = useMemo(
    () => recorded.filter((verdict) => verdict.pendingAction !== 'none'),
    [recorded],
  );

  // The family whose members are open for correction, and the labels being typed into them.
  // Correcting a label was the one thing a reviewer could not do here: a member already inside a
  // family had no edit affordance at all, so the first session's mistakes had to be fixed through
  // the API by hand.
  const [openFamily, setOpenFamily] = useState<FamilyDetail | null>(null);
  const [memberLabels, setMemberLabels] = useState<Record<string, string>>({});
  const [relabelling, setRelabelling] = useState<string | null>(null);

  const openMembers = useCallback(async (familyId: string) => {
    if (openFamily?.id === familyId) {
      setOpenFamily(null);
      return;
    }
    try {
      const family = await familyReviewService.getFamily(familyId);
      setOpenFamily(family);
      setMemberLabels(
        Object.fromEntries(family.members.map((m) => [m.productId, m.variantLabel ?? ''])),
      );
    } catch {
      toast.error('No se han podido leer los miembros de la familia.');
    }
  }, [openFamily]);

  const relabel = useCallback(
    async (familyId: string, productId: string) => {
      setRelabelling(productId);
      try {
        await familyReviewService.relabelMember(familyId, productId, memberLabels[productId]);
        toast.success('Etiqueta corregida.');
        const family = await familyReviewService.getFamily(familyId);
        setOpenFamily(family);
        await loadFamilies(page);
      } catch {
        toast.error(
          'No se ha podido corregir. Dos miembros de una familia no pueden compartir etiqueta.',
        );
      } finally {
        setRelabelling(null);
      }
    },
    [memberLabels, loadFamilies, page],
  );

  const applyVerdict = useCallback(
    async (verdict: RecordedVerdict) => {
      const key = `${verdict.productId}:${verdict.familyId}`;
      setApplying(key);
      try {
        await familyReviewService.applyVerdict(verdict, labels[key]);
        toast.success(
          verdict.pendingAction === 'remove'
            ? `«${verdict.productName}» sale de «${verdict.familyName}».`
            : `«${verdict.productName}» entra en «${verdict.familyName}».`,
        );
        await Promise.all([loadRecorded(), loadFamilies(page)]);
      } catch {
        // The most likely refusal is a duplicate variant label, which the family's uniqueness
        // index rejects. Saying so beats a generic failure: it is a question the reviewer can
        // answer by typing a different label.
        toast.error(
          'No se ha podido aplicar. Si es una alta, revisa que la etiqueta de variante no '
            + 'coincida con la de otro miembro.',
        );
      } finally {
        setApplying(null);
      }
    },
    [labels, loadFamilies, loadRecorded, page],
  );

  const recordVerdict = useCallback(
    (verdict: FamilyVerdict) => {
      // Measured here and **sent with the judgement**, not merely accumulated. The average the
      // delivery checklist asks for has to survive the tab closing, and the first review session
      // lost its timings precisely because this number lived only in component state.
      const spentMs = Date.now() - openedAt.current;
      setElapsedMs((current) => current + spentMs);
      openedAt.current = Date.now();
      setReviewed((current) => current + 1);
      const timed = { ...verdict, reviewSeconds: Math.round((spentMs / 1000) * 10) / 10 };
      // Last one wins for a pair, mirroring the server: ticking a row twice before submitting is
      // a person correcting themselves, and sending both would break the unique index.
      setPending((current) => [
        ...current.filter(
          (item) => !(item.productId === verdict.productId && item.familyId === verdict.familyId),
        ),
        timed,
      ]);
    },
    [],
  );

  const submitPending = useCallback(async () => {
    if (pending.length === 0) return;

    setSaving(true);
    try {
      const result = await familyReviewService.recordVerdicts(pending);
      toast.success(
        `${result.created} veredicto(s) registrado(s)` +
          (result.updated > 0 ? `, ${result.updated} corregido(s)` : ''),
      );
      setPending([]);
      await Promise.all([loadAudit(), loadFamilies(page)]);
    } catch {
      toast.error('No se han podido guardar los veredictos.');
    } finally {
      setSaving(false);
    }
  }, [pending, loadAudit, loadFamilies, page]);

  const dissolve = useCallback(
    async (family: FamilyListItem) => {
      try {
        await familyReviewService.dissolveFamily(family.id);
        toast.success(`Familia «${family.name}» disuelta.`);
        await Promise.all([loadAudit(), loadFamilies(page)]);
      } catch {
        toast.error('No se ha podido disolver la familia.');
      }
    },
    [loadAudit, loadFamilies, page],
  );

  const averageSeconds = useMemo(
    () => (reviewed === 0 ? 0 : elapsedMs / reviewed / 1000),
    [elapsedMs, reviewed],
  );

  /**
   * What the reviewer decided about a pair, or undefined if they have not.
   *
   * Returns the **outcome** rather than a boolean. A boolean only says "judged", and a screen
   * that highlights on it marks the same button whichever answer was given — which makes the two
   * answers indistinguishable at exactly the moment a reviewer needs to see what they just did.
   */
  const verdictFor = useCallback(
    (productId: string, familyId: string) =>
      pending.find((item) => item.productId === productId && item.familyId === familyId)?.outcome,
    [pending],
  );

  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Revisión de familias</h1>
          <p className="text-muted-foreground text-sm">
            Auditar lo que existe: miembros que el vector no respalda, y productos sueltos que
            parecen pertenecer a una familia.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Read from the server, so it survives the tab closing. The session counter beside it
              is only the work done since this page opened. */}
          <Badge variant="secondary" className="gap-1">
            <Timer className="size-3" />
            {metrics
              ? `${metrics.totalJudged} juzgado(s)` +
                (metrics.averageReviewSeconds !== null
                  ? ` · ${metrics.averageReviewSeconds} s de media`
                  : ' · sin tiempos medidos')
              : '—'}
            {reviewed > 0 && ` · ${reviewed} en esta sesión (${averageSeconds.toFixed(1)} s)`}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void loadAudit();
              void loadFamilies(page);
            }}
          >
            <RefreshCw className="size-4" />
            Recalcular
          </Button>
          <Button size="sm" disabled={pending.length === 0 || saving} onClick={submitPending}>
            Guardar {pending.length > 0 ? `(${pending.length})` : ''}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="families">
        <TabsList>
          <TabsTrigger value="families">Familias ({familiesTotal})</TabsTrigger>
          <TabsTrigger value="flagged">
            Marcados{auditState === 'loaded' ? ` (${audit?.flaggedMembers.length ?? 0})` : ''}
          </TabsTrigger>
          <TabsTrigger value="orphans">
            Huérfanos{auditState === 'loaded' ? ` (${audit?.orphanCandidates.length ?? 0})` : ''}
          </TabsTrigger>
          <TabsTrigger value="apply">
            Aplicar{actionable.length > 0 ? ` (${actionable.length})` : ''}
          </TabsTrigger>
          <TabsTrigger value="incidents">Incidencias</TabsTrigger>
        </TabsList>

        {/* ── Judgements the catalogue has not acted on ──────────────────────────────────────── */}
        <TabsContent value="apply">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wrench className="size-4" />
                Cambios pendientes de aplicar
              </CardTitle>
              <CardDescription>
                Un veredicto registra lo que decidiste; no mueve la pertenencia. Aquí están las
                decisiones que el catálogo todavía no refleja.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {actionable.length === 0 ? (
                <EmptyButComputed>
                  Las {recorded.length} decisiones registradas ya están reflejadas en el catálogo.
                </EmptyButComputed>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Acción</TableHead>
                      <TableHead>Producto</TableHead>
                      <TableHead>Familia</TableHead>
                      <TableHead>Etiqueta de variante</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {actionable.map((verdict) => {
                      const key = `${verdict.productId}:${verdict.familyId}`;
                      const adding = verdict.pendingAction === 'add';
                      return (
                        <TableRow key={key}>
                          <TableCell>
                            <Badge variant={adding ? 'secondary' : 'destructive'}>
                              {adding ? 'Añadir' : 'Sacar'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="font-medium">{verdict.productName}</div>
                            <div className="text-muted-foreground text-xs">{verdict.sku}</div>
                          </TableCell>
                          <TableCell>{verdict.familyName}</TableCell>
                          <TableCell>
                            {adding ? (
                              <Input
                                value={labels[key] ?? ''}
                                onChange={(event) =>
                                  setLabels((current) => ({
                                    ...current,
                                    [key]: event.target.value,
                                  }))
                                }
                                placeholder="p. ej. S baño de oro"
                                aria-label={`Etiqueta de variante para ${verdict.productName}`}
                                className="h-8 w-48"
                              />
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant={adding ? 'primary' : 'destructive'}
                              disabled={applying === key}
                              onClick={() => void applyVerdict(verdict)}
                            >
                              {applying === key ? 'Aplicando…' : 'Aplicar'}
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Families: needs no vectors, so it stays usable while the audit does not ────────── */}
        <TabsContent value="families">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-4" />
                Familias del catálogo
              </CardTitle>
              <CardDescription>
                Esta lista no depende del servicio de IA y sigue disponible aunque la auditoría no
                lo esté.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {familiesState === 'loading' && <Skeleton className="h-40 w-full" />}

              {familiesState === 'unavailable' && (
                <Unavailable reason="No se ha podido leer el catálogo de familias." />
              )}

              {familiesState === 'loaded' && families.length === 0 && (
                <EmptyButComputed>
                  El catálogo no tiene ninguna familia todavía.
                </EmptyButComputed>
              )}

              {familiesState === 'loaded' && families.length > 0 && (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Familia</TableHead>
                        <TableHead>Origen</TableHead>
                        <TableHead className="text-right">Miembros</TableHead>
                        <TableHead className="text-right">Revisados</TableHead>
                        <TableHead className="text-right">Rechazados</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {families.map((family) => [
                        <TableRow key={family.id}>
                          <TableCell className="font-medium">{family.name}</TableCell>
                          <TableCell>
                            <Badge variant={family.origin === 'Manual' ? 'outline' : 'secondary'}>
                              {family.origin === 'Manual' ? 'Manual' : 'Aprobada por IA'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">{family.memberCount}</TableCell>
                          <TableCell className="text-right">
                            {family.reviewedMemberCount}
                          </TableCell>
                          <TableCell className="text-right">
                            {family.rejectedMemberCount > 0 ? (
                              <Badge variant="destructive">{family.rejectedMemberCount}</Badge>
                            ) : (
                              '—'
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void openMembers(family.id)}
                              aria-label={`Editar etiquetas de ${family.name}`}
                            >
                              <Pencil className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void dissolve(family)}
                              aria-label={`Disolver ${family.name}`}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </TableCell>
                        </TableRow>,
                        openFamily?.id === family.id ? (
                          <TableRow key={`${family.id}-members`}>
                            <TableCell colSpan={6} className="bg-muted/30">
                              <div className="flex flex-col gap-2 p-2">
                                <span className="text-xs font-semibold">
                                  Etiquetas de variante — una vacía significa «pieza base», y dos
                                  miembros no pueden compartirla
                                </span>
                                {openFamily.members.map((member) => (
                                  <div key={member.productId} className="flex items-center gap-2">
                                    <span className="w-64 truncate text-sm">
                                      {member.name}
                                      <span className="text-muted-foreground"> · {member.sku}</span>
                                    </span>
                                    <Input
                                      value={memberLabels[member.productId] ?? ''}
                                      onChange={(event) =>
                                        setMemberLabels((current) => ({
                                          ...current,
                                          [member.productId]: event.target.value,
                                        }))
                                      }
                                      aria-label={`Etiqueta de ${member.name}`}
                                      className="h-8 w-52"
                                    />
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={relabelling === member.productId}
                                      onClick={() => void relabel(family.id, member.productId)}
                                    >
                                      Guardar etiqueta
                                    </Button>
                                  </div>
                                ))}
                              </div>
                            </TableCell>
                          </TableRow>
                        ) : null,
                      ]).flat().filter(Boolean)}
                    </TableBody>
                  </Table>

                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-muted-foreground text-sm">
                      {familiesTotal} familia(s)
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page <= 1}
                        onClick={() => setPage((current) => current - 1)}
                      >
                        Anterior
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={families.length === 0 || page * 50 >= familiesTotal}
                        onClick={() => setPage((current) => current + 1)}
                      >
                        Siguiente
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Flagged members ────────────────────────────────────────────────────────────────── */}
        <TabsContent value="flagged">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="size-4" />
                Miembros que el vector no respalda
              </CardTitle>
              <CardDescription>
                Un producto de otra familia está más cerca de ellos que su propio peor hermano.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {auditState === 'loading' && <Skeleton className="h-40 w-full" />}
              {auditState === 'unavailable' && <Unavailable reason={auditReason} />}

              {auditState === 'loaded' && audit!.flaggedMembers.length === 0 && (
                <EmptyButComputed>
                  Se han examinado {audit!.membersExaminedCount} pertenencias en{' '}
                  {audit!.familiesReviewedCount} familias y ninguna quedó marcada.
                </EmptyButComputed>
              )}

              {auditState === 'loaded' && audit!.flaggedMembers.length > 0 && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Producto</TableHead>
                      <TableHead>En la familia</TableHead>
                      <TableHead className="text-right">Margen</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {audit!.flaggedMembers.map((member) => (
                      <TableRow key={`${member.productId}-${member.familyId}`}>
                        <TableCell>
                          <div className="font-medium">{member.name}</div>
                          <div className="text-muted-foreground text-xs">
                            {member.sku}
                            {member.variantLabel ? ` · ${member.variantLabel}` : ' · pieza base'}
                          </div>
                        </TableCell>
                        <TableCell>{member.familyName ?? '—'}</TableCell>
                        <TableCell className="text-right font-mono">
                          {formatMargin(member.margin)}
                        </TableCell>
                        <TableCell className="text-right">
                          <VerdictButtons
                            outcome={verdictFor(member.productId, member.familyId)}
                            onConfirm={() =>
                              recordVerdict({
                                productId: member.productId,
                                familyId: member.familyId,
                                outcome: 'Confirmed',
                                marginAtReview: member.margin,
                              })
                            }
                            onReject={() =>
                              recordVerdict({
                                productId: member.productId,
                                familyId: member.familyId,
                                outcome: 'Rejected',
                                marginAtReview: member.margin,
                              })
                            }
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Orphan candidates ──────────────────────────────────────────────────────────────── */}
        <TabsContent value="orphans">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Inbox className="size-4" />
                Productos que parecen pertenecer a una familia
              </CardTitle>
              <CardDescription>
                Nominados por margen relativo. La pureza se muestra para ordenar, nunca para
                seleccionar.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {auditState === 'loading' && <Skeleton className="h-40 w-full" />}
              {auditState === 'unavailable' && <Unavailable reason={auditReason} />}

              {auditState === 'loaded' && audit!.orphanCandidates.length === 0 && (
                <EmptyButComputed>
                  Ningún producto sin familia supera el margen configurado.
                </EmptyButComputed>
              )}

              {auditState === 'loaded' && audit!.orphanCandidates.length > 0 && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Producto</TableHead>
                      <TableHead>Familia candidata</TableHead>
                      <TableHead className="text-right">Margen</TableHead>
                      <TableHead className="text-right">Pureza</TableHead>
                      <TableHead>Origen</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {audit!.orphanCandidates.map((candidate) => (
                      <TableRow key={`${candidate.productId}-${candidate.familyId}`}>
                        <TableCell>
                          <div className="font-medium">{candidate.name}</div>
                          <div className="text-muted-foreground text-xs">
                            {candidate.sku} · {candidate.pieceType}
                          </div>
                        </TableCell>
                        <TableCell>{candidate.familyName ?? '—'}</TableCell>
                        <TableCell className="text-right font-mono">
                          {formatMargin(candidate.margin)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {candidate.purity}/5
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={candidate.dataOrigin === 'real' ? 'secondary' : 'outline'}
                          >
                            {candidate.dataOrigin === 'real' ? 'real' : 'sintético'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <VerdictButtons
                            outcome={verdictFor(candidate.productId, candidate.familyId)}
                            onConfirm={() =>
                              recordVerdict({
                                productId: candidate.productId,
                                familyId: candidate.familyId,
                                outcome: 'Confirmed',
                                marginAtReview: candidate.margin,
                              })
                            }
                            onReject={() =>
                              recordVerdict({
                                productId: candidate.productId,
                                familyId: candidate.familyId,
                                outcome: 'Rejected',
                                marginAtReview: candidate.margin,
                              })
                            }
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Refusals: catalogue findings, not membership questions ─────────────────────────── */}
        <TabsContent value="incidents">
          <Card>
            <CardHeader>
              <CardTitle>Incidencias de catálogo</CardTitle>
              <CardDescription>
                Grupos que una guarda rechazó y productos que la puerta de tipo de pieza excluyó.
                No son preguntas de pertenencia: no se juzgan, se arreglan en el catálogo.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {auditState === 'loading' && <Skeleton className="h-40 w-full" />}
              {auditState === 'unavailable' && <Unavailable reason={auditReason} />}

              {auditState === 'loaded' && (
                <>
                  <section>
                    <h3 className="mb-2 text-sm font-semibold">
                      Grupos rechazados ({audit!.rejectedGroups.length})
                    </h3>
                    {audit!.rejectedGroups.length === 0 ? (
                      <EmptyButComputed>Ninguna guarda rechazó un grupo.</EmptyButComputed>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Raíz</TableHead>
                            <TableHead>Motivo</TableHead>
                            <TableHead>Productos</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {audit!.rejectedGroups.map((group) => (
                            <TableRow key={`${group.pieceType}-${group.root}`}>
                              <TableCell className="font-mono">{group.root}</TableCell>
                              <TableCell>
                                <Badge variant="outline">{group.reason}</Badge>
                              </TableCell>
                              <TableCell>{group.productNames.join(' · ')}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </section>

                  <section>
                    <h3 className="mb-2 text-sm font-semibold">
                      Excluidos por la puerta ({audit!.excludedProducts.length})
                    </h3>
                    {audit!.excludedProducts.length === 0 ? (
                      <EmptyButComputed>
                        Ningún producto quedó fuera por falta de tipo de pieza.
                      </EmptyButComputed>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Producto</TableHead>
                            <TableHead>Motivo</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {audit!.excludedProducts.map((product) => (
                            <TableRow key={product.productId}>
                              <TableCell>
                                <div className="font-medium">{product.name}</div>
                                <div className="text-muted-foreground text-xs">{product.sku}</div>
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{product.reason}</Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </section>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/**
 * The two answers, each showing whether it is the one that was given.
 *
 * The state is the **outcome**, not a boolean. Highlighting on "has a verdict" marks the same
 * button whichever answer was chosen, so a reviewer cannot tell a confirmation from a dismissal
 * on the row they just answered — which on a queue of 156 is how a mis-click becomes permanent
 * without anybody noticing.
 *
 * The two are styled differently on purpose rather than both filled: a dismissal is the
 * destructive answer, and colour carries that faster than reading the label. `aria-pressed`
 * states the same thing for a screen reader, and gives the tests something honest to assert.
 */
function VerdictButtons({
  outcome,
  onConfirm,
  onReject,
}: {
  outcome: FamilyReviewOutcome | undefined;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const confirmed = outcome === 'Confirmed';
  const rejected = outcome === 'Rejected';

  return (
    <div className="flex justify-end gap-1">
      <Button
        variant={confirmed ? 'primary' : 'outline'}
        size="sm"
        onClick={onConfirm}
        aria-pressed={confirmed}
        aria-label="Confirmar pertenencia"
      >
        {confirmed && <Check className="size-3" />}
        Confirmar
      </Button>
      <Button
        variant={rejected ? 'destructive' : 'outline'}
        size="sm"
        onClick={onReject}
        aria-pressed={rejected}
        aria-label="Rechazar pertenencia"
      >
        {rejected && <X className="size-3" />}
        Descartar
      </Button>
    </div>
  );
}
