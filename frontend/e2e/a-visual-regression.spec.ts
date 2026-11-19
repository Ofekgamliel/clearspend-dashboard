import { expect, test, type Page } from '@playwright/test';

const screenshotOptions = {
  animations: 'disabled' as const,
  maxDiffPixelRatio: 0.05,
};

async function openDashboard(page: Page): Promise<void> {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();
  await expect(page.locator('.categories-panel')).toBeVisible();
  await expect(page.locator('.events-panel-preview')).toBeVisible();
  await expect(page.locator('.observations-panel-preview')).not.toHaveAttribute('aria-busy', 'true');
}

test('main dashboard matches approved desktop and narrow layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDashboard(page);
  await expect(page).toHaveScreenshot('dashboard-desktop.png', { ...screenshotOptions, fullPage: true });

  await page.setViewportSize({ width: 430, height: 900 });
  await expect(page).toHaveScreenshot('dashboard-narrow.png', { ...screenshotOptions, fullPage: true });
});

test('transaction, import, and merchant modals match approved layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDashboard(page);

  await page.getByRole('button', { name: /View all transactions/ }).click();
  const transactions = page.getByRole('dialog', { name: 'All transactions' });
  await expect(transactions).toBeVisible();
  await expect(transactions).toHaveScreenshot('modal-transactions.png', screenshotOptions);
  await page.getByRole('button', { name: 'Close transactions' }).click();

  await page.getByRole('button', { name: 'Manage data' }).click();
  await page.getByRole('menuitem', { name: /Import statements/ }).click();
  const importDialog = page.getByRole('dialog', { name: 'Import statements' });
  await expect(importDialog).toBeVisible();
  await expect(importDialog).toHaveScreenshot('modal-import.png', screenshotOptions);
  await page.getByRole('button', { name: 'Close import' }).click();

  await page.getByRole('button', { name: 'Manage data' }).click();
  await page.getByRole('menuitem', { name: /Merchants/ }).click();
  const merchants = page.getByRole('dialog', { name: 'Merchants' });
  await expect(merchants).toBeVisible();
  await expect(merchants.locator('.merchant-list-item').first()).toBeVisible();
  await expect(merchants).toHaveScreenshot('modal-merchants.png', screenshotOptions);
});

test('recurring and observation modals match approved layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDashboard(page);

  await page.getByRole('button', { name: 'View all details →' }).click();
  const recurring = page.getByRole('dialog', { name: 'Recurring & commitments' });
  await expect(recurring).toBeVisible();
  await expect(recurring).toHaveScreenshot('modal-recurring.png', screenshotOptions);
  await page.getByRole('button', { name: 'Close recurring details' }).click();

  const observationCard = page.locator('.observation-card-preview').first();
  await expect(observationCard).toBeVisible();
  await observationCard.click();
  const observation = page.getByRole('dialog').first();
  await expect(observation).toBeVisible();
  await expect(observation).toHaveScreenshot('modal-observation.png', screenshotOptions);
});

test('event detail, edit, and create modals match approved layouts', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openDashboard(page);

  await page.locator('.event-card-preview').first().click();
  const detail = page.getByRole('dialog').first();
  await expect(detail).toBeVisible();
  await expect(detail).toHaveScreenshot('modal-event-detail.png', screenshotOptions);
  await detail.getByRole('button', { name: 'Edit event' }).click();
  const edit = page.getByRole('dialog', { name: 'Edit event' });
  await expect(edit).toBeVisible();
  await expect(edit).toHaveScreenshot('modal-event-edit.png', screenshotOptions);
  await page.getByRole('button', { name: 'Close event editor' }).click();
  await page.getByRole('button', { name: 'Close event' }).click();

  await page.getByRole('button', { name: /New event/ }).click();
  const create = page.getByRole('dialog', { name: 'Create new event' });
  await expect(create).toBeVisible();
  await expect(create).toHaveScreenshot('modal-event-create.png', screenshotOptions);
});
