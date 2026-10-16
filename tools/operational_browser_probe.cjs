// Read-only target-port acceptance. No campaign/contact mutations or queue start.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const origin='http://127.0.0.1:8000';
const out=path.resolve('output/operational-activation');
(async()=>{
  fs.mkdirSync(out,{recursive:true});
  const expected=process.env.EXPECT_SMTP_ENABLED==='true';
  const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  const errors=[],blocked=[],checks=[];
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*',route=>{
      const request=route.request();
      if(new URL(request.url()).origin!==origin || !['GET','HEAD'].includes(request.method())){
        blocked.push(request.method()+' '+new URL(request.url()).pathname);return route.abort();
      }
      return route.continue();
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    for(const url of ['/','/campaigns/new','/contacts','/history','/history/38','/campaigns/38/monitor']){
      assert.equal((await page.goto(origin+url)).status(),200);checks.push(url+' HTTP200');
    }
    const state=await (await context.request.get(origin+'/campaigns/38/status.json')).json();
    assert.equal(state.execution_state,'completed');assert.equal(state.counts.accepted,1000);
    assert.equal(state.counts.errors,430);assert.equal(state.counts.sending,0);
    checks.push('monitor: 1000 historical acceptances, 430 later-bounce errors, no inflight');
    for(const id of [17,18,28]){
      const s=await(await context.request.get(origin+`/campaigns/${id}/status.json`)).json();
      assert.equal(s.execution_state,'interrupted');assert.equal(s.manual_pause,true);
    }
    checks.push('17/18/28 interrupted and manual_pause');
    await page.goto(origin+'/campaigns/35/summary');
    assert.equal(await page.locator('select[name="mode"]').inputValue(),'dry_run');
    assert.equal((await page.locator('option[value="smtp"]').getAttribute('disabled'))!==null,!expected);
    assert.equal(await page.locator('[name="smtp_ack"]').isChecked(),false);
    checks.push('SMTP '+(expected?'ON':'OFF')+'; default dry-run; acknowledgement unchecked');
    await page.goto(origin+'/campaigns/35/recipients?sort=last_sent&direction=asc');
    await page.waitForFunction(()=>document.querySelector('[data-selection-url]')?.dataset.selectionReady==='true');
    assert((await page.locator('tbody tr').first().innerText()).includes('Nigdy'));
    const selection=await(await context.request.get(origin+'/campaigns/35/selection')).json();
    assert.equal(selection.selected_count,1);
    checks.push('recipient handshake; saved selection 1; Nigdy sorted first');
    await page.setViewportSize({width:390,height:844});
    await page.goto(origin+'/campaigns/new');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(out,'editor-mobile.png')});
    await page.goto(origin+'/');
    const sync=await(await context.request.get(origin+'/mail-sync/status.json')).json();
    assert.equal(sync.enabled,true);assert.equal(sync.connection,'active');
    checks.push('IMAP enabled/active; desktop and mobile GET UI');
    assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,expected?'browser-smtp-on.json':'browser-smtp-off.json'),JSON.stringify({checks,errors,blocked,smtp_enabled:expected,sync:{last_success:sync.last_success,next_sync:sync.next_sync,new_messages:sync.new_messages,reviews:sync.reviews}},null,2));
    console.log(JSON.stringify({checks,errors,blocked,smtp_enabled:expected}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
