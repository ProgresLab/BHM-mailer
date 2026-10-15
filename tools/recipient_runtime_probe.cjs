// Read-only diagnosis of the operational recipient API. Never permits writes.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const origin = 'http://127.0.0.1:8000';
const out = path.resolve('output/recipient-runtime');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');

(async () => {
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const writes = [], errors = [], api = [];
    await context.route('**/*', route => {
      const req = route.request();
      if (new URL(req.url()).origin !== origin || !['GET','HEAD'].includes(req.method())) {
        writes.push({method:req.method(),url:req.url()});
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => {
      if (new URL(r.url()).pathname === '/campaigns/32/selection') {
        api.push({url:r.url(), method:r.request().method(), status:r.status(), allow:r.headers().allow});
      }
    });
    const response = await page.goto(origin+'/campaigns/32/recipients');
    await page.waitForFunction(() => {
      const root = document.querySelector('[data-selection-url]');
      return root?.dataset.selectionReady === 'true' || document.querySelector('[data-selection-message]')?.textContent.includes('Wybór zablokowany');
    });
    const endpoint = await context.request.get(origin+'/campaigns/32/selection');
    const payload = await endpoint.json();
    // Never persist contact IDs, names, addresses or campaign content.
    const safeBody = endpoint.ok() ? {workflow:payload.workflow, editable:payload.editable,
      selected_count:payload.selected_count, selected_ids_is_array:Array.isArray(payload.selected_ids)} : {detail:payload.detail};
    const spec = await (await context.request.get(origin+'/openapi.json')).json();
    const scriptURL = await page.locator('script[src*="app.js"]').getAttribute('src');
    const servedJS = await (await context.request.get(new URL(scriptURL,origin).href)).body();
    const screenshot = path.join(out,'8000-recipient-gate.png');
    await page.screenshot({path:screenshot, mask:[page.locator('tbody'),page.locator('.page-head > p:not(.eyebrow)')],maskColor:'#e2e8f0'});
    const result = {checked_at:new Date().toISOString(), port:8000, page_http:response.status(),
      selection_requests:api, direct_probe:{url:endpoint.url(),method:'GET',status:endpoint.status(),allow:endpoint.headers().allow,body:safeBody},
      runtime_selection_methods:Object.keys(spec.paths['/campaigns/{campaign_id}/selection'] || {}),
      scriptURL, served_js_matches_source:sha(servedJS)===sha(fs.readFileSync('app/static/app.js')),
      selection_ready:await page.locator('[data-selection-url]').getAttribute('data-selection-ready'),
      message:await page.locator('[data-selection-message]').textContent(),
      checkbox_count:await page.locator('[data-recipient]').count(), disabled_count:await page.locator('[data-recipient]:disabled').count(),
      add_disabled:await page.locator('[data-selection-add]').isDisabled(),javascript_errors:errors,blocked_requests:writes,screenshot};
    fs.writeFileSync(path.join(out,'8000-browser.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result,null,2));
    assert.deepEqual(writes,[]);
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
})().catch(e => {console.error(e);process.exitCode=1;});
