// Reads existing real results only. Never configures credentials or starts generation.
const {createRequire}=require('node:module'),path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {chromium}=createRequire(path.join(path.dirname(process.execPath),'..','node_modules','runtime.js'))('playwright');
(async()=>{
 const server=spawn('python',['tests/serve_readonly_fixture.py'],{windowsHide:true,stdio:['ignore','pipe','pipe']});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('fixture startup timeout')),45000);server.stdout.on('data',b=>{const m=b.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]);}});server.on('exit',c=>{clearTimeout(timer);reject(Error('fixture exit '+c));});});
  browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
  const page=await browser.newPage({viewport:{width:1512,height:982}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);await page.locator('#enter-teacher').click();await page.locator('#loading').waitFor({state:'hidden'});
  await page.locator('[data-mode="diagnosis"]').click();await page.locator('#search').fill('模拟电子技术');await page.locator('#search-results button').first().click();await page.locator('#agent-toggle').click();
  await page.waitForFunction(()=>document.querySelector('#agent-diagnostic').textContent.includes('71.28'));
  assert.ok(await page.locator('#agent-send').isDisabled());
  await page.screenshot({path:'review/agent-v5/real-teacher-C02.png',fullPage:true});
  await page.locator('#agent-close').click();await page.selectOption('#person','DEMO001');await page.selectOption('#role','student');await page.locator('#search').fill('小信号放大');await page.locator('#search-results button').first().click();await page.locator('#agent-toggle').click();
  await page.waitForFunction(()=>document.querySelector('#agent-context').textContent.includes('小信号放大'));
  await page.waitForFunction(()=>document.querySelector('#agent-diagnostic .agent-diagnosis-section') || document.querySelector('#agent-diagnostic').textContent.includes('验证'));
  await page.screenshot({path:'review/agent-v5/real-student-knowledge.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'review/agent-v5/real-readonly-mobile.png',fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.equal(await page.evaluate(async()=>{const r=await fetch('/api/agent/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:'只读拦截检查'})});return r.status;}),403);
  assert.deepEqual(errors,[]);
  fs.writeFileSync('review/agent-v5/real-browser-check.json',JSON.stringify({status:'passed',source:'packaged_real_model_artifacts',external_calls:0,checks:['teacher course result','student knowledge result','no-key question disabled and backend rejection','390px no overflow','no page errors']},null,2));
  console.log('Real packaged results browser checks passed; no external calls');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
