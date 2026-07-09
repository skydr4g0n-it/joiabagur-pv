import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  type ColumnDef,
  createColumnHelper,
} from '@tanstack/react-table';
import { Download, Filter, Info } from 'lucide-react';
import { toast } from 'sonner';

import { inventoryMovementReportService } from '@/services/inventory-movement-report.service';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import type {
  InventoryMovementDetailRow,
  InventoryMovementOutputModel,
  InventoryMovementReportFilter,
  InventoryMovementReportRow,
} from '@/types/inventory-movement-report.types';
import type { PointOfSale } from '@/types/point-of-sale.types';

import { DataGrid, DataGridContainer } from '@/components/ui/data-grid';
import { DataGridTable } from '@/components/ui/data-grid-table';
import { DataGridPagination } from '@/components/ui/data-grid-pagination';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Alert,
  AlertDescription,
} from '@/components/ui/alert';

const columnHelper = createColumnHelper<InventoryMovementReportRow>();
const fmtNum = (v: number) => v.toLocaleString('es-ES');
const fmtDate = (v: string) => new Date(v).toLocaleString('es-ES');

type SortState = { sortBy?: string; sortDirection?: string };

export function InventoryMovementSummaryPage() {
  const [items, setItems] = useState<InventoryMovementReportRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 20 });
  const [hasSearched, setHasSearched] = useState(false);

  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [pointOfSaleId, setPointOfSaleId] = useState<string | undefined>();
  const [outputModel, setOutputModel] = useState<InventoryMovementOutputModel>('summary');
  const [productSearch, setProductSearch] = useState('');
  const [sort, setSort] = useState<SortState>({});

  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const pos = await pointOfSaleService.getPointsOfSale();
        setPointsOfSale(pos);
      } catch {
        toast.error('Error al cargar puntos de venta');
      }
    };
    load();
  }, []);

  const canSearch = startDate.length > 0 && endDate.length > 0;

  const fetchReport = useCallback(async () => {
    if (!canSearch) return;
    setIsLoading(true);
    try {
      const params: InventoryMovementReportFilter = {
        outputModel,
        startDate,
        endDate,
        pointOfSaleId,
        productSearch: productSearch.trim() || undefined,
        page: pagination.pageIndex + 1,
        pageSize: pagination.pageSize,
        ...(outputModel === 'summary' ? sort : {}),
      };
      const result = await inventoryMovementReportService.getReport(params);
      setItems(result.items);
      setTotalCount(result.totalCount);
      setTotalPages(result.totalPages);
      setHasSearched(true);
    } catch {
      toast.error('Error al cargar el reporte de movimientos de inventario');
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate, pointOfSaleId, outputModel, productSearch, pagination.pageIndex, pagination.pageSize, sort, canSearch]);

  useEffect(() => {
    if (hasSearched) {
      fetchReport();
    }
  }, [pagination.pageIndex, pagination.pageSize, sort, outputModel]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = () => {
    setPagination(prev => ({ ...prev, pageIndex: 0 }));
    if (outputModel === 'detail') setSort({});
    setHasSearched(true);
    fetchReport();
  };

  const handleOutputModelChange = (value: InventoryMovementOutputModel) => {
    setOutputModel(value);
    setPagination(prev => ({ ...prev, pageIndex: 0 }));
    setSort({});
  };

  const handleSort = (columnId: string) => {
    setSort(prev => {
      if (prev.sortBy === columnId) {
        if (prev.sortDirection === 'asc') return { sortBy: columnId, sortDirection: 'desc' };
        if (prev.sortDirection === 'desc') return {};
        return { sortBy: columnId, sortDirection: 'asc' };
      }
      return { sortBy: columnId, sortDirection: 'asc' };
    });
    setPagination(prev => ({ ...prev, pageIndex: 0 }));
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const params: InventoryMovementReportFilter = {
        outputModel,
        startDate,
        endDate,
        pointOfSaleId,
        productSearch: productSearch.trim() || undefined,
        ...(outputModel === 'summary' ? sort : {}),
      };
      const blob = await inventoryMovementReportService.exportReport(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const now = new Date();
      const ts = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}-${String(now.getMinutes()).padStart(2, '0')}`;
      a.download = `reporte-movimientos-inventario-${ts}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Reporte exportado correctamente');
    } catch {
      // 409 is handled by the service with a toast
    } finally {
      setIsExporting(false);
    }
  };

  const sortIndicator = (col: string) => {
    if (sort.sortBy !== col) return '';
    return sort.sortDirection === 'asc' ? ' ↑' : ' ↓';
  };

  const columns = useMemo<ColumnDef<InventoryMovementReportRow, unknown>[]>(
    () => outputModel === 'summary' ? [
      columnHelper.accessor('productName', {
        header: () => 'Producto',
        cell: (info) => info.getValue(),
        size: 250,
      }),
      columnHelper.accessor('productSku', {
        header: () => 'SKU',
        cell: (info) => <span className="font-mono text-sm">{info.getValue()}</span>,
        size: 130,
      }),
      columnHelper.accessor('additions', {
        header: () => (
          <button type="button" className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('additions')}>
            Adiciones{sortIndicator('additions')}
          </button>
        ),
        cell: (info) => <span className="text-green-600 font-medium">{fmtNum(info.getValue() as number)}</span>,
        size: 120,
      }),
      columnHelper.accessor('subtractions', {
        header: () => (
          <button type="button" className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('subtractions')}>
            Sustracciones{sortIndicator('subtractions')}
          </button>
        ),
        cell: (info) => <span className="text-red-600 font-medium">{fmtNum(info.getValue() as number)}</span>,
        size: 130,
      }),
      columnHelper.accessor('difference', {
        header: () => (
          <button type="button" className="flex items-center gap-1 hover:text-foreground" onClick={() => handleSort('difference')}>
            Diferencia{sortIndicator('difference')}
          </button>
        ),
        cell: (info) => {
          const val = info.getValue() as number;
          const color = val > 0 ? 'text-green-600' : val < 0 ? 'text-red-600' : '';
          return <span className={`font-medium ${color}`}>{fmtNum(val)}</span>;
        },
        size: 120,
      }),
    ] : [
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).movementDate, {
        id: 'movementDate',
        header: () => 'Fecha',
        cell: (info) => fmtDate(info.getValue() as string),
        size: 160,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).movementTypeName, {
        id: 'movementTypeName',
        header: () => 'Tipo',
        cell: (info) => info.getValue(),
        size: 110,
      }),
      columnHelper.accessor('productName', {
        header: () => 'Producto',
        cell: (info) => info.getValue(),
        size: 220,
      }),
      columnHelper.accessor('productSku', {
        header: () => 'SKU',
        cell: (info) => <span className="font-mono text-sm">{info.getValue()}</span>,
        size: 120,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).pointOfSaleName, {
        id: 'pointOfSaleName',
        header: () => 'Punto de Venta',
        cell: (info) => info.getValue(),
        size: 180,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).quantityChange, {
        id: 'quantityChange',
        header: () => 'Cambio',
        cell: (info) => {
          const val = info.getValue() as number;
          const color = val > 0 ? 'text-green-600' : val < 0 ? 'text-red-600' : '';
          return <span className={`font-medium ${color}`}>{fmtNum(val)}</span>;
        },
        size: 100,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).quantityBefore, {
        id: 'quantityBefore',
        header: () => 'Antes',
        cell: (info) => fmtNum(info.getValue() as number),
        size: 90,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).quantityAfter, {
        id: 'quantityAfter',
        header: () => 'Después',
        cell: (info) => fmtNum(info.getValue() as number),
        size: 100,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).userName, {
        id: 'userName',
        header: () => 'Usuario',
        cell: (info) => info.getValue(),
        size: 160,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).reason, {
        id: 'reason',
        header: () => 'Motivo',
        cell: (info) => info.getValue() || '-',
        size: 220,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).saleId, {
        id: 'saleId',
        header: () => 'Venta',
        cell: (info) => info.getValue() ? <span className="font-mono text-xs">{info.getValue() as string}</span> : '-',
        size: 160,
      }),
      columnHelper.accessor((row) => (row as InventoryMovementDetailRow).returnId, {
        id: 'returnId',
        header: () => 'Devolución',
        cell: (info) => info.getValue() ? <span className="font-mono text-xs">{info.getValue() as string}</span> : '-',
        size: 160,
      }),
    ],
    [outputModel, sort], // eslint-disable-line react-hooks/exhaustive-deps
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
          <h1 className="text-2xl font-bold tracking-tight">Resumen de Movimientos de Inventario</h1>
          <p className="text-muted-foreground">
            Vista resumida o detallada de movimientos de inventario
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Info className="size-3" />
            Máximo 50.000 filas. Si hay más resultados, ajuste los filtros.
          </p>
          <Button variant="outline" onClick={handleExport} disabled={isExporting || !hasSearched}>
            <Download className="mr-2 size-4" />
            {isExporting ? 'Exportando...' : 'Exportar a Excel'}
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
          <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            <div className="space-y-2">
              <Label>Fecha Inicio *</Label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Fecha Fin *</Label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Modelo de salida</Label>
              <Select
                value={outputModel}
                onValueChange={(v) => handleOutputModelChange(v as InventoryMovementOutputModel)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Resumen" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="summary">Resumen</SelectItem>
                  <SelectItem value="detail">Detalle</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Punto de Venta</Label>
              <Select
                value={pointOfSaleId || 'all'}
                onValueChange={(v) => setPointOfSaleId(v === 'all' ? undefined : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos los puntos de venta" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos los puntos de venta</SelectItem>
                  {pointsOfSale.map((pos) => (
                    <SelectItem key={pos.id} value={pos.id}>{pos.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Producto o SKU</Label>
              <Input
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                placeholder="Nombre o SKU"
              />
            </div>
            <div className="space-y-2">
              <Label>&nbsp;</Label>
              <Button onClick={handleSearch} disabled={!canSearch} className="w-full">
                Buscar
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Help legend */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          <strong>Adiciones</strong> = entradas al inventario (devoluciones, ajustes positivos, importaciones).{' '}
          <strong>Sustracciones</strong> = salidas del inventario (ventas, ajustes negativos).{' '}
          <strong>Diferencia</strong> = Adiciones − Sustracciones.
        </AlertDescription>
      </Alert>

      {/* Data table */}
      {hasSearched && (
        <DataGridContainer>
          <DataGrid
            table={table}
            recordCount={totalCount}
            isLoading={isLoading}
            emptyMessage="No se encontraron movimientos para los filtros seleccionados"
          >
            <DataGridTable />
            <DataGridPagination />
          </DataGrid>
        </DataGridContainer>
      )}
    </div>
  );
}

export default InventoryMovementSummaryPage;
