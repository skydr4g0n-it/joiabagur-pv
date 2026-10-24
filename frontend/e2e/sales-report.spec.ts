import { test, expect } from '@playwright/test';

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

test.describe('Sales Report', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedSession(page);

    await page.route('**/api/point-of-sales', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{ id: 'pos-1', name: 'Tienda Centro', code: 'C1', isActive: true }],
      });
    });

    await page.route('**/api/users', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });

    await page.route('**/api/payment-methods', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
  });

  test('should show net amount in parentheses when report loads', async ({ page }) => {
    await page.route('**/api/reports/sales**', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          items: [],
          totalCount: 0,
          page: 1,
          pageSize: 20,
          totalPages: 0,
          totalSalesCount: 2,
          totalQuantity: 3,
          totalAmount: 1000,
          totalCommission: 200,
          totalAmountNet: 800,
          aggregatesByPointOfSale: null,
        },
      });
    });

    await page.goto('/reports/sales');

    await expect(page.getByText(/1\.000,00 € \(800,00 €\)/)).toBeVisible();
    await expect(page.getByText('Comisión total')).toBeVisible();
    await expect(page.getByText('200,00 €').first()).toBeVisible();
  });
});
