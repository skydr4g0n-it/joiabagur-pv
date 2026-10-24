import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { Plus, Trash2 } from 'lucide-react';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import type { PointOfSale } from '@/types/point-of-sale.types';
import type { CommissionTier, CommissionTierInput } from '@/types/commission-tier.types';

interface TierRow extends CommissionTierInput {
  key: string;
}

interface CommissionTiersDialogProps {
  open: boolean;
  onClose: () => void;
  pointOfSale: PointOfSale | null;
}

function toRow(tier: CommissionTier): TierRow {
  return {
    key: tier.id,
    minAmountInclusive: Math.round(tier.minAmountInclusive),
    maxAmountInclusive: tier.maxAmountInclusive != null ? Math.round(tier.maxAmountInclusive) : null,
    commissionPercent: tier.commissionPercent,
  };
}

function emptyRow(): TierRow {
  return {
    key: crypto.randomUUID(),
    minAmountInclusive: 0,
    maxAmountInclusive: null,
    commissionPercent: 0,
  };
}

export function CommissionTiersDialog({ open, onClose, pointOfSale }: CommissionTiersDialogProps) {
  const [rows, setRows] = useState<TierRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open && pointOfSale) {
      loadTiers();
    }
  }, [open, pointOfSale]);

  const loadTiers = async () => {
    if (!pointOfSale) return;
    setIsLoading(true);
    try {
      const tiers = await pointOfSaleService.getCommissionTiers(pointOfSale.id);
      setRows(tiers.length > 0 ? tiers.map(toRow) : [emptyRow()]);
    } catch {
      toast.error('Error al cargar las comisiones');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!pointOfSale) return;

    const payload: CommissionTierInput[] = rows.map((r) => ({
      minAmountInclusive: r.minAmountInclusive,
      maxAmountInclusive: r.maxAmountInclusive,
      commissionPercent: r.commissionPercent,
    }));

    setIsSaving(true);
    try {
      await pointOfSaleService.replaceCommissionTiers(pointOfSale.id, payload);
      toast.success('Comisiones guardadas correctamente');
      onClose();
    } catch (error: unknown) {
      const message =
        (error as { message?: string })?.message ?? 'Error al guardar las comisiones';
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Comisiones — {pointOfSale?.name}</DialogTitle>
          <DialogDescription>
            Tramos anuales en euros enteros. El primer tramo debe empezar en 0.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
            {rows.map((row, index) => (
              <div key={row.key} className="grid grid-cols-12 gap-2 items-end border rounded-md p-3">
                <div className="col-span-3 space-y-1">
                  <Label>Mín. €</Label>
                  <Input
                    type="number"
                    min={0}
                    step={1}
                    value={row.minAmountInclusive}
                    onChange={(e) => {
                      const value = Number(e.target.value);
                      setRows((prev) =>
                        prev.map((r, i) => (i === index ? { ...r, minAmountInclusive: value } : r))
                      );
                    }}
                  />
                </div>
                <div className="col-span-3 space-y-1">
                  <Label>Máx. €</Label>
                  <Input
                    type="number"
                    min={0}
                    step={1}
                    placeholder="Sin límite"
                    value={row.maxAmountInclusive ?? ''}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const value = raw === '' ? null : Number(raw);
                      setRows((prev) =>
                        prev.map((r, i) => (i === index ? { ...r, maxAmountInclusive: value } : r))
                      );
                    }}
                  />
                </div>
                <div className="col-span-3 space-y-1">
                  <Label>%</Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={row.commissionPercent}
                    onChange={(e) => {
                      const value = Number(e.target.value);
                      setRows((prev) =>
                        prev.map((r, i) => (i === index ? { ...r, commissionPercent: value } : r))
                      );
                    }}
                  />
                </div>
                <div className="col-span-3 flex justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
                    disabled={rows.length <= 1}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={() => setRows((p) => [...p, emptyRow()])}>
              <Plus className="mr-2 size-4" />
              Añadir tramo
            </Button>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={isSaving || isLoading}>
            {isSaving ? 'Guardando…' : 'Guardar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
