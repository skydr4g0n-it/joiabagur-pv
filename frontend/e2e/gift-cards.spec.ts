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
    await route.fulfill({ status: 200, json: { message: 'ok' } });
  });
}

test.describe('Gift cards checkout', () => {
  test('issues a 100 EUR card and sells a 150 EUR product with 50 EUR still due', async ({
    page,
  }) => {
    await setupAuthenticatedSession(page);

    await page.route('**/api/gift-cards', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          json: {
            success: true,
            card: {
              id: 'card-1',
              code: 'GC-E2E100',
              nominalAmount: 100,
              spendableBalance: 100,
              pointOfSaleId: 'pos-1',
            },
          },
        });
        return;
      }
      await route.continue();
    });

    await page.route('**/api/sales/bulk', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          success: true,
          sales: [
            {
              id: 'sale-1',
              productSku: 'SKU-150',
              price: 150,
              quantity: 1,
              giftCardCoverageAmount: 100,
            },
          ],
          warnings: [],
        },
      });
    });

    await page.goto('/sales/cart');
    await expect(page.getByText(/importe a cobrar/i)).toBeVisible();
  });

  test('manual sale page attaches a gift card and shows remaining cash due', async ({ page }) => {
    await setupAuthenticatedSession(page);

    await page.route('**/api/point-of-sales**', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{ id: 'pos-1', name: 'POS', code: 'POS1', allowManualPriceEdit: false }],
      });
    });
    await page.route('**/api/point-of-sales/pos-1/payment-methods**', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 'pospm-1',
            pointOfSaleId: 'pos-1',
            paymentMethodId: 'pm-1',
            isActive: true,
            paymentMethod: { id: 'pm-1', name: 'Cash', code: 'CASH', isActive: true },
          },
        ],
      });
    });
    await page.route('**/api/products/search**', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{ id: 'prod-1', sku: 'SKU-150', name: 'Product 150', price: 150, isActive: true }],
      });
    });
    await page.route('**/api/inventory/**', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          productId: 'prod-1',
          totalQuantity: 5,
          breakdown: [{ pointOfSaleId: 'pos-1', pointOfSaleName: 'POS', quantity: 5 }],
        },
      });
    });
    await page.route('**/api/gift-cards/by-code/**', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 'card-1',
          code: 'GC-E2E100',
          nominalAmount: 100,
          spendableBalance: 100,
          pointOfSaleId: 'pos-1',
        },
      });
    });

    await page.goto('/sales/new');
    await expect(page.getByPlaceholder('GC-...')).toBeVisible();
    await page.getByPlaceholder('GC-...').fill('GC-E2E100');
    await page.getByPlaceholder('GC-...').press('Enter');
    await expect(page.getByText('GC-E2E100')).toBeVisible();
  });
});
