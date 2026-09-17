import assert from 'node:assert/strict';
import { test } from 'node:test';

import { resolveConfig } from '../config';

test('no base URL means explicit mock mode', () => {
  assert.equal(resolveConfig({}).mode, 'mock');
  assert.equal(resolveConfig({ EXPO_PUBLIC_API_BASE_URL: '  ' }).mode, 'mock');
});

test('base URL enables http mode and trims trailing slash', () => {
  const cfg = resolveConfig({ EXPO_PUBLIC_API_BASE_URL: 'http://192.168.1.20:8000/' });
  assert.equal(cfg.mode, 'http');
  assert.equal(cfg.apiBaseUrl, 'http://192.168.1.20:8000');
});
