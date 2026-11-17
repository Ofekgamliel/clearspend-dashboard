import { expect, test, type Locator, type Page } from '@playwright/test';

async function expectLargeDialog(dialog: Locator): Promise<void> {
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveCSS('border-radius', '16px');
  const title = dialog.locator('h2').first();
  await expect(title).toHaveCSS('font-size', '22px');
  const close = dialog.getByRole('button', { name: /^Close / });
  await expect(close).toHaveCSS('width', '30px');
  await expect(close).toHaveCSS('height', '30px');
  await expect(close).toHaveCSS('border-radius', '8px');
}

async function openTransactions(page: Page): Promise<Locator> {
  await page.getByRole('button', { name: /View all transactions/ }).click();
  return page.getByRole('dialog', { name: 'All transactions' });
}

test('dashboard panels share the established frame and heading scale', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();

  for (const selector of [
    '.trend-panel',
    '.cards-panel',
    '.categories-panel',
    '.observations-panel-preview',
    '.recurring-panel-preview',
    '.events-panel-preview',
    '.transactions-panel',
  ]) {
    await expect(page.locator(selector)).toHaveCSS('border-radius', '14px');
  }

  for (const selector of [
    '.trend-head h2',
    '.cards-head h2',
    '.categories-head h2',
    '.observations-head-preview h2',
    '.recurring-panel-head h2',
    '.events-title-line h2',
    '.transactions-head h2',
  ]) {
    await expect(page.locator(selector)).toHaveCSS('font-size', '15px');
  }
});

test('large dialogs, compact editors and their controls use defined visual tiers', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();

  const transactions = await openTransactions(page);
  await expectLargeDialog(transactions);

  const categoryButton = transactions.getByRole('button', { name: /^Change category for / }).first();
  await categoryButton.focus();
  await categoryButton.press('Enter');
  const editor = page.locator('.transaction-category-editor');
  await expect(editor).toBeVisible();
  await expect(editor.locator('h2')).toHaveCSS('font-size', '17px');
  await expect(editor.locator('select')).toHaveCSS('height', '36px');
  await expect(editor.getByRole('button', { name: 'Save correction' })).toHaveCSS('height', '34px');
  await expect(editor.getByRole('button', { name: 'Close category correction' })).toHaveCSS('width', '30px');
  await page.getByRole('button', { name: 'Close category correction' }).click();
  await page.getByRole('button', { name: 'Close transactions' }).click();

  await page.locator('.category-view-details').click();
  await expectLargeDialog(page.getByRole('dialog', { name: 'All categories' }));
});
