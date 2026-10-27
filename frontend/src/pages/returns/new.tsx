/**
 * New Return Page (EP5)
 * Form for registering a new product return
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Search, RotateCcw, Camera, X, AlertCircle, CheckCircle2, Package } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';

import { useAuth } from '@/providers/auth-provider';
import { returnsService } from '@/services/returns.service';
import { productService } from '@/services/product.service';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import { ROUTES } from '@/routing/routes';
import type { Product } from '@/types/product.types';
import type { PointOfSale } from '@/types/point-of-sale.types';
import type { EligibleSale, CreateReturnRequest, SaleAssociationRequest } from '@/types/returns.types';
import { ReturnCategory, ReturnCategoryLabels } from '@/types/returns.types';

interface SaleSelection {
  saleId: string;
  selected: boolean;
  quantity: number;
  maxQuantity: number;
  unitPrice: number;
}

export function NewReturnPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';

  // Form state
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);
  const [selectedPosId, setSelectedPosId] = useState<string>('');
  const [eligibleSales, setEligibleSales] = useState<EligibleSale[]>([]);
  const [loadingEligibleSales, setLoadingEligibleSales] = useState(false);
  const [saleSelections, setSaleSelections] = useState<SaleSelection[]>([]);
  const [category, setCategory] = useState<ReturnCategory>(ReturnCategory.Defectuoso);
  const [reason, setReason] = useState('');
  const [photoBase64, setPhotoBase64] = useState<string>('');
  const [photoFileName, setPhotoFileName] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Load points of sale on mount
  useEffect(() => {
    const loadPOS = async () => {
      try {
        const pos = await pointOfSaleService.getPointsOfSale();
        setPointsOfSale(pos.filter(p => p.isActive));
        // If operator, auto-select their assigned POS
        if (!isAdmin && pos.length === 1) {
          setSelectedPosId(pos[0].id);
        }
      } catch (error) {
        toast.error('Error al cargar puntos de venta');
        console.error(error);
      }
    };
    loadPOS();
  }, [isAdmin]);

  // Search products with debounce
  const handleSearch = useCallback(async (query: string) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    try {
      const results = await productService.searchProducts(query);
      // Convert ProductListItem[] to Product[] for compatibility
      setSearchResults(results.filter(p => p.isActive) as unknown as Product[]);
    } catch (error) {
      console.error('Error searching products:', error);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      handleSearch(searchQuery);
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery, handleSearch]);

  // Load eligible sales when product and POS are selected
  useEffect(() => {
    const loadEligibleSales = async () => {
      if (!selectedProduct || !selectedPosId) {
        setEligibleSales([]);
        setSaleSelections([]);
        return;
      }

      setLoadingEligibleSales(true);
      try {
        const response = await returnsService.getEligibleSales(selectedProduct.id, selectedPosId);
        setEligibleSales(response.eligibleSales);
        // Initialize selections
        setSaleSelections(response.eligibleSales.map(sale => ({
          saleId: sale.saleId,
          selected: false,
          quantity: 0,
          maxQuantity: sale.availableForReturn,
          unitPrice: sale.unitPrice,
        })));
      } catch (error: unknown) {
        const err = error as { response?: { status?: number } };
        if (err?.response?.status === 403) {
          toast.error('No tiene acceso a este punto de venta');
        } else {
          toast.error('Error al cargar ventas elegibles');
        }
        console.error(error);
      } finally {
        setLoadingEligibleSales(false);
      }
    };
    loadEligibleSales();
  }, [selectedProduct, selectedPosId]);

  // Handle product selection
  const handleSelectProduct = (product: Product) => {
    setSelectedProduct(product);
    setSearchQuery('');
    setSearchResults([]);
  };

  // Handle sale selection toggle
  const handleToggleSale = (saleId: string) => {
    setSaleSelections(prev => prev.map(s => {
      if (s.saleId === saleId) {
        const newSelected = !s.selected;
        return {
          ...s,
          selected: newSelected,
          quantity: newSelected ? Math.min(1, s.maxQuantity) : 0,
        };
      }
      return s;
    }));
  };

  // Handle quantity change for a sale
  const handleQuantityChange = (saleId: string, quantity: number) => {
    setSaleSelections(prev => prev.map(s => {
      if (s.saleId === saleId) {
        const validQuantity = Math.max(0, Math.min(quantity, s.maxQuantity));
        return {
          ...s,
          quantity: validQuantity,
          selected: validQuantity > 0,
        };
      }
      return s;
    }));
  };

  // Handle photo upload
  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      toast.error('Por favor seleccione una imagen');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast.error('La imagen no debe exceder 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1];
      setPhotoBase64(base64);
      setPhotoFileName(file.name);
    };
    reader.readAsDataURL(file);
  };

  // Calculate totals
  const totalQuantity = saleSelections.reduce((sum, s) => sum + (s.selected ? s.quantity : 0), 0);
  const totalValue = saleSelections.reduce((sum, s) => sum + (s.selected ? s.quantity * s.unitPrice : 0), 0);

  // Format currency
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  // Submit return
  const handleSubmit = async () => {
    if (!selectedProduct || !selectedPosId || totalQuantity === 0) {
      toast.error('Complete todos los campos requeridos');
      return;
    }

    const selectedSales = saleSelections.filter(s => s.selected && s.quantity > 0);
    if (selectedSales.length === 0) {
      toast.error('Seleccione al menos una venta');
      return;
    }

    setSubmitting(true);
    try {
      const request: CreateReturnRequest = {
        productId: selectedProduct.id,
        pointOfSaleId: selectedPosId,
        quantity: totalQuantity,
        category,
        reason: reason.trim() || undefined,
        saleAssociations: selectedSales.map(s => ({
          saleId: s.saleId,
          quantity: s.quantity,
        })),
        photoBase64: photoBase64 || undefined,
        photoFileName: photoFileName || undefined,
      };

      const result = await returnsService.createReturn(request);
      toast.success(`Devolución registrada. Nuevo stock: ${result.newStockQuantity}`);
      navigate(ROUTES.RETURNS.ROOT);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };
      toast.error(err?.response?.data?.message || 'Error al crear la devolución');
      console.error(error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to={ROUTES.RETURNS.ROOT}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Nueva Devolución</h1>
          <p className="text-muted-foreground">
            Registra una devolución de producto
          </p>
        </div>
      </div>

      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Las ventas cubiertas por tarjeta regalo y la emisión de tarjetas no admiten devolución
          clásica. Usa el cambio de producto desde el detalle de la tarjeta regalo (un solo uso por
          tarjeta; el valor nominal no se reactiva).
        </AlertDescription>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Form */}
        <div className="space-y-6 lg:col-span-2">
          {/* Step 1: Select Point of Sale */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">1. Punto de Venta</CardTitle>
              <CardDescription>
                Seleccione el punto de venta donde se realizó la venta original
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={selectedPosId} onValueChange={setSelectedPosId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccione un punto de venta" />
                </SelectTrigger>
                <SelectContent>
                  {pointsOfSale.map((pos) => (
                    <SelectItem key={pos.id} value={pos.id}>
                      {pos.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Step 2: Search and Select Product */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">2. Producto</CardTitle>
              <CardDescription>
                Busque el producto que se está devolviendo
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!selectedProduct ? (
                <>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      placeholder="Buscar por SKU o nombre..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9"
                    />
                  </div>

                  {searching && (
                    <div className="space-y-2">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-12 w-full" />
                      ))}
                    </div>
                  )}

                  {!searching && searchResults.length > 0 && (
                    <div className="space-y-2">
                      {searchResults.map((product) => (
                        <button
                          key={product.id}
                          onClick={() => handleSelectProduct(product)}
                          className="flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent"
                        >
                          <Package className="h-8 w-8 text-muted-foreground" />
                          <div>
                            <div className="font-medium">{product.name}</div>
                            <div className="text-sm text-muted-foreground">
                              SKU: {product.sku} | {formatCurrency(product.price)}
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="flex items-center justify-between rounded-lg border bg-accent/50 p-3">
                  <div className="flex items-center gap-3">
                    <Package className="h-8 w-8 text-primary" />
                    <div>
                      <div className="font-medium">{selectedProduct.name}</div>
                      <div className="text-sm text-muted-foreground">
                        SKU: {selectedProduct.sku} | {formatCurrency(selectedProduct.price)}
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      setSelectedProduct(null);
                      setEligibleSales([]);
                      setSaleSelections([]);
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Step 3: Select Sales */}
          {selectedProduct && selectedPosId && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">3. Ventas Elegibles</CardTitle>
                <CardDescription>
                  Seleccione las ventas de las cuales se está devolviendo el producto (últimos 30 días)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingEligibleSales ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-16 w-full" />
                    ))}
                  </div>
                ) : eligibleSales.length === 0 ? (
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      No hay ventas elegibles para devolución de este producto en este punto de venta.
                      Solo se permiten devoluciones de ventas de los últimos 30 días.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="space-y-3">
                    {eligibleSales.map((sale, index) => {
                      const selection = saleSelections[index];
                      return (
                        <div
                          key={sale.saleId}
                          className={`rounded-lg border p-4 transition-colors ${
                            selection?.selected ? 'border-primary bg-primary/5' : ''
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <Checkbox
                              checked={selection?.selected || false}
                              onCheckedChange={() => handleToggleSale(sale.saleId)}
                            />
                            <div className="flex-1">
                              <div className="flex items-center justify-between">
                                <div>
                                  <div className="font-medium">Venta del {formatDate(sale.saleDate)}</div>
                                  <div className="text-sm text-muted-foreground">
                                    {sale.paymentMethodName} | {formatCurrency(sale.unitPrice)}/unidad
                                  </div>
                                </div>
                                <Badge variant={sale.daysRemaining < 7 ? 'destructive' : 'secondary'}>
                                  {sale.daysRemaining} días restantes
                                </Badge>
                              </div>
                              <div className="mt-2 flex items-center gap-4 text-sm">
                                <span>Vendido: {sale.originalQuantity}</span>
                                <span>Ya devuelto: {sale.returnedQuantity}</span>
                                <span className="font-medium text-primary">
                                  Disponible: {sale.availableForReturn}
                                </span>
                              </div>
                              {selection?.selected && (
                                <div className="mt-3 flex items-center gap-2">
                                  <Label className="text-sm">Cantidad a devolver:</Label>
                                  <Input
                                    type="number"
                                    min={1}
                                    max={selection.maxQuantity}
                                    value={selection.quantity}
                                    onChange={(e) => handleQuantityChange(sale.saleId, parseInt(e.target.value) || 0)}
                                    className="w-20"
                                  />
                                  <span className="text-sm text-muted-foreground">
                                    / {selection.maxQuantity}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Step 4: Return Details */}
          {totalQuantity > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">4. Detalles de la Devolución</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Categoría de Devolución *</Label>
                  <Select
                    value={category.toString()}
                    onValueChange={(v) => setCategory(parseInt(v) as ReturnCategory)}
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

                <div className="space-y-2">
                  <Label>Motivo (opcional)</Label>
                  <Textarea
                    placeholder="Describe el motivo de la devolución..."
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    maxLength={500}
                    rows={3}
                  />
                  <p className="text-xs text-muted-foreground">{reason.length}/500 caracteres</p>
                </div>

                <div className="space-y-2">
                  <Label>Foto (opcional)</Label>
                  <div className="flex items-center gap-4">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handlePhotoChange}
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Camera className="mr-2 h-4 w-4" />
                      {photoBase64 ? 'Cambiar foto' : 'Subir foto'}
                    </Button>
                    {photoFileName && (
                      <div className="flex items-center gap-2 text-sm">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        {photoFileName}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={() => {
                            setPhotoBase64('');
                            setPhotoFileName('');
                          }}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Summary Sidebar */}
        <div className="lg:col-span-1">
          <Card className="sticky top-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RotateCcw className="h-5 w-5" />
                Resumen
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedProduct ? (
                <>
                  <div>
                    <div className="text-sm text-muted-foreground">Producto</div>
                    <div className="font-medium">{selectedProduct.name}</div>
                    <div className="text-sm text-muted-foreground">SKU: {selectedProduct.sku}</div>
                  </div>

                  {selectedPosId && (
                    <div>
                      <div className="text-sm text-muted-foreground">Punto de Venta</div>
                      <div className="font-medium">
                        {pointsOfSale.find(p => p.id === selectedPosId)?.name}
                      </div>
                    </div>
                  )}

                  <div className="border-t pt-4">
                    <div className="flex justify-between text-sm">
                      <span>Cantidad a devolver</span>
                      <span className="font-medium">{totalQuantity}</span>
                    </div>
                    <div className="mt-2 flex justify-between">
                      <span>Valor total</span>
                      <span className="text-lg font-bold text-primary">{formatCurrency(totalValue)}</span>
                    </div>
                  </div>

                  {totalQuantity > 0 && (
                    <div>
                      <div className="text-sm text-muted-foreground">Categoría</div>
                      <Badge>{ReturnCategoryLabels[category]}</Badge>
                    </div>
                  )}

                  <Button
                    className="w-full"
                    size="lg"
                    disabled={submitting || totalQuantity === 0}
                    onClick={handleSubmit}
                  >
                    {submitting ? (
                      'Procesando...'
                    ) : (
                      <>
                        <RotateCcw className="mr-2 h-4 w-4" />
                        Registrar Devolución
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <div className="text-center text-muted-foreground">
                  <Package className="mx-auto mb-2 h-12 w-12 opacity-50" />
                  <p>Seleccione un producto para comenzar</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default NewReturnPage;
