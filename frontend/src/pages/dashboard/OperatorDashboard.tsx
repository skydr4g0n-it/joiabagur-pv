import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ShoppingCart, RotateCcw, ScanLine, Package, ExternalLink } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useAuth } from '@/providers/auth-provider';
import { dashboardService } from '@/services/dashboard.service';
import { salesService } from '@/services/sales.service';
import { inventoryService } from '@/services/inventory.service';
import type { DashboardStats } from '@/types/dashboard.types';
import type { Sale } from '@/types/sales.types';
import { ROUTES } from '@/routing/routes';

const DAY_LABELS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(amount);

interface WeekDayData {
  day: string;
  revenue: number;
}

interface LowStockItem {
  productName: string;
  sku: string;
  stock: number;
}

export function OperatorDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [weekData, setWeekData] = useState<WeekDayData[]>([]);
  const [recentSales, setRecentSales] = useState<Sale[]>([]);
  const [lowStock, setLowStock] = useState<LowStockItem[]>([]);
  const [stockSummary, setStockSummary] = useState({ skus: 0, units: 0 });
  const [loading, setLoading] = useState(true);

  const posId = user?.assignedPointOfSales?.find((p) => p.isActive)?.pointOfSaleId;

  useEffect(() => {
    if (!posId) return;

    const load = async () => {
      try {
        // Calculate week boundaries (Mon-Sun)
        const now = new Date();
        const dayOfWeek = now.getDay();
        const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
        const weekStart = new Date(now);
        weekStart.setDate(now.getDate() - daysFromMonday);
        weekStart.setHours(0, 0, 0, 0);

        const [dashStats, salesHistory, stockResult] = await Promise.all([
          dashboardService.getStats(posId),
          salesService.getSalesHistory({
            pointOfSaleId: posId,
            startDate: weekStart.toISOString().split('T')[0],
            pageSize: 50,
            page: 1,
          }),
          inventoryService.getAllStock(posId),
        ]);

        setStats(dashStats);

        const salesWithoutReturns = salesHistory.sales.filter((s) => !s.hasReturn);
        setRecentSales(salesWithoutReturns.slice(0, 8));

        // Build weekly trend (Mon-Sun, exclude returned)
        const revenueByDay = new Map<number, number>();
        for (const sale of salesWithoutReturns) {
          const saleDate = new Date(sale.saleDate);
          const saleDow = saleDate.getDay();
          const dayIndex = saleDow === 0 ? 6 : saleDow - 1;
          revenueByDay.set(dayIndex, (revenueByDay.get(dayIndex) ?? 0) + sale.total);
        }

        const todayIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
        const weekChart: WeekDayData[] = DAY_LABELS.map((label, i) => ({
          day: label,
          revenue: i <= todayIndex ? (revenueByDay.get(i) ?? 0) : 0,
        }));
        setWeekData(weekChart);

        // Stock summary and low stock items
        const items = stockResult.items ?? [];
        let skuCount = 0;
        let totalUnits = 0;
        const lowItems: LowStockItem[] = [];

        for (const inv of items) {
          if (inv.quantity > 0) {
            skuCount++;
            totalUnits += inv.quantity;
          }
          if (inv.quantity <= 2) {
            lowItems.push({
              productName: inv.productName,
              sku: inv.productSku,
              stock: inv.quantity,
            });
          }
        }

        setStockSummary({ skus: skuCount, units: totalUnits });
        setLowStock(lowItems);
      } catch (err) {
        console.error('Failed to load operator dashboard:', err);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [posId]);

  if (!posId) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">No tienes un punto de venta asignado.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-muted-foreground">Cargando dashboard...</div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="space-y-6 pb-24">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Mi Dashboard</h1>
        <p className="text-muted-foreground">
          {user?.assignedPointOfSales?.find((p) => p.pointOfSaleId === posId)?.name ?? 'Mi punto de venta'}
        </p>
      </div>

      {/* Row 1 — KPI Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Mis ventas hoy</CardTitle>
            <ShoppingCart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(stats.salesTodayTotal)}</div>
            <p className="text-xs text-muted-foreground">{stats.salesTodayCount} ventas</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Esta semana</CardTitle>
            <ShoppingCart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(stats.weeklyRevenue ?? 0)}</div>
            <p className="text-xs text-muted-foreground">Lun - Dom</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Devoluciones hoy</CardTitle>
            <RotateCcw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.returnsTodayCount ?? 0}</div>
            <p className="text-xs text-muted-foreground">registradas hoy</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Artículos en stock</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stockSummary.skus}</div>
            <p className="text-xs text-muted-foreground">{stockSummary.units} unidades</p>
          </CardContent>
        </Card>
      </div>

      {/* Row 2 — Weekly trend chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Mis ventas esta semana</CardTitle>
          <CardDescription>Ingresos diarios (Lun - Dom)</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={weekData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}€`} />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Line type="monotone" dataKey="revenue" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Row 3 — Recent sales + Low stock tables */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">Últimas ventas</CardTitle>
              <CardDescription>8 ventas más recientes</CardDescription>
            </div>
            <Link
              to={ROUTES.SALES.HISTORY}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              Ver todo <ExternalLink className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {recentSales.length === 0 ? (
              <p className="text-sm text-muted-foreground">No hay ventas recientes.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Hora</TableHead>
                    <TableHead>Producto</TableHead>
                    <TableHead className="text-center">Cant.</TableHead>
                    <TableHead className="text-right">Importe</TableHead>
                    <TableHead>Pago</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentSales.map((sale) => (
                    <TableRow key={sale.id}>
                      <TableCell className="text-xs">
                        {new Date(sale.saleDate).toLocaleTimeString('es-ES', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </TableCell>
                      <TableCell className="font-medium max-w-[120px] truncate">{sale.productName}</TableCell>
                      <TableCell className="text-center">{sale.quantity}</TableCell>
                      <TableCell className="text-right font-medium">{formatCurrency(sale.total)}</TableCell>
                      <TableCell className="text-xs">{sale.paymentMethodName}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">Stock bajo</CardTitle>
              <CardDescription>Productos con stock &le; 2 unidades</CardDescription>
            </div>
            <Link
              to={ROUTES.INVENTORY.ROOT}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              Ver inventario <ExternalLink className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {lowStock.length === 0 ? (
              <p className="text-sm text-muted-foreground">No hay productos con stock bajo.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Producto</TableHead>
                    <TableHead>SKU</TableHead>
                    <TableHead className="text-right">Stock</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lowStock.map((item, i) => (
                    <TableRow key={`${item.sku}-${i}`}>
                      <TableCell className="font-medium">{item.productName}</TableCell>
                      <TableCell className="text-muted-foreground">{item.sku}</TableCell>
                      <TableCell className="text-right">
                        <span className={item.stock === 0 ? 'text-red-600 font-bold' : 'text-amber-600 font-semibold'}>
                          {item.stock}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 start-0 end-0 z-50 bg-background border-t border-input shadow-lg lg:start-(--sidebar-width)">
        <div className="flex justify-around items-center p-3 max-w-lg mx-auto gap-2">
          <Link
            to={ROUTES.SALES.NEW}
            className="flex-1 flex flex-col items-center gap-1 bg-primary text-primary-foreground rounded-xl py-3 px-2 text-center hover:bg-primary/90 transition-colors"
          >
            <ShoppingCart className="h-5 w-5" />
            <span className="text-xs font-medium">Venta manual</span>
          </Link>
          <Link
            to={ROUTES.SALES.NEW_SCAN}
            className="flex-1 flex flex-col items-center gap-1 bg-primary text-primary-foreground rounded-xl py-3 px-2 text-center hover:bg-primary/90 transition-colors"
          >
            <ScanLine className="h-5 w-5" />
            <span className="text-xs font-medium">Escanear código</span>
          </Link>
          <Link
            to={ROUTES.RETURNS.NEW}
            className="flex-1 flex flex-col items-center gap-1 bg-secondary text-secondary-foreground rounded-xl py-3 px-2 text-center hover:bg-secondary/90 transition-colors"
          >
            <RotateCcw className="h-5 w-5" />
            <span className="text-xs font-medium">Devolución</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default OperatorDashboard;
