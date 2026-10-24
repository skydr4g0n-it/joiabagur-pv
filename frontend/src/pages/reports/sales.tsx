import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  ColumnDef,
  createColumnHelper,
} from '@tanstack/react-table';
import { Download, Filter, Search, Info } from 'lucide-react';
import { toast } from 'sonner';

import { salesReportService } from '@/services/sales-report.service';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import { userService } from '@/services/user.service';
import { paymentMethodService } from '@/services/payment-method.service';
import type { SalesReportItem, SalesReportFilterRequest } from '@/types/sales-report.types';
import type { PointOfSale } from '@/types/point-of-sale.types';
import type { UserListItem } from '@/types/user.types';
import type { PaymentMethod } from '@/types/payment-method.types';

import { DataGrid, DataGridContainer } from '@/components/ui/data-grid';
import { DataGridTable } from '@/components/ui/data-grid-table';
import { DataGridPagination } from '@/components/ui/data-grid-pagination';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { formatCurrency, formatGrossWithNetInParentheses } from '@/lib/format-currency';
import type { SalesReportPosAggregate } from '@/types/sales-report.types';

const columnHelper = createColumnHelper<SalesReportItem>();
const fmt = formatCurrency;

function getDefaultDateRange() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return {
    startDate: start.toISOString().split('T')[0],
    endDate: end.toISOString().split('T')[0],
  };
}

