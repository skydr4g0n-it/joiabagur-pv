/**
 * Application Route Constants
 * Centralized route definitions for the application
 */

export const ROUTES = {
  // Public routes
  AUTH: {
    LOGIN: '/auth/login',
  },

  // Protected routes
  DASHBOARD: '/dashboard',

  // Module routes - organized by epic
  PRODUCTS: {
    ROOT: '/products',
    CATALOG: '/products/catalog',
    CREATE: '/products/create',
    EDIT: (id: string) => `/products/${id}/edit`,
    IMPORT: '/products/import',
    COMPONENTS: '/products/components',
    COMPONENT_TEMPLATES: '/products/component-templates',
  },
  INVENTORY: {
    ROOT: '/inventory',
    STOCK: '/inventory/stock',
    ASSIGN: '/inventory/assign',
    IMPORT: '/inventory/import',
    ADJUST: '/inventory/adjust',
    MOVEMENTS: '/inventory/movements',
    CENTRALIZED: '/inventory/centralized',
  },
  SALES: {
    ROOT: '/sales',
    NEW: '/sales/new',
    NEW_SCAN: '/sales/new/scan',
    NEW_IMAGE: '/sales/new/image',
    NEW_ASSISTED: '/sales/new/assisted',
    CART: '/sales/cart',
    HISTORY: '/sales/history',
    DETAIL: (id: string) => `/sales/${id}`,
  },
  AI_MODEL: '/admin/ai-model',
  RETURNS: {
    ROOT: '/returns',
    NEW: '/returns/new',
    HISTORY: '/returns/history',
    DETAIL: (id: string) => `/returns/${id}`,
  },
  PAYMENT_METHODS: '/payment-methods',
  USERS: '/users',
  POINTS_OF_SALE: '/points-of-sale',
  REPORTS: {
    ROOT: '/reports',
    SALES: '/reports/sales',
    PRODUCT_MARGINS: '/reports/product-margins',
    PRODUCTS_WITHOUT_COMPONENTS: '/reports/products-without-components',
    INVENTORY_MOVEMENT_SUMMARY: '/reports/inventory-movement-summary',
  },
} as const;

/**
 * Check if a route is public (doesn't require authentication)
 */
export function isPublicRoute(path: string): boolean {
  const publicRoutes = [ROUTES.AUTH.LOGIN];
  return publicRoutes.some((route) => path.startsWith(route));
}
