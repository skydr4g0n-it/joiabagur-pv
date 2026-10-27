/**
 * Gift card issuance form
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';

import { useAuth } from '@/providers/auth-provider';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import { paymentMethodService } from '@/services/payment-method.service';
import { giftCardService } from '@/services/gift-card.service';
import { ROUTES } from '@/routing/routes';
import { formatCurrency } from '@/lib/format-currency';
import {
  GIFT_CARD_PRESET_AMOUNTS,
  type GiftCardDetail,
} from '@/types/gift-card.types';
import type { PointOfSale } from '@/types/point-of-sale.types';
import type { PaymentMethod } from '@/types/payment-method.types';
import { GiftCardCodesPanel } from './components/gift-card-codes-panel';

const GIFT_CARD_PAYMENT_CODE = 'GIFT_CARD';

function minExpiryDateUtc(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

const issueSchema = z.object({
  pointOfSaleId: z.string().min(1, 'Selecciona un punto de venta'),
  paymentMethodId: z.string().min(1, 'Selecciona un método de pago'),
  amountMode: z.enum(['preset', 'custom']),
  presetAmount: z.string().optional(),
  customAmount: z.string().optional(),
  expiryDate: z.string().min(1, 'La fecha de caducidad es obligatoria'),
  holderName: z.string().max(100, 'Máximo 100 caracteres').optional(),
});

type IssueFormValues = z.infer<typeof issueSchema>;

export function GiftCardIssuePage() {
  useAuth();
  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [loadingPos, setLoadingPos] = useState(true);
  const [issuedCard, setIssuedCard] = useState<GiftCardDetail | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<IssueFormValues>({
    resolver: zodResolver(issueSchema),
    defaultValues: {
      pointOfSaleId: '',
      paymentMethodId: '',
      amountMode: 'preset',
      presetAmount: '100',
      customAmount: '',
      expiryDate: minExpiryDateUtc(),
      holderName: '',
    },
  });

  const selectedPosId = form.watch('pointOfSaleId');

  const loadPaymentMethodsForPos = async (posId: string) => {
    const assignments = await paymentMethodService.getPointOfSalePaymentMethods(posId);
    const methods = assignments
      .filter((a) => a.isActive && a.paymentMethod?.isActive)
      .map((a) => a.paymentMethod)
      .filter((m) => m.code !== GIFT_CARD_PAYMENT_CODE);
    setPaymentMethods(methods);
    return methods;
  };

  useEffect(() => {
    const load = async () => {
      try {
        const pos = await pointOfSaleService.getPointsOfSale();
        const activePos = pos.filter((p) => p.isActive);
        setPointsOfSale(activePos);
        if (activePos.length > 0) {
          const methods = await loadPaymentMethodsForPos(activePos[0].id);
          form.reset({
            ...form.getValues(),
            pointOfSaleId: activePos[0].id,
            paymentMethodId: methods[0]?.id ?? '',
          });
        }
      } catch {
        toast.error('Error al cargar puntos de venta');
      } finally {
        setLoadingPos(false);
      }
    };
    load();
  }, [form]);

  useEffect(() => {
    const loadMethods = async () => {
      if (!selectedPosId) return;
      try {
        const methods = await loadPaymentMethodsForPos(selectedPosId);
        const current = form.getValues('paymentMethodId');
        if (!methods.some((m) => m.id === current)) {
          form.setValue('paymentMethodId', methods[0]?.id ?? '');
        }
      } catch {
        toast.error('Error al cargar métodos de pago');
      }
    };
    if (!loadingPos) {
      loadMethods();
    }
  }, [selectedPosId, form, loadingPos]);

  const resolveNominal = (values: IssueFormValues): number | null => {
    if (values.amountMode === 'preset') {
      const preset = parseFloat(values.presetAmount ?? '');
      if (GIFT_CARD_PRESET_AMOUNTS.includes(preset as (typeof GIFT_CARD_PRESET_AMOUNTS)[number])) {
        return preset;
      }
      return null;
    }
    const custom = parseFloat(values.customAmount ?? '');
    if (Number.isNaN(custom) || custom < 0.01 || custom > 99999.99) return null;
    return Math.round(custom * 100) / 100;
  };

  const onSubmit = async (values: IssueFormValues) => {
    const nominal = resolveNominal(values);
    if (nominal === null) {
      toast.error('Importe no válido');
      return;
    }

    setSubmitting(true);
    try {
      const result = await giftCardService.issue(
        {
          pointOfSaleId: values.pointOfSaleId,
          paymentMethodId: values.paymentMethodId,
          nominalAmount: nominal,
          expiryDate: values.expiryDate,
          holderName: values.holderName?.trim() || undefined,
        },
        globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-gift-card-issue`,
      );

      if (result.isForbidden) {
        toast.error('No tienes permiso para emitir en este punto de venta');
        return;
      }
      if (!result.success || !result.card) {
        toast.error(result.errorMessage || 'No se pudo emitir la tarjeta');
        return;
      }

      setIssuedCard(result.card);
      toast.success('Tarjeta emitida correctamente');
    } catch (error: unknown) {
      const message =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Error al emitir la tarjeta';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const amountMode = form.watch('amountMode');

  const presetOptions = useMemo(() => GIFT_CARD_PRESET_AMOUNTS, []);

  if (issuedCard) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" asChild>
            <Link to={ROUTES.GIFT_CARDS.ROOT}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Volver al listado
            </Link>
          </Button>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Tarjeta emitida</CardTitle>
            <CardDescription>
              Nominal {formatCurrency(issuedCard.nominalAmount)} · Código{' '}
              <span className="font-mono">{issuedCard.code}</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <GiftCardCodesPanel
              cardId={issuedCard.id}
              code={issuedCard.code}
              nominalAmount={issuedCard.nominalAmount}
            />
            <Button asChild>
              <Link to={ROUTES.GIFT_CARDS.DETAIL(issuedCard.id)}>Ver detalle</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to={ROUTES.GIFT_CARDS.ROOT}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Volver
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Emitir tarjeta regalo</h1>
          <p className="text-muted-foreground">Venta del producto sistema con el importe elegido</p>
        </div>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Datos de emisión</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingPos ? (
            <Loader2 className="mx-auto size-8 animate-spin" />
          ) : (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="pointOfSaleId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Punto de venta</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Seleccionar" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {pointsOfSale.map((pos) => (
                            <SelectItem key={pos.id} value={pos.id}>
                              {pos.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="paymentMethodId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Método de pago</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Seleccionar" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {paymentMethods.map((pm) => (
                            <SelectItem key={pm.id} value={pm.id}>
                              {pm.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="amountMode"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Importe</FormLabel>
                      <FormControl>
                        <RadioGroup
                          onValueChange={field.onChange}
                          value={field.value}
                          className="flex flex-col gap-3"
                        >
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="preset" id="preset" />
                            <Label htmlFor="preset">Importes predefinidos</Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="custom" id="custom" />
                            <Label htmlFor="custom">Importe libre</Label>
                          </div>
                        </RadioGroup>
                      </FormControl>
                    </FormItem>
                  )}
                />

                {amountMode === 'preset' && (
                  <FormField
                    control={form.control}
                    name="presetAmount"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Importe predefinido</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {presetOptions.map((amount) => (
                              <SelectItem key={amount} value={String(amount)}>
                                {formatCurrency(amount)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}

                {amountMode === 'custom' && (
                  <FormField
                    control={form.control}
                    name="customAmount"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Importe libre (€)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            step="0.01"
                            min="0.01"
                            max="99999.99"
                            placeholder="0,00"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}

                <FormField
                  control={form.control}
                  name="expiryDate"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Fecha de caducidad (UTC)</FormLabel>
                      <FormControl>
                        <Input type="date" min={minExpiryDateUtc()} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="holderName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Titular (opcional)</FormLabel>
                      <FormControl>
                        <Input placeholder="Nombre del titular" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button type="submit" disabled={submitting} className="w-full">
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Emitiendo...
                    </>
                  ) : (
                    'Emitir tarjeta'
                  )}
                </Button>
              </form>
            </Form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default GiftCardIssuePage;
