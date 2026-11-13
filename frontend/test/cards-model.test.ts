import assert from 'node:assert/strict';
import test from 'node:test';
import type { DashboardCard } from '../src/api/contracts.ts';
import { cardProviderClass, cardShareWidth, cardTransactionLabel } from '../src/features/cards/model.ts';

const card: DashboardCard = {
  key: 'max:1234',
  provider: 'max',
  product_name: 'Synthetic card',
  card_last4: '1234',
  amount: 500,
  share: 45.5,
  transactions: 1234,
};

test('bounds only the visual card-share width', () => {
  assert.equal(cardShareWidth(45.5), 45.5);
  assert.equal(cardShareWidth(140), 100);
  assert.equal(cardShareWidth(-12), 0);
});

test('preserves provider styling and transaction labels', () => {
  assert.equal(cardProviderClass(card), 'mastercard');
  assert.equal(cardProviderClass({ ...card, provider: 'isracard' }), 'standard');
  assert.equal(cardTransactionLabel(1234), '1,234 trx');
});
