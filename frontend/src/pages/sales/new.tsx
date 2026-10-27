/**
 * Manual Sales Registration Page (EP3)
 * Allows operators to register sales by searching for products
 */
import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { ArrowLeft, Search, ShoppingCart, AlertTriangle, CheckCircle2, Plus, Gift } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

import { useCart } from '@/providers/cart-provider';
import { getImageUrl } from '@/lib/image-url';
import { formatCurrency } from '@/lib/format-currency';
import { computeGiftCardCoverageTotal } from '@/lib/gift-card-allocation';
import { salesService } from '@/services/sales.service';
import { productService } from '@/services/product.service';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import { paymentMethodService } from '@/services/payment-method.service';
import { inventoryService } from '@/services/inventory.service';
import { giftCardService } from '@/services/gift-card.service';
import { ROUTES } from '@/routing/routes';
import type { Product } from '@/types/product.types';
import type { PointOfSale } from '@/types/point-of-sale.types';
import type { PaymentMethod } from '@/types/payment-method.types';
import type { GiftCardByCode } from '@/types/gift-card.types';

const GIFT_CARD_PAYMENT_CODE = 'GIFT_CARD';

// State passed from image recognition or the sales scanner
interface LocationState {
  productId?: string;
  photoDataUrl?: string;
  giftCardCode?: string;
  giftCardCodes?: string[];
}

