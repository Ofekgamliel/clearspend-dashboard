import { expect, test } from '@playwright/test';

test('promoted palette applies and persists from the main picker', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();
  await page.getByRole('button', { name: 'Choose dashboard colors' }).click();
  await page.getByRole('menuitemradio', { name: /Ruby night/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', 'ruby');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', 'ruby');
});

test('selected palette persists and reaches import and merchant modal content', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();

  await page.getByRole('button', { name: 'Choose dashboard colors' }).click();
  await page.getByRole('menuitemradio', { name: /Graphite & amber/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', 'graphite');

  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', 'graphite');
  await expect(page.locator('.income-panel')).toBeVisible();

  await page.getByRole('button', { name: 'Manage data' }).click();
  await page.getByRole('menuitem', { name: /Import statements/ }).click();
  const importDialog = page.getByRole('dialog', { name: 'Import statements' });
  await expect(importDialog).toBeVisible();
  expect(await importDialog.locator('.import-drop').evaluate((element) => {
    const probe = document.createElement('i');
    probe.style.backgroundColor = 'var(--ui-surface-hover)';
    document.body.append(probe);
    const matches = getComputedStyle(element).backgroundColor === getComputedStyle(probe).backgroundColor;
    probe.remove();
    return matches;
  })).toBe(true);
  await page.getByRole('button', { name: 'Close import' }).click();

  await page.getByRole('button', { name: 'Manage data' }).click();
  await page.getByRole('menuitem', { name: /Merchants/ }).click();
  const merchantDialog = page.getByRole('dialog', { name: 'Merchants' });
  await expect(merchantDialog.locator('.merchant-list-item').first()).toBeVisible();
  expect(await merchantDialog.locator('.merchant-manager-summary span').first().evaluate((element) => {
    const probe = document.createElement('i');
    probe.style.backgroundColor = 'var(--ui-surface)';
    document.body.append(probe);
    const matches = getComputedStyle(element).backgroundColor === getComputedStyle(probe).backgroundColor;
    probe.remove();
    return matches;
  })).toBe(true);
});
