import {
  LayoutGrid,
  Package,
  Warehouse,
  ShoppingCart,
  RotateCcw,
  FileText,
  Settings,
  CreditCard,
  Users,
  Store,
} from 'lucide-react';
import { type MenuConfig } from './types';
import { ROUTES } from '@/routing/routes';

/**
 * Administrator Sidebar Menu
 * Full access to all modules including configuration and reports
 */
export const MENU_ADMINISTRATOR: MenuConfig = [
  {
    title: 'Dashboard',
    icon: LayoutGrid,
    path: ROUTES.DASHBOARD,
  },
  {
    title: 'Productos',
    icon: Package,
    path: ROUTES.PRODUCTS.ROOT,
  },
  {
    title: 'Inventario',
    icon: Warehouse,
    path: ROUTES.INVENTORY.ROOT,
  },
  {
    title: 'Ventas',
    icon: ShoppingCart,
    path: ROUTES.SALES.ROOT,
  },
  {
    title: 'Devoluciones',
    icon: RotateCcw,
    path: ROUTES.RETURNS.ROOT,
  },
  {
    title: 'Reportes',
    icon: FileText,
    path: ROUTES.REPORTS.ROOT,
  },
  {
    title: 'Configuración',
    icon: Settings,
    children: [
      {
        title: 'Gestión de Productos',
        icon: Package,
        path: ROUTES.PRODUCTS.ROOT,
      },
      {
        title: 'Modelo de IA',
        icon: ShoppingCart,
        path: ROUTES.AI_MODEL,
      },
      {
        title: 'Revisión de familias',
        icon: Users,
        path: ROUTES.FAMILY_REVIEW,
      },
      {
        title: 'Métodos de Pago',
        icon: CreditCard,
        path: ROUTES.PAYMENT_METHODS,
      },
      {
        title: 'Usuarios',
        icon: Users,
        path: ROUTES.USERS,
      },
      {
        title: 'Puntos de Venta',
        icon: Store,
        path: ROUTES.POINTS_OF_SALE,
      },
    ],
  },
];

/**
 * Operator Sidebar Menu
 * Limited access to sales-related functions only
 */
export const MENU_OPERATOR: MenuConfig = [
  {
    title: 'Dashboard',
    icon: LayoutGrid,
    path: ROUTES.DASHBOARD,
  },
  {
    title: 'Productos',
    icon: Package,
    path: ROUTES.PRODUCTS.CATALOG,
  },
  {
    title: 'Ventas',
    icon: ShoppingCart,
    path: ROUTES.SALES.ROOT,
  },
  {
    title: 'Devoluciones',
    icon: RotateCcw,
    path: ROUTES.RETURNS.ROOT,
  },
  {
    title: 'Inventario',
    icon: Warehouse,
    path: ROUTES.INVENTORY.STOCK,
  },
];

/**
 * Get menu configuration based on user role
 * @param role - User role ('Administrator' or 'Operator')
 * @returns Menu configuration for the role
 */
export function getMenuForRole(role: 'Administrator' | 'Operator'): MenuConfig {
  switch (role) {
    case 'Administrator':
      return MENU_ADMINISTRATOR;
    case 'Operator':
      return MENU_OPERATOR;
    default:
      return MENU_OPERATOR;
  }
}
