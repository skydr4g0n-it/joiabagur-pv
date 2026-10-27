/**
 * Printable gift card code panel (Code128 + QR)
 */
import { useEffect, useState } from 'react';
import { Barcode, Loader2, Printer, QrCode } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { generateCode128Svg, downloadSvg } from '@/lib/code128';
import { giftCardService } from '@/services/gift-card.service';
import { formatCurrency } from '@/lib/format-currency';

interface GiftCardCodesPanelProps {
  cardId: string;
  code: string;
  nominalAmount: number;
  showPrint?: boolean;
}

export function GiftCardCodesPanel({
  cardId,
  code,
  nominalAmount,
  showPrint = true,
}: GiftCardCodesPanelProps) {
  const [qrSvg, setQrSvg] = useState<string | null>(null);
  const [loadingQr, setLoadingQr] = useState(true);
  const code128Svg = generateCode128Svg(code);

  useEffect(() => {
    let cancelled = false;
    setLoadingQr(true);
    giftCardService
      .getQrCodeSvg(cardId)
      .then((svg) => {
        if (!cancelled) setQrSvg(svg);
      })
      .catch(() => {
        if (!cancelled) setQrSvg(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingQr(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cardId]);

  const handlePrint = () => {
    const printWindow = window.open('', '_blank', 'width=480,height=640');
    if (!printWindow) return;
    printWindow.document.write(`
      <html><head><title>Tarjeta ${code}</title>
      <style>body{font-family:Arial,sans-serif;text-align:center;padding:24px}
      h1{font-size:18px;margin-bottom:8px}.nominal{font-size:22px;font-weight:bold;margin:16px 0}
      svg{max-width:100%}</style></head><body>
      <h1>Tarjeta regalo</h1>
      <p class="nominal">${formatCurrency(nominalAmount)}</p>
      <p>${code}</p>
      ${code128Svg}
      ${qrSvg ?? ''}
      </body></html>`);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  return (
    <div id="gift-card-print-panel" className="grid gap-6 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Barcode className="size-5" />
            Código de barras
          </CardTitle>
          <CardDescription>Código {code}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          <div
            className="max-w-full overflow-hidden rounded border bg-white p-2"
            dangerouslySetInnerHTML={{ __html: code128Svg }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => downloadSvg(code128Svg, `barcode-${code}.svg`)}
          >
            Descargar código de barras
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <QrCode className="size-5" />
            Código QR
          </CardTitle>
          <CardDescription>Escanea en caja para aplicar la tarjeta</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          {loadingQr ? (
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
          ) : qrSvg ? (
            <>
              <div
                className="max-w-[200px] rounded border bg-white p-2"
                dangerouslySetInnerHTML={{ __html: qrSvg }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => downloadSvg(qrSvg, `qr-${code}.svg`)}
              >
                Descargar QR
              </Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No se pudo generar el QR</p>
          )}
        </CardContent>
      </Card>

      {showPrint && (
        <div className="md:col-span-2">
          <Button type="button" variant="secondary" onClick={handlePrint}>
            <Printer className="mr-2 size-4" />
            Imprimir tarjeta
          </Button>
        </div>
      )}
    </div>
  );
}
