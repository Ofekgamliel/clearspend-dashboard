const test = require('node:test');
const assert = require('node:assert/strict');

const { ApiError, getJson, postForm, postJson } = require('./legacy/api.js');

function response(payload, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: async () => payload,
  };
}

test('GET requests disable caching and return the decoded payload', async () => {
  let request;
  global.fetch = async (url, options) => {
    request = { url, options };
    return response({ value: 7 });
  };

  const payload = await getJson('/api/synthetic', 'Synthetic load failed');

  assert.deepEqual(payload, { value: 7 });
  assert.deepEqual(request, {
    url: '/api/synthetic',
    options: { cache: 'no-store' },
  });
});

test('JSON mutations keep the established POST content type and serialized body', async () => {
  let request;
  global.fetch = async (url, options) => {
    request = { url, options };
    return response({ status: 'saved' });
  };

  await postJson('/api/synthetic', { amount: 12 }, 'Synthetic save failed');

  assert.equal(request.url, '/api/synthetic');
  assert.equal(request.options.method, 'POST');
  assert.deepEqual(request.options.headers, { 'Content-Type': 'application/json' });
  assert.equal(request.options.body, '{"amount":12}');
});

test('form uploads do not add a JSON content type', async () => {
  const body = { synthetic: 'form-data-placeholder' };
  let options;
  global.fetch = async (_url, requestOptions) => {
    options = requestOptions;
    return response({ status: 'ready' });
  };

  await postForm('/api/import/analyze', body, 'Synthetic upload failed');

  assert.deepEqual(options, { method: 'POST', body });
});

test('API failures preserve the server message and expose status context', async () => {
  global.fetch = async () => response(
    { error: 'Synthetic conflict' },
    { ok: false, status: 409 },
  );

  await assert.rejects(
    postJson('/api/synthetic', {}, 'Synthetic save failed'),
    error => error instanceof ApiError
      && error.message === 'Synthetic conflict'
      && error.status === 409
      && error.url === '/api/synthetic',
  );
});
