// Drive the same controls as a resident or presenter. Each run owns its server.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const { createInterface } = require('node:readline');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const story = require('./story.json');

const root = path.resolve(__dirname, '../..');
const out = path.resolve(process.argv[2] || 'family-capture');
const film = process.argv.includes('--film');
fs.mkdirSync(out, { recursive: true });

async function main() {
  const server = spawn(process.env.PYTHON || 'python3', ['backend/family_demo.py', '--port', '0'], {
    cwd: root, stdio: ['ignore', 'pipe', 'inherit']
  });
  let browser;
  try {
    const lines = createInterface({ input: server.stdout });
    const [line] = await Promise.race([
      once(lines, 'line'), once(server, 'exit').then(([code]) => {throw Error('Server exited: ' + code);})
    ]);
    const base = line.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
    browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined});
    const viewport = {width: 1600, height: 792};
    const context = await browser.newContext({viewport, locale: 'zh-CN',
      ...(film ? {recordVideo: {dir:out, size:viewport}} : {})});
    const page = await context.newPage();
    const zero = Date.now(), beats = [];
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.setDefaultTimeout(5500);
    await page.goto(base);
    const by = id => page.getByTestId(id);
    const read = async () => (await page.request.get(base + '/api/family/state')).json();
    const device = (s,id) => s.devices.find(d => d.id === id).value;
    await page.getByText('家庭网关已连接', {exact:true}).waitFor();
    const baseline = await read();
    assert.equal(baseline.members.length, 3);
    assert.equal(baseline.devices.length, 8);
    if (film) {
      // Click highlights are a recording aid. App state is only changed by the controls.
      await page.addStyleTag({content:'.film-click{position:fixed;z-index:2147483647;pointer-events:none;width:32px;height:32px;margin:-16px;border:2px solid #1597b5;border-radius:100%;background:#1393b133;animation:film-ring .6s ease-out forwards}@keyframes film-ring{to{transform:scale(1.7);opacity:0}}'});
      await page.evaluate(() => document.addEventListener('pointerdown', e => {
        const ring = document.createElement('i');ring.className='film-click';
        ring.style.left=e.clientX+'px';ring.style.top=e.clientY+'px';
        (document.querySelector('dialog[open]') || document.body).append(ring);
        setTimeout(()=>ring.remove(),650);
      }));
    }
    const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
    const pause = ms => wait(film ? ms : 0);
    const click = async id => {await by(id).click(); await pause(210);};
    const close = async () => {await page.locator('#sheet-close').click(); await pause(180);};
    const shot = async name => {await page.screenshot({path:path.join(out, name+'.jpg'),type:'jpeg',quality:87});};
    const submit = async (id, endpoint) => {
      const [res] = await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/family/'+endpoint)
        && r.request().method()==='POST'), click(id)]);
      assert.ok(res.ok(), (await res.text()).slice(0,250));
      await page.waitForFunction(()=>!document.body.classList.contains('pending'));
      return res.json();
    };
    const event = async id => {await click('presenter-toggle'); await pause(450);return submit('sim-'+id,'events');};
    // Editorial panels are isolated from the household app. The real page keeps its
    // pending proposal, selected resident, and virtual gateway state throughout.
    await page.route('**/__film/architecture.html*', route => route.fulfill({
      path: path.join(__dirname, 'architecture.html'), contentType:'text/html; charset=utf-8'
    }));
    await page.route('**/apps/mobile/assets/logo-mark.png', route => route.fulfill({
      path: path.join(root, 'apps/mobile/assets/logo-mark.png'), contentType:'image/png'
    }));
    async function showPanel(stage) {
      await page.evaluate(stage => {
        const frame = document.createElement('iframe');
        frame.id = 'architecture-panel';
        frame.title = '源码导览';
        frame.src = '/__film/architecture.html?stage=' + encodeURIComponent(stage);
        frame.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;margin:0;padding:0;max-width:none;max-height:none;box-sizing:border-box;border:0;z-index:2147483647;background:#132f38';
        // A modal in the top layer may be open. Leave it intact under the film insert.
        frame.setAttribute('popover', 'manual');
        document.body.append(frame);
        frame.showPopover();
      }, stage);
      const doc = page.frameLocator('#architecture-panel');
      await doc.locator('[data-stage="' + stage + '"]').first().waitFor({state:'attached'});
      await doc.locator('img').evaluate(img => img.decode());
      const active = doc.locator('.stage.active');
      const sourcePath = await active.locator('.path').innerText();
      const source = fs.readFileSync(path.join(root, sourcePath), 'utf8').replace(/\s+/g, ' ');
      for (const snippet of await active.locator('pre code').allTextContents()) {
        assert.ok(source.includes(snippet.replace(/\s+/g, ' ').trim()), 'Source excerpt changed: ' + sourcePath);
      }
    }
    const beat = async (id, work) => {
      const i = beats.length;
      assert.equal(story[i].id,id);
      const start = Date.now();
      beats.push({id,at:(start-zero)/1000});
      if (story[i].panel) await showPanel(story[i].panel);
      if (work) await work();
      await pause(Math.max(250, story[i].seconds * 1000 - (Date.now() - start)));
      if (story[i].panel) await page.locator('#architecture-panel').evaluate(frame => frame.remove());
    };
    await beat('home',async()=>{await shot('home');});
    await beat('arrival',async()=>{
      const s=await event('arrival');
      assert.ok(s.suggestion.actions.length >= 2);
      assert.equal(device(s,'living-light'),device(baseline,'living-light'));
      await pause(800);await shot('arrival');
      await click('action-trace');await pause(1150);await shot('trace');await close();
    });
    await beat('planning', async()=>{await shot('architecture-planning');});
    await beat('edit',async()=>{
      await click('action-edit');await by('edit-text').fill('我今晚还要看书，客厅亮一点，卧室先别动');
      await pause(900);
      const s=await submit('edit-text-save','decision');
      assert.deepEqual(s.suggestion.actions,[{deviceId:'living-light',value:65}]);
      assert.equal(device(s,'living-light'),device(baseline,'living-light'));
      await shot('revision');
    });
    await beat('consent', async()=>{await shot('architecture-consent');});
    await beat('confirm',async()=>{
      const s=await submit('action-confirm','decision');
      assert.equal(s.receipts[0].observed,65);
      assert.equal(device(s,'living-ac'),device(baseline,'living-ac'));
      await click('action-receipts');await pause(1200);await close();
    });
    await beat('study',async()=>{
      await click('voice-open');await by('voice-member').selectOption('child');
      await click('voice-example');await pause(750);
      const s=await submit('speech-send','events');assert.ok(s.suggestion.actions.some(a=>a.deviceId==='study-fan'));
      await pause(1100);await submit('action-confirm','decision');
    });
    await beat('movie',async()=>{
      const s=await event('tv');assert.equal(s.suggestion.actions.find(a=>a.deviceId==='living-speaker').value,18);
      await pause(900);await shot('coordination');await submit('action-confirm','decision');
    });
    await beat('fault',async()=>{
      await click('presenter-toggle');await by('fault-controls').locator('summary').click();
      await by('fault-device').selectOption('bed-curtain');await by('fault-mode').selectOption('unknown');
      await submit('fault-apply','devices');
      await event('sleep');
    });
    await beat('receipt',async()=>{
      const s=await submit('action-confirm','decision');
      assert.ok(s.receipts.some(r=>r.status==='unknown'&&r.observed===null));
      assert.ok(s.receipts.some(r=>r.status==='confirmed'));
      await click('action-receipts');await pause(650);await shot('receipts');
    });
    await beat('gateway', async()=>{await shot('architecture-receipt');});
    await beat('tomorrow',async()=>{
      await close();await click('presenter-toggle');await submit('next-day','next-day');
      const s=await event('arrival');assert.equal(s.suggestion.actions.find(a=>a.deviceId==='living-light').value,45);
    });
    const end=(Date.now()-zero)/1000;
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'timeline.json'),JSON.stringify({beats,end},null,2));
    const video=page.video();
    await context.close();
    if(video) await video.saveAs(path.join(out,'capture.webm'));
    // Portrait usability checks run on a separate page, outside the film.
    const mobile = await browser.newPage({viewport:{width:390,height:844},locale:'zh-CN'});
    await mobile.goto(base);await mobile.getByTestId('action-confirm').waitFor();
    assert.ok(await mobile.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await mobile.screenshot({path:path.join(out,'phone-viewport.jpg'),quality:86});
    await mobile.getByTestId('voice-open').click();
    await mobile.getByTestId('speech-input').waitFor();
    console.log('Passed: arrival, pending state, scoped edit, confirmed readback, study, shared volume, unknown receipt, next evening, mobile, voice panel.');
  } finally {
    if(browser) await browser.close();
    server.kill();
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
