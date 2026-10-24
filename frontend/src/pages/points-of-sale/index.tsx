/**
 * Points of Sale Module - EP8
 * Point of sale management page with CRUD operations
 */

import { useState, useEffect, useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  ColumnDef,
  createColumnHelper,
} from '@tanstack/react-table';
import {
  Plus,
  Pencil,
  MoreHorizontal,
  CheckCircle2,
  XCircle,
  Power,
  Users,
  CreditCard,
  Percent,
} from 'lucide-react';
import { useAuth } from '@/providers/auth-provider';
import { pointOfSaleService } from '@/services/point-of-sale.service';
import { PointOfSale } from '@/types/point-of-sale.types';
import { DataGrid, DataGridContainer } from '@/components/ui/data-grid';
import { DataGridTable } from '@/components/ui/data-grid-table';
import { DataGridPagination } from '@/components/ui/data-grid-pagination';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { PointOfSaleFormDialog } from './components/point-of-sale-form-dialog';
import { OperatorAssignmentsDialog } from './components/operator-assignments-dialog';
import { PaymentMethodAssignmentsDialog } from './components/payment-method-assignments-dialog';
import { CommissionTiersDialog } from './components/commission-tiers-dialog';

const columnHelper = createColumnHelper<PointOfSale>();

export function PointsOfSalePage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  const [pointsOfSale, setPointsOfSale] = useState<PointOfSale[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isFormDialogOpen, setIsFormDialogOpen] = useState(false);
  const [isOperatorsDialogOpen, setIsOperatorsDialogOpen] = useState(false);
  const [isPaymentMethodsDialogOpen, setIsPaymentMethodsDialogOpen] = useState(false);
  const [isCommissionDialogOpen, setIsCommissionDialogOpen] = useState(false);
  const [selectedPointOfSale, setSelectedPointOfSale] = useState<PointOfSale | null>(null);

  // Fetch points of sale
  const fetchPointsOfSale = async () => {
    setIsLoading(true);
    try {
      const data = await pointOfSaleService.getPointsOfSale();
      console.log('Fetched points of sale:', data);
      setPointsOfSale(data);
    } catch (error) {
      toast.error('Error al cargar los puntos de venta');
      console.error('Failed to fetch points of sale:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPointsOfSale();
  }, []);

  // Handle create point of sale
  const handleCreate = () => {
    setSelectedPointOfSale(null);
    setIsFormDialogOpen(true);
  };

  // Handle edit point of sale
  const handleEdit = (pointOfSale: PointOfSale) => {
    setSelectedPointOfSale(pointOfSale);
    setIsFormDialogOpen(true);
  };

  // Handle manage operators
  const handleManageOperators = (pointOfSale: PointOfSale) => {
    setSelectedPointOfSale(pointOfSale);
    setIsOperatorsDialogOpen(true);
  };

  // Handle manage payment methods
  const handleManagePaymentMethods = (pointOfSale: PointOfSale) => {
    setSelectedPointOfSale(pointOfSale);
    setIsPaymentMethodsDialogOpen(true);
  };

  const handleManageCommissions = (pointOfSale: PointOfSale) => {
    setSelectedPointOfSale(pointOfSale);
    setIsCommissionDialogOpen(true);
  };

  // Handle status toggle
  const handleToggleStatus = async (pointOfSale: PointOfSale) => {
    console.log('Toggling status for POS:', pointOfSale);
    try {
      const result = await pointOfSaleService.changePointOfSaleStatus(pointOfSale.id, !pointOfSale.isActive);
      console.log('Status change result:', result);
      toast.success(
        pointOfSale.isActive
          ? 'Punto de venta desactivado correctamente'
          : 'Punto de venta activado correctamente'
      );
      fetchPointsOfSale();
    } catch (error: any) {
      const errorMessage =
        error?.message || 'Error al cambiar el estado del punto de venta';
      toast.error(errorMessage);
      console.error('Failed to toggle point of sale status:', error);
    }
  };

  // Handle form dialog close
  const handleFormDialogClose = (success?: boolean) => {
    setIsFormDialogOpen(false);
    setSelectedPointOfSale(null);
    if (success) {
      fetchPointsOfSale();
    }
  };

  // Handle operators dialog close
  const handleOperatorsDialogClose = () => {
    setIsOperatorsDialogOpen(false);
    setSelectedPointOfSale(null);
  };

  // Handle payment methods dialog close
  const handlePaymentMethodsDialogClose = () => {
    setIsPaymentMethodsDialogOpen(false);
    setSelectedPointOfSale(null);
  };

  const handleCommissionDialogClose = () => {
    setIsCommissionDialogOpen(false);
    setSelectedPointOfSale(null);
  };

  // Table columns
  const columns = useMemo<ColumnDef<PointOfSale, unknown>[]>(
    () => [
      columnHelper.accessor('name', {
        header: () => 'Nombre',
        cell: (info) => <span className="font-medium">{info.getValue()}</span>,
        size: 200,
        meta: {
          skeleton: <Skeleton className="h-4 w-32" />,
        },
      }),
      columnHelper.accessor('code', {
        header: () => 'Código',
        cell: (info) => <span className="font-mono text-sm">{info.getValue()}</span>,
        size: 120,
        meta: {
          skeleton: <Skeleton className="h-4 w-20" />,
        },
      }),
      columnHelper.accessor('address', {
        header: () => 'Dirección',
        cell: (info) => (
          <span className="text-sm text-muted-foreground">{info.getValue() || '-'}</span>
        ),
        size: 250,
        meta: {
          skeleton: <Skeleton className="h-4 w-48" />,
        },
      }),
      columnHelper.accessor('phone', {
        header: () => 'Teléfono',
        cell: (info) => (
          <span className="text-sm text-muted-foreground">{info.getValue() || '-'}</span>
        ),
        size: 130,
        meta: {
          skeleton: <Skeleton className="h-4 w-24" />,
        },
      }),
      columnHelper.accessor('isActive', {
        header: () => 'Estado',
        cell: (info) => (
          <div className="flex items-center gap-1.5">
            {info.getValue() ? (
              <>
                <CheckCircle2 className="size-4 text-green-600" />
                <span className="text-green-600">Activo</span>
              </>
            ) : (
              <>
                <XCircle className="size-4 text-muted-foreground" />
                <span className="text-muted-foreground">Inactivo</span>
              </>
            )}
          </div>
        ),
        size: 120,
        meta: {
          skeleton: <Skeleton className="h-5 w-16" />,
        },
      }),
      columnHelper.display({
        id: 'actions',
        header: () => 'Acciones',
        cell: ({ row }) => {
          const pointOfSale = row.original;
          return (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon">
                  <MoreHorizontal className="size-4" />
                  <span className="sr-only">Abrir menú</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleEdit(pointOfSale)}>
                  <Pencil className="mr-2 size-4" />
                  Editar
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => handleManageOperators(pointOfSale)}>
                  <Users className="mr-2 size-4" />
                  Asignar Operadores
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleManagePaymentMethods(pointOfSale)}>
                  <CreditCard className="mr-2 size-4" />
                  Métodos de Pago
                </DropdownMenuItem>
                {isAdmin && (
                  <DropdownMenuItem onClick={() => handleManageCommissions(pointOfSale)}>
                    <Percent className="mr-2 size-4" />
                    Comisiones
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => handleToggleStatus(pointOfSale)}>
                  <Power className="mr-2 size-4" />
                  {pointOfSale.isActive ? 'Desactivar' : 'Activar'}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          );
        },
        size: 70,
        meta: {
          skeleton: <Skeleton className="h-8 w-8 ml-auto" />,
        },
      }),
    ],
    [isAdmin]
  );

  const table = useReactTable({
    data: pointsOfSale,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowProps: (row) => ({
      className: !row.original.isActive ? 'opacity-60 bg-muted/30' : '',
    }),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Puntos de Venta</h1>
          <p className="text-muted-foreground">
            Gestión de puntos de venta y ubicaciones del negocio
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 size-4" />
          Nuevo Punto de Venta
        </Button>
      </div>

      {/* Info Banner */}
      <div className="rounded-lg border bg-muted/50 p-4">
        <div className="flex items-start gap-3">
          <Badge variant="outline" className="mt-0.5">
            Info
          </Badge>
          <div className="flex-1 space-y-1">
            <p className="text-sm font-medium">Gestión de ubicaciones</p>
            <p className="text-sm text-muted-foreground">
              Los puntos de venta representan las ubicaciones físicas donde se realizan las
              operaciones comerciales. Puedes asignar operadores y métodos de pago específicos a
              cada ubicación. Los administradores tienen acceso a todos los puntos de venta,
              mientras que los operadores solo acceden a sus asignaciones.
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Badge variant="outline">Total</Badge>
            <span className="text-2xl font-bold">{pointsOfSale.length}</span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Puntos de venta registrados</p>
        </div>
        <div className="rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-green-600 text-green-600">
              Activos
            </Badge>
            <span className="text-2xl font-bold text-green-600">
              {pointsOfSale.filter((pos) => pos.isActive).length}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">En operación</p>
        </div>
        <div className="rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-muted-foreground text-muted-foreground">
              Inactivos
            </Badge>
            <span className="text-2xl font-bold text-muted-foreground">
              {pointsOfSale.filter((pos) => !pos.isActive).length}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Fuera de servicio</p>
        </div>
      </div>

      {/* Data Table */}
      <DataGridContainer>
        <DataGrid
          table={table}
          recordCount={pointsOfSale.length}
          isLoading={isLoading}
          emptyMessage="No hay puntos de venta registrados"
        >
          <DataGridTable />
          <DataGridPagination />
        </DataGrid>
      </DataGridContainer>

      {/* Dialogs */}
      <PointOfSaleFormDialog
        open={isFormDialogOpen}
        onClose={handleFormDialogClose}
        pointOfSale={selectedPointOfSale}
      />

      <OperatorAssignmentsDialog
        open={isOperatorsDialogOpen}
        onClose={handleOperatorsDialogClose}
        pointOfSale={selectedPointOfSale}
      />

      <PaymentMethodAssignmentsDialog
        open={isPaymentMethodsDialogOpen}
        onClose={handlePaymentMethodsDialogClose}
        pointOfSale={selectedPointOfSale}
      />

      <CommissionTiersDialog
        open={isCommissionDialogOpen}
        onClose={handleCommissionDialogClose}
        pointOfSale={selectedPointOfSale}
      />
    </div>
  );
}

export default PointsOfSalePage;