export function SalesReportPage() {
  const [items, setItems] = useState<SalesReportItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [aggregates, setAggregates] = useState({
    totalSalesCount: 0,
    totalQuantity: 0,
    totalAmount: 0,
    totalCommission: 0,
    totalAmountNet: 0,
  });
  const [posAggregates, setPosAggregates] = useState<SalesReportPosAggregate[]>([]);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 20 });

  const defaultDates = useMemo(() => getDefaultDateRange(), []);
  const [filters, setFilters] = useState<SalesReportFilterRequest>({
    startDate: defaultDates.startDate,
    endDate: defaultDates.endDate,
  });
  const [search, setSearch] = useState('');

  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);

  useEffect(() => {
    const loadFilterData = async () => {
      try {
        const [pos, u, pm] = await Promise.all([
          pointOfSaleService.getPointsOfSale(),
          userService.getUsers(),
          paymentMethodService.getPaymentMethods(),
        ]);
        setPointsOfSale(pos);
        setUsers(u);
        setPaymentMethods(pm);
      } catch {
        toast.error('Error al cargar datos de filtros');
      }
    };
    loadFilterData();
  }, []);

  const fetchReport = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: SalesReportFilterRequest = {
        ...filters,
        search: search.length >= 2 ? search : undefined,
        page: pagination.pageIndex + 1,
        pageSize: pagination.pageSize,
      };
      const result = await salesReportService.getSalesReport(params);
      setItems(result.items);
      setTotalCount(result.totalCount);
      setTotalPages(result.totalPages);
      setAggregates({
        totalSalesCount: result.totalSalesCount,
        totalQuantity: result.totalQuantity,
        totalAmount: result.totalAmount,
        totalCommission: result.totalCommission ?? 0,
        totalAmountNet: result.totalAmountNet ?? result.totalAmount,
      });
      setPosAggregates(result.aggregatesByPointOfSale ?? []);
    } catch {
      toast.error('Error al cargar el reporte de ventas');
    } finally {
      setIsLoading(false);
    }
  }, [filters, search, pagination.pageIndex, pagination.pageSize]);

  useEffect(() => {
    if (filters.startDate && filters.endDate) {
      fetchReport();
    }
  }, [fetchReport]);

  const handleFilterChange = (key: keyof SalesReportFilterRequest, value: string | number | boolean | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value === 'all' ? undefined : value }));
    setPagination(prev => ({ ...prev, pageIndex: 0 }));
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const params: SalesReportFilterRequest = {
        ...filters,
        search: search.length >= 2 ? search : undefined,
      };
      const blob = await salesReportService.exportSalesReport(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const now = new Date();
      const ts = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}`;
      a.download = `reporte-ventas-${ts}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Reporte exportado correctamente');
    } catch {
      // 409 is handled by the service with a toast
    } finally {
      setIsExporting(false);
    }
  };

  const columns = useMemo<ColumnDef<SalesReportItem, unknown>[]>(
    () => [
      columnHelper.accessor('saleDate', {
        header: () => 'Fecha',
        cell: (info) => new Date(info.getValue() as string).toLocaleDateString('es-ES'),
        size: 100,
        meta: { skeleton: <Skeleton className="h-4 w-20" /> },
      }),
      columnHelper.accessor('saleDate', {
        id: 'saleTime',
        header: () => 'Hora',
        cell: (info) =>
          new Date(info.getValue() as string).toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit',
          }),
        size: 70,
        meta: { skeleton: <Skeleton className="h-4 w-14" /> },
      }),
      columnHelper.accessor('productSku', {
        header: () => 'SKU',
        cell: (info) => <span className="font-mono text-sm">{info.getValue()}</span>,
        size: 110,
        meta: { skeleton: <Skeleton className="h-4 w-20" /> },
      }),
      columnHelper.accessor('productName', {
        header: () => 'Producto',
        cell: (info) => info.getValue(),
        size: 180,
        meta: { skeleton: <Skeleton className="h-4 w-28" /> },
      }),
      columnHelper.accessor('collectionName', {
        header: () => 'Colección',
        cell: (info) => info.getValue() || '—',
        size: 120,
        meta: { skeleton: <Skeleton className="h-4 w-20" /> },
      }),
      columnHelper.accessor('pointOfSaleName', {
        header: () => 'POS',
        cell: (info) => info.getValue(),
        size: 120,
        meta: { skeleton: <Skeleton className="h-4 w-20" /> },
      }),
      columnHelper.accessor('quantity', {
        header: () => 'Cant.',
        cell: (info) => info.getValue(),
        size: 60,
        meta: { skeleton: <Skeleton className="h-4 w-10" /> },
      }),
      columnHelper.accessor('price', {
        header: () => 'Precio',
        cell: (info) => fmt(info.getValue() as number),
        size: 100,
        meta: { skeleton: <Skeleton className="h-4 w-16" /> },
      }),
      columnHelper.accessor('total', {
        header: () => 'Total',
        cell: (info) => <span className="font-medium">{fmt(info.getValue() as number)}</span>,
        size: 100,
        meta: { skeleton: <Skeleton className="h-4 w-16" /> },
      }),
      columnHelper.accessor('paymentMethodName', {
        header: () => 'Método pago',
        cell: (info) => info.getValue(),
        size: 110,
        meta: { skeleton: <Skeleton className="h-4 w-20" /> },
      }),
      columnHelper.accessor('operatorName', {
        header: () => 'Operador',
        cell: (info) => info.getValue(),
        size: 110,
        meta: { skeleton: <Skeleton className="h-4 w-20" /> },
      }),
      columnHelper.accessor('hasPhoto', {
        header: () => 'Foto',
        cell: (info) =>
          info.getValue() ? (
            <Badge variant="secondary" className="text-xs">Sí</Badge>
          ) : null,
        size: 60,
        meta: { skeleton: <Skeleton className="h-4 w-8" /> },
      }),
    ],
    []
  );

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: totalPages,
    state: { pagination },
    onPaginationChange: setPagination,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Reporte de Ventas</h1>
          <p className="text-muted-foreground">
            Análisis detallado de ventas con filtros avanzados y exportación a Excel
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Info className="size-3" />
            Máximo 10.000 filas. Si hay más resultados, ajuste los filtros.
          </p>
          <Button variant="outline" onClick={handleExport} disabled={isExporting}>
            <Download className="mr-2 size-4" />
            {isExporting ? 'Exportando...' : 'Exportar Excel'}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Filter className="h-5 w-5" />
            Filtros
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <Label>Fecha Inicio</Label>
              <Input
                type="date"
                value={filters.startDate || ''}
                onChange={(e) => handleFilterChange('startDate', e.target.value || undefined)}
              />
            </div>
            <div className="space-y-2">
              <Label>Fecha Fin</Label>
              <Input
                type="date"
                value={filters.endDate || ''}
                onChange={(e) => handleFilterChange('endDate', e.target.value || undefined)}
              />
            </div>

            <div className="space-y-2">
              <Label>Punto de Venta</Label>
              <Select
                value={filters.pointOfSaleId || 'all'}
                onValueChange={(v) => handleFilterChange('pointOfSaleId', v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {pointsOfSale.map((pos) => (
                    <SelectItem key={pos.id} value={pos.id}>{pos.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Operador</Label>
              <Select
                value={filters.userId || 'all'}
                onValueChange={(v) => handleFilterChange('userId', v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>{u.username}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Método de Pago</Label>
              <Select
                value={filters.paymentMethodId || 'all'}
                onValueChange={(v) => handleFilterChange('paymentMethodId', v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {paymentMethods.map((pm) => (
                    <SelectItem key={pm.id} value={pm.id}>{pm.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Importe mínimo</Label>
              <Input
                type="number"
                min={0}
                step="0.01"
                placeholder="Sin mínimo"
                value={filters.amountMin ?? ''}
                onChange={(e) =>
                  handleFilterChange('amountMin', e.target.value ? Number(e.target.value) : undefined)
                }
              />
            </div>

            <div className="space-y-2">
              <Label>Importe máximo</Label>
              <Input
                type="number"
                min={0}
                step="0.01"
                placeholder="Sin máximo"
                value={filters.amountMax ?? ''}
                onChange={(e) =>
                  handleFilterChange('amountMax', e.target.value ? Number(e.target.value) : undefined)
                }
              />
            </div>

            <div className="space-y-2">
              <Label>&nbsp;</Label>
              <div className="flex flex-col gap-2 pt-1">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={filters.hasPhoto === true}
                    onCheckedChange={(checked) =>
                      handleFilterChange('hasPhoto', checked === true ? true : undefined)
                    }
                  />
                  Solo con foto
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={filters.priceWasOverridden === true}
                    onCheckedChange={(checked) =>
                      handleFilterChange('priceWasOverridden', checked === true ? true : undefined)
                    }
                  />
                  Solo con precio modificado
                </label>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar por producto o SKU..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPagination((prev) => ({ ...prev, pageIndex: 0 }));
            }}
            className="pl-9"
          />
        </div>
      </div>

      {/* Global totals */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Total ventas (según filtros)</p>
          <p className="text-2xl font-bold">
            {isLoading ? <Skeleton className="h-8 w-20" /> : aggregates.totalSalesCount.toLocaleString('es-ES')}
          </p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Unidades totales</p>
          <p className="text-2xl font-bold">
            {isLoading ? <Skeleton className="h-8 w-20" /> : aggregates.totalQuantity.toLocaleString('es-ES')}
          </p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Importe total</p>
          <p className="text-2xl font-bold text-green-600">
            {isLoading ? (
              <Skeleton className="h-8 w-40" />
            ) : (
              formatGrossWithNetInParentheses(aggregates.totalAmount, aggregates.totalAmountNet)
            )}
          </p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Comisión total</p>
          <p className="text-2xl font-bold">
            {isLoading ? <Skeleton className="h-8 w-24" /> : fmt(aggregates.totalCommission)}
          </p>
        </div>
      </div>

      {posAggregates.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Desglose por punto de venta</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {posAggregates.map((row) => {
              const posName =
                pointsOfSale.find((p) => p.id === row.pointOfSaleId)?.name ?? row.pointOfSaleId;
              return (
                <div key={row.pointOfSaleId} className="flex flex-wrap justify-between gap-2 border-b pb-2 last:border-0">
                  <span className="font-medium">{posName}</span>
                  <span>
                    {formatGrossWithNetInParentheses(row.totalAmount, row.totalAmountNet)} · Comisión{' '}
                    {fmt(row.totalCommission)}
                  </span>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Data table */}
      <DataGridContainer>
        <DataGrid
          table={table}
          recordCount={totalCount}
          isLoading={isLoading}
          emptyMessage="No se encontraron ventas para los filtros seleccionados"
        >
          <DataGridTable />
          <DataGridPagination />
        </DataGrid>
      </DataGridContainer>
    </div>
  );
}

export default SalesReportPage;
