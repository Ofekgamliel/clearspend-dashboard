import { expect, test } from '@playwright/test';

test('healthy runtime mounts progressive skeletons before dashboard data settles', async ({ page }) => {
  let releaseDashboard!: () => void;
  const dashboardGate = new Promise<void>((resolve) => { releaseDashboard = resolve; });
  let releaseRecurring!: () => void;
  const recurringGate = new Promise<void>((resolve) => { releaseRecurring = resolve; });
  const featureRequests = new Set<string>();

  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (['/api/categories', '/api/events', '/api/recurring', '/api/observations'].includes(path)) featureRequests.add(path);
  });
  await page.route('**/api/dashboard?**', async (route) => {
    await dashboardGate;
    await route.continue();
  });
  await page.route('**/api/recurring?**', async (route) => {
    await recurringGate;
    await route.continue();
  });

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.locator('.income-skeleton')).toBeVisible();
  await expect(page.locator('.metric-card-skeleton')).toHaveCount(4);
  await expect(page.locator('.trend-skeleton')).toBeVisible();
  await expect(page.locator('.transaction-skeleton-row')).toHaveCount(5);
  const skeletonAnimation = await page.locator('.income-skeleton .ui-skeleton').first().evaluate((element) =>
    getComputedStyle(element, '::after').display,
  );
  expect(skeletonAnimation).toBe('none');
  await expect.poll(() => [...featureRequests].sort()).toEqual([
    '/api/categories', '/api/events', '/api/observations', '/api/recurring',
  ]);
  await expect(page.locator('.income-panel')).not.toContainText(/₪\s*[\d,.]+/);
  await expect(page.getByRole('button', { name: 'View all details' })).toBeDisabled();

  releaseDashboard();
  releaseRecurring();
  await expect(page.locator('.income-skeleton')).toHaveCount(0);
  await expect(page.locator('.metric-value').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'View all details' })).toBeEnabled();
});

test('the income skeleton follows the narrow one-column layout', async ({ page }) => {
  let releaseDashboard!: () => void;
  const dashboardGate = new Promise<void>((resolve) => { releaseDashboard = resolve; });
  await page.route('**/api/dashboard?**', async (route) => {
    await dashboardGate;
    await route.continue();
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const columns = await page.locator('.income-skeleton-metrics').evaluate((element) =>
    getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/),
  );
  expect(columns).toHaveLength(1);
  await expect(page.locator('.income-skeleton-metrics > div').nth(1)).toHaveCSS('border-left-width', '0px');
  releaseDashboard();
  await expect(page.locator('.income-skeleton')).toHaveCount(0);
});

test('skeleton tokens remain distinct in alternate light and dark themes', async ({ page }) => {
  let releaseDashboard!: () => void;
  const dashboardGate = new Promise<void>((resolve) => { releaseDashboard = resolve; });
  await page.route('**/api/dashboard?**', async (route) => {
    await dashboardGate;
    await route.continue();
  });
  await page.goto('/');

  for (const theme of ['Clay & sky', 'Graphite & amber']) {
    await page.getByRole('button', { name: 'Choose dashboard colors' }).click();
    await page.getByRole('menuitemradio', { name: new RegExp(theme.replace('&', '\\&')) }).click();
    const colors = await page.locator('.income-skeleton .ui-skeleton').first().evaluate((element) => ({
      base: getComputedStyle(element).backgroundColor,
      highlight: getComputedStyle(element, '::after').backgroundImage,
      scheme: getComputedStyle(document.documentElement).colorScheme,
    }));
    expect(colors.base).not.toBe('rgba(0, 0, 0, 0)');
    expect(colors.highlight).not.toBe('none');
    expect(colors.highlight).not.toContain(colors.base);
    expect(colors.scheme).toBe(theme === 'Graphite & amber' ? 'dark' : 'light');
  }

  releaseDashboard();
  await expect(page.locator('.income-skeleton')).toHaveCount(0);
});

test('a reporting-scope change removes old financial values while its response is pending', async ({ page }) => {
  await page.goto('/');
  const previousMetric = await page.locator('.metric-value').first().innerText();
  let releaseDashboard!: () => void;
  const dashboardGate = new Promise<void>((resolve) => { releaseDashboard = resolve; });
  await page.route('**/api/dashboard?**', async (route) => {
    if (new URL(route.request().url()).searchParams.get('period') !== 'year') {
      await route.continue();
      return;
    }
    await dashboardGate;
    await route.continue();
  });

  await page.getByRole('button', { name: 'Latest year' }).click();
  await expect(page.locator('.metric-card-skeleton')).toHaveCount(4);
  await expect(page.locator('.metrics-grid')).not.toContainText(previousMetric);
  await expect(page.getByRole('status')).toContainText('Updating dashboard for Latest year');

  releaseDashboard();
  await expect(page.locator('.metric-card-skeleton')).toHaveCount(0);
});

test('feature-local scope changes remove category and income-sensitive observation content', async ({ page }) => {
  await page.goto('/');
  const categoryText = await page.locator('.category-row').first().innerText();
  const observation = page.locator('.observation-card-preview').first();
  await expect(observation).toBeVisible();
  const observationText = await observation.innerText();

  let releaseCategories!: () => void;
  const categoriesGate = new Promise<void>((resolve) => { releaseCategories = resolve; });
  await page.route('**/api/categories?**', async (route) => {
    if (new URL(route.request().url()).searchParams.get('event_scope') !== 'routine') {
      await route.continue();
      return;
    }
    await categoriesGate;
    await route.continue();
  });
  await page.getByRole('button', { name: 'Routine only' }).click();
  await expect(page.locator('.categories-skeleton')).toBeVisible();
  await expect(page.locator('.categories-panel')).not.toContainText(categoryText);
  releaseCategories();
  await expect(page.locator('.categories-skeleton')).toHaveCount(0);

  let releaseObservations!: () => void;
  const observationsGate = new Promise<void>((resolve) => { releaseObservations = resolve; });
  await page.route('**/api/observations?**', async (route) => {
    if (new URL(route.request().url()).searchParams.get('income_hidden') !== 'true') {
      await route.continue();
      return;
    }
    await observationsGate;
    await route.continue();
  });
  await page.getByRole('button', { name: 'Hide income values' }).click();
  await expect(page.locator('.observations-skeleton')).toBeVisible();
  await expect(page.locator('.observations-panel-preview')).not.toContainText(observationText);
  releaseObservations();
  await expect(page.locator('.observations-skeleton')).toHaveCount(0);
});

test('a failed scope change ends skeletons without restoring stale values', async ({ page }) => {
  await page.goto('/');
  const previousMetric = await page.locator('.metric-value').first().innerText();
  let failRequest = true;
  await page.route('**/api/dashboard?**', async (route) => {
    if (new URL(route.request().url()).searchParams.get('period') !== 'year') {
      await route.continue();
      return;
    }
    if (failRequest) {
      failRequest = false;
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Synthetic dashboard failure' }),
      });
      return;
    }
    await route.continue();
  });

  await page.getByRole('button', { name: 'Latest year' }).click();
  await expect(page.locator('.dashboard-load-error')).toContainText('Synthetic dashboard failure');
  await expect(page.locator('.metric-card-skeleton')).toHaveCount(0);
  await expect(page.locator('.metrics-grid')).toHaveCount(0);
  await expect(page.locator('.categories-panel')).toBeVisible();
  await expect(page.locator('main').getByRole('alert')).toHaveCount(1);
  await page.locator('.dashboard-load-error').getByRole('button', { name: 'Retry' }).click();
  await expect(page.locator('.dashboard-load-error')).toHaveCount(0);
  await expect(page.locator('.metric-value').first()).toBeVisible();
  await expect(page.locator('.metrics-grid')).not.toContainText(previousMetric);
});

