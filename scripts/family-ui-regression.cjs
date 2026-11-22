// Exercises the sharing and speaker-selection boundaries in two real browser tabs.
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

// Only the first property action pauses. The test releases it through stdin,
// after both browsers have observed execution on the real HTTP read path.
const heldGatewayServer = `
import sys
from family_demo import make_server
from app.family.gateway import VirtualFamilyGateway
from app.family.service import FamilyEvening

class HeldGateway(VirtualFamilyGateway):
    hold = True
    def submit(self, action_id, device_id, value):
        if self.hold:
            self.hold = False
            sys.stdin.readline()
        return super().submit(action_id, device_id, value)

with make_server(0) as server:
    server.session = FamilyEvening(gateway_factory=HeldGateway)
    print(f"http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()
`;

async function startServer({ holdFirstAction = false, profile } = {}) {
  const args = holdFirstAction
    ? ['-u', '-c', heldGatewayServer]
    : ['-u', 'family_demo.py', '--port', '0'];
  if (profile) args.push('--miot-profile', profile);
  const server = spawn(process.env.PYTHON || 'python3', args, {
    cwd: path.join(__dirname, '../backend'),
    env: require('./family-test-env.cjs'),
    stdio: [holdFirstAction ? 'pipe' : 'ignore', 'pipe', 'inherit']
  });
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

async function speakerDraft(page) {
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

async function interimSpeech(page, base) {
  // Drive the browser's speech callbacks without a microphone or cloud ASR.
  // At first the recognizer hears “确认”; the final utterance is a question.
  await page.addInitScript(() => {
    window.SpeechRecognition = class {
      start() {
        window.recognitionUnderTest = this;
        this.onstart();
      }
      stop() {}
      abort() {}
    };
  });
  await page.goto(base);
  await page.getByTestId('proposal-title').waitFor();
  await page.getByTestId('presenter-toggle').click();
  await submit(page, 'reset-demo', 'reset');
  await event(page, 'arrival');
  await page.getByTestId('voice-open').click();
  await page.getByTestId('voice-listen').click();
  const input = page.getByTestId('speech-input');
  const send = page.getByTestId('speech-send');
  const deliver = async (text, final) =>
    page.evaluate(
      ({ text, final }) => {
        const result = Object.assign([{ transcript: text }], { isFinal: final });
        window.recognitionUnderTest.onresult({ results: [result] });
      },
      { text, final }
    );
  await deliver('确认', false);
  assert.equal(await input.inputValue(), '确认');
  assert.equal(await send.isDisabled(), true, 'interim recognition must never authorize execution');
  await input.press('Enter');
  let current = await (await page.request.get(base + '/api/family/state')).json();
  assert.equal(current.receipts.length, 0);
  assert.ok(current.suggestion);
  await deliver('确认之前，可以先看看方案吗', true);
  await page.evaluate(() => window.recognitionUnderTest.onend());
  assert.equal(await send.isEnabled(), true);
  assert.equal(await input.inputValue(), '确认之前，可以先看看方案吗');
  await input.fill('确认方案');
  current = await (await submit(page, 'speech-send', 'decision')).json();
  assert.equal(current.lastOutcome, 'confirmed');
}

async function unrelatedReceipts(first, second, base) {
  await first.getByTestId('presenter-toggle').click();
  await submit(first, 'reset-demo', 'reset');
  const arrival = await event(first, 'arrival');
  await first.getByTestId('voice-open').click();
  await first.getByTestId('speech-input').fill('确认方案');
  await second.goto(base);
  await second.getByTestId('action-confirm').waitFor();
  await submit(second, 'action-confirm', 'decision');
  await event(second, 'study');
  await submit(second, 'action-confirm', 'decision');
  await event(second, 'tv');
  const skipped = await (await submit(second, 'action-dismiss', 'decision')).json();
  assert.equal(skipped.lastOutcome, 'dismissed');
  assert.equal(
    await second.getByTestId('action-receipts').count(),
    0,
    'a skipped TV suggestion must not show the earlier study receipts'
  );

  // Replaying the previously completed arrival shows that original decision to
  // the caller while the shared home remains in its later state.
  const replay = await (await submit(first, 'speech-send', 'decision')).json();
  assert.equal(replay.decisionReplayed, true);
  assert.equal(replay.decisionResult.suggestionId, arrival.suggestion.id);
  assert.equal(replay.lastOutcome, 'dismissed');
  await first.getByText('原建议的执行回执', { exact: true }).waitFor();
  const receipts = await first.locator('#sheet-body').innerText();
  assert.match(receipts, /客厅灯/);
  assert.doesNotMatch(receipts, /书桌灯/);
  await first.locator('#sheet-close').click();
  assert.equal(await first.getByTestId('action-receipts').count(), 0);
}

async function visibleHousehold(observer, operator, base) {
  await operator.goto(base);
  await operator.getByTestId('presenter-toggle').click();
  await submit(operator, 'reset-demo', 'reset');
  await observer.goto(base);
  await observer.getByTestId('proposal-title').waitFor();
  const arrival = await event(operator, 'arrival');
  await observer.getByRole('heading', { name: arrival.suggestion.title }).waitFor({ timeout: 10000 });

  // An unchanged read must not replace focused controls on the passive screen.
  await observer.getByTestId('action-confirm').focus();
  await observer.waitForResponse(r => r.url() === base + '/api/family/state');
  await observer.evaluate(() => new Promise(resolve => requestAnimationFrame(() => resolve())));
  assert.equal(
    await observer.getByTestId('action-confirm').evaluate(el => el === document.activeElement),
    true
  );

  await observer.getByTestId('action-edit').click();
  await observer.getByTestId('edit-text').fill('这次只调客厅灯到 35%');
  const child = await event(operator, 'study');
  // One full refresh interval passes while the edit is open.
  await observer.waitForTimeout(2800);
  assert.equal(await observer.getByTestId('edit-text').inputValue(), '这次只调客厅灯到 35%');
  assert.equal(await observer.getByTestId('proposal-title').innerText(), arrival.suggestion.title);
  await observer.locator('#sheet-close').click();
  await observer.getByRole('heading', { name: child.suggestion.title }).waitFor();
}

async function slowConfirmation(browser) {
  const { server, base } = await startServer({ holdFirstAction: true });
  const context = await browser.newContext();
  const resident = await context.newPage(),
    observer = await context.newPage();
  let submitted;
  try {
    await resident.goto(base);
    await resident.getByTestId('proposal-title').waitFor();
    await event(resident, 'arrival');
    await observer.goto(base);
    await observer.getByTestId('action-confirm').waitFor();
    submitted = submit(resident, 'action-confirm', 'decision');
    const progress = observer.getByTestId('execution-progress');
    await progress.waitFor({ timeout: 10000 });
    assert.match(await progress.innerText(), /0 \/ 3/);
    await resident.getByTestId('execution-progress').waitFor({ timeout: 10000 });
    assert.equal(await observer.getByTestId('action-confirm').count(), 0);
    server.stdin.end('continue\n');
    const completed = await (await submitted).json();
    assert.equal(completed.receipts.length, 3);
    await observer.getByTestId('action-receipts').waitFor({ timeout: 10000 });
    await observer.getByTestId('action-receipts').click();
    assert.match(await observer.locator('#sheet-body').innerText(), /客厅灯/);
  } finally {
    if (!server.stdin.writableEnded) server.stdin.end('continue\n');
    if (submitted) await submitted.catch(() => {});
    await context.close();
    server.kill();
  }
}

async function twoModelReceipts(browser) {
  const { server, base } = await startServer({ profile: 'examples/family-miot-two-models.json' });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true
  });
  try {
    const page = await context.newPage();
    await page.goto(base);
    await event(page, 'study');
    assert.equal((await submit(page, 'action-confirm', 'decision')).status(), 200);
    await page.getByTestId('action-receipts').click();
    const expected = [
      ['desk-light', '75%', 'yeelink.light.lamp4', 'sim-model-desk-lamp', '2 / 2'],
      ['study-fan', '1档', 'dmaker.fan.p5', 'sim-model-study-fan', '2 / 4']
    ];
    for (const [device, reading, model, did, address] of expected) {
      const details = page.getByTestId('receipt-protocol-' + device);
      assert.equal(await details.getAttribute('open'), null);
      await page.getByText('目标 ' + reading + ' · 回读 ' + reading, { exact: true }).waitFor();
      const summary = details.locator('summary');
      assert.ok((await summary.boundingBox()).height >= 44);
      await summary.tap();
      assert.deepEqual(await details.locator('dd').allInnerTexts(), [
        model, did, address, '响应码 0', '响应码 0'
      ]);
    }
    const sheet = page.locator('dialog[open]');
    assert.ok(await sheet.evaluate(el => el.scrollWidth <= el.clientWidth));

    // A write acknowledgement without a read acknowledgement must remain visible as such.
    await page.locator('#sheet-close').click();
    await page.getByTestId('presenter-toggle').click();
    await submit(page, 'reset-demo', 'reset');
    await page.getByTestId('presenter-toggle').click();
    await page.getByTestId('fault-controls').locator('summary').tap();
    await page.getByTestId('fault-device').selectOption('study-fan');
    await page.getByTestId('fault-mode').selectOption('unknown');
    await submit(page, 'fault-apply', 'devices');
    await event(page, 'study');
    await submit(page, 'action-confirm', 'decision');
    await page.getByTestId('action-receipts').click();
    const fan = page.getByTestId('receipt-protocol-study-fan');
    await fan.locator('summary').tap();
    assert.deepEqual((await fan.locator('dd').allInnerTexts()).slice(-2), ['响应码 0', '无回包']);
    await sheet.getByText('目标 1档 · 尚无可确认的回读值', { exact: true }).waitFor();
  } finally {
    await context.close();
    server.kill();
  }
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
    await speakerDraft(first);
    await interimSpeech(first, base);
    await unrelatedReceipts(first, second, base);
    await visibleHousehold(first, second, base);
    await slowConfirmation(browser);
    await twoModelReceipts(browser);
    console.log(
      'PASS: household updates, live execution, stable drafts, speaker attribution, scoped receipts and model protocol details'
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
