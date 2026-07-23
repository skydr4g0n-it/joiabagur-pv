import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { CameraOff, Flashlight, FlashlightOff, X, ScanLine, Search } from 'lucide-react';
import { toast } from 'sonner';
import { BarcodeScanningService } from '@/services/barcode-scanning.service';
import { productService } from '@/services/product.service';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ROUTES } from '@/routing/routes';

type ScanState = 'initializing' | 'scanning' | 'error' | 'success';

export function ScanningPage() {
  const navigate = useNavigate();
  const [scanState, setScanState] = useState<ScanState>('initializing');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [flashOn, setFlashOn] = useState(false);
  const [manualSku, setManualSku] = useState('');
  const [isSubmittingManual, setIsSubmittingManual] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const serviceRef = useRef<BarcodeScanningService | null>(null);

  const isCompatible = useCallback(() => {
    return !!(navigator.mediaDevices?.getUserMedia);
  }, []);

  useEffect(() => {
    if (!isCompatible()) {
      setScanState('error');
      setErrorMessage('Permiso de cámara denegado');
      return;
    }

    const service = new BarcodeScanningService();
    serviceRef.current = service;

    const initCamera = async () => {
      try {
        if (!videoRef.current) return;
        await service.startCamera(videoRef.current);
        setScanState('scanning');

        if (canvasRef.current) {
          service.continuousScan(videoRef.current, canvasRef.current, handleDecode);
        }
      } catch {
        setScanState('error');
        setErrorMessage('No se pudo acceder a la cámara. Verifica los permisos.');
      }
    };

    initCamera();

    return () => {
      service.stopCamera();
      serviceRef.current = null;
    };
  }, []);

  const handleDecode = useCallback(
    async (result: { value: string; type: string }) => {
      const sku = result.value.trim();

      try {
        const products = await productService.searchProducts(sku);
        const exactMatch = products.find(
          (p: any) => p.sku?.toUpperCase() === sku.toUpperCase(),
        );

        if (!exactMatch) {
          toast.error('Producto no encontrado', {
            description: `SKU: ${sku}`,
          });
          return;
        }

        setScanState('success');
        toast.success('Producto seleccionado', {
          description: `${exactMatch.name}`,
        });

        serviceRef.current?.stopContinuousScan();
        navigate(ROUTES.SALES.NEW, {
          state: { selectedProduct: exactMatch },
        });
      } catch {
        toast.error('Producto no encontrado', {
          description: `SKU: ${sku}`,
        });
      }
    },
    [navigate],
  );

  const handleToggleFlash = async () => {
    if (!serviceRef.current || !videoRef.current) return;
    const result = await serviceRef.current.toggleFlash(videoRef.current);
    setFlashOn(result);
  };

  const handleManualSubmit = async () => {
    if (!manualSku.trim()) return;
    setIsSubmittingManual(true);

    try {
      const products = await productService.searchProducts(manualSku.trim());
      const exactMatch = products.find(
        (p: any) => p.sku?.toUpperCase() === manualSku.trim().toUpperCase(),
      );

      if (!exactMatch) {
        toast.error('Producto no encontrado', {
          description: `SKU: ${manualSku}`,
        });
        setIsSubmittingManual(false);
        return;
      }

      setScanState('success');
      toast.success('Producto seleccionado', {
        description: `${exactMatch.name}`,
      });

      navigate(ROUTES.SALES.NEW, {
        state: { selectedProduct: exactMatch },
      });
    } catch {
      toast.error('Error al buscar producto');
      setIsSubmittingManual(false);
    }
  };

  const handleClose = () => {
    serviceRef.current?.stopCamera();
    navigate(ROUTES.SALES.ROOT);
  };

  const handleRetry = () => {
    setScanState('initializing');
    setErrorMessage('');

    const service = new BarcodeScanningService();
    serviceRef.current = service;

    const initCamera = async () => {
      try {
        if (!videoRef.current) return;
        await service.startCamera(videoRef.current);
        setScanState('scanning');

        if (canvasRef.current) {
          service.continuousScan(videoRef.current, canvasRef.current, handleDecode);
        }
      } catch {
        setScanState('error');
        setErrorMessage('No se pudo acceder a la cámara. Verifica los permisos.');
      }
    };

    initCamera();
  };

  return (
    <div className="relative flex h-[calc(100vh-8rem)] flex-col">
      <canvas ref={canvasRef} className="hidden" />
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={scanState === 'scanning' ? 'absolute inset-0 size-full object-cover' : 'hidden'}
      />

      {scanState === 'initializing' && (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center space-y-4">
            <div className="size-8 animate-pulse rounded-full bg-primary/20 mx-auto" />
            <p className="text-muted-foreground">Iniciando cámara...</p>
          </div>
        </div>
      )}

      {scanState === 'error' && (
        <div className="flex flex-1 items-center justify-center p-4">
          <Card className="w-full max-w-md">
            <CardContent className="pt-6 space-y-4">
              <div className="flex flex-col items-center gap-4 text-center">
                <CameraOff className="size-12 text-destructive" />
                <div>
                  <h3 className="font-semibold text-lg">Error de cámara</h3>
                  <p className="text-sm text-muted-foreground mt-1">{errorMessage}</p>
                </div>
              </div>
              <Button className="w-full" onClick={handleRetry}>
                Reintentar
              </Button>
              <Button variant="outline" className="w-full" onClick={() => navigate(ROUTES.SALES.NEW)}>
                Entrada manual
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {scanState === 'scanning' && (
        <>
          <div className="relative flex-1 overflow-hidden bg-black">
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="relative size-64">
                <div className="absolute left-0 top-0 size-8 border-l-2 border-t-2 border-white" />
                <div className="absolute right-0 top-0 size-8 border-r-2 border-t-2 border-white" />
                <div className="absolute bottom-0 left-0 size-8 border-b-2 border-l-2 border-white" />
                <div className="absolute bottom-0 right-0 size-8 border-b-2 border-r-2 border-white" />
              </div>
            </div>

            <div className="absolute bottom-24 left-0 right-0 text-center">
              <p className="text-white/80 text-sm bg-black/50 inline-block px-4 py-1 rounded-full">
                Enfoca el código de barras o QR en el recuadro
              </p>
            </div>
          </div>

          <div className="flex items-center justify-center gap-4 p-4 bg-background border-t">
            <Button
              variant="outline"
              size="icon"
              onClick={handleToggleFlash}
              title={flashOn ? 'Apagar flash' : 'Encender flash'}
            >
              {flashOn ? <FlashlightOff className="size-5" /> : <Flashlight className="size-5" />}
            </Button>

            <Button variant="outline" size="icon" onClick={handleClose} title="Cerrar">
              <X className="size-5" />
            </Button>
          </div>
        </>
      )}

      {scanState !== 'initializing' && (
        <div className="p-4 border-t bg-background">
          <div className="flex gap-2">
            <Input
              placeholder="Ingresa SKU manualmente..."
              value={manualSku}
              onChange={(e) => setManualSku(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleManualSubmit();
              }}
              disabled={isSubmittingManual || scanState === 'success'}
            />
            <Button
              onClick={handleManualSubmit}
              disabled={!manualSku.trim() || isSubmittingManual || scanState === 'success'}
            >
              <Search className="mr-2 size-4" />
              Buscar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ScanningPage;
