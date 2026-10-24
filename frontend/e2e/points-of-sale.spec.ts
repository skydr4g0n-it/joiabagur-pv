/**
 * E2E Tests for Point of Sale Management
 * Tests POS list, create, edit, status toggle, and assignments
 */

import { test, expect } from '@playwright/test';

// Helper to setup authenticated session
async function setupAuthenticatedSession(page: import('@playwright/test').Page) {
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      json: {
        userId: '1',
        username: 'admin',
        firstName: 'Admin',
        lastName: 'User',
        role: 'Administrator',
      },
    });
  });

  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill({ status: 200, json: { message: 'Token refreshed' } });
  });
}

const mockPointsOfSale = [
  {
    id: '1',
    name: 'Tienda Centro',
    code: 'CENTRO-001',
    address: 'Calle Principal 123, Madrid',
    phone: '+34 600 123 456',
    email: 'centro@test.com',
    isActive: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    name: 'Hotel Plaza',
    code: 'HOTEL-PLZ',
    address: 'Plaza Mayor 1, Barcelona',
    phone: '+34 600 789 012',
    email: 'plaza@test.com',
    isActive: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: '3',
    name: 'Aeropuerto',
    code: 'AIRPORT-MAD',
    address: 'Terminal 4, Madrid',
    phone: null,
    email: null,
    isActive: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
];

test.describe('Point of Sale Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedSession(page);

    // Mock points of sale list endpoint
    await page.route('**/api/point-of-sales', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: mockPointsOfSale });
      } else {
        await route.continue();
      }
    });
  });

  test.describe('Points of Sale List', () => {
    test('should display points of sale page', async ({ page }) => {
      await page.goto('/points-of-sale');

      await expect(page.getByRole('heading', { name: /puntos de venta/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /nuevo punto de venta/i })).toBeVisible();
    });

    test('should display page description', async ({ page }) => {
      await page.goto('/points-of-sale');

      await expect(
        page.getByText('Gestión de puntos de venta y ubicaciones del negocio')
      ).toBeVisible();
    });

    test('should display all points of sale in the table', async ({ page }) => {
      await page.goto('/points-of-sale');

      await expect(page.getByText('Tienda Centro')).toBeVisible();
      await expect(page.getByText('CENTRO-001')).toBeVisible();
      await expect(page.getByText('Hotel Plaza')).toBeVisible();
      await expect(page.getByText('HOTEL-PLZ')).toBeVisible();
      await expect(page.getByText('Aeropuerto')).toBeVisible();
      await expect(page.getByText('AIRPORT-MAD')).toBeVisible();
    });

    test('should display addresses and contact information', async ({ page }) => {
      await page.goto('/points-of-sale');

      await expect(page.getByText('Calle Principal 123, Madrid')).toBeVisible();
      await expect(page.getByText('+34 600 123 456')).toBeVisible();
      await expect(page.getByText('Plaza Mayor 1, Barcelona')).toBeVisible();
    });

    test('should display statistics cards', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Total
      await expect(page.getByText('3').first()).toBeVisible();
      await expect(page.getByText('Puntos de venta registrados')).toBeVisible();

      // Active
      await expect(page.getByText('2')).toBeVisible();
      await expect(page.getByText('En operación')).toBeVisible();

      // Inactive
      await expect(page.getByText('1')).toBeVisible();
      await expect(page.getByText('Fuera de servicio')).toBeVisible();
    });

    test('should display info banner', async ({ page }) => {
      await page.goto('/points-of-sale');

      await expect(page.getByText('Gestión de ubicaciones')).toBeVisible();
      await expect(
        page.getByText(/Los puntos de venta representan las ubicaciones físicas/i)
      ).toBeVisible();
    });
  });

  test.describe('Point of Sale Status', () => {
    test('should display active status with green indicator', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Should show 2 active status indicators
      const activeStatuses = page.getByText('Activo');
      await expect(activeStatuses.first()).toBeVisible();
    });

    test('should display inactive status with gray indicator', async ({ page }) => {
      await page.goto('/points-of-sale');

      await expect(page.getByText('Inactivo')).toBeVisible();
    });
  });

  test.describe('Create Point of Sale', () => {
    test('should open create dialog when clicking new button', async ({ page }) => {
      await page.goto('/points-of-sale');

      const createButton = page.getByRole('button', { name: /nuevo punto de venta/i });
      await createButton.click();

      // Dialog should open
      await expect(page.getByRole('dialog')).toBeVisible();
      await expect(page.getByText('Crear Punto de Venta')).toBeVisible();
    });

    test('should display empty form fields in create dialog', async ({ page }) => {
      await page.goto('/points-of-sale');

      await page.getByRole('button', { name: /nuevo punto de venta/i }).click();

      // Check form fields are present
      await expect(page.getByLabel(/^nombre/i)).toBeVisible();
      await expect(page.getByLabel(/^código/i)).toBeVisible();
      await expect(page.getByLabel(/dirección/i)).toBeVisible();
      await expect(page.getByLabel(/teléfono/i)).toBeVisible();
      await expect(page.getByLabel(/email/i)).toBeVisible();
    });

    test('should create new point of sale successfully', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Mock create endpoint
      await page.route('**/api/point-of-sales', async (route) => {
        if (route.request().method() === 'POST') {
          const body = route.request().postDataJSON();
          await route.fulfill({
            status: 201,
            json: {
              id: '4',
              ...body,
              isActive: true,
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          });
        } else {
          await route.continue();
        }
      });

      // Open create dialog
      await page.getByRole('button', { name: /nuevo punto de venta/i }).click();

      // Fill in form
      await page.getByLabel(/^nombre/i).fill('Nueva Tienda');
      await page.getByLabel(/^código/i).fill('NUEVA-001');
      await page.getByLabel(/dirección/i).fill('Avenida Test 456');
      await page.getByLabel(/teléfono/i).fill('+34 600 999 888');
      await page.getByLabel(/email/i).fill('nueva@test.com');

      // Submit form
      await page.getByRole('button', { name: /^crear$/i }).click();

      // Should show success message
      await expect(page.getByText('Punto de venta creado correctamente')).toBeVisible();
    });

    test('should validate code format - convert to uppercase', async ({ page }) => {
      await page.goto('/points-of-sale');

      await page.getByRole('button', { name: /nuevo punto de venta/i }).click();

      // Type lowercase code
      await page.getByLabel(/^código/i).fill('test-code');
      
      // Should be converted to uppercase
      await expect(page.getByLabel(/^código/i)).toHaveValue('TEST-CODE');
    });
  });

  test.describe('Edit Point of Sale', () => {
    test('should open edit dialog when clicking edit action', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Click on first POS action menu
      const actionButtons = page.getByRole('button', { name: /abrir menú/i });
      await actionButtons.first().click();

      // Click edit option
      await page.getByRole('menuitem', { name: /^editar$/i }).click();

      // Dialog should open in edit mode
      await expect(page.getByRole('dialog')).toBeVisible();
      await expect(page.getByText('Editar Punto de Venta')).toBeVisible();
    });

    test('should display prepopulated form fields in edit dialog', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Open action menu and click edit
      await page.getByRole('button', { name: /abrir menú/i }).first().click();
      await page.getByRole('menuitem', { name: /^editar$/i }).click();

      // Form should be prepopulated with Tienda Centro data
      await expect(page.getByLabel(/^nombre/i)).toHaveValue('Tienda Centro');
      await expect(page.getByLabel(/^código/i)).toHaveValue('CENTRO-001');
      await expect(page.getByLabel(/dirección/i)).toHaveValue('Calle Principal 123, Madrid');
      await expect(page.getByLabel(/teléfono/i)).toHaveValue('+34 600 123 456');
      await expect(page.getByLabel(/email/i)).toHaveValue('centro@test.com');
    });

    test('should update point of sale successfully', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Mock update endpoint
      await page.route('**/api/point-of-sales/*', async (route) => {
        if (route.request().method() === 'PUT') {
          const body = route.request().postDataJSON();
          await route.fulfill({
            status: 200,
            json: {
              ...mockPointsOfSale[0],
              ...body,
              updatedAt: '2024-01-02T00:00:00Z',
            },
          });
        } else {
          await route.continue();
        }
      });

      // Open edit dialog
      await page.getByRole('button', { name: /abrir menú/i }).first().click();
      await page.getByRole('menuitem', { name: /^editar$/i }).click();

      // Update name
      await page.getByLabel(/^nombre/i).fill('Tienda Centro Actualizada');

      // Submit form
      await page.getByRole('button', { name: /actualizar/i }).click();

      // Should show success message
      await expect(page.getByText('Punto de venta actualizado correctamente')).toBeVisible();
    });
  });

  test.describe('Operator Assignments', () => {
    test('should open operator assignments dialog', async ({ page }) => {
      // Mock users endpoint
      await page.route('**/api/users', async (route) => {
        await route.fulfill({
          status: 200,
          json: [
            {
              id: '1',
              username: 'operator1',
              firstName: 'Juan',
              lastName: 'Pérez',
              email: 'juan@test.com',
              role: 'Operator',
              isActive: true,
            },
          ],
        });
      });

      // Mock operator assignments endpoint
      await page.route('**/api/point-of-sales/*/operators', async (route) => {
        await route.fulfill({ status: 200, json: [] });
      });

      await page.goto('/points-of-sale');

      // Open action menu
      await page.getByRole('button', { name: /abrir menú/i }).first().click();

      // Click assign operators
      await page.getByRole('menuitem', { name: /asignar operadores/i }).click();

      // Dialog should open
      await expect(page.getByText('Asignar Operadores')).toBeVisible();
      await expect(page.getByText(/Selecciona los operadores/i)).toBeVisible();
    });
  });

  test.describe('Payment Method Assignments', () => {
    test('should open payment method assignments dialog', async ({ page }) => {
      // Mock payment methods endpoint
      await page.route('**/api/payment-methods*', async (route) => {
        await route.fulfill({
          status: 200,
          json: [
            {
              id: '1',
              code: 'CASH',
              name: 'Efectivo',
              description: 'Pago en efectivo',
              isActive: true,
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
        });
      });

      // Mock payment method assignments endpoint
      await page.route('**/api/point-of-sales/*/payment-methods*', async (route) => {
        await route.fulfill({ status: 200, json: [] });
      });

      await page.goto('/points-of-sale');

      // Open action menu
      await page.getByRole('button', { name: /abrir menú/i }).first().click();

      // Click payment methods
      await page.getByRole('menuitem', { name: /métodos de pago/i }).click();

      // Dialog should open
      await expect(page.getByText('Asignar Métodos de Pago')).toBeVisible();
      await expect(page.getByText(/Selecciona los métodos de pago/i)).toBeVisible();
    });
  });

  test.describe('Toggle Point of Sale Status', () => {
    test('should display activate/deactivate option in actions menu', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Open action menu for active POS
      await page.getByRole('button', { name: /abrir menú/i }).first().click();

      // Should show deactivate option
      await expect(page.getByRole('menuitem', { name: /desactivar/i })).toBeVisible();
    });

    test('should deactivate active point of sale', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Mock status change endpoint
      await page.route('**/api/point-of-sales/*/status', async (route) => {
        if (route.request().method() === 'PATCH') {
          await route.fulfill({
            status: 200,
            json: {
              ...mockPointsOfSale[0],
              isActive: false,
              updatedAt: '2024-01-02T00:00:00Z',
            },
          });
        } else {
          await route.continue();
        }
      });

      // Open action menu and deactivate
      await page.getByRole('button', { name: /abrir menú/i }).first().click();
      await page.getByRole('menuitem', { name: /desactivar/i }).click();

      // Should show success message
      await expect(page.getByText('Punto de venta desactivado correctamente')).toBeVisible();
    });

    test('should activate inactive point of sale', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Mock status change endpoint
      await page.route('**/api/point-of-sales/*/status', async (route) => {
        if (route.request().method() === 'PATCH') {
          await route.fulfill({
            status: 200,
            json: {
              ...mockPointsOfSale[2],
              isActive: true,
              updatedAt: '2024-01-02T00:00:00Z',
            },
          });
        } else {
          await route.continue();
        }
      });

      // Find inactive POS (3rd row) and activate
      const actionButtons = page.getByRole('button', { name: /abrir menú/i });
      await actionButtons.nth(2).click();
      
      await page.getByRole('menuitem', { name: /activar/i }).click();

      // Should show success message
      await expect(page.getByText('Punto de venta activado correctamente')).toBeVisible();
    });
  });

  test.describe('Commission tiers', () => {
    test('should save commission tiers when admin submits valid ranges', async ({ page }) => {
      await page.goto('/points-of-sale');

      await page.route('**/api/point-of-sales/1/commission-tiers', async (route) => {
        if (route.request().method() === 'GET') {
          await route.fulfill({ status: 200, json: [] });
        } else if (route.request().method() === 'PUT') {
          const body = route.request().postDataJSON();
          await route.fulfill({
            status: 200,
            json: body.tiers.map((t: Record<string, unknown>, i: number) => ({
              id: String(i + 1),
              ...t,
            })),
          });
        } else {
          await route.continue();
        }
      });

      await page.getByRole('button', { name: /abrir menú/i }).first().click();
      await page.getByRole('menuitem', { name: /comisiones/i }).click();

      await expect(page.getByRole('dialog', { name: /comisiones/i })).toBeVisible();

      await page.getByLabel(/mín\. €/i).first().fill('0');
      await page.getByLabel(/máx\. €/i).first().fill('20000');
      await page.getByLabel(/^%$/i).first().fill('20');

      await page.getByRole('button', { name: /guardar/i }).click();
      await expect(page.getByText('Comisiones guardadas correctamente')).toBeVisible();
    });
  });

  test.describe('Error Handling', () => {
    test('should display error when points of sale fail to load', async ({ page }) => {
      // Override route to simulate error
      await page.route('**/api/point-of-sales', async (route) => {
        await route.fulfill({ status: 500, json: { error: 'Server error' } });
      });

      await page.goto('/points-of-sale');

      await expect(page.getByText('Error al cargar los puntos de venta')).toBeVisible();
    });

    test('should display error when create fails', async ({ page }) => {
      await page.goto('/points-of-sale');

      // Mock create endpoint with error
      await page.route('**/api/point-of-sales', async (route) => {
        if (route.request().method() === 'POST') {
          await route.fulfill({
            status: 409,
            json: { error: 'El código de punto de venta ya está en uso' },
          });
        } else {
          await route.continue();
        }
      });

      // Open create dialog and fill form
      await page.getByRole('button', { name: /nuevo punto de venta/i }).click();
      await page.getByLabel(/^nombre/i).fill('Tienda Test');
      await page.getByLabel(/^código/i).fill('CENTRO-001');
      await page.getByRole('button', { name: /^crear$/i }).click();

      // Should show error message
      await expect(page.getByText('El código de punto de venta ya está en uso')).toBeVisible();
    });
  });
});
