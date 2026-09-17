import assert from 'node:assert/strict';
import { test } from 'node:test';

import { autoDismissDelay, INFO_DISMISS_MS } from '../features/shell/notices';

test('info notices fade after 3 s; warnings and errors stay', () => {
  assert.equal(autoDismissDelay('info'), INFO_DISMISS_MS);
  assert.equal(INFO_DISMISS_MS, 3000);
  assert.equal(autoDismissDelay('warning'), null);
  assert.equal(autoDismissDelay('error'), null);
  assert.equal(autoDismissDelay(null), null);
});
