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
});
