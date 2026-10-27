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

test.describe('Retired image recognition routes', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedSession(page);
  });

  test('should open the dashboard when visiting a retired recognition route', async ({ page }) => {
    await page.goto('/admin/ai-model');
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.goto('/sales/new/image');
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test('should omit Modelo de IA when the administrator sidebar is shown', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('link', { name: 'Modelo de IA' })).toHaveCount(0);
  });
});
