/**
 * Sales Cart Page
 * Displays cart lines, allows removal, shows totals,
 * revalidates stock, and provides bulk checkout confirmation.
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  ShoppingCart,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  PackageX,
  Loader2,
  Gift,
  Plus,
} from 'lucide-react';
import { toast } from 'sonner';

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

import { useCart } from '@/providers/cart-provider';
import { salesService } from '@/services/sales.service';
import { inventoryService } from '@/services/inventory.service';
import { giftCardService } from '@/services/gift-card.service';
import { paymentMethodService } from '@/services/payment-method.service';
import { computeGiftCardCoverageTotal } from '@/lib/gift-card-allocation';
import { formatCurrency } from '@/lib/format-currency';
import { ROUTES } from '@/routing/routes';
import type { CartLine } from '@/types/sales.types';
import type { GiftCardByCode } from '@/types/gift-card.types';

const GIFT_CARD_PAYMENT_CODE = 'GIFT_CARD';

interface StockStatus {
  available: number;
  sufficient: boolean;
}

export function SalesCartPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    lines,
    lineCount,
    total,
    pointOfSaleName,
    pointOfSaleId,
    paymentMethodName,
    paymentMethodId,
    removeLine,
    clearCart,
  } = useCart();

  const [stockMap, setStockMap] = useState<Record<string, StockStatus>>({});
  const [stockLoading, setStockLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [globalNote, setGlobalNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [attachedCards, setAttachedCards] = useState<GiftCardByCode[]>([]);
  const [cardCodeInput, setCardCodeInput] = useState('');
  const [addingCard, setAddingCard] = useState(false);
  const [giftCardPaymentMethodId, setGiftCardPaymentMethodId] = useState<string | null>(null);

  useEffect(() => {
    const loadGiftPay = async () => {
      if (!pointOfSaleId) return;
      try {
        const assignments = await paymentMethodService.getPointOfSalePaymentMethods(
          pointOfSaleId,
          true,
        );
        const gift = assignments.find((a) => a.paymentMethod?.code === GIFT_CARD_PAYMENT_CODE);
        setGiftCardPaymentMethodId(gift?.paymentMethodId ?? null);
      } catch {
        setGiftCardPaymentMethodId(null);
      }
    };
    loadGiftPay();
  }, [pointOfSaleId]);

  const lineTotals = useMemo(
    () =>
      lines.map((l) => {
        const price = l.price ?? l.productPrice;
        return { lineTotal: price * l.quantity };
      }),
    [lines],
  );

  const coverageTotal = useMemo(
    () =>
      computeGiftCardCoverageTotal(
        lineTotals,
        attachedCards.map((c) => ({ code: c.code, spendableBalance: c.spendableBalance })),
      ),
    [lineTotals, attachedCards],
  );

  const cashDue = Math.max(0, Math.round((total - coverageTotal) * 100) / 100);

  const addGiftCardByCode = async (rawCode: string) => {
    const code = rawCode.trim().toUpperCase();
    if (!code.startsWith('GC-')) {
      toast.error('El código debe empezar por GC-');
      return;
    }
    if (!pointOfSaleId) {
      toast.error('Selecciona un punto de venta en el carrito');
      return;
    }
    if (attachedCards.some((c) => c.code === code)) {
      toast.error('Esta tarjeta ya está en el carrito');
      return;
    }
    setAddingCard(true);
    try {
      const card = await giftCardService.getByCode(code, pointOfSaleId);
      setAttachedCards((prev) => [...prev, card]);
      setCardCodeInput('');
      toast.success(`Tarjeta ${code} añadida`);
    } catch (error: unknown) {
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'No se pudo validar la tarjeta regalo';
      toast.error(message);
    } finally {
      setAddingCard(false);
    }
  };

  // Revalidate stock for all lines
  const revalidateStock = useCallback(async () => {
    if (lines.length === 0 || !pointOfSaleId) return;

    setStockLoading(true);
    const newMap: Record<string, StockStatus> = {};

    try {
      const uniqueProductIds = [...new Set(lines.map((l) => l.productId))];
      await Promise.all(
        uniqueProductIds.map(async (productId) => {
          try {
            const breakdown =
              await inventoryService.getProductStockBreakdown(productId);
            const posStock = breakdown?.breakdown.find(
              (b) => b.pointOfSaleId === pointOfSaleId,
            );
            const available = posStock?.quantity ?? 0;
            const totalRequested = lines
              .filter((l) => l.productId === productId)
              .reduce((sum, l) => sum + l.quantity, 0);
            newMap[productId] = {
              available,
              sufficient: available >= totalRequested,
            };
          } catch {
            newMap[productId] = { available: 0, sufficient: false };
          }
        }),
      );
    } catch {
      toast.error('Error al verificar stock');
    } finally {
      setStockMap(newMap);
      setStockLoading(false);
    }
  }, [lines, pointOfSaleId]);

  useEffect(() => {
    revalidateStock();
  }, [revalidateStock]);

  useEffect(() => {
    const code = (location.state as { giftCardCode?: string } | null)?.giftCardCode;
    if (code) {
      addGiftCardByCode(code);
      navigate(location.pathname, { replace: true, state: {} });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once when navigated from scanner
  }, [location.state]);

  const hasInsufficientStock = Object.values(stockMap).some((s) => !s.sufficient);
  const canCheckout = lineCount > 0 && !hasInsufficientStock && !stockLoading;

  const handleRemoveLine = (line: CartLine) => {
    removeLine(line.id);
    toast.success(`"${line.productName}" eliminado del carrito`);
  };

  const handleCheckout = async () => {
    if (!pointOfSaleId || !paymentMethodId) return;

    setSubmitting(true);
    const idempotencyKey = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-bulk`;
    const effectivePaymentMethodId =
      cashDue <= 0 && giftCardPaymentMethodId ? giftCardPaymentMethodId : paymentMethodId;

    if (cashDue <= 0 && attachedCards.length > 0 && !giftCardPaymentMethodId) {
      toast.error('Método de pago de tarjeta regalo no configurado en este POS');
      return;
    }

    try {
      const result = await salesService.createBulkSales(
        {
          pointOfSaleId,
          paymentMethodId: effectivePaymentMethodId,
          giftCardCodes: attachedCards.length > 0 ? attachedCards.map((c) => c.code) : undefined,
          notes: globalNote || undefined,
          lines: lines.map((l) => ({
            productId: l.productId,
            quantity: l.quantity,
            price: l.price !== undefined && l.price !== l.productPrice ? l.price : undefined,
            photoBase64: l.photoBase64,
            photoFileName: l.photoFileName,
          })),
        },
        idempotencyKey,
      );

      if (!result.success) {
        toast.error(result.errorMessage || 'Error al procesar el checkout');
        return;
      }

      clearCart();
      setConfirmOpen(false);
      toast.success(
        `Checkout exitoso: ${result.sales.length} venta(s) registrada(s)`,
      );

      if (result.warnings.length > 0) {
        result.warnings.forEach((w) => {
          toast.warning(`${w.productName}: ${w.message}`, { duration: 5000 });
        });
      }

      navigate(ROUTES.SALES.HISTORY);
    } catch (error: unknown) {
      const msg =
        (error as { message?: string }).message ||
        'Error al procesar el checkout';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (lineCount === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link to={ROUTES.SALES.ROOT}>
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Carrito de Ventas
            </h1>
            <p className="text-muted-foreground">
              Tu carrito está vacío
            </p>
          </div>
        </div>

        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <PackageX className="h-16 w-16 text-muted-foreground/40" />
            <p className="mt-4 text-lg font-medium text-muted-foreground">
              No hay productos en el carrito
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Agrega productos desde la página de registro de ventas
            </p>
            <Button className="mt-6" asChild>
              <Link to={ROUTES.SALES.NEW}>Registrar Venta</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link to={ROUTES.SALES.ROOT}>
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Carrito de Ventas
            </h1>
            <p className="text-muted-foreground">
              {lineCount} producto(s) &middot; {pointOfSaleName}
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            clearCart();
            toast.success('Carrito vaciado');
          }}
        >
          Vaciar carrito
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Line items */}
        <div className="space-y-3 lg:col-span-2">
          {stockLoading && (
            <Alert>
              <Loader2 className="h-4 w-4 animate-spin" />
              <AlertTitle>Verificando stock...</AlertTitle>
            </Alert>
          )}

          {hasInsufficientStock && !stockLoading && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Stock insuficiente</AlertTitle>
              <AlertDescription>
                Algunas líneas no tienen stock suficiente. Elimínalas para
                continuar con el checkout.
              </AlertDescription>
            </Alert>
          )}

          {lines.map((line) => {
            const stock = stockMap[line.productId];
            const linePrice = line.price ?? line.productPrice;
            const lineTotal = linePrice * line.quantity;
            const insufficient = stock && !stock.sufficient;

            return (
              <Card
                key={line.id}
                className={insufficient ? 'border-destructive' : ''}
              >
                <CardContent className="flex items-center gap-4 py-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="font-semibold truncate">
                          {line.productName}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          SKU: {line.productSku}
                        </p>
                      </div>
                      <Badge variant="outline" className="shrink-0">
                        x{line.quantity}
                      </Badge>
                    </div>

                    <div className="mt-2 flex items-center gap-4 text-sm">
                      <span className="text-muted-foreground">
                        €{linePrice.toFixed(2)} c/u
                      </span>
                      {line.price !== undefined &&
                        line.price !== line.productPrice && (
                          <span className="text-xs text-amber-600">
                            Precio oficial: €{line.productPrice.toFixed(2)}
                          </span>
                        )}
                      <span className="font-semibold">
                        €{lineTotal.toFixed(2)}
                      </span>
                    </div>

                    {stock && (
                      <div className="mt-1 text-xs">
                        {insufficient ? (
                          <span className="text-destructive font-medium">
                            Stock disponible: {stock.available} (insuficiente)
                          </span>
                        ) : (
                          <span className="text-muted-foreground">
                            Stock disponible: {stock.available}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0 text-destructive hover:text-destructive"
                    onClick={() => handleRemoveLine(line)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Checkout summary */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShoppingCart className="h-5 w-5" />
              Resumen
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Punto de venta</span>
                <span className="font-medium">{pointOfSaleName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Método de pago</span>
                <span className="font-medium">{paymentMethodName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Líneas</span>
                <span className="font-medium">{lineCount}</span>
              </div>
            </div>

            <div className="space-y-2 border-t pt-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Gift className="size-4" />
                Tarjetas regalo
              </div>
              {attachedCards.map((card) => (
                <div key={card.code} className="flex items-center justify-between text-sm">
                  <span className="font-mono">{card.code}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-destructive"
                    onClick={() =>
                      setAttachedCards((prev) => prev.filter((c) => c.code !== card.code))
                    }
                  >
                    Quitar
                  </Button>
                </div>
              ))}
              <div className="flex gap-2">
                <Input
                  placeholder="GC-..."
                  value={cardCodeInput}
                  onChange={(e) => setCardCodeInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addGiftCardByCode(cardCodeInput);
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  disabled={addingCard}
                  onClick={() => addGiftCardByCode(cardCodeInput)}
                >
                  <Plus className="size-4" />
                </Button>
              </div>
            </div>

            <div className="border-t pt-3 space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Subtotal</span>
                <span>{formatCurrency(total)}</span>
              </div>
              {coverageTotal > 0 && (
                <div className="flex items-center justify-between text-sm text-emerald-700">
                  <span>Cobertura tarjeta</span>
                  <span>-{formatCurrency(coverageTotal)}</span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="font-semibold">Importe a cobrar</span>
                <span className="text-xl font-bold text-primary">
                  {formatCurrency(cashDue)}
                </span>
              </div>
            </div>

            <Button
              className="w-full"
              size="lg"
              disabled={!canCheckout}
              onClick={() => setConfirmOpen(true)}
            >
              <ShoppingCart className="mr-2 h-5 w-5" />
              Realizar Checkout
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Checkout Confirmation Dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Checkout</DialogTitle>
            <DialogDescription>
              Se registrarán {lineCount} venta(s) de forma atómica.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertTitle>Resumen del Checkout</AlertTitle>
              <AlertDescription>
                <div className="mt-2 space-y-1 text-sm">
                  <p>
                    <strong>Líneas:</strong> {lineCount}
                  </p>
                  <p>
                    <strong>Importe a cobrar:</strong> {formatCurrency(cashDue)}
                  </p>
                  <p>
                    <strong>Punto de venta:</strong> {pointOfSaleName}
                  </p>
                  <p>
                    <strong>Método de pago:</strong> {paymentMethodName}
                  </p>
                </div>
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <Label htmlFor="global-note">Nota global (opcional)</Label>
              <Textarea
                id="global-note"
                placeholder="Añadir nota para todas las ventas..."
                value={globalNote}
                onChange={(e) => setGlobalNote(e.target.value)}
                maxLength={500}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button onClick={handleCheckout} disabled={submitting}>
              {submitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Procesando...
                </>
              ) : (
                'Confirmar Checkout'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default SalesCartPage;
