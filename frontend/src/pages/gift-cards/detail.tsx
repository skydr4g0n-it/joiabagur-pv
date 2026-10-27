/**
 * Gift card detail and trace
 */
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';

import { useAuth } from '@/providers/auth-provider';
import { giftCardService } from '@/services/gift-card.service';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import { ROUTES } from '@/routing/routes';
import { formatCurrency } from '@/lib/format-currency';
import type { GiftCardDetail } from '@/types/gift-card.types';
import type { PointOfSale } from '@/types/point-of-sale.types';
import { GiftCardCodesPanel } from './components/gift-card-codes-panel';

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('es-ES');
}

export function GiftCardDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  const [card, setCard] = useState<GiftCardDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [allPos, setAllPos] = useState<PointOfSale[]>([]);
  const [targetPosId, setTargetPosId] = useState('');
  const [reassigning, setReassigning] = useState(false);

  const loadCard = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const detail = await giftCardService.getById(id);
      setCard(detail);
    } catch {
      toast.error('No se pudo cargar la tarjeta');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCard();
  }, [id]);

  useEffect(() => {
    if (!isAdmin || !reassignOpen) return;
    pointOfSaleService.getPointsOfSale().then((pos) => {
      setAllPos(pos.filter((p) => p.isActive));
    });
  }, [isAdmin, reassignOpen]);

  const handleReassign = async () => {
    if (!id || !targetPosId) return;
    setReassigning(true);
    try {
      const updated = await giftCardService.reassign(id, { toPointOfSaleId: targetPosId });
      setCard(updated);
      setReassignOpen(false);
      toast.success('Tarjeta reasignada');
    } catch (error: unknown) {
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Error al reasignar';
      toast.error(message);
    } finally {
      setReassigning(false);
    }
  };

  if (loading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!card) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to={ROUTES.GIFT_CARDS.ROOT}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Volver
          </Link>
        </Button>
        <p className="text-muted-foreground">Tarjeta no encontrada</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" asChild>
            <Link to={ROUTES.GIFT_CARDS.ROOT}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Volver
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight font-mono">{card.code}</h1>
            <p className="text-muted-foreground">{card.pointOfSaleName}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {card.linkedProducts.length > 0 && (
            <Button variant="default" asChild>
              <Link to={ROUTES.GIFT_CARDS.EXCHANGE(card.id)}>Cambiar producto</Link>
            </Button>
          )}
          {isAdmin && (
            <Button variant="outline" onClick={() => setReassignOpen(true)}>
              Reasignar POS
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Nominal</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{formatCurrency(card.nominalAmount)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Saldo gastable</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {formatCurrency(card.spendableBalance)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Resto contabilizado</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {formatCurrency(card.accountedRemainder)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Caducidad</CardTitle>
          </CardHeader>
          <CardContent className="text-lg">{card.expiryDate}</CardContent>
        </Card>
      </div>

      {card.holderName && (
        <p className="text-sm">
          <span className="text-muted-foreground">Titular:</span> {card.holderName}
        </p>
      )}

      <GiftCardCodesPanel
        cardId={card.id}
        code={card.code}
        nominalAmount={card.nominalAmount}
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>Productos vinculados</CardTitle>
          {card.linkedProducts.length > 0 && (
            <Button size="sm" asChild>
              <Link to={ROUTES.GIFT_CARDS.EXCHANGE(card.id)}>Cambiar producto</Link>
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {card.linkedProducts.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin coberturas registradas</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Producto</TableHead>
                  <TableHead>Fecha venta</TableHead>
                  <TableHead className="text-right">Cobertura</TableHead>
                  <TableHead className="text-right">Acción</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {card.linkedProducts.map((link) => (
                  <TableRow key={link.saleId}>
                    <TableCell>
                      {link.productName}
                      <span className="ml-2 text-xs text-muted-foreground">{link.productSku}</span>
                    </TableCell>
                    <TableCell>{formatDateTime(link.saleDate)}</TableCell>
                    <TableCell className="text-right">{formatCurrency(link.coverageAmount)}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" asChild>
                        <Link
                          to={`${ROUTES.GIFT_CARDS.EXCHANGE(card.id)}?saleId=${encodeURIComponent(link.saleId)}`}
                        >
                          Cambiar
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Operaciones</CardTitle>
        </CardHeader>
        <CardContent>
          {card.operations.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin operaciones adicionales</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Detalle</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {card.operations.map((op, index) => (
                  <TableRow key={`${op.type}-${index}`}>
                    <TableCell>{op.type}</TableCell>
                    <TableCell>{formatDateTime(op.occurredAt)}</TableCell>
                    <TableCell>{op.detail || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Emisión en {card.issuanceSalePointOfSaleName} ·{' '}
        {formatDateTime(card.issuanceSaleDate)}
      </p>

      <Dialog open={reassignOpen} onOpenChange={setReassignOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reasignar punto de venta</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label>Nuevo punto de venta</Label>
            <Select value={targetPosId} onValueChange={setTargetPosId}>
              <SelectTrigger>
                <SelectValue placeholder="Seleccionar" />
              </SelectTrigger>
              <SelectContent>
                {allPos
                  .filter((p) => p.id !== card.pointOfSaleId)
                  .map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReassignOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleReassign} disabled={!targetPosId || reassigning}>
              {reassigning ? <Loader2 className="size-4 animate-spin" /> : 'Confirmar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default GiftCardDetailPage;
