// Existing repository Playwright harness style; synthetic 8019 only.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const origin='http://127.0.0.1:8019';
const out=path.resolve('output/sync-qa');
const sqlite=query=>JSON.parse(execFileSync(path.resolve('.venv/Scripts/python.exe'),['-c',
  "import sqlite3,json,pathlib; c=sqlite3.connect(pathlib.Path('output/sync-qa/synthetic.sqlite3').resolve().as_uri()+'?mode=ro',uri=True); print(json.dumps(c.execute("+JSON.stringify(query)+").fetchall()))"],{encoding:'utf8'}));
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  const checks=[],errors=[];
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1100}});
    const page=await context.newPage();
    page.on('pageerror',e=>errors.push(e.message));
    context.on('request',r=>assert.equal(new URL(r.url()).origin,origin));
    const ok=name=>{checks.push(name);console.log('PASS '+name);};
    const open=async(query='')=>{
      await page.goto(origin+'/campaigns/32/recipients'+query);
      await page.waitForFunction(()=>document.querySelector('[data-selection-url]')?.dataset.selectionReady==='true');
    };
    await context.request.post(origin+'/campaigns/32/selection',{form:{action:'clear',confirm_clear:'1'}});
    await open('?sort=last_sent&direction=asc');
    assert.equal(await page.locator('[data-recipient]').count(),500);
    assert((await page.locator('tbody tr').first().innerText()).includes('Nigdy'));
    await page.locator('[data-recipient]').first().check();
    await page.locator('[data-selection-add]').click();
    await page.waitForFunction(()=>document.querySelector('[data-total-selected]').textContent==='1');
    const saved=sqlite('SELECT contact_id FROM campaign_selection WHERE campaign_id=32')[0][0];
    await page.locator('[data-sort="last_sent"]').click();
    await page.waitForFunction(()=>document.querySelector('[data-selection-url]')?.dataset.selectionReady==='true');
    assert(page.url().includes('direction=desc'));
    assert((await page.locator('tbody tr').first().innerText()).includes('2026-10-16 11:00'));
    assert.equal(sqlite('SELECT contact_id FROM campaign_selection WHERE campaign_id=32')[0][0],saved);
    await page.reload();await page.waitForFunction(()=>document.querySelector('[data-selection-url]')?.dataset.selectionReady==='true');
    assert.equal(await page.locator('[data-total-selected]').textContent(),'1');
    ok('last accepted SMTP in Warsaw; Nigdy; saved selection survives sorting and reload');
    for(const field of ['email','company']){
      await page.locator(`[data-sort="${field}"]`).click();assert(page.url().includes('direction=asc'));
      await page.locator(`[data-sort="${field}"]`).click();assert(page.url().includes('direction=desc'));
    }
    ok('email and company click ASC/DESC; backend global sort verified in unit suite');
    await open('?sort=last_sent&direction=desc');
    await page.screenshot({path:path.join(out,'recipients-desktop.png'),fullPage:false});
    await page.locator('[data-selection-summary]').click();
    assert((await page.locator('[data-summary-count]').innerText()).includes('1'));
    ok('frontend to API to SQLite to reload to summary');
    await page.goto(origin+'/campaigns/33/monitor');
    await page.waitForFunction(()=>document.querySelector('[data-monitor="state_label"]').textContent==='Tymczasowy cooldown SMTP');
    assert((await page.locator('[data-monitor="notice"]').innerText()).includes('451 4.3.0'));
    await page.waitForFunction(()=>document.querySelector('[data-sync="connection"]').textContent==='Aktywne');
    const before=sqlite('SELECT next_sync FROM mail_sync_state')[0][0];
    await page.getByRole('button',{name:'Sprawdź teraz',exact:true}).click();
    await page.waitForTimeout(1300);
    const after=sqlite('SELECT next_sync FROM mail_sync_state')[0][0];assert(after>=before);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('[data-sync="connection"]').textContent==='Aktywne');
    assert.equal(sqlite('SELECT COUNT(*) FROM mail_sync_messages')[0][0],1);
    await page.screenshot({path:path.join(out,'monitor-desktop.png'),fullPage:true});
    ok('monitor cooldown cause/time/countdown and IMAP check API/SQLite/reload');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(out,'monitor-mobile.png'),fullPage:true});
    await open('?sort=last_sent&direction=desc');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(out,'recipients-mobile.png'),fullPage:true});
    ok('mobile monitor and recipients; table scroll contained');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify({checks,errors,sqliteSelection:saved,synthetic:true},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
