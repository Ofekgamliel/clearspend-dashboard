import { expect, test } from '@playwright/test';
import { tmpdir } from 'node:os';
import path from 'node:path';

test('all five import stages review and commit a synthetic statement', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Manage data' }).click();
  await page.getByRole('menuitem', { name: /Import statements/ }).click();

  const dialog = page.getByRole('dialog', { name: 'Import statements' });
  await expect(dialog).toBeVisible();
  const steps = dialog.getByRole('navigation', { name: 'Import steps' });
  await expect(steps.getByRole('button', { name: /1 Files/ })).toHaveClass(/active/);
  await dialog.locator('input[type="file"]').setInputFiles(path.join(tmpdir(), 'clearspend-browser-e2e-statement.xlsx'));

  await expect(steps.getByRole('button', { name: /2 Checks/ })).toHaveClass(/active/);
  await expect(dialog.getByText('1 files staged. Nothing was added to the database.')).toBeVisible();
  await expect(dialog.locator('.import-metrics')).toContainText('Parsed rows1');
  await expect(dialog.locator('.import-metrics')).toContainText('Confirmed new1');
  await expect(dialog.getByText('No exact duplicates found.')).toBeVisible();
  await expect(dialog.getByText('No uncertain matches need review.')).toBeVisible();
  await dialog.getByRole('button', { name: 'Continue' }).click();

  await expect(steps.getByRole('button', { name: /3 Merchants/ })).toHaveClass(/active/);
  const merchantRow = dialog.locator('.merchant-decisions tbody tr', { hasText: 'Synthetic Browser Import' });
  await expect(merchantRow).toBeVisible();
  await merchantRow.locator('td').nth(2).getByRole('combobox').selectOption('create');
  await merchantRow.locator('td').nth(3).getByRole('combobox').selectOption('Utilities');
  await merchantRow.locator('td').nth(5).getByRole('combobox').selectOption('exact');
  await dialog.getByRole('button', { name: 'Continue' }).click();

  await expect(steps.getByRole('button', { name: /4 Reconcile/ })).toHaveClass(/active/);
  const reconciliation = dialog.locator('.import-table-wrap table tbody tr', { hasText: 'clearspend-browser-e2e-statement.xlsx' });
  await expect(reconciliation).toContainText('₪300.00');
  await expect(reconciliation).toContainText('Matched');
  await dialog.getByRole('button', { name: 'Continue' }).click();

  await expect(steps.getByRole('button', { name: /5 Approve/ })).toHaveClass(/active/);
  await expect(dialog.locator('.import-preview tbody tr', { hasText: 'Synthetic Browser Import' })).toContainText('Utilities');
  await expect(dialog.getByText('Nothing has been added yet. Approve & import is the only action that writes this batch.')).toBeVisible();
  await dialog.getByRole('button', { name: 'Approve & import' }).click();
  await expect(dialog).toBeHidden();

  const transactions = await page.request.get('/api/transactions?period=all&month=&card=all&q=synthetic%20browser%20import&category=&event_scope=all');
  expect(transactions.ok()).toBeTruthy();
  const transactionPayload = await transactions.json();
  expect(transactionPayload.transactions).toHaveLength(1);
  expect(transactionPayload.transactions[0]).toMatchObject({
    merchant_raw: 'Synthetic Browser Import',
    category: 'Utilities',
    card_last4: '0003',
    billing_month: '2030-12',
  });

  const audit = await page.request.get('/api/mapping');
  expect(audit.ok()).toBeTruthy();
  const auditPayload = await audit.json();
  expect(auditPayload.recent_imports[0]).toMatchObject({
    original_name: 'clearspend-browser-e2e-statement.xlsx',
    inserted_rows: 1,
    duplicate_rows: 0,
  });
});
