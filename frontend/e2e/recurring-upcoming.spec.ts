import { expect, test } from '@playwright/test';

test('Upcoming is lazy, month-local, and scoped only by card', async ({ page }) => {
  const upcomingRequests: string[] = [];
  page.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/recurring?') && url.includes('view=upcoming')) {
      upcomingRequests.push(url);
    }
  });

  await page.goto('/');
  const panel = page.locator('.recurring-panel-preview');
  await expect(panel).not.toHaveAttribute('aria-busy', 'true');
  expect(upcomingRequests).toHaveLength(0);
  const overviewHeight = await panel.evaluate((element) => Math.round(element.getBoundingClientRect().height));
  const overviewSwitchX = await panel.locator('.recurring-view-switch').evaluate((element) => Math.round(element.getBoundingClientRect().x));

  await panel.getByRole('button', { name: 'Upcoming', exact: true }).click();
  await expect(panel.locator('.recurring-upcoming-months button')).toHaveCount(3);
  await expect(panel).not.toContainText('estimates and confirmed charges');
  const upcomingSwitchX = await panel.locator('.recurring-view-switch').evaluate((element) => Math.round(element.getBoundingClientRect().x));
  expect(upcomingSwitchX).toBe(overviewSwitchX);
  const paymentList = panel.getByRole('region', { name: /expected payments/ });
  await expect(paymentList).toHaveAttribute('tabindex', '0');
  const upcomingHeight = await panel.evaluate((element) => Math.round(element.getBoundingClientRect().height));
  expect(Math.abs(upcomingHeight - overviewHeight)).toBeLessThanOrEqual(1);
  await expect.poll(() => upcomingRequests.length).toBe(1);
  expect(upcomingRequests[0]).toContain('card=all');

  const secondMonth = panel.locator('.recurring-upcoming-months button').nth(1);
  await secondMonth.click();
  await expect(secondMonth).toHaveAttribute('aria-pressed', 'true');
  expect(upcomingRequests).toHaveLength(1);

  await page.getByRole('button', { name: 'Latest year' }).click();
  await expect(page.getByRole('button', { name: 'Latest year' })).toHaveAttribute('aria-pressed', 'true');
  expect(upcomingRequests).toHaveLength(1);

  await page.getByRole('button', { name: 'Choose card' }).click();
  await page.getByRole('option', { name: /Synthetic MAX/ }).click();
  await expect.poll(() => upcomingRequests.length).toBe(2);
  expect(upcomingRequests[1]).toContain('card=max%3A0001');
});

test('Upcoming keeps dense and unresolved content bounded across responsive layouts', async ({ page }) => {
  await page.route('**/api/recurring?*', async (route) => {
    if (!route.request().url().includes('view=upcoming')) {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    const payload = await response.json();
    const month = payload.months[0];
    const source = month.payments[0];
    month.payments = Array.from({ length: 8 }, (_, index) => ({
      ...source,
      occurrence_id: `${source.occurrence_id}-stress-${index}`,
      display_name: index === 0 ? 'A deliberately long recurring payment name' : `${source.display_name} ${index + 1}`,
      annual: index === 1,
      ending: index === 2,
    }));
    month.payment_count = month.payments.length;
    month.annual_count = 1;
    month.ending_installment_count = 1;
    month.comparison_label = 'highest_known_estimate';
    payload.unresolved = Array.from({ length: 8 }, (_, index) => ({
      source_kind: 'recurring_profile',
      source_id: `stress-unresolved-${index}`,
      display_name: `Unresolved recurring source ${index + 1}`,
      card: null,
      reason: 'ambiguous_phase',
    }));
    await route.fulfill({ response, json: payload });
  });

  await page.setViewportSize({ width: 900, height: 900 });
  await page.goto('/');
  const panel = page.locator('.recurring-panel-preview');
  await expect(panel).not.toHaveAttribute('aria-busy', 'true');
  const overviewHeight = await panel.evaluate((element) => Math.round(element.getBoundingClientRect().height));
  await panel.getByRole('button', { name: 'Upcoming', exact: true }).click();

  const paymentList = panel.getByRole('region', { name: /expected payments/ });
  await expect(paymentList).toBeVisible();
  const paymentAlignment = await panel.locator('.recurring-upcoming-payment-name').first().evaluate((element) => ({
    merchant: getComputedStyle(element.querySelector('strong')!).textAlign,
    card: getComputedStyle(element.querySelector('small')!).textAlign,
    baselineDifference: Math.abs(
      element.querySelector('strong')!.getBoundingClientRect().bottom
      - element.querySelector('small')!.getBoundingClientRect().bottom,
    ),
  }));
  expect(paymentAlignment.merchant).toBe('right');
  expect(paymentAlignment.card).toBe('left');
  expect(paymentAlignment.baselineDifference).toBeLessThanOrEqual(2);
  expect(await paymentList.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  const upcomingHeight = await panel.evaluate((element) => Math.round(element.getBoundingClientRect().height));
  expect(upcomingHeight).toBe(overviewHeight);

  await panel.locator('.recurring-unresolved summary').click();
  expect(await panel.evaluate((element) => Math.round(element.getBoundingClientRect().height))).toBe(overviewHeight);
  const unresolvedList = panel.getByRole('region', { name: 'Sources not forecast' });
  expect(await unresolvedList.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);

  const monthStrip = panel.locator('.recurring-upcoming-months');
  expect(await monthStrip.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
  const cardsFit = await monthStrip.locator('button').evaluateAll((cards) => cards.every((card) => card.scrollWidth <= card.clientWidth));
  expect(cardsFit).toBe(true);

  await page.setViewportSize({ width: 430, height: 900 });
  await page.reload();
  await panel.getByRole('button', { name: 'Upcoming', exact: true }).click();
  await expect(panel.locator('.recurring-upcoming-columns')).toBeHidden();
  const panelOverflow = await panel.evaluate((element) => {
    const boundary = element.getBoundingClientRect();
    return [...element.querySelectorAll<HTMLElement>('*')]
      .filter((child) => !child.closest('.recurring-upcoming-months'))
      .filter((child) => child.getBoundingClientRect().right > boundary.right + 1)
      .map((child) => child.className || child.tagName);
  });
  expect(panelOverflow).toEqual([]);
  await expect(panel).toHaveScreenshot('recurring-upcoming-narrow.png', {
    animations: 'disabled', maxDiffPixelRatio: 0.05,
  });
});
