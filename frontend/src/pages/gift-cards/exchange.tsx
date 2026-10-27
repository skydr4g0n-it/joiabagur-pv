/**
 * Gift card product exchange (cambio de producto vinculado)
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Search, ShoppingCart } from 'lucide-react';
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
import { getImageUrl } from '@/lib/image-url';
import { ROUTES } from '@/routing/routes';
import type { GiftCardDetail } from '@/types/gift-card.types';
import type { ProductListItem } from '@/types/product.types';
import { ReturnCategory, ReturnCategoryLabels } from '@/types/returns.types';

export function GiftCardExchangePage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const saleIdFromQuery = searchParams.get('saleId');
  const navigate = useNavigate();
  const [card, setCard] = useState<GiftCardDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [selectedSaleId, setSelectedSaleId] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [searchResults, setSearchResults] = useState<ProductListItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const skipNextSearchRef = useRef(false);
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
        const linked = detail.linkedProducts.find((line) => line.saleId === saleIdFromQuery);
        if (linked) {
          setSelectedSaleId(linked.saleId);
        } else if (detail.linkedProducts.length === 1) {
          setSelectedSaleId(detail.linkedProducts[0].saleId);
        }
      })
      .catch(() => toast.error('No se pudo cargar la tarjeta'))
      .finally(() => setLoading(false));
  }, [id, saleIdFromQuery]);

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

  useEffect(() => {
    if (skipNextSearchRef.current) {
      skipNextSearchRef.current = false;
      return;
    }

    const trimmedSearch = productSearch.trim();
    if (!trimmedSearch || trimmedSearch.length < 2) {
      setSearchResults([]);
      return;
    }

    setSearchLoading(true);
    const timeoutId = setTimeout(async () => {
      try {
        const results = await productService.searchProducts(trimmedSearch);
        setSearchResults(results.slice(0, 10));
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);

    return () => {
      clearTimeout(timeoutId);
      setSearchLoading(false);
    };
  }, [productSearch]);

  const handleSelectProduct = (product: ProductListItem) => {
    skipNextSearchRef.current = true;
    setReplacementProduct(product);
    setProductSearch(product.sku);
    setSearchResults([]);
    if (selectedLink) {
      setCashDuePreview(Math.max(0, product.price - selectedLink.coverageAmount));
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
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Buscar por SKU o nombre (mín. 2 caracteres)..."
              className="pl-10"
              value={productSearch}
              onChange={(e) => {
                setProductSearch(e.target.value);
                setReplacementProduct(null);
                setCashDuePreview(null);
              }}
            />
            {searchLoading && (
              <p className="mt-1 text-xs text-muted-foreground">Buscando…</p>
            )}
            {searchResults.length > 0 && (
              <div className="absolute z-10 mt-1 w-full rounded-md border bg-background shadow-lg">
                {searchResults.map((product) => {
                  const photoUrl = getImageUrl(product.primaryPhotoUrl);
                  return (
                    <button
                      key={product.id}
                      type="button"
                      className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted"
                      onClick={() => handleSelectProduct(product)}
                    >
                      {photoUrl ? (
                        <img
                          src={photoUrl}
                          alt={product.name}
                          className="h-10 w-10 flex-shrink-0 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md bg-muted">
                          <ShoppingCart className="h-5 w-5 text-muted-foreground" />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">{product.name}</div>
                        <div className="text-sm text-muted-foreground">
                          SKU: {product.sku} | {formatCurrency(product.price)}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
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
