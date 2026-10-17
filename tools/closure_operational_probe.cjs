// GET/HEAD-only acceptance on canonical8000. Never starts a queue or campaign.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const origin='http://127.0.0.1:8000';
const out=path.resolve('output/closure-2026-10-17');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  const checks=[],blocked=[],errors=[];
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*',route=>{
      const r=route.request();
      if(new URL(r.url()).origin!==origin || !['GET','HEAD'].includes(r.method())){
        blocked.push(r.method()+' '+new URL(r.url()).pathname);return route.abort();
      }
      return route.continue();
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    for(const url of ['/','/campaigns/new','/contacts','/history','/history/40','/campaigns/40/monitor']){
      assert.equal((await page.goto(origin+url)).status(),200);checks.push(url+' HTTP200');
    }
    await page.waitForFunction(()=>document.querySelector('[data-monitor="state_label"]')?.textContent==='Zakończone z błędami');
    const status=await(await context.request.get(origin+'/campaigns/40/status.json')).json();
    assert.equal(status.execution_state,'completed_with_errors');
    assert.equal(status.counts.accepted,661);assert.equal(status.counts.cancelled,312);
    assert.equal(status.counts.pending,0);assert.equal(status.counts.uncertain,0);
    assert.equal(await page.locator('[data-control="resume"]').isDisabled(),true);
    assert.equal(await page.locator('[data-monitor="cancelled"]').innerText(),'312');
    checks.push('closed40: 661 historical acceptances,312 cancelled,zero pending/unknown,resume disabled');
    await page.screenshot({path:path.join(out,'closed-monitor-desktop.png'),mask:[page.locator('.page-head'),page.locator('[data-monitor-events]')],maskColor:'#e2e8f0'});
    for(const id of [17,18,28]){
      const s=await(await context.request.get(origin+`/campaigns/${id}/status.json`)).json();
      assert.equal(s.execution_state,'interrupted');assert.equal(s.manual_pause,true);
    }
    // Use an existing approved campaign to inspect selection; never create one.
    await page.goto(origin+'/campaigns/39/recipients?sort=last_sent&direction=asc');
    await page.waitForFunction(()=>document.querySelector('[data-selection-url]')?.dataset.selectionReady==='true');
    const selection=await(await context.request.get(origin+'/campaigns/39/selection')).json();
    assert.equal(selection.workflow,'explicit_add_v1');assert.equal(selection.selected_count,0);
    assert.equal(await page.locator('[data-recipient]').count(),500);
    assert((await page.locator('tbody tr').first().innerText()).includes('Nigdy'));
    const script=await page.locator('script[src*="app.js"]').getAttribute('src');
    const served=await(await context.request.get(new URL(script,origin).href)).body();
    assert.equal(crypto.createHash('sha256').update(served).digest('hex'),crypto.createHash('sha256').update(fs.readFileSync('app/static/app.js')).digest('hex'));
    checks.push('actual selection API:empty existing approved39,500/page,global last-send sort,served JS matches source');
    await page.goto(origin+'/campaigns/39/summary');
    assert.equal(await page.locator('select[name="mode"]').inputValue(),'dry_run');
    assert.equal(await page.locator('option[value="smtp"]').isDisabled(),false);
    assert.equal(await page.locator('[name="smtp_ack"]').isChecked(),false);
    checks.push('SMTP enabled; dry-run default; separate acknowledgement unchecked');
    await page.setViewportSize({width:390,height:844});
    await page.goto(origin+'/campaigns/new');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(out,'new-editor-mobile.png')});
    await page.goto(origin+'/campaigns/40/monitor');
    await page.waitForFunction(()=>document.querySelector('[data-monitor="cancelled"]')?.textContent==='312');
    await page.screenshot({path:path.join(out,'closed-monitor-mobile.png'),mask:[page.locator('.page-head'),page.locator('[data-monitor-events]')],maskColor:'#e2e8f0'});
    const sync=await(await context.request.get(origin+'/mail-sync/status.json')).json();
    assert.equal(sync.enabled,true);assert.equal(sync.connection,'active');assert.equal(sync.last_error,'');
    checks.push('IMAP ON active;desktop/mobile real backend;GET/HEAD only');
    assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
    const report={checks,errors,blocked,counts:status.counts,selection_count:selection.selected_count,
      imap:{enabled:sync.enabled,last_success:sync.last_success,next_sync:sync.next_sync,new_messages:sync.new_messages}};
    fs.writeFileSync(path.join(out,'browser-operational.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
