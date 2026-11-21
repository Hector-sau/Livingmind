// Exercises the sharing and speaker-selection boundaries in two real browser tabs.
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function startServer() {
  const server = spawn(
    process.env.PYTHON || 'python3',
    ['-u', 'backend/family_demo.py', '--port', '0'],
    {
      cwd: path.join(__dirname, '..'),
      stdio: ['ignore', 'pipe', 'inherit']
    }
  );
  try {
    const base = await new Promise((resolve, reject) => {
      let out = '';
      server.once('error', reject);
      server.once('exit', code => reject(new Error('Family service exited: ' + code)));
      server.stdout.on('data', chunk => {
        out += chunk.toString();
        const match = out.match(/http:\/\/127\.0\.0\.1:\d+\s/);
        if (match) resolve(match[0].trim());
      });
    });
    return { base, server };
  } catch (error) {
    server.kill();
    throw error;
  }
}

async function submit(page, id, endpoint) {
  const response = page.waitForResponse(
    r => r.request().method() === 'POST' && r.url().endsWith('/api/family/' + endpoint)
  );
  await page.getByTestId(id).click();
  const result = await response;
  await page.locator('body:not(.pending)').waitFor();
  return result;
}

async function event(page, type) {
  await page.getByTestId('presenter-toggle').click();
  const response = await submit(page, 'sim-' + type, 'events');
  assert.equal(response.status(), 200);
  return response.json();
}

async function sharedProposal(first, second, base) {
  const initial = await event(first, 'arrival');
  await second.goto(base);
  await second.getByTestId('action-edit').waitFor();
  await first.getByTestId('action-edit').click();
  await first.getByTestId('edit-text').fill('今晚只调客厅灯到 35%');
  await second.getByTestId('action-edit').click();
  await second.getByTestId('edit-text').fill('今晚只调客厅灯到 48%');
  const edited = await (await submit(second, 'edit-text-save', 'decision')).json();
  assert.notEqual(edited.suggestion.id, initial.suggestion.id);

  const stale = await submit(first, 'edit-text-save', 'decision');
  assert.equal(stale.status(), 409);
  await first.locator('dialog:not([open])').waitFor({ state: 'attached' });
  assert.match(await first.locator('#proposal').innerText(), /48%/);
  const synced = await (await first.request.get(base + '/api/family/state')).json();
  assert.equal(synced.suggestion.id, edited.suggestion.id);
  assert.equal(synced.receipts.length, 0);

  // The new owner can also differ. The UI recovers even if ownership is checked
  // before the stale ID on the server.
  await first.getByTestId('action-edit').click();
  await first.getByTestId('edit-text').fill('今晚只调客厅灯到 35%');
  const child = await event(second, 'study');
  const replaced = await submit(first, 'edit-text-save', 'decision');
  assert.ok([403, 409].includes(replaced.status()));
  await first.locator('dialog:not([open])').waitFor({ state: 'attached' });
  assert.equal(await first.getByTestId('proposal-title').innerText(), child.suggestion.title);
  assert.equal(await first.getByTestId('resident-member').inputValue(), 'mother');

  // A mismatched speaker seeing the actual current proposal still gets a refusal.
  const refused = await submit(first, 'action-confirm', 'decision');
  assert.equal(refused.status(), 403);
  assert.equal((await (await first.request.get(base + '/api/family/state')).json()).receipts.length, 0);
}

async function speakerDraft(page, base) {
  await page.getByTestId('presenter-toggle').click();
  await submit(page, 'reset-demo', 'reset');
  await page.getByTestId('voice-open').click();
  await page.getByTestId('voice-example').click();
  const input = page.getByTestId('speech-input');
  assert.equal(await input.inputValue(), '我到家了');
  await page.getByTestId('voice-member').selectOption('father');
  assert.equal(await input.inputValue(), '');
  assert.match(await page.locator('#voice-status').innerText(), /切换说话人/);

  const submissions = [];
  page.on('request', r => {
    if (r.method() === 'POST') submissions.push(r);
  });
  await page.getByTestId('speech-send').click();
  assert.match(await page.locator('#voice-status').innerText(), /请说一句话/);
  await input.fill('孩子开始学习');
  await page.getByTestId('speech-send').click();
  assert.match(await page.locator('#voice-status').innerText(), /当前选择的是爸爸/);
  await page.getByTestId('voice-member').selectOption('mother');
  assert.equal(await input.inputValue(), '');
  await input.fill('爸爸看电视');
  await page.getByTestId('speech-send').click();
  assert.match(await page.locator('#voice-status').innerText(), /当前选择的是妈妈/);
  assert.equal(submissions.length, 0);

  await page.getByTestId('voice-member').selectOption('father');
  await input.fill('我想看电视');
  const resumed = await (await submit(page, 'speech-send', 'events')).json();
  assert.equal(resumed.suggestion.memberId, 'father');
  assert.equal(resumed.receipts.length, 0);
  assert.equal(submissions.length, 1);
  assert.equal(submissions[0].postDataJSON().source, 'resident-input');
}

async function main() {
  const { base, server } = await startServer();
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true
    });
    const first = await context.newPage();
    const second = await context.newPage();
    await first.goto(base);
    await first.getByTestId('proposal-title').waitFor();
    await sharedProposal(first, second, base);
    await speakerDraft(first, base);
    console.log(
      'PASS: shared-tab proposal refresh, cross-member drafts, named actors, and input source'
    );
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
}
main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
