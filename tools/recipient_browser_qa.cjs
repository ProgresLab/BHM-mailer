// Run with NODE_PATH pointing at the bundled Node packages. Synthetic 8018 only.
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const origin = 'http://127.0.0.1:8018';
const base = `${origin}/campaigns/32`;
const out = path.resolve('output/recipient-qa');
const shots = path.resolve('output/playwright');
fs.mkdirSync(out,{recursive:true}); fs.mkdirSync(shots,{recursive:true});

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1100}});
    const page = await context.newPage();
    const errors=[], responses=[], checks=[];
    const sqliteChecks=[];
    const sqlite = expected => {
      const code = "import sqlite3,json,pathlib; p=pathlib.Path('output/recipient-qa/synthetic.sqlite3').resolve(); c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True); print(json.dumps(dict(selected_count=c.execute('SELECT COUNT(*) FROM campaign_selection WHERE campaign_id=32').fetchone()[0], emails=[r[0] for r in c.execute('SELECT email FROM contacts JOIN campaign_selection s ON contacts.id=s.contact_id WHERE s.campaign_id=32 ORDER BY email LIMIT 1')], sends=c.execute('SELECT COUNT(*) FROM email_sends').fetchone()[0])))";
      const data=JSON.parse(execFileSync(path.resolve('.venv/Scripts/python.exe'),['-c',code],{encoding:'utf8'}));
      assert.equal(data.selected_count,expected);assert.equal(data.sends,0);
      sqliteChecks.push(data);return data;
    };
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{if(r.request().method()==='POST')responses.push({path:new URL(r.url()).pathname,status:r.status()});});
    page.on('request',r=>assert.equal(new URL(r.url()).origin,origin,'QA must never access another server'));
    const ok = name => {checks.push(name);console.log(`PASS ${name}`);};
    const state = async () => (await context.request.get(base+'/selection')).json();
    const open = async (query='') => {
      await page.goto(base+'/recipients'+query);
      await page.waitForFunction(()=>document.querySelector('[data-selection-url]')?.dataset.selectionReady==='true');
    };
    const count = async n => page.waitForFunction(n=>document.querySelector('[data-total-selected]')?.textContent===String(n),n);
    const pending = async n => assert.equal(await page.locator('[data-pending-selected]').textContent(),String(n));
    const add = async n => {
      const response=page.waitForResponse(r=>r.url()===base+'/selection'&&r.request().method()==='POST');
      await page.getByRole('button',{name:'Dodaj do kampanii',exact:true}).click();
      assert.equal((await response).status(),200);await count(n);
      await page.waitForFunction(()=>document.querySelector('[data-selection-message]').textContent.includes('Zapisano'));
      await pending(0);
      assert(page.url().includes('/recipients'));
      assert.equal((await state()).selected_count,n);
    };
    await open('?search=marcin');
    assert((await page.locator('main').innerText()).includes('QA — wybór odbiorców'));
    assert.equal((await context.request.post(base+'/selection',{form:{action:'clear',confirm_clear:'1'}})).status(),200);
    await open('?search=marcin');
    // A legacy cached bundle has no listeners for the modern data-recipient DOM.
    const legacy=execFileSync('git',['show','HEAD:app/static/app.js'],{encoding:'utf8'});
    const stale=await context.newPage();
    await stale.route('**/static/app.js*',r=>r.fulfill({contentType:'text/javascript',body:legacy}));
    await stale.goto(base+'/recipients?search=marcin');
    await stale.locator('[data-recipient]').check();
    assert.equal(await stale.locator('[data-pending-selected]').textContent(),'0');
    await stale.locator('[data-recipient]').uncheck();await stale.locator('[data-visible-all]').check();
    assert.equal(await stale.locator('[data-recipient]:checked').count(),0);
    await stale.screenshot({path:path.join(shots,'recipient-legacy-js-reproduction.png')});
    await stale.close();
    assert((await page.locator('script[src*="app.js"]').getAttribute('src')).includes('?v=recipients-'));
    ok('legacy cached JS reproduces dead counter/select-visible; current asset URL is versioned');

    await page.route('**/campaigns/32/selection',r=>r.fulfill({status:405,contentType:'application/json',body:'{"detail":"Method Not Allowed"}'}));
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('[data-selection-message]').textContent.includes('Wybór zablokowany'));
    assert(await page.locator('[data-recipient]').isDisabled());
    assert(await page.locator('[data-selection-add]').isDisabled());
    assert(await page.locator('[data-selection-clear]').isDisabled());
    await page.unroute('**/campaigns/32/selection');await open('?search=marcin');
    ok('old process/API mismatch visibly blocks mutation until controlled activation');

    await page.locator('[data-recipient]').check();await pending(1);
    assert.equal((await state()).selected_count,0); // Checkbox never autosaves.
    sqlite(0);
    await add(1);
    assert.deepEqual(sqlite(1).emails,['marcin@example.test']);
    await page.reload();await count(1);
    sqlite(1);
    assert(await page.locator('[data-recipient]').isChecked());
    assert(await page.locator('[data-recipient]').isDisabled());
    assert.equal(await page.locator('[data-membership]').innerText(),'Dodano');
    await page.screenshot({path:path.join(shots,'recipient-single-desktop.png')});
    await page.getByRole('link',{name:'Przejdź do podsumowania',exact:true}).click();
    await page.waitForURL(base+'/summary');
    assert.equal(await page.locator('[data-summary-recipients] tbody tr').count(),1);
    assert((await page.locator('[data-summary-recipients]').innerText()).includes('marcin@example.test'));
    await page.screenshot({path:path.join(shots,'recipient-summary-desktop.png')});
    ok('marcin checkbox -> temporary 1 -> add -> SQLite 1 -> reload -> summary exactly 1');
    for(const width of [390,360]) {
      await page.setViewportSize({width,height:844});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(shots,`recipient-summary-${width}.png`),fullPage:true});
      await page.getByRole('link',{name:'Wróć do dodawania kontaktów'}).click();
      await page.waitForURL(base+'/recipients');
      await page.locator('[name=search]').fill('marcin');
      await page.getByRole('button',{name:'Filtruj',exact:true}).click();
      await count(1);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(shots,`recipient-selection-${width}.png`),fullPage:true});
      await page.getByRole('link',{name:'Przejdź do podsumowania',exact:true}).click();
      await page.waitForURL(base+'/summary');
    }
    ok('desktop and mobile 390/360 selection + summary without page overflow');
    await page.setViewportSize({width:1440,height:1100});
    await page.getByRole('button',{name:'Usuń marcin@example.test z kampanii'}).click();
    await page.waitForFunction(()=>document.querySelector('[data-summary-count]').textContent==='0 / 1000');
    assert.equal((await state()).selected_count,0);
    ok('remove individual recipient from summary leaves contact intact');
    await open();
    assert.equal(await page.locator('[data-recipient]').count(),500);
    assert.equal(await page.locator('[data-selection-summary]').getAttribute('aria-disabled'),'true');
    await page.locator('[data-visible-all]').check();await pending(500);
    assert.equal(await page.locator('[data-recipient]:checked').count(),500);
    await page.locator('[data-visible-all]').uncheck();await pending(0);
    assert.equal(await page.locator('[data-recipient]:checked').count(),0);
    ok('500 per page; select visible / deselect visible; summary disabled when empty');
    await page.locator('[data-visible-all]').check();await add(500);
    sqlite(500);
    // Navigate using the actual pagination link, preserving stored recipients.
    await page.getByRole('navigation',{name:'Strony odbiorców',exact:true}).getByRole('link',{name:'2',exact:true}).click();
    await page.locator('[data-visible-all]').check();await pending(500);await add(1000);
    sqlite(1000);
    await page.reload();await count(1000);
    sqlite(1000);
    await page.screenshot({path:path.join(shots,'recipient-1000-desktop.png')});
    await page.getByRole('link',{name:'Przejdź do podsumowania',exact:true}).click();
    await page.waitForURL(base+'/summary');
    assert.equal(await page.locator('[data-summary-recipients] tbody tr').count(),1000);
    ok('500 + 500 via real pagination -> SQLite 1000 -> reload -> summary 1000');
    await open('?search=qa01499');
    await page.locator('[data-recipient]').check();await pending(1);
    const over=page.waitForResponse(r=>r.url()===base+'/selection'&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Dodaj do kampanii',exact:true}).click();
    assert.equal((await over).status(),400);
    await page.waitForFunction(()=>document.querySelector('[data-selection-message]').textContent.includes('Limit'));
    assert.equal((await state()).selected_count,1000);await pending(1);
    ok('1001 rejected by backend; no false UI success or partial save');

    // Clear requires a real confirmation, and cancellation preserves the DB.
    page.once('dialog',d=>d.dismiss());await page.locator('[data-selection-clear]').click();
    assert.equal((await state()).selected_count,1000);
    page.once('dialog',d=>d.accept());await page.locator('[data-selection-clear]').click();
    await count(0);assert.equal((await state()).selected_count,0);
    ok('clear persistent campaign list requires confirmation; cancel leaves 1000');

    await open();await page.locator('[data-visible-all]').check();await add(500);
    await page.getByRole('navigation',{name:'Strony odbiorców',exact:true}).getByRole('link',{name:'2',exact:true}).click();
    // Each change is a browser event, never a direct call to the selection code.
    for(let i=0;i<300;i++) await page.locator('[data-recipient]').nth(i).check();
    await pending(300);await add(800);
    await page.locator('[name=search]').fill('qa01499');
    await page.getByRole('button',{name:'Filtruj',exact:true}).click();
    await page.locator('[data-recipient]').check();await add(801);await page.reload();await count(801);
    ok('500 + 300 + search/add 1 -> persisted 801 across filters and reload');

    page.once('dialog',d=>d.accept());await page.locator('[data-selection-clear]').click();await count(0);
    await open('?search=marcin');await page.locator('[data-recipient]').check();
    await page.route('**/campaigns/32/selection',r=>r.request().method()==='POST' ?
      r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Syntetyczny błąd API'})}) : r.continue());
    await page.getByRole('button',{name:'Dodaj do kampanii',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('[data-selection-message]').textContent.includes('Nie potwierdzono zapisu'));
    assert.equal((await state()).selected_count,0);await pending(1);
    assert.equal(await page.locator('[data-total-selected]').textContent(),'0');
    await page.unroute('**/campaigns/32/selection');
    ok('API 503 keeps pending checkbox; saved count 0; no success');
    // Double DOM click in the same turn exercises the in-flight duplicate guard.
    let postCount=0;
    const listener=r=>{if(r.url()===base+'/selection'&&r.method()==='POST')postCount++;};
    page.on('request',listener);
    await page.locator('[data-selection-add]').evaluate(b=>{b.click();b.click();});
    await count(1);await pending(0);assert.equal(postCount,1);page.off('request',listener);
    ok('double add produces one request and one stored recipient');

    const tab=await context.newPage();await tab.goto(base+'/recipients?search=qa01499');
    await tab.locator('[data-recipient]').check();
    await tab.getByRole('button',{name:'Dodaj do kampanii',exact:true}).click();
    await tab.waitForFunction(()=>document.querySelector('[data-total-selected]').textContent==='2');
    await page.bringToFront();
    await page.waitForFunction(()=>document.querySelector('[data-total-selected]').textContent==='2');
    await page.reload();await count(2);
    assert.equal((await state()).selected_count,2);
    await tab.close();
    ok('two tabs add without replacement and synchronize from SQLite');

    await open('?search=zz-&active_only=0');
    assert.equal(await page.locator('[data-recipient]').count(),3);
    assert.equal(await page.locator('[data-recipient]:disabled').count(),3);
    assert(await page.locator('[data-visible-all]').isDisabled());
    const ids=await page.locator('[data-recipient]').evaluateAll(bs=>bs.map(b=>b.value));
    const rejected=await context.request.post(base+'/selection',{form:{visible:ids.join(','),checked:ids.join(',')}});
    assert.equal(rejected.status(),200);assert.equal((await state()).selected_count,2);
    ok('unsubscribed/bounced/invalid disabled and excluded even via direct API');
    // Leave a readable one-contact example in the isolated sandbox.
    page.once('dialog',d=>d.accept());await page.locator('[data-selection-clear]').click();await count(0);
    await open('?search=marcin');await page.locator('[data-recipient]').check();await add(1);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify({checks,passed:checks.length,errors,responses,sqliteChecks,final:await state()},null,2));
    console.log(`${checks.length} browser scenarios passed`);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
