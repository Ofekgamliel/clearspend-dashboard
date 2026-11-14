import { expect, test } from '@playwright/test';

test('category drill-down opens grouped merchants and individual source rows', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.categories-panel')).toBeVisible();
  await page.getByRole('button', { name: 'View transactions in Food & groceries' }).click();

  const dialog = page.getByRole('dialog', { name: 'Food & groceries' });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.merchant-group-row td:first-child strong').first()).toHaveCSS('text-align', 'left');
  await expect(dialog.getByRole('button', { name: 'By merchant' })).toHaveAttribute('aria-pressed', 'true');
  await expect(dialog.locator('.merchant-group-row', { hasText: 'Synthetic Market' })).toContainText('1');

  await dialog.getByRole('button', { name: 'Expand Synthetic Market' }).click();
  await expect(dialog.locator('.merchant-group-detail-row')).toContainText('Synthetic Market');
  await expect(dialog.locator('.merchant-group-detail-row')).toContainText('3 Nov 26');

  await dialog.getByRole('button', { name: 'Individual' }).click();
  await expect(dialog.locator('.transaction-source-table tbody tr', { hasText: 'Synthetic Market' })).toHaveCount(1);
});

test('search, sorting, category correction, reimbursement, and event assignment persist', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'All time' }).click();
  await page.getByRole('button', { name: /View all transactions/ }).click();
  const dialog = page.getByRole('dialog', { name: 'All transactions' });
  const search = dialog.getByPlaceholder('Search every merchant, display name or category…');
  await search.fill('market');
  await expect(dialog.locator('.transactions-modal-summary strong')).toHaveText('2 matches');

  const table = dialog.locator('.transaction-source-table');
  const dateHeader = table.getByRole('columnheader', { name: /Transaction date/ });
  await expect(dateHeader).toHaveAttribute('aria-sort', 'descending');
  await dateHeader.getByRole('button').click();
  await expect(dateHeader).toHaveAttribute('aria-sort', 'ascending');

  const marketRows = table.locator('tbody tr', { hasText: 'Synthetic Market' });
  await expect(marketRows).toHaveCount(2);
  await expect(marketRows.first()).toContainText('4 Oct 26');
  const targetRow = marketRows.first();

  const categoryButton = targetRow.getByRole('button', { name: 'Change category for Synthetic Market' });
  await categoryButton.focus();
  await categoryButton.click();
  const categoryDialog = page.getByRole('dialog', { name: 'Change transaction category' });
  await categoryDialog.getByLabel('New category').selectOption('Transport');
  await categoryDialog.getByRole('button', { name: 'Save correction' }).click();
  await expect(page.locator('.transaction-save-notice')).toContainText('Transaction corrected');
  await expect(targetRow).toContainText('Transport');
  await expect(targetRow).toContainText('One-off correction');

  await targetRow.getByRole('button', { name: 'Adjust spending for Synthetic Market' }).click();
  const adjustmentDialog = page.getByRole('dialog', { name: 'Mark as reimbursed' });
  await adjustmentDialog.getByLabel('Partially reimbursed').check();
  await adjustmentDialog.getByLabel('Reimbursed amount').fill('100');
  await adjustmentDialog.getByLabel('Reimbursement date').fill('2026-10-05');
  await adjustmentDialog.getByLabel('Note').fill('Synthetic shared purchase');
  await adjustmentDialog.getByRole('button', { name: 'Save adjustment' }).click();
  await expect(page.locator('.transaction-save-notice')).toContainText('Reimbursement saved');
  await expect(targetRow).toContainText('₪100.00 reimbursed');
  await expect(targetRow).toContainText('Personal: 320.5 ILS');

  await targetRow.getByRole('combobox', { name: 'Assign event for Synthetic Market' }).selectOption({ label: 'Synthetic Vienna 2026' });
  await expect(page.locator('.transaction-save-notice')).toContainText('Event assigned');
  await expect(targetRow.getByRole('combobox', { name: 'Change event for Synthetic Market' })).toHaveValue('synthetic-vienna-2026');

  const response = await page.request.get('/api/transactions?period=all&month=&card=all&q=market&category=&event_scope=all');
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  const changed = payload.transactions.find((item: { transaction_date: string }) => item.transaction_date === '2026-10-04');
  expect(changed).toMatchObject({
    category: 'Transport',
    category_source: 'transaction_override',
    adjustment_type: 'partial_reimbursement',
    reimbursed_amount: 100,
    personal_amount: 320.5,
    event_id: 'synthetic-vienna-2026',
  });
});