test('a late independent-panel response cannot replace the newest category scope', async ({ page }) => {
  await page.goto('/');
  let releaseRoutine!: () => void;
  const routineGate = new Promise<void>((resolve) => { releaseRoutine = resolve; });
  await page.route('**/api/categories?**', async (route) => {
    const scope = new URL(route.request().url()).searchParams.get('event_scope');
    if (scope === 'routine') await routineGate;
    const response = await route.fetch();
    const payload = await response.json();
    if (payload.categories.length) {
      payload.categories[0].amount = scope === 'routine' ? 111_111 : 222_222;
      payload.total = payload.categories.reduce((sum: number, item: { amount: number }) => sum + item.amount, 0);
    }
    await route.fulfill({ response, json: payload });
  });

  await page.getByRole('button', { name: 'Routine only' }).click();
  await expect(page.locator('.categories-skeleton')).toBeVisible();
  await page.getByRole('button', { name: 'All spending' }).click();
  await expect(page.locator('.categories-panel')).toContainText('222,222');
  releaseRoutine();
  await expect(page.getByRole('button', { name: 'All spending' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.categories-panel')).toContainText('222,222');
  await expect(page.locator('.categories-panel')).not.toContainText('111,111');
});

test('a late response for an older scope cannot replace the newest selection', async ({ page }) => {
  await page.goto('/');
  let releaseYear!: () => void;
  const yearGate = new Promise<void>((resolve) => { releaseYear = resolve; });
  await page.route('**/api/dashboard?**', async (route) => {
    const period = new URL(route.request().url()).searchParams.get('period');
    if (!['year', 'all'].includes(period ?? '')) {
      await route.continue();
      return;
    }
    if (period === 'year') await yearGate;
    const response = await route.fetch();
    const payload = await response.json();
    payload.metrics.spent = period === 'year' ? 111_111 : 222_222;
    await route.fulfill({ response, json: payload });
  });

  await page.getByRole('button', { name: 'Latest year' }).click();
  await page.getByRole('button', { name: 'All time' }).click();
  await expect(page.locator('.metric-value').first()).toContainText('222,222');
  releaseYear();
  await expect(page.getByRole('button', { name: 'All time' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.metric-value').first()).toContainText('222,222');
  await expect(page.locator('.metrics-grid')).not.toContainText('111,111');
});
