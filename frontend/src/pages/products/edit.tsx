/**
 * Product Edit Page - EP1 HU-EP1-003
 * Form for editing existing products with SKU immutability
 */

import { useState, useEffect } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowLeft, Loader2, CheckCircle2, Package, AlertCircle, QrCode, Barcode } from 'lucide-react';
import { productService } from '@/services/product.service';
import { Collection, Product } from '@/types/product.types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';
import { ROUTES } from '@/routing/routes';
import { ProductPhotoUpload } from './components/product-photo-upload';
import { ComponentAssignmentSection } from './components/component-assignment-section';
import { useAuth } from '@/providers/auth-provider';
import { generateCode128Svg, downloadSvg } from '@/lib/code128';
import apiClient from '@/services/api.service';

// Validation schema - Note: SKU is not included as it's immutable
const updateProductSchema = z.object({
  name: z
    .string()
    .min(1, 'El nombre es requerido')
    .max(200, 'El nombre no puede exceder 200 caracteres'),
  description: z
    .string()
    .max(1000, 'La descripción no puede exceder 1000 caracteres')
    .optional()
    .or(z.literal('')),
  price: z
    .string()
    .min(1, 'El precio es requerido')
    .refine((val) => {
      const num = parseFloat(val);
      return !isNaN(num) && num > 0;
    }, 'El precio debe ser mayor que 0'),
  collectionId: z.string().optional(),
  isActive: z.boolean(),
});

type UpdateProductFormValues = z.infer<typeof updateProductSchema>;

// No collection value for the select
const NO_COLLECTION_VALUE = '__none__';

