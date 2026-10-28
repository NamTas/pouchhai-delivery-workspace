// Optional end-to-end checks. All created records are temporary test fixtures.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process'),fs=require('fs'),os=require('os'),path=require('path'),assert=require('assert');
(async()=>{
 const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'pouchhai-live-')),db=path.join(temp,'test.sqlite3');
 const server=spawn(process.env.PYTHON||'python',['-u','-c',`import app; from pathlib import Path; s=app.make_server(0,Path(${JSON.stringify(db)})); print(s.server_port,flush=True);s.serve_forever()`],{cwd:root,stdio:['ignore','pipe','pipe']});let browser;
 try{
 const port=await new Promise((resolve,reject)=>{server.stdout.once('data',d=>resolve(Number(d.toString().trim())));server.once('exit',code=>reject(Error('Server exited '+code)));server.stderr.on('data',d=>process.stderr.write(d));});
 const launch={headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote']};if(process.env.CHROMIUM_EXECUTABLE)launch.executablePath=process.env.CHROMIUM_EXECUTABLE;
 browser=await chromium.launch(launch);const context=await browser.newContext({viewport:{width:1500,height:1100},acceptDownloads:true});const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));const base=`http://127.0.0.1:${port}`;
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#result-count').textContent==='0 orders');
 assert(await page.locator('#empty').isVisible());assert.equal(await page.locator('#workspace').inputValue(),'live');assert(!/portfolio|job application|prototype/i.test(await page.locator('body').innerText()));
 const meta=await(await context.request.get(base+'/api/meta')).json(),today=meta.today;const day=n=>{const date=new Date(today+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+n);return date.toISOString().slice(0,10);};
 await page.locator('#add-order').click();await page.locator('#order-id').fill('TEST-101');await page.locator('#order-city').fill('Dhaka');await page.locator('#order-area').fill('Mirpur');await page.locator('#order-date').fill(day(-4));await page.locator('#order-expected').fill(day(-1));await page.locator('#order-source').fill('Temporary browser test fixture');await page.locator('#save-order').click();await page.waitForFunction(()=>!document.querySelector('#drawer').hidden);
 assert.equal(await page.locator('#stat-orders').textContent(),'1');assert.equal(await page.locator('#stat-overdue').textContent(),'1');assert(await page.locator('#review-form').isVisible());
 const size=await page.locator('td').first().evaluate(el=>parseFloat(getComputedStyle(el).fontSize));assert(size>=13);
 await page.locator('#edit-order').click();await page.locator('#order-delivered').fill(today);await page.locator('#change-note').fill('Delivery confirmation received in test fixture.');await page.locator('#save-order').click();await page.waitForFunction(()=>!document.querySelector('#order-dialog').open);
 assert.equal(await page.locator('#stat-delivered').textContent(),'1');assert.equal(await page.locator('#stat-overdue').textContent(),'0');
 await page.locator('#edit-status').selectOption('In review');await page.locator('#edit-owner').selectOption('Support desk');await page.locator('#edit-note').fill('<img src=x onerror="window.__xss=1"> Evidence checked.');await page.locator('#save').click();await page.waitForSelector('.form-message.success');assert.equal(await page.evaluate(()=>window.__xss),undefined);
 await page.locator('#edit-status').selectOption('Resolved');await page.locator('#edit-resolution').selectOption('Delivery confirmed');await page.locator('#edit-note').fill('Recorded delivery confirmed in fixture.');await page.locator('#save').click();await page.waitForSelector('.form-message.success');assert.equal(await page.locator('#stat-open').textContent(),'0');
 await page.locator('#close-drawer').click();
 await page.locator('#open-import').click();let csv='order_id,city,area,order_date,expected_delivery_date,dispatched_date,delivered_date,source_reference\nCSV-201,Dhaka,Gulshan,'+day(-2)+','+day(2)+',,,Temporary test fixture\n';
 await page.locator('#csv-file').setInputFiles({name:'orders.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});await page.locator('#preview-import').click();await page.waitForFunction(()=>!document.querySelector('#confirm-import').disabled);assert.equal(await page.locator('#stat-orders').textContent(),'1');await page.locator('#confirm-import').click();await page.waitForFunction(()=>!document.querySelector('#import-dialog').open);assert.equal(await page.locator('#stat-orders').textContent(),'2');
 await page.locator('#search').fill('CSV-201');assert.equal(await page.locator('[data-order]').count(),1);await page.locator('[data-order]').click();assert(await page.locator('#review-form').isHidden());await page.locator('#close-drawer').click();await page.locator('#reset').click();
 await page.locator('#workspace').selectOption('demo');await page.waitForFunction(()=>document.querySelector('#stat-orders').textContent==='120');assert(await page.locator('#live-actions').isHidden());
 await page.locator('#workspace').selectOption('live');await page.waitForFunction(()=>document.querySelector('#stat-orders').textContent==='2');await page.reload();await page.waitForFunction(()=>document.querySelector('#stat-orders').textContent==='2');
 const downloadPromise=page.waitForEvent('download');await page.locator('#export-orders').click();const download=await downloadPromise;assert.equal(download.suggestedFilename(),'pouchhai-orders.csv');
 await page.locator('#search').fill('MISSING');assert(await page.locator('#empty').isVisible());await page.locator('#reset').click();
 await page.locator('#nav-context').click();assert(await page.locator('#context-dialog').isVisible());await page.locator('#close-context').click();
 // A separate write must appear through the actual 30-second refresh timer.
 const external=await context.request.post(base+'/api/order?workspace=live',{headers:{'X-Review-Client':'pouchhai'},data:{order_id:'AUTO-301',city:'Dhaka',area:'',order_date:today,expected_delivery_date:day(2),source_reference:'Temporary refresh test fixture'}});assert(external.ok());
 await page.waitForFunction(()=>document.querySelector('#stat-orders').textContent==='3',{},{timeout:35000});
 if(process.env.SCREENSHOT_DIR){fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'desktop.png'),fullPage:true});}
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('#add-order').click();assert(await page.locator('#order-id').isVisible());await page.locator('#close-order-dialog').click();
 if(process.env.SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS: empty own workspace, neutral branding, add own order, readable fonts, date update, current delay, review save/closure, escaped notes, CSV preview/import, demo separation, reload persistence, exports, search, help, actual 30-second local refresh and mobile form/overflow.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exit(1);});
