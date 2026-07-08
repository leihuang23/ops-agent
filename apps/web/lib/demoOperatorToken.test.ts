import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveDemoOperatorToken } from './demoOperatorToken.ts';

test('demo operator token prefers submitted form token over scoped cookie', () => {
  assert.equal(
    resolveDemoOperatorToken('fresh-form-token', 'stale-cookie-token'),
    'fresh-form-token',
  );
});

test('demo operator token falls back to scoped cookie when form token is absent', () => {
  assert.equal(resolveDemoOperatorToken(null, 'cookie-token'), 'cookie-token');
  assert.equal(resolveDemoOperatorToken('', 'cookie-token'), 'cookie-token');
});
