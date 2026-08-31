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
  CheckCircle2,
  CloudOff,
  Inbox,
  RefreshCw,
  Timer,
  Trash2,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
  FamilyVerdict,
  ListState,
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

  useEffect(() => {
    const controller = new AbortController();
    void loadFamilies(page, controller.signal);
    return () => controller.abort();
  }, [loadFamilies, page]);

  const recordVerdict = useCallback(
    (verdict: FamilyVerdict) => {
      setElapsedMs((current) => current + (Date.now() - openedAt.current));
      openedAt.current = Date.now();
      setReviewed((current) => current + 1);
      // Last one wins for a pair, mirroring the server: ticking a row twice before submitting is
      // a person correcting themselves, and sending both would break the unique index.
      setPending((current) => [
        ...current.filter(
          (item) => !(item.productId === verdict.productId && item.familyId === verdict.familyId),
        ),
        verdict,
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

  const isJudged = useCallback(
    (productId: string, familyId: string) =>
      pending.some((item) => item.productId === productId && item.familyId === familyId),
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
          <Badge variant="secondary" className="gap-1">
            <Timer className="size-3" />
            {reviewed} revisado(s)
            {reviewed > 0 && ` · ${averageSeconds.toFixed(1)} s de media`}
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
          <TabsTrigger value="incidents">Incidencias</TabsTrigger>
        </TabsList>

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
                      {families.map((family) => (
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
                              onClick={() => void dissolve(family)}
                              aria-label={`Disolver ${family.name}`}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
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
                            judged={isJudged(member.productId, member.familyId)}
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
                            judged={isJudged(candidate.productId, candidate.familyId)}
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
 * The two answers, with the keyboard shortcuts a queue of 156 needs.
 *
 * `C` and `R` rather than a mouse round trip per row: the review is measured, and a reviewer who
 * has to aim at two small buttons per item spends the session aiming.
 */
function VerdictButtons({
  judged,
  onConfirm,
  onReject,
}: {
  judged: boolean;
  onConfirm: () => void;
  onReject: () => void;
}) {
  return (
    <div className="flex justify-end gap-1">
      <Button
        variant={judged ? 'secondary' : 'outline'}
        size="sm"
        onClick={onConfirm}
        onKeyDown={(event) => event.key === 'c' && onConfirm()}
        aria-label="Confirmar pertenencia"
      >
        Confirmar
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onReject}
        onKeyDown={(event) => event.key === 'r' && onReject()}
        aria-label="Rechazar pertenencia"
      >
        Descartar
      </Button>
    </div>
  );
}
