// Export exactly one CSS viewport per device at its native display scale.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const { createInterface } = require('node:readline');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '../..');
const out = path.resolve(process.argv[2] || path.join(root,'docs/media'));
const devices = [
  {name:'phone', width:390, height:844, scale:3},
  {name:'phone-compact',width:375,height:812,scale:3,exportFrame:false},
  {name:'ipad-portrait', width:820, height:1180, scale:2},
  {name:'ipad-large-portrait', width:1024, height:1366, scale:2,exportFrame:false},
  {name:'ipad-landscape', width:1180, height:820, scale:2},
];
async function main(){
  fs.mkdirSync(out,{recursive:true});
  let browser;
  const server=spawn(process.env.PYTHON || 'python3',['backend/family_demo.py','--port','0'],{cwd:root,env:require('../family-test-env.cjs'),stdio:['ignore','pipe','inherit']});
  try {
    const [line]=await once(createInterface({input:server.stdout}),'line');
    const base=line.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
    browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined});
    const cover=await browser.newPage({viewport:{width:1280,height:640},deviceScaleFactor:1.5});
    await cover.goto(pathToFileURL(path.join(__dirname,'cover.html')).href);
    await cover.screenshot({path:path.join(out,'social-cover.jpg'),type:'jpeg',quality:90});
    await cover.close();
    const measurements=[];
    for(const d of devices){
      const ctx=await browser.newContext({viewport:{width:d.width,height:d.height},deviceScaleFactor:d.scale,isMobile:true,hasTouch:true,locale:'zh-CN'});
      const p=await ctx.newPage();
      try {
        await p.request.post(base+'/api/family/reset',{data:{}});
        await p.goto(base);
        await p.waitForFunction(()=>document.querySelector('#conn-state')?.textContent === '家庭网关已连接');
        await p.getByTestId('presenter-toggle').tap();
        await p.getByTestId('sim-arrival').tap();
        const confirm = p.getByTestId('action-confirm');
        await confirm.waitFor();
        await p.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
        await p.waitForTimeout(3350);  // Allow the ephemeral simulated-event toast to leave.
        const geometry=await p.evaluate(()=>{
          const primary=['presenter-toggle','voice-open','action-confirm','action-edit'];
          const room=paneBounds('.room-hero'), service=paneBounds('.service');
          function paneBounds(selector){
            const {x,y,right,bottom}=document.querySelector(selector).getBoundingClientRect();
            return {x,y,right,bottom};
          }
          return {room,service,width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,
            pageHeight:document.documentElement.scrollHeight,dpr:devicePixelRatio,
            targetHeights:Object.fromEntries(primary.map(id=>[id,document.querySelector('[data-testid="'+id+'"]').getBoundingClientRect().height]))};
        });
        assert.equal(geometry.width,d.width);assert.equal(geometry.height,d.height);assert.equal(geometry.dpr,d.scale);
        assert.ok(geometry.scrollWidth<=d.width, d.name+' horizontal overflow');
        for(const [id,h] of Object.entries(geometry.targetHeights))assert.ok(h>=43.5, d.name+' '+id+' touch height '+h);
        if(d.width < d.height){
          assert.ok(geometry.service.y >= geometry.room.bottom, d.name+' proposal must stack below the room');
        }else{
          assert.ok(geometry.service.x >= geometry.room.right, d.name+' proposal must sit beside the room');
          assert.ok(Math.abs(geometry.service.y-geometry.room.y)<1, d.name+' panels must share a top edge');
        }
        const fileName=d.exportFrame===false ? null : d.name+'.jpg';
        if(fileName)await p.screenshot({path:path.join(out,fileName),type:'jpeg',quality:84,fullPage:false});
        await p.locator('#devices').scrollIntoViewIfNeeded();
        assert.ok(await p.locator('#devices').isVisible());
        // Resident can scroll back up and consent at this screen size.
        await confirm.tap();
        await p.getByTestId('action-receipts').tap();
        await p.getByText('设备执行回执',{exact:true}).waitFor();
        measurements.push({profile:d.name,...geometry});
      } finally{await ctx.close();}
    }
    // Export the gallery at a common scale: 390:820:1180. Each image retains its own aspect ratio.
    const gallery=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1.5});
    await gallery.goto(pathToFileURL(path.join(root,'docs/index.html')).href);
    const figures=gallery.locator('.devices img');
    for(let i=0;i<await figures.count();i++){
      const key=['phone','ipad-portrait','ipad-landscape'][i];
      await figures.nth(i).evaluate((img,source)=>{img.src=source;return img.decode();},
        pathToFileURL(path.join(out,key+'.jpg')).href);
    }
    await gallery.locator('.devices').screenshot({path:path.join(out,'device-sizes.jpg'),type:'jpeg',quality:91});
    await gallery.close();
    console.log(JSON.stringify(measurements,null,2));
  } finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
