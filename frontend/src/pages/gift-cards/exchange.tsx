/**
 * Gift card product exchange (cambio de producto vinculado)
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';

import { giftCardService } from '@/services/gift-card.service';
import { productService } from '@/services/product.service';
import { paymentMethodService } from '@/services/payment-method.service';
import { formatCurrency } from '@/lib/format-currency';
import { ROUTES } from '@/routing/routes';
import type { GiftCardDetail } from '@/types/gift-card.types';
import type { ProductListItem } from '@/types/product.types';
import { ReturnCategory, ReturnCategoryLabels } from '@/types/returns.types';

export function GiftCardExchangePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [card, setCard] = useState<GiftCardDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedSaleId, setSelectedSaleId] = useState('');
  const [replacementSku, setReplacementSku] = useState('');
  const [replacementProduct, setReplacementProduct] = useState<ProductListItem | null>(null);
  const [category, setCategory] = useState<ReturnCategory>(ReturnCategory.Defectuoso);
  const [paymentMethodId, setPaymentMethodId] = useState('');
  const [paymentMethods, setPaymentMethods] = useState<{ id: string; name: string }[]>([]);
  const [cashDuePreview, setCashDuePreview] = useState<number | null>(null);

  useEffect(() => {
    if (!id) return;
    giftCardService
      .getById(id)
      .then((detail) => {
        setCard(detail);
        if (detail.linkedProducts.length === 1) {
          setSelectedSaleId(detail.linkedProducts[0].saleId);
        }
      })
      .catch(() => toast.error('No se pudo cargar la tarjeta'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!card) return;
    paymentMethodService
      .getPointOfSalePaymentMethods(card.pointOfSaleId, true)
      .then((rows) =>
        setPaymentMethods(
          rows
            .filter((r) => r.isActive && r.paymentMethod?.code !== 'GIFT_CARD')
            .map((r) => ({ id: r.paymentMethodId, name: r.paymentMethod?.name ?? '' })),
        ),
      )
      .catch(() => setPaymentMethods([]));
  }, [card]);

  const selectedLink = useMemo(
    () => card?.linkedProducts.find((l) => l.saleId === selectedSaleId),
    [card, selectedSaleId],
  );

  const lookupReplacement = async () => {
    const sku = replacementSku.trim();
    if (!sku) return;
    try {
      const products = await productService.searchProducts(sku);
      const match = products.find((p) => p.sku?.toUpperCase() === sku.toUpperCase());
      if (!match) {
        toast.error('Producto no encontrado');
        setReplacementProduct(null);
        return;
      }
      setReplacementProduct(match);
      if (selectedLink) {
        const diff = Math.max(0, match.price - selectedLink.coverageAmount);
        setCashDuePreview(diff);
      }
    } catch {
      toast.error('Error al buscar producto');
    }
  };

  const handleSubmit = async () => {
    if (!id || !card || !selectedSaleId || !replacementProduct || !paymentMethodId) {
      toast.error('Completa todos los campos');
      return;
    }
    setSubmitting(true);
    try {
      const result = await giftCardService.exchange(
        id,
        {
          pointOfSaleId: card.pointOfSaleId,
          paymentMethodId,
          returnCategory: category,
          returnLines: [{ saleId: selectedSaleId, quantity: 1 }],
          newProducts: [{ productId: replacementProduct.id, quantity: 1 }],
        },
        globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-exchange`,
      );
      toast.success(`Cambio registrado. Efectivo a cobrar: ${formatCurrency(result.cashDue)}`);
      navigate(ROUTES.GIFT_CARDS.DETAIL(id));
    } catch (error: unknown) {
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'No se pudo completar el cambio';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-muted-foreground">Cargando…</div>;
  }

  if (!card) {
    return <div className="p-6">Tarjeta no encontrada</div>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4">
      <Button variant="ghost" size="sm" asChild>
        <Link to={ROUTES.GIFT_CARDS.DETAIL(card.id)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver al detalle
        </Link>
      </Button>

      <div>
        <h1 className="text-2xl font-bold">Cambio de producto</h1>
        <p className="font-mono text-muted-foreground">{card.code}</p>
      </div>

      <Alert>
        <AlertDescription>
          Las ventas cubiertas por tarjeta regalo solo pueden cambiarse aquí (no por devolución
          clásica). La tarjeta es de un solo uso; el resto contabilizado se aplica al nuevo
          producto.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Producto a devolver</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Venta vinculada</Label>
            <Select value={selectedSaleId} onValueChange={setSelectedSaleId}>
              <SelectTrigger>
                <SelectValue placeholder="Seleccionar" />
              </SelectTrigger>
              <SelectContent>
                {card.linkedProducts.map((link) => (
                  <SelectItem key={link.saleId} value={link.saleId}>
                    {link.productName} ({formatCurrency(link.coverageAmount)})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Categoría de devolución</Label>
            <Select
              value={String(category)}
              onValueChange={(v) => setCategory(Number(v) as ReturnCategory)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(ReturnCategoryLabels).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Producto nuevo</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="SKU del producto nuevo"
              value={replacementSku}
              onChange={(e) => setReplacementSku(e.target.value)}
            />
            <Button type="button" variant="outline" onClick={lookupReplacement}>
              Buscar
            </Button>
          </div>
          {replacementProduct && (
            <p className="text-sm">
              {replacementProduct.name} — {formatCurrency(replacementProduct.price)}
            </p>
          )}
          {cashDuePreview != null && (
            <p className="text-sm font-medium text-primary">
              Importe en efectivo estimado: {formatCurrency(cashDuePreview)}
            </p>
          )}
          <div className="space-y-2">
            <Label>Método de pago (exceso en efectivo)</Label>
            <Select value={paymentMethodId} onValueChange={setPaymentMethodId}>
              <SelectTrigger>
                <SelectValue placeholder="Seleccionar" />
              </SelectTrigger>
              <SelectContent>
                {paymentMethods.map((pm) => (
                  <SelectItem key={pm.id} value={pm.id}>
                    {pm.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button className="w-full" disabled={submitting} onClick={handleSubmit}>
            {submitting ? <Loader2 className="size-4 animate-spin" /> : 'Confirmar cambio'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default GiftCardExchangePage;