export function ProductEditPage() {
  const navigate = useNavigate();
  const { productId } = useParams<{ productId: string }>();
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isLoadingCollections, setIsLoadingCollections] = useState(true);
  const [showSuccess, setShowSuccess] = useState(false);
  const [qrSvg, setQrSvg] = useState<string | null>(null);
  const [code128Svg, setCode128Svg] = useState<string | null>(null);
  const [isLoadingQr, setIsLoadingQr] = useState(false);

  const form = useForm<UpdateProductFormValues>({
    resolver: zodResolver(updateProductSchema),
    defaultValues: {
      name: '',
      description: '',
      price: '',
      collectionId: undefined,
      isActive: true,
    },
    mode: 'onTouched',
    reValidateMode: 'onChange',
  });

  // Load product data
  useEffect(() => {
    const loadProduct = async () => {
      if (!productId) {
        setLoadError('ID de producto no válido');
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        const data = await productService.getProduct(productId);
        setProduct(data);
        
        // Pre-populate form with product data
        form.reset({
          name: data.name,
          description: data.description || '',
          price: data.price.toString(),
          collectionId: data.collectionId || undefined,
          isActive: data.isActive,
        });
        
        setLoadError(null);
      } catch (error: any) {
        console.error('Failed to load product:', error);
        if (error.response?.status === 404) {
          setLoadError('Producto no encontrado');
        } else {
          setLoadError('Error al cargar el producto');
        }
        toast.error('No se pudo cargar el producto');
      } finally {
        setIsLoading(false);
      }
    };

    loadProduct();
  }, [productId, form]);

  // Load collections
  useEffect(() => {
    const loadCollections = async () => {
      try {
        const data = await productService.getCollections();
        setCollections(data);
      } catch (error) {
        console.error('Failed to load collections:', error);
        // Non-blocking error - collections are optional
      } finally {
        setIsLoadingCollections(false);
      }
    };

    loadCollections();
  }, []);

  useEffect(() => {
    if (!product?.sku?.trim()) {
      setQrSvg(null);
      setCode128Svg(null);
      return;
    }

    setIsLoadingQr(true);

    const loadQr = async () => {
      try {
        const response = await apiClient.get(`/products/${productId}/qrcode`, {
          responseType: 'text',
        });
        setQrSvg(response.data);
      } catch {
        setQrSvg(null);
      } finally {
        setIsLoadingQr(false);
      }
    };

    loadQr();
    setCode128Svg(generateCode128Svg(product.sku));
  }, [product?.sku, productId]);

  const onSubmit = async (values: UpdateProductFormValues) => {
    if (!productId || !product) {
      toast.error('Error: ID de producto no válido');
      return;
    }

    setIsSubmitting(true);

    try {
      const updateData = {
        name: values.name.trim(),
        description: values.description?.trim() || undefined,
        price: parseFloat(values.price),
        collectionId: values.collectionId && values.collectionId !== NO_COLLECTION_VALUE 
          ? values.collectionId 
          : undefined,
        isActive: values.isActive,
      };

      await productService.updateProduct(productId, updateData);

      setShowSuccess(true);
      toast.success('Producto actualizado exitosamente', {
        description: `${values.name} ha sido actualizado`,
      });

      // Navigate back after a short delay
      setTimeout(() => {
        navigate(ROUTES.PRODUCTS.ROOT);
      }, 1500);
    } catch (error: any) {
      console.error('Failed to update product:', error);
      
      if (error.response?.status === 404) {
        toast.error('Producto no encontrado');
        setTimeout(() => navigate(ROUTES.PRODUCTS.ROOT), 1000);
      } else if (error.response?.status === 400) {
        const errorMessage = error.response?.data?.error || 
                           error.response?.data?.errors?.join(', ') || 
                           'Datos inválidos';
        toast.error('Error de validación', {
          description: errorMessage,
        });
      } else {
        toast.error('Error al actualizar el producto', {
          description: 'Por favor, intenta nuevamente',
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Show loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="size-8 animate-spin mx-auto text-primary" />
          <p className="text-muted-foreground">Cargando producto...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (loadError || !product) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link to={ROUTES.PRODUCTS.ROOT}>
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Editar Producto</h1>
          </div>
        </div>

        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>
            {loadError || 'No se pudo cargar el producto'}
          </AlertDescription>
        </Alert>

        <Button variant="outline" asChild>
          <Link to={ROUTES.PRODUCTS.ROOT}>
            Volver a Productos
          </Link>
        </Button>
      </div>
    );
  }

  // Show success state
  if (showSuccess) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="mx-auto w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
                <CheckCircle2 className="size-6 text-green-600 dark:text-green-400" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-semibold">¡Producto Actualizado!</h3>
                <p className="text-sm text-muted-foreground">
                  El producto ha sido actualizado exitosamente
                </p>
              </div>
              <Button asChild className="w-full">
                <Link to={ROUTES.PRODUCTS.ROOT}>
                  Volver a Productos
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to={ROUTES.PRODUCTS.ROOT}>
            <ArrowLeft className="size-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Editar Producto</h1>
          <p className="text-muted-foreground">
            Actualiza la información del producto
          </p>
        </div>
      </div>

      {/* SKU Immutability Notice */}
      <Alert>
        <Package className="size-4" />
        <AlertDescription>
          El SKU <strong>{product.sku}</strong> no puede ser modificado. Si necesitas cambiar el SKU, 
          debes crear un nuevo producto.
        </AlertDescription>
      </Alert>

      {/* Form */}
      <Card>
        <CardHeader>
          <CardTitle>Información del Producto</CardTitle>
          <CardDescription>
            Edita los campos que desees actualizar
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              {/* SKU Field - Disabled */}
              <FormItem>
                <FormLabel>SKU</FormLabel>
                <FormControl>
                  <Input 
                    value={product.sku} 
                    disabled 
                    className="bg-muted cursor-not-allowed"
                  />
                </FormControl>
                <FormDescription>
                  El SKU es inmutable y no puede ser modificado
                </FormDescription>
              </FormItem>

              {/* Name Field */}
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nombre *</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Ej: Anillo de Oro 18k"
                        {...field}
                        disabled={isSubmitting}
                      />
                    </FormControl>
                    <FormDescription>
                      Nombre descriptivo del producto
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Description Field */}
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Descripción</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Descripción detallada del producto..."
                        className="resize-none"
                        rows={4}
                        {...field}
                        disabled={isSubmitting}
                      />
                    </FormControl>
                    <FormDescription>
                      Información adicional sobre el producto (opcional)
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Price Field */}
              <FormField
                control={form.control}
                name="price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Precio (€) *</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="0.00"
                        {...field}
                        disabled={isSubmitting}
                      />
                    </FormControl>
                    <FormDescription>
                      Precio de venta del producto
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Collection Field */}
              <FormField
                control={form.control}
                name="collectionId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Colección</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value || NO_COLLECTION_VALUE}
                      disabled={isSubmitting || isLoadingCollections}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona una colección" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={NO_COLLECTION_VALUE}>
                          Sin colección
                        </SelectItem>
                        {collections.map((collection) => (
                          <SelectItem key={collection.id} value={collection.id}>
                            {collection.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Agrupa el producto en una colección (opcional)
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Active Status Field */}
              <FormField
                control={form.control}
                name="isActive"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">
                        Estado del Producto
                      </FormLabel>
                      <FormDescription>
                        {field.value ? 'Producto activo y visible' : 'Producto inactivo y oculto'}
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Button
                        type="button"
                        variant={field.value ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => field.onChange(!field.value)}
                        disabled={isSubmitting}
                      >
                        {field.value ? 'Activo' : 'Inactivo'}
                      </Button>
                    </FormControl>
                  </FormItem>
                )}
              />

              {/* Form Actions */}
              <div className="flex gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate(ROUTES.PRODUCTS.ROOT)}
                  disabled={isSubmitting}
                  className="flex-1"
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting || !form.formState.isDirty}
                  className="flex-1"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Actualizando...
                    </>
                  ) : (
                    'Actualizar Producto'
                  )}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>

      {/* Component Assignment Section - Admin only */}
      {isAdmin && productId && (
        <ComponentAssignmentSection
          productId={productId}
          productPrice={parseFloat(form.watch('price') || '0')}
          onAdjustPrice={(suggestedPrice) => {
            form.setValue('price', suggestedPrice.toFixed(2), { shouldDirty: true });
          }}
        />
      )}

      {/* QR Code and Barcode Sections */}
      {product.sku?.trim() ? (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <QrCode className="size-5" />
                Código QR
              </CardTitle>
              <CardDescription>
                Escanea este código QR para identificar el producto
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-4">
              {isLoadingQr ? (
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
              ) : qrSvg ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const blob = new Blob([qrSvg], { type: 'image/svg+xml' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `qr-${product.sku}.svg`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  }}
                >
                  Descargar QR
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">No se pudo generar el QR</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Barcode className="size-5" />
                Código de Barras
              </CardTitle>
              <CardDescription>
                Código Code128 generado desde el SKU
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-4">
              {code128Svg ? (
                <>
                  <div
                    className="w-full max-w-[250px]"
                    dangerouslySetInnerHTML={{ __html: code128Svg }}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => downloadSvg(code128Svg, `barcode-${product.sku}.svg`)}
                  >
                    Descargar código de barras
                  </Button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No se pudo generar el código de barras</p>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">
              <p>Genere un SKU para ver los códigos</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Photo Upload Section */}
      <ProductPhotoUpload
        productId={productId}
        productSku={product.sku}
        photos={product.photos || []}
        onPhotosChange={() => {
          // Reload product to get updated photos
          productService.getProduct(productId).then((data) => {
            setProduct(data);
          });
        }}
      />
    </div>
  );
}

export default ProductEditPage;

