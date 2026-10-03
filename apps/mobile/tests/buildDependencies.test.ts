import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { test } from 'node:test';

test('xcode still loads via CommonJS and generates its expected IDs with patched uuid', () => {
  const require = createRequire(import.meta.url);
  const xcodeRequire = createRequire(require.resolve('xcode'));
  assert.equal(xcodeRequire('uuid/package.json').version, '11.1.1');
  const project = require('xcode').project('/tmp/livingmind-placeholder.pbxproj');
  // No file read/write. Exercise the actual xcode call site, not merely uuid.v4.
  project.hash = { project: { objects: {} } };
  const ids = new Set(Array.from({ length: 100 }, () => project.generateUuid()));
  assert.equal(ids.size, 100);
  for (const id of ids) assert.match(String(id), /^[0-9A-F]{24}$/);
});
