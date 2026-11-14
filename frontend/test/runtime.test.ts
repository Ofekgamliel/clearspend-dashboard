import assert from 'node:assert/strict';
import test from 'node:test';
import { EXPECTED_API_COMPATIBILITY, runtimeCompatibilityError } from '../src/api/runtime.ts';

test('accepts only the compatible healthy local runtime', () => {
  assert.equal(runtimeCompatibilityError({
    status: 'ok', mode: 'local', database: true, api_compatibility: EXPECTED_API_COMPATIBILITY,
  }), '');
  assert.match(runtimeCompatibilityError({
    status: 'ok', mode: 'local', database: true,
  }), /different builds/i);
  assert.match(runtimeCompatibilityError({
    status: 'ok', mode: 'local', database: false, api_compatibility: EXPECTED_API_COMPATIBILITY,
  }), /database is unavailable/i);
});
