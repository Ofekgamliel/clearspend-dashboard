import { expect, test } from '@playwright/test';

test('event creation and editing persist through the production UI', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'New event' }).click();
  const create = page.getByRole('dialog', { name: 'Create new event' });
  await create.getByLabel('Name').fill('Synthetic Review Event');
  await create.getByLabel('Type').selectOption('other');
  await create.getByLabel('Start date').fill('2026-11-20');
  await create.getByLabel('End date').fill('2026-11-21');
  await create.getByLabel('Budget').fill('900');
  await create.getByLabel('Status').selectOption('planned');
  await create.getByRole('button', { name: 'Create event' }).click();

  await expect(page.getByRole('status')).toContainText('Event created');
  const eventCard = page.locator('.event-card-preview', { hasText: 'Synthetic Review Event' });
  await expect(eventCard).toBeVisible();
  await eventCard.click();

  const detail = page.getByRole('dialog', { name: 'Synthetic Review Event' });
  await detail.getByRole('button', { name: 'Edit event' }).click();
  const edit = page.getByRole('dialog', { name: 'Edit event' });
  await edit.getByLabel('Name').fill('Synthetic Reviewed Event');
  await edit.getByLabel('Budget').fill('1200');
  await edit.getByLabel('Status').selectOption('completed');
  await edit.getByRole('button', { name: 'Save changes' }).click();

  await expect(page.getByRole('status')).toContainText('Event updated');
  await expect(page.getByRole('dialog', { name: 'Synthetic Reviewed Event' })).toBeVisible();

  const response = await page.request.get('/api/events?period=month&month=2026-11&card=all');
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  const persisted = payload.events.find((item: { name: string }) => item.name === 'Synthetic Reviewed Event');
  expect(persisted).toMatchObject({
    event_type: 'other',
    start_date: '2026-11-20',
    end_date: '2026-11-21',
    status: 'completed',
  });
  expect(Number(persisted.budget)).toBe(1200);
});

test('observation review and undo persist through the production API', async ({ page }) => {
  await page.goto('/');
  const transactionsResponse = await page.request.get(
    '/api/transactions?period=month&month=2026-11&card=all&q=market&category=&event_scope=all',
  );
  expect(transactionsResponse.ok()).toBeTruthy();
  const transactions = (await transactionsResponse.json()).transactions;
  const transactionId = transactions[0].id;
  const findingKey = `UNUSUAL TRANSACTION:${transactionId}`;
  const review = {
    finding_key: findingKey,
    observation_type: 'UNUSUAL TRANSACTION',
    resolution: 'not_unusual',
    month: '2026-11',
    transaction_ids: [transactionId],
    recurring_series_id: '',
    occurrence_start: '',
    occurrence_end: '',
    merchant_label: 'Synthetic Market',
    remove: false,
  };

  const saved = await page.request.post('/api/observation-review', { data: review });
  expect(saved.ok()).toBeTruthy();
  await expect.poll(async () => {
    const response = await page.request.get('/api/observation-reviews');
    const payload = await response.json();
    return payload.reviews.some((item: { finding_key: string }) => item.finding_key === findingKey);
  }).toBeTruthy();

  const restored = await page.request.post('/api/observation-review', {
    data: { ...review, remove: true },
  });
  expect(restored.ok()).toBeTruthy();
  await expect.poll(async () => {
    const response = await page.request.get('/api/observation-reviews');
    const payload = await response.json();
    return payload.reviews.some((item: { finding_key: string }) => item.finding_key === findingKey);
  }).toBeFalsy();
});
