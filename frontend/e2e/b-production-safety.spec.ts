import { expect, test } from '@playwright/test';

test('production dashboard exposes no preview or debug labels', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();
  const forbidden = new Set([
    'PREVIEW', 'PREVIEW MODE', 'DEMO', 'DEMO DATA', 'DEBUG',
    'MOCK DATA', 'SAMPLE DATA', 'PLACEHOLDER',
  ]);
  const visibleLines = (await page.locator('body').innerText())
    .split('\n')
    .map((value) => value.trim().toUpperCase())
    .filter(Boolean);
  expect(visibleLines.filter((value) => forbidden.has(value))).toEqual([]);

  const accessibleLabels = await page.locator('[aria-label], [title]').evaluateAll((elements) =>
    elements.flatMap((element) => [element.getAttribute('aria-label'), element.getAttribute('title')])
      .filter((value): value is string => Boolean(value))
      .map((value) => value.trim().toUpperCase()),
  );
  expect(accessibleLabels.filter((value) => forbidden.has(value))).toEqual([]);
});

test('Hebrew transaction text and LTR currency values keep explicit direction', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.transactions-panel')).toBeVisible();
  await page.route('**/api/transactions?**', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    if (payload.transactions?.length) {
      payload.transactions[0] = {
        ...payload.transactions[0],
        merchant_raw: 'חנות בדיקה תל אביב',
        merchant_display_name: 'חנות בדיקה',
        merchant_normalized: 'חנות בדיקה תל אביב',
        category: 'מזון וצריכה',
        subcategory: 'סופרמרקט',
        amount: 92.5,
        charged_currency: 'ILS',
        original_amount: 25,
        original_currency: 'USD',
      };
    }
    await route.fulfill({ response, json: payload });
  });

  await page.getByRole('button', { name: /View all transactions/ }).click();
  const dialog = page.getByRole('dialog', { name: 'All transactions' });
  const row = dialog.locator('.transaction-source-table tbody tr', { hasText: 'חנות בדיקה תל אביב' });
  await expect(row).toHaveCount(1);
  await expect(row.locator('td').nth(0).locator('strong')).toHaveAttribute('dir', 'auto');
  await expect(row.locator('td').nth(0).locator('strong')).toHaveCSS('text-align', 'left');
  await expect(row.locator('.transaction-category-pill > span')).toHaveAttribute('dir', 'auto');
  await expect(row.locator('td').nth(6)).toHaveAttribute('dir', 'ltr');
  await expect(row.locator('td').nth(6)).toContainText('92.5 ILS');
  await expect(row.locator('td').nth(7)).toHaveAttribute('dir', 'ltr');
  await expect(row.locator('td').nth(7)).toContainText('25 USD');
});