export function ManualSalesPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { addLine, lineCount } = useCart();
  
  // Get pre-selected product from image recognition
  const locationState = location.state as LocationState | null;

  // Prevent re-search when productSearch is set programmatically after a selection
  const skipNextSearchRef = useRef(false);
  const consumedScannerCodesRef = useRef(false);

  // State
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [productSearch, setProductSearch] = useState('');
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  
  // Form state
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedPosId, setSelectedPosId] = useState<string>('');
  const [selectedPaymentMethodId, setSelectedPaymentMethodId] = useState<string>('');
  const [quantity, setQuantity] = useState(1);
  const [manualPrice, setManualPrice] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [availableStock, setAvailableStock] = useState<number | null>(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [attachedCards, setAttachedCards] = useState<GiftCardByCode[]>([]);
  const [cardCodeInput, setCardCodeInput] = useState('');
  const [addingCard, setAddingCard] = useState(false);
  const [giftCardPaymentMethodId, setGiftCardPaymentMethodId] = useState<string | null>(null);

  // Confirmation dialog
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        const posData = await pointOfSaleService.getPointsOfSale();
        setPointsOfSale(posData);
        if (posData.length > 0) {
          setSelectedPosId(posData[0].id);
        }
        
        // If a productId was passed from image recognition, pre-select that product
        // Note: productId could be empty string if image recognition enrichment failed
        if (locationState?.productId && locationState.productId.trim() !== '') {
          try {
            const preSelectedProduct = await productService.getProduct(locationState.productId);
            
            if (preSelectedProduct) {
              skipNextSearchRef.current = true;
              setSelectedProduct(preSelectedProduct);
              setProductSearch(preSelectedProduct.sku);
              toast.success(`Producto "${preSelectedProduct.name}" seleccionado automáticamente`);
            } else {
              // Product truly not found or not accessible
              toast.warning('El producto seleccionado no está disponible en tus puntos de venta');
            }
          } catch (fetchError) {
            console.warn('Could not fetch product by ID:', fetchError);
            toast.warning('El producto seleccionado no está disponible en tus puntos de venta');
          }
        }
      } catch (error) {
        toast.error('Error al cargar datos');
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [locationState?.productId]);

  // Load payment methods when POS changes
  useEffect(() => {
    const loadPaymentMethods = async () => {
      if (!selectedPosId) return;
      
      let methods: PaymentMethod[] = [];
      
      try {
        // First try to get payment methods assigned to this point of sale
        const posPaymentMethods = await paymentMethodService.getPointOfSalePaymentMethods(selectedPosId);
        const gift = posPaymentMethods.find(
          (pm) => pm.paymentMethod?.code === GIFT_CARD_PAYMENT_CODE,
        );
        setGiftCardPaymentMethodId(gift?.paymentMethodId ?? null);
        // Filter to active assignments only and extract the payment method
        methods = posPaymentMethods
          .filter(
            (pm) =>
              pm.isActive &&
              pm.paymentMethod &&
              pm.paymentMethod.code !== GIFT_CARD_PAYMENT_CODE,
          )
          .map((pm) => pm.paymentMethod);
      } catch (error) {
        console.error('Error loading payment methods for POS:', error);
        setGiftCardPaymentMethodId(null);
      }
      
      // If no POS-specific methods, fall back to all payment methods
      if (methods.length === 0) {
        try {
          const allMethods = await paymentMethodService.getPaymentMethods();
          methods = allMethods.filter(
            (m) => m.isActive && m.code !== GIFT_CARD_PAYMENT_CODE,
          );
        } catch (fallbackError) {
          console.error('Error loading fallback payment methods:', fallbackError);
        }
      }
      
      setPaymentMethods(methods);
      if (methods.length > 0) {
        setSelectedPaymentMethodId(methods[0].id);
      } else {
        setSelectedPaymentMethodId('');
      }
    };
    loadPaymentMethods();
    setAttachedCards([]);
  }, [selectedPosId]);

  // Check stock when product and POS are selected
  useEffect(() => {
    const checkStock = async () => {
      if (!selectedProduct || !selectedPosId) {
        setAvailableStock(null);
        return;
      }
      
      setStockLoading(true);
      try {
        // Use getProductStockBreakdown to get stock across all POSes for this product
        // This is more reliable than getStock which returns paginated results
        const stockBreakdown = await inventoryService.getProductStockBreakdown(selectedProduct.id);
        
        if (stockBreakdown) {
          // Find stock for the selected POS
          const posStock = stockBreakdown.breakdown.find(
            (b) => b.pointOfSaleId === selectedPosId
          );
          setAvailableStock(posStock?.quantity ?? 0);
        } else {
          // Product has no inventory assignments
          setAvailableStock(0);
        }
      } catch (error) {
        console.error('Error checking stock:', error);
        setAvailableStock(null);
      } finally {
        setStockLoading(false);
      }
    };
    checkStock();
  }, [selectedProduct, selectedPosId]);

  // Product search using API with debounce
  useEffect(() => {
    if (skipNextSearchRef.current) {
      skipNextSearchRef.current = false;
      return;
    }

    const trimmedSearch = productSearch.trim();
    if (trimmedSearch.toUpperCase().startsWith('GC-')) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }

    if (!trimmedSearch || trimmedSearch.length < 2) {
      setSearchResults([]);
      return;
    }
    
    setSearchLoading(true);
    const timeoutId = setTimeout(async () => {
      try {
        const results = await productService.searchProducts(trimmedSearch);
        setSearchResults(results.slice(0, 10));
      } catch (error) {
        console.error('Error searching products:', error);
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300); // 300ms debounce

    return () => {
      clearTimeout(timeoutId);
      setSearchLoading(false);
    };
  }, [productSearch]);

  // Check if selected POS allows manual price edit
  const selectedPos = pointsOfSale.find((pos) => pos.id === selectedPosId);
  const allowManualPriceEdit = selectedPos?.allowManualPriceEdit ?? false;

  // Reset manual price when POS changes or when manual editing is disabled
  useEffect(() => {
    if (!allowManualPriceEdit) {
      setManualPrice('');
    }
  }, [allowManualPriceEdit, selectedPosId]);

  // Select product from search
  const handleSelectProduct = (product: Product) => {
    skipNextSearchRef.current = true;
    setSelectedProduct(product);
    setProductSearch(product.sku);
    setSearchResults([]);
    setQuantity(1);
    setManualPrice('');
  };

  // Calculate effective price and total
  const effectivePrice = allowManualPriceEdit && manualPrice !== ''
    ? parseFloat(manualPrice) || 0
    : selectedProduct?.price ?? 0;
  const total = effectivePrice * quantity;
  const coverageTotal = useMemo(
    () =>
      computeGiftCardCoverageTotal(
        [{ lineTotal: total }],
        attachedCards.map((c) => ({ code: c.code, spendableBalance: c.spendableBalance })),
      ),
    [total, attachedCards],
  );
  const cashDue = Math.max(0, Math.round((total - coverageTotal) * 100) / 100);
  const isPriceOverridden = allowManualPriceEdit && manualPrice !== '' && effectivePrice !== selectedProduct?.price;

  const addGiftCardByCode = async (rawCode: string) => {
    const code = rawCode.trim().toUpperCase();
    if (!code.startsWith('GC-')) {
      toast.error('El código debe empezar por GC-');
      return;
    }
    if (!selectedPosId) {
      toast.error('Selecciona un punto de venta');
      return;
    }
    setAddingCard(true);
    try {
      const card = await giftCardService.getByCode(code, selectedPosId);
      let duplicated = false;
      setAttachedCards((prev) => {
        if (prev.some((c) => c.code === code)) {
          duplicated = true;
          return prev;
        }
        return [...prev, card];
      });
      if (duplicated) {
        toast.error('Esta tarjeta ya está en la venta');
        return;
      }
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

  useEffect(() => {
    const codes = [
      ...(locationState?.giftCardCodes ?? []),
      ...(locationState?.giftCardCode ? [locationState.giftCardCode] : []),
    ];
    if (consumedScannerCodesRef.current || codes.length === 0 || !selectedPosId) return;
    consumedScannerCodesRef.current = true;

    const attach = async () => {
      for (const code of codes) {
        await addGiftCardByCode(code);
      }
      navigate(location.pathname, {
        replace: true,
        state: {
          productId: locationState?.productId,
          photoDataUrl: locationState?.photoDataUrl,
        },
      });
    };
    void attach();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- attach once when scanner navigates here
  }, [locationState?.giftCardCode, locationState?.giftCardCodes, selectedPosId]);

  // Validation
  const isFormValid = 
    selectedProduct && 
    selectedPosId && 
    selectedPaymentMethodId && 
    quantity > 0 &&
    effectivePrice > 0 &&
    availableStock !== null &&
    availableStock >= quantity;

  // Handle sale submission
  const handleSubmitSale = async () => {
    if (!selectedProduct || !isFormValid) return;

    const effectivePaymentMethodId =
      cashDue <= 0 && attachedCards.length > 0 && giftCardPaymentMethodId
        ? giftCardPaymentMethodId
        : selectedPaymentMethodId;

    if (cashDue <= 0 && attachedCards.length > 0 && !giftCardPaymentMethodId) {
      toast.error('Método de pago de tarjeta regalo no configurado en este POS');
      return;
    }

    setSubmitting(true);
    try {
      if (attachedCards.length > 0) {
        const idempotencyKey = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-manual-gc`;
        const result = await salesService.createBulkSales(
          {
            pointOfSaleId: selectedPosId,
            paymentMethodId: effectivePaymentMethodId,
            giftCardCodes: attachedCards.map((c) => c.code),
            notes: notes || undefined,
            lines: [
              {
                productId: selectedProduct.id,
                quantity,
                price: isPriceOverridden ? effectivePrice : undefined,
              },
            ],
          },
          idempotencyKey,
        );

        if (!result.success) {
          toast.error(result.errorMessage || 'Error al registrar la venta');
          return;
        }

        toast.success('Venta registrada exitosamente');
        result.warnings.forEach((w) => {
          toast.warning(`${w.productName}: ${w.message}`, { duration: 5000 });
        });
      } else {
        const result = await salesService.createSale({
          productId: selectedProduct.id,
          pointOfSaleId: selectedPosId,
          paymentMethodId: selectedPaymentMethodId,
          quantity,
          price: isPriceOverridden ? effectivePrice : undefined,
          notes: notes || undefined,
        });

        toast.success('Venta registrada exitosamente');

        if (result.isLowStock) {
          toast.warning(`⚠️ Stock bajo: quedan ${result.remainingStock} unidades`, {
            duration: 5000,
          });
        }
      }

      setConfirmDialogOpen(false);
      navigate(ROUTES.SALES.ROOT);
    } catch (error: unknown) {
      const errorMessage = (error as { message?: string }).message || 'Error al registrar la venta';
      toast.error(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddToCart = () => {
    if (!selectedProduct || !isFormValid) return;
    const selectedPos = pointsOfSale.find((pos) => pos.id === selectedPosId);
    const selectedPaymentMethod = paymentMethods.find(
      (m) => m.id === selectedPaymentMethodId,
    );
    if (!selectedPos || !selectedPaymentMethod) return;

    const added = addLine({
      productId: selectedProduct.id,
      productSku: selectedProduct.sku,
      productName: selectedProduct.name,
      productPrice: selectedProduct.price,
      quantity,
      price: isPriceOverridden ? effectivePrice : undefined,
      pointOfSaleId: selectedPosId,
      pointOfSaleName: selectedPos.name,
      paymentMethodId: selectedPaymentMethodId,
      paymentMethodName: selectedPaymentMethod.name,
    });

    if (added) {
      toast.success(`"${selectedProduct.name}" agregado al carrito`);
      const codes = attachedCards.map((c) => c.code);
      setSelectedProduct(null);
      setProductSearch('');
      setQuantity(1);
      setManualPrice('');
      setNotes('');
      setAvailableStock(null);
      setAttachedCards([]);
      if (codes.length > 0) {
        navigate(ROUTES.SALES.CART, { state: { giftCardCodes: codes } });
      }
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to={ROUTES.SALES.ROOT}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Nueva Venta</h1>
          <p className="text-muted-foreground">
            Registro manual de venta
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Product Selection */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Search className="h-5 w-5" />
              Seleccionar Producto
            </CardTitle>
            <CardDescription>
              Busca por SKU o nombre del producto
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Buscar producto (mín. 2 caracteres)..."
                className="pl-10"
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && productSearch.trim().toUpperCase().startsWith('GC-')) {
                    e.preventDefault();
                    addGiftCardByCode(productSearch);
                    skipNextSearchRef.current = true;
                    setProductSearch('');
                  }
                }}
              />
              
              {/* Search Results Dropdown */}
              {searchResults.length > 0 && (
                <div className="absolute z-10 mt-1 w-full rounded-md border bg-background shadow-lg">
                  {searchResults.map((product) => {
                    const primaryPhoto = product.photos?.find((p) => p.isPrimary) || product.photos?.[0];
                    const photoUrl = getImageUrl(primaryPhoto?.url);
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
                            className="h-10 w-10 rounded-md object-cover flex-shrink-0"
                          />
                        ) : (
                          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted flex-shrink-0">
                            <ShoppingCart className="h-5 w-5 text-muted-foreground" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">{product.name}</div>
                          <div className="text-sm text-muted-foreground">
                            SKU: {product.sku} | €{product.price.toFixed(2)}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Selected Product */}
            {selectedProduct && (
              <div className="rounded-lg border p-4">
                <div className="flex items-start gap-4">
                  {/* Product Photo */}
                  {(() => {
                    const primaryPhoto = selectedProduct.photos?.find((p) => p.isPrimary) || selectedProduct.photos?.[0];
                    const photoUrl = getImageUrl(primaryPhoto?.url);
                    return photoUrl ? (
                      <img 
                        src={photoUrl} 
                        alt={selectedProduct.name}
                        className="h-20 w-20 rounded-lg object-cover flex-shrink-0"
                      />
                    ) : (
                      <div className="flex h-20 w-20 items-center justify-center rounded-lg bg-muted flex-shrink-0">
                        <ShoppingCart className="h-8 w-8 text-muted-foreground" />
                      </div>
                    );
                  })()}
                  <div className="flex-1 flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold">{selectedProduct.name}</h3>
                      <p className="text-sm text-muted-foreground">SKU: {selectedProduct.sku}</p>
                      <p className="mt-1 text-lg font-bold text-primary">
                        €{selectedProduct.price.toFixed(2)}
                      </p>
                      {allowManualPriceEdit && (
                        <div className="mt-2 space-y-1">
                          <Label htmlFor="manual-price" className="text-sm">
                            Precio manual
                          </Label>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground">€</span>
                            <Input
                              id="manual-price"
                              type="number"
                              min={0.01}
                              step={0.01}
                              placeholder={selectedProduct.price.toFixed(2)}
                              value={manualPrice}
                              onChange={(e) => setManualPrice(e.target.value)}
                              className="w-32"
                            />
                          </div>
                          {isPriceOverridden && (
                            <p className="text-xs text-amber-600">
                              Precio oficial: €{selectedProduct.price.toFixed(2)}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                    <Badge variant={selectedProduct.isActive ? 'primary' : 'secondary'}>
                      {selectedProduct.isActive ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </div>
                </div>

                {/* Stock Info */}
                <div className="mt-4 flex items-center gap-2">
                  {stockLoading ? (
                    <Skeleton className="h-5 w-32" />
                  ) : availableStock !== null ? (
                    <>
                      <span className="text-sm text-muted-foreground">
                        Stock disponible:
                      </span>
                      <Badge variant={availableStock > 0 ? 'primary' : 'destructive'}>
                        {availableStock} unidades
                      </Badge>
                    </>
                  ) : null}
                </div>

                {/* Quantity Input */}
                <div className="mt-4 space-y-2">
                  <Label htmlFor="quantity">Cantidad</Label>
                  <Input
                    id="quantity"
                    type="number"
                    min={1}
                    max={availableStock || 1}
                    value={quantity}
                    onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                    className="w-24"
                  />
                  {availableStock !== null && quantity > availableStock && (
                    <p className="text-sm text-destructive">
                      Stock insuficiente
                    </p>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sale Details */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ShoppingCart className="h-5 w-5" />
              Detalles de Venta
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Point of Sale */}
            <div className="space-y-2">
              <Label>Punto de Venta</Label>
              <Select value={selectedPosId} onValueChange={setSelectedPosId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar..." />
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

            {/* Payment Method */}
            <div className="space-y-2">
              <Label>Método de Pago</Label>
              <Select 
                value={selectedPaymentMethodId} 
                onValueChange={setSelectedPaymentMethodId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar..." />
                </SelectTrigger>
                <SelectContent>
                  {paymentMethods.map((method) => (
                    <SelectItem key={method.id} value={method.id}>
                      {method.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="notes">Notas (opcional)</Label>
              <Textarea
                id="notes"
                placeholder="Añadir notas..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={500}
              />
            </div>

            <div className="space-y-2">
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

            {/* Total */}
            <div className="rounded-lg bg-muted p-4">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Precio unitario</span>
                <span>€{effectivePrice.toFixed(2)}</span>
              </div>
              {isPriceOverridden && (
                <div className="flex items-center justify-between text-xs text-amber-600">
                  <span>Precio oficial</span>
                  <span>€{(selectedProduct?.price || 0).toFixed(2)}</span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Cantidad</span>
                <span>×{quantity}</span>
              </div>
              {coverageTotal > 0 && (
                <div className="flex items-center justify-between text-sm text-emerald-700">
                  <span>Cobertura tarjeta</span>
                  <span>-{formatCurrency(coverageTotal)}</span>
                </div>
              )}
              <div className="mt-2 flex items-center justify-between border-t pt-2">
                <span className="font-semibold">Importe a cobrar</span>
                <span className="text-xl font-bold text-primary">
                  {formatCurrency(cashDue)}
                </span>
              </div>
            </div>

            {/* Submit Buttons */}
            <Button 
              className="w-full" 
              size="lg"
              disabled={!isFormValid}
              onClick={() => setConfirmDialogOpen(true)}
            >
              <ShoppingCart className="mr-2 h-5 w-5" />
              Registrar Venta
            </Button>

            <Button
              className="w-full"
              size="lg"
              variant="outline"
              disabled={!isFormValid}
              onClick={handleAddToCart}
            >
              <Plus className="mr-2 h-5 w-5" />
              Añadir al carrito
            </Button>

            {lineCount > 0 && (
              <Button
                className="w-full"
                size="sm"
                variant="secondary"
                asChild
              >
                <Link to={ROUTES.SALES.CART}>
                  <ShoppingCart className="mr-2 h-4 w-4" />
                  Ver carrito ({lineCount})
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Venta</DialogTitle>
            <DialogDescription>
              ¿Estás seguro de que deseas registrar esta venta?
            </DialogDescription>
          </DialogHeader>
          
          {selectedProduct && (
            <div className="space-y-4">
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertTitle>Resumen de Venta</AlertTitle>
                <AlertDescription>
                  <div className="mt-2 space-y-1 text-sm">
                    <p><strong>Producto:</strong> {selectedProduct.name}</p>
                    <p><strong>SKU:</strong> {selectedProduct.sku}</p>
                    <p><strong>Precio unitario:</strong> €{effectivePrice.toFixed(2)}</p>
                    {isPriceOverridden && (
                      <p className="text-amber-600">
                        <strong>Precio oficial:</strong> €{selectedProduct.price.toFixed(2)} (modificado)
                      </p>
                    )}
                    <p><strong>Cantidad:</strong> {quantity}</p>
                    <p><strong>Importe a cobrar:</strong> {formatCurrency(cashDue)}</p>
                  </div>
                </AlertDescription>
              </Alert>

              {availableStock !== null && availableStock - quantity <= 5 && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Advertencia de Stock</AlertTitle>
                  <AlertDescription>
                    Después de esta venta quedarán solo {availableStock - quantity} unidades.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setConfirmDialogOpen(false)}
              disabled={submitting}
            >
              Cancelar
            </Button>
            <Button 
              onClick={handleSubmitSale}
              disabled={submitting}
            >
              {submitting ? 'Procesando...' : 'Confirmar Venta'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ManualSalesPage;
