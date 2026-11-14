import { expect, test } from '@playwright/test';

test.describe.serial('merchant and recurring management', () => {
  test('merchant display identity and exact-alias category changes persist', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Manage data' }).click();
    await page.getByRole('menuitem', { name: /Merchants/ }).click();

    const dialog = page.getByRole('dialog', { name: 'Merchants' });
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder('Search names and aliases…').fill('Synthetic Utilities');
    await dialog.locator('.merchant-list-item', { hasText: 'Synthetic Utilities' }).click();

    await dialog.getByLabel('Display name').fill('Synthetic Home Services');
    const southAlias = dialog.locator('.merchant-alias-table tbody tr', { hasText: 'Synthetic Utility South' });
    await southAlias.getByRole('combobox').selectOption('Transport');
    await expect(dialog.getByRole('button', { name: 'Apply changes' })).toBeDisabled();
    await dialog.getByRole('button', { name: 'Review impact' }).click();
    await expect(dialog.locator('.merchant-impact-review')).toContainText('Rename 2 exact aliases across 3 existing transactions');
    await expect(dialog.locator('.merchant-impact-review')).toContainText('Update permanent categories for 1 exact aliases');
    await dialog.getByRole('button', { name: 'Apply changes' }).click();
    await expect(dialog.getByRole('status')).toContainText('Synthetic Home Services saved');

    const response = await page.request.get('/api/merchants');
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    const merchant = payload.merchants.find((item: { canonical_group_id: string }) => item.canonical_group_id === 'synthetic-utilities');
    expect(merchant.display_name).toBe('Synthetic Home Services');
    expect(merchant.aliases.find((alias: { merchant_normalized: string }) => alias.merchant_normalized === 'synthetic utility south').category).toBe('Transport');
    expect(merchant.aliases.find((alias: { merchant_normalized: string }) => alias.merchant_normalized === 'synthetic utility north').category).toBe('Utilities');
  });

  test('recurring type, cadence, and lifecycle changes persist', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Manage data' }).click();
    await page.getByRole('menuitem', { name: /Merchants/ }).click();

    const dialog = page.getByRole('dialog', { name: 'Merchants' });
    await dialog.getByPlaceholder('Search names and aliases…').fill('Synthetic Gym');
    await dialog.locator('.merchant-list-item', { hasText: 'Synthetic Gym' }).click();
    const editor = dialog.locator('.merchant-recurring-editor');
    await expect(editor).toContainText('Recurring');
    await editor.getByLabel('Type').selectOption('Usage-based recurring');
    await editor.getByLabel('Cadence').selectOption('Quarterly');
    await editor.getByLabel('Lifecycle').selectOption('ended');
    await editor.getByLabel('End month').fill('2026-11');
    await editor.getByRole('button', { name: 'Save recurring settings' }).click();
    await expect(dialog.getByRole('status')).toContainText('Synthetic Gym recurring settings saved');

    const response = await page.request.get('/api/merchants');
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    const profile = payload.merchants.find((item: { canonical_group_id: string }) => item.canonical_group_id === 'synthetic-gym').recurring_profile;
    expect(profile).toMatchObject({
      verdict: 'recurring',
      recurring_type: 'Usage-based recurring',
      cadence: 'Quarterly',
      cadence_months: 3,
      lifecycle_status: 'ended',
      end_month: '2026-11',
      included_aliases: ['synthetic gym'],
    });
  });

  test('manage data exposes only the three primary destinations', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Manage data' }).click();
    const menu = page.getByRole('menu');
    await expect(menu.getByRole('menuitem')).toHaveCount(3);
    await expect(menu.getByRole('menuitem').allTextContents()).resolves.toEqual(expect.arrayContaining([
      expect.stringContaining('Import statements'),
      expect.stringContaining('Import history'),
      expect.stringContaining('Merchants'),
    ]));
  });
});
