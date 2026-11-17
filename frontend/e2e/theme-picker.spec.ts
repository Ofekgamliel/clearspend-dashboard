import { expect, test } from '@playwright/test';

const palettes = [
  ['current', 'Current violet', 'rgb(246, 246, 251)', 'rgb(255, 255, 255)', 'rgb(102, 88, 232)'],
  ['forest', 'Forest & lime', 'rgb(241, 243, 235)', 'rgb(255, 254, 249)', 'rgb(44, 101, 77)'],
  ['midnight', 'Midnight & aqua', 'rgb(7, 21, 26)', 'rgb(16, 36, 42)', 'rgb(86, 227, 186)'],
  ['clay', 'Clay & sky', 'rgb(246, 238, 232)', 'rgb(255, 250, 246)', 'rgb(173, 75, 53)'],
  ['plum', 'Plum & apricot', 'rgb(245, 239, 245)', 'rgb(255, 250, 255)', 'rgb(115, 63, 115)'],
  ['ocean', 'Ocean & mint', 'rgb(234, 243, 243)', 'rgb(251, 255, 255)', 'rgb(8, 127, 140)'],
  ['rose', 'Rose & gold', 'rgb(248, 239, 237)', 'rgb(255, 250, 248)', 'rgb(163, 63, 93)'],
  ['cobalt', 'Cobalt & lemon', 'rgb(237, 241, 248)', 'rgb(252, 253, 255)', 'rgb(40, 94, 209)'],
  ['sage', 'Sage & terracotta', 'rgb(241, 240, 233)', 'rgb(253, 252, 247)', 'rgb(100, 118, 90)'],
  ['graphite', 'Graphite & amber', 'rgb(17, 19, 21)', 'rgb(27, 30, 33)', 'rgb(224, 165, 59)'],
  ['navy', 'Navy & coral', 'rgb(11, 21, 40)', 'rgb(19, 33, 58)', 'rgb(255, 128, 108)'],
  ['sand', 'Sand & teal', 'rgb(244, 240, 229)', 'rgb(255, 253, 247)', 'rgb(20, 125, 120)'],
] as const;

test('chooses and persists every dashboard palette', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();

  for (const [id, label, pageColor, panelColor, chartColor] of palettes) {
    await page.getByRole('button', { name: 'Choose color theme' }).click();
    await page.getByRole('menuitemradio', { name: new RegExp(`^${label}`) }).click();
    await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', id);
    await expect(page.locator('body')).toHaveCSS('background-color', pageColor);
    await expect(page.locator('.income-panel')).toHaveCSS('background-color', panelColor);
    await expect(page.locator('.category-dot').first()).toHaveCSS('background-color', chartColor);
    await expect(page.locator('.trend-category-segment[fill="var(--theme-chart-1)"]').first()).toHaveCSS('fill', chartColor);
    expect(await page.locator('.category-donut').evaluate((element) => getComputedStyle(element).backgroundImage)).toContain(chartColor);
  }

  expect(await page.evaluate(() => localStorage.getItem('clearspend-color-theme'))).toBe('sand');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', 'sand');
  await expect(page.locator('.income-panel')).toBeVisible();
});

test('theme menu is keyboard dismissible and fits the narrow dashboard', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 900 });
  await page.goto('/');
  const trigger = page.getByRole('button', { name: 'Choose color theme' });
  await trigger.click();
  const menu = page.getByRole('menu', { name: 'Color themes' });
  await expect(menu).toBeVisible();
  const box = await menu.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(430);
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await expect(trigger).toBeFocused();
});

test('privacy-mode income allocation follows every selected palette', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Hide income values' }).click();
  await expect(page.locator('.income-hidden-allocation')).toBeVisible();
  const observed = new Set<string>();

  for (const [id, label] of palettes) {
    await page.getByRole('button', { name: 'Choose color theme' }).click();
    await page.getByRole('menuitemradio', { name: new RegExp(`^${label}`) }).click();
    await expect(page.locator('html')).toHaveAttribute('data-clearspend-theme', id);
    const colors = await page.locator('.income-hidden-allocation').evaluate((element) => {
      const segments = element.querySelectorAll('span');
      return [
        getComputedStyle(element).backgroundColor,
        getComputedStyle(segments[0]).backgroundColor,
        getComputedStyle(segments[1]).backgroundColor,
      ];
    });
    expect(colors).not.toContain('rgb(222, 217, 244)');
    expect(colors).not.toContain('rgb(226, 242, 235)');
    expect(colors[1]).not.toBe(colors[0]);
    expect(colors[2]).not.toBe(colors[0]);
    observed.add(colors.join('|'));
  }

  expect(observed.size).toBe(palettes.length);
});

test('dark palettes cover dashboard dialogs and nested transaction editors', async ({ page }) => {
  test.setTimeout(60_000);
  await page.addInitScript(() => localStorage.setItem('clearspend-color-theme', 'graphite'));
  await page.goto('/');
  await expect(page.locator('.income-panel')).toBeVisible();

  async function expectThemed(selector: string): Promise<void> {
    const surface = page.locator(selector);
    await expect(surface).toBeVisible();
    await expect(surface).toHaveCSS('background-color', 'rgb(27, 30, 33)');
    await expect(surface).toHaveCSS('color', 'rgb(240, 242, 242)');
  }

  await page.getByRole('button', { name: /View all transactions/ }).click();
  await expectThemed('.transactions-modal');
  const transactionDialog = page.getByRole('dialog', { name: 'All transactions' });
  const categoryButton = transactionDialog.getByRole('button', { name: /^Change category for / }).first();
  await categoryButton.focus();
  await categoryButton.press('Enter');
  await expectThemed('.transaction-category-editor');
  await page.getByRole('button', { name: 'Close category correction' }).click();
  await transactionDialog.getByRole('button', { name: /^Adjust spending for / }).first().click();
  await expectThemed('.transaction-adjustment-editor');
  await page.getByRole('button', { name: 'Close spending adjustment' }).click();
  await page.getByRole('button', { name: 'Close transactions' }).click();

  await page.locator('.category-view-details').click();
  await expectThemed('.category-overview-modal');
  await page.getByRole('button', { name: 'Close category overview' }).click();

  await page.getByRole('button', { name: 'View all details →' }).click();
  await expectThemed('.recurring-modal-preview');
  await page.getByRole('button', { name: 'Close recurring details' }).click();

  await page.locator('.observation-card-preview').first().click();
  await expectThemed('.observation-modal-preview');
  await page.getByRole('button', { name: 'Close observation details' }).click();

  await page.getByRole('button', { name: /New event/ }).click();
  await expectThemed('.event-create-modal-preview');
  await page.getByRole('button', { name: 'Close event creation' }).click();

  for (const [menuLabel, selector, closeLabel] of [
    [/Import statements/, '.import-manager', 'Close import'],
    [/Import history/, '.import-audit-modal', 'Close import history'],
    [/Merchants/, '.merchant-manager', 'Close merchant management'],
  ] as const) {
    await page.getByRole('button', { name: 'Manage data' }).click();
    await page.getByRole('menuitem', { name: menuLabel }).click();
    await expectThemed(selector);
    await page.getByRole('button', { name: closeLabel }).click();
  }
});
