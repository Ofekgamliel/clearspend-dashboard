import { expect, test } from '@playwright/test';

test('period, month, and card filters refresh the complete dashboard', async ({ page }) => {
  const dashboardRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/dashboard?')) dashboardRequests.push(request.url());
  });
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Month', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Choose month' })).toContainText('November 2026');
  const periodGeometry = await page.locator('.period-tabs').evaluate((element) => ({
    width: element.getBoundingClientRect().width,
    buttonWidth: [...element.querySelectorAll('button')].reduce((sum, button) => sum + button.getBoundingClientRect().width, 0),
  }));
  expect(periodGeometry.width).toBeLessThanOrEqual(periodGeometry.buttonWidth + 8);
  await expect(page.getByRole('button', { name: 'Choose month' })).toHaveCSS('width', '190px');
  await expect(page.getByRole('button', { name: 'Choose card' })).toHaveCSS('width', '205px');

  await page.getByRole('button', { name: 'Latest year' }).click();
  await expect(page.getByRole('button', { name: 'Latest year' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => dashboardRequests.at(-1)).toContain('period=year');

  await page.getByRole('button', { name: 'All time' }).click();
  await expect(page.getByRole('button', { name: 'All time' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => dashboardRequests.at(-1)).toContain('period=all');

  await page.getByRole('button', { name: 'Choose month' }).click();
  await page.getByRole('button', { name: 'October 2026', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Month', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Choose month' })).toContainText('October 2026');
  await expect.poll(() => dashboardRequests.at(-1)).toContain('month=2026-10');

  await page.getByRole('button', { name: 'Choose card' }).click();
  await page.getByRole('option', { name: /Synthetic MAX/ }).click();
  await expect(page.getByRole('button', { name: 'Choose card' })).toContainText('Synthetic MAX •• 0001');
  await expect.poll(() => dashboardRequests.at(-1)).toContain('card=max%3A0001');
  await expect(page.locator('.payment-card[aria-pressed="true"]')).toContainText('Synthetic MAX');
});
