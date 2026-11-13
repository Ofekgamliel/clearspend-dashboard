const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildObservationsUrl,
  loadObservationPayload,
} = require('../../dist/observation-client.js');

test('observation endpoint URL includes the selected scope and income visibility', () => {
  assert.equal(
    buildObservationsUrl({
      period: 'latest',
      card: 'Visa 8522',
      month: '2026-11',
      incomeHidden: true,
    }),
    '/api/observations?period=latest&card=Visa+8522&month=2026-11&income_hidden=true',
  );
});

test('observation loader uses the consolidated backend payload first', async () => {
  let fallbackCalled = false;
  const result = await loadObservationPayload(
    async url => ({ url, findings: [{ type: 'TEST' }] }),
    { period: 'month', card: 'all', month: '2026-11', incomeHidden: false },
    async () => {
      fallbackCalled = true;
      return { findings: [] };
    },
  );

  assert.equal(result.source, 'backend');
  assert.equal(result.payload.findings[0].type, 'TEST');
  assert.equal(fallbackCalled, false);
});

test('observation loader preserves the browser engine as an automatic fallback', async () => {
  const backendError = new Error('Endpoint unavailable');
  const result = await loadObservationPayload(
    async () => { throw backendError; },
    { period: 'all', card: 'all', month: '2026-11' },
    async error => ({ findings: [{ type: 'LEGACY' }], receivedError: error }),
  );

  assert.equal(result.source, 'browser-fallback');
  assert.equal(result.payload.findings[0].type, 'LEGACY');
  assert.equal(result.payload.receivedError, backendError);
  assert.equal(result.backendError, backendError);
});
