const {createRequire}=require('node:module'),path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const req=createRequire(path.join(path.dirname(process.execPath),'..','node_modules','runtime.js'));
const {chromium}=req('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
 const page=await browser.newPage({viewport:{width:1512,height:982}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const ready=async()=>{await page.locator('#loading').waitFor({state:'hidden'});await page.waitForSelector('g.node');};
 const pick=async(selector,value)=>{await page.selectOption(selector,value);await ready();};
 const find=async text=>{await page.locator('#search').fill(text);await page.locator('#search-results button').first().click();await page.waitForTimeout(400);};
 const positions=()=>page.locator('g.node').evaluateAll(es=>es.map(e=>[e.dataset.nodeId,e.getAttribute('transform')]));
 await page.goto('http://127.0.0.1:8765');await page.locator('#enter-teacher').click();await ready();await page.waitForTimeout(400);
 assert.equal(await page.locator('g.node').count(),30);
 await page.locator('[data-mode="diagnosis"]').click();await find('通信电子线路');
 assert.match(await page.locator('#sidebar').innerText(),/49.7/);
 await page.locator('#zoom-in').click();await page.waitForTimeout(350);
 const before=await positions(),zoomBefore=await page.locator('#graph > g').getAttribute('transform');
 await pick('#person','DEMO001');
 assert.match(await page.locator('#sidebar').innerText(),/53.2/);assert.match(await page.locator('#sidebar').innerText(),/学习进度 60%/);
 assert.deepEqual(await positions(),before);assert.equal(await page.locator('#graph > g').getAttribute('transform'),zoomBefore);
 assert.equal(await page.locator('[data-node-id="C05"] path.shape').evaluate(e=>getComputedStyle(e).stroke),'rgb(223, 116, 62)');
 assert.match(await page.locator('#sidebar').innerText(),/帮扶依据/);
 await page.screenshot({path:'review/personalized-teacher.png',fullPage:true});
 await pick('#role','student');assert.match(await page.locator('#sidebar').innerText(),/复习建议/);assert.doesNotMatch(await page.locator('#sidebar').innerText(),/帮扶依据/);
 assert.match(await page.locator('#sidebar').innerText(),/53.2/);assert.deepEqual(await positions(),before);
 await page.locator('[data-resource]').first().click();await page.waitForFunction(()=>document.querySelector('#resource-content').textContent.includes('自查'));
 assert.ok(await page.locator('#resource-dialog').isVisible());await page.locator('#resource-close').click();
 await page.locator('.close').click();assert.equal(await page.locator('.ability-profile button').count(),12);
 await page.screenshot({path:'review/personalized-student.png',fullPage:true});
 await find('通信电子线路');await pick('#person','DEMO002');assert.match(await page.locator('#sidebar').innerText(),/46.7/);
 await pick('#person','DEMO001');assert.match(await page.locator('#sidebar').innerText(),/53.2/);
 await pick('#scenario','course_totals_only');await page.locator('#expand').click();
 assert.equal(await page.locator('g.node').count(),138);assert.equal(await page.locator('path.pending').count(),108);
 await find('快速傅里叶');assert.match(await page.locator('#sidebar').innerText(),/已完成学习/);assert.match(await page.locator('.score-line strong').innerText(),/—/);
 await pick('#scenario','mixed_evidence');await find('调幅与检波');assert.match(await page.locator('#sidebar').innerText(),/尚未学习/);
 await find('振荡器');assert.match(await page.locator('#sidebar').innerText(),/学习中/);assert.match(await page.locator('#sidebar').innerText(),/待评价/);
 await page.locator('.close').click();await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
 await page.screenshot({path:'review/personalized-mobile.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.locator('#toggle-sidebar').click();assert.ok(await page.locator('#sidebar').isHidden());
 // Fresh student entry must choose a named demo identity, without authentication.
 const entry=await browser.newPage({viewport:{width:1360,height:900}});entry.on('pageerror',e=>errors.push(String(e)));
 await entry.goto('http://127.0.0.1:8765');await entry.locator('#choose-student').click();await entry.selectOption('#entry-student','DEMO003');await entry.locator('#enter-student').click();
 await entry.locator('#loading').waitFor({state:'hidden'});assert.equal(await entry.locator('#role').inputValue(),'student');assert.match(await entry.locator('#class-name').innerText(),/DEMO2024003/);
 assert.equal(await entry.locator('.ability-profile button').count(),12);
 // A failed object load masks old facts and is retryable.
 await entry.route('**/snapshots/student/DEMO002/mixed_evidence.json',route=>route.abort());
 await entry.selectOption('#person','DEMO002');await entry.locator('#loading button').waitFor();
 assert.ok(await entry.locator('#loading').isVisible());assert.ok(await entry.locator('.canvas-wrap').isHidden());
 await entry.unroute('**/snapshots/student/DEMO002/mixed_evidence.json');await entry.locator('#loading button').click();await entry.locator('#loading').waitFor({state:'hidden'});
 assert.match(await entry.locator('#class-name').innerText(),/DEMO2024002/);
 assert.deepEqual(errors,[]);
 fs.writeFileSync('review/personalization-browser-check.json',JSON.stringify({status:'passed',browser:'Chrome headless',checks:['teacher class entry','personal identity entry','individual vs class scores','teacher/student same facts and isolated advice','subject/role switch preserves coordinates and zoom','risk stroke survives selection','12 ability profile','local resource viewer','subject switching','course total 108 null knowledge','not-started vs learning without assessment','390px no overflow','mobile panel toggle','failed request masks old facts and retry','no runtime errors']},null,2));
 console.log('Personalization browser checks passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
