/**
 * Gift card list (tarjetas regalo)
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Gift, PlusCircle } from 'lucide-react';
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
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

import { giftCardService } from '@/services/gift-card.service';
import { formatCurrency } from '@/lib/format-currency';
import { ROUTES } from '@/routing/routes';
import type { GiftCardListItem } from '@/types/gift-card.types';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES');
}

export function GiftCardsListPage() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<GiftCardListItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await giftCardService.list(page, 50);
      setItems(result.items);
      setTotalPages(result.totalPages);
    } catch {
      toast.error('Error al cargar tarjetas regalo');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tarjetas regalo</h1>
          <p className="text-muted-foreground">Emisión y seguimiento de tarjetas regalo</p>
        </div>
        <Button asChild>
          <Link to={ROUTES.GIFT_CARDS.ISSUE}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Emitir tarjeta
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Gift className="size-5" />
            Listado
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-48 w-full" />
          ) : items.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No hay tarjetas regalo. Emite la primera desde el botón superior.
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Código</TableHead>
                    <TableHead>Punto de venta</TableHead>
                    <TableHead>Titular</TableHead>
                    <TableHead className="text-right">Nominal</TableHead>
                    <TableHead className="text-right">Saldo</TableHead>
                    <TableHead>Caducidad</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((card) => (
                    <TableRow key={card.id}>
                      <TableCell className="font-mono text-sm">{card.code}</TableCell>
                      <TableCell>{card.pointOfSaleName}</TableCell>
                      <TableCell>{card.holderName || '—'}</TableCell>
                      <TableCell className="text-right">{formatCurrency(card.nominalAmount)}</TableCell>
                      <TableCell className="text-right">
                        {card.spendableBalance > 0 ? (
                          <Badge variant="secondary">{formatCurrency(card.spendableBalance)}</Badge>
                        ) : (
                          <Badge variant="outline">Usada</Badge>
                        )}
                      </TableCell>
                      <TableCell>{formatDate(card.expiryDate)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" asChild>
                          <Link to={ROUTES.GIFT_CARDS.DETAIL(card.id)}>Ver</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {totalPages > 1 && (
                <div className="mt-4 flex justify-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Anterior
                  </Button>
                  <span className="flex items-center text-sm text-muted-foreground">
                    Página {page} de {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default GiftCardsListPage;
