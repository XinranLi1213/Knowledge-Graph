const {createRequire}=require('node:module'),path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {chromium}=createRequire(path.join(path.dirname(process.execPath),'..','node_modules','runtime.js'))('playwright');
(async()=>{
 const server=spawn('python',['tools/serve.py'],{env:{...process.env,AGENT_PROVIDER:'rules',AGENT_PORT:'0',AGENT_DB_PATH:'.runtime/browser-agent-'+Date.now()+'.sqlite3'},windowsHide:true,stdio:['ignore','pipe','pipe']});
 let browser;
 try{
  const url=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Local Agent did not start')),15000);server.stdout.on('data',b=>{const m=b.toString().match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]);}});server.on('exit',code=>{clearTimeout(timer);reject(Error('Server exit '+code));});});
  browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
  const page=await browser.newPage({viewport:{width:1512,height:982}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url);await page.locator('#enter-teacher').click();await page.locator('#loading').waitFor({state:'hidden'});
  await page.selectOption('#person','DEMO001');await page.locator('#loading').waitFor({state:'hidden'});await page.locator('[data-mode="diagnosis"]').click();
  await page.locator('#search').fill('通信电子线路');await page.locator('#search-results button').first().click();await page.waitForTimeout(450);
  await page.locator('#agent-toggle').click();await page.waitForFunction(()=>document.querySelector('#agent-diagnostic').textContent.includes('53.17'));
  assert.match(await page.locator('#agent-mode').innerText(),/规则演示/);
  const position=await page.locator('[data-node-id="C05"]').getAttribute('transform'),zoom=await page.locator('#graph > g').getAttribute('transform');
  await page.locator('#agent-question').fill('为什么这门课需要关注？');await page.locator('#agent-send').click();
  await page.waitForFunction(()=>document.querySelector('#agent-messages').textContent.includes('规则演示回答'));
  assert.match(await page.locator('#agent-messages').innerText(),/依据 r1/);
  await page.locator('#agent-demo').click();await page.waitForFunction(()=>document.querySelector('#agent-context').textContent.includes('评价 r2'));
  await page.waitForFunction(()=>document.querySelector('#agent-diagnostic').textContent.includes('59.12'));
  assert.match(await page.locator('#sidebar .score-line').innerText(),/59.1/);
  assert.match(await page.locator('#agent-messages').innerText(),/历史评价，当前为 r2/);
  assert.equal(await page.locator('[data-node-id="C05"]').getAttribute('transform'),position);
  assert.equal(await page.locator('#graph > g').getAttribute('transform'),zoom);
  await page.locator('#agent-question').fill('现在和之前有什么变化？');await page.locator('#agent-send').click();
  await page.waitForFunction(()=>{const t=document.querySelectorAll('.agent-turn');return t.length>=2&&t[t.length-1].textContent.includes('节点结果变化');});
  assert.match(await page.locator('.agent-turn').last().innerText(),/依据 r2/);
  await page.screenshot({path:'review/agent-console-desktop.png',fullPage:true});
  // Full-snapshot API: unrelated evidence changes revalidate C05 without regeneration.
  const result=await page.evaluate(async()=>{
   const q=new URLSearchParams({subject_type:'student',subject_id:'DEMO001',scenario:'mixed_evidence'});
   const snapshot=await (await fetch('/api/agent/snapshot?'+q)).json();snapshot.revision=3;
   snapshot.evidence.find(e=>e.node_id==='C09.K01').title='与C05无关的证据描述修订';
   return (await fetch('/api/agent/snapshots',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({subject_type:'student',subject_id:'DEMO001',scenario:'mixed_evidence',audience:'teacher',base_revision:2,event_id:'browser-independent-evidence',snapshot})})).json();
  });assert.equal(result.changed,true);
  await page.waitForFunction(()=>document.querySelector('#agent-context').textContent.includes('评价 r3'));
  await page.waitForFunction(()=>document.querySelector('#agent-diagnostic').textContent.includes('依赖未变'));
  await page.locator('#agent-close').click();await page.selectOption('#role','student');await page.locator('#loading').waitFor({state:'hidden'});
  await page.locator('#agent-toggle').click();assert.ok(await page.locator('#agent-demo').isHidden());
  await page.waitForFunction(()=>document.querySelector('#agent-context').textContent.includes('r3'));
  await page.locator('#agent-diagnostic .agent-result').waitFor();
  assert.equal(await page.locator('.agent-turn').count(),0);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'review/agent-console-mobile.png',fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#agent-close').click();assert.ok(await page.locator('#agent-console').isHidden());
  assert.deepEqual(errors,[]);
  fs.writeFileSync('review/agent-browser-check.json',JSON.stringify({status:'passed',provider:'rules_demo',real_model_called:false,checks:['automatic diagnosis on node selection','context-bound follow-up','demo assessment publishes r2 facts','automatic new diagnosis','historical r1 answer label','next question binds r2','unrelated evidence revalidates without regeneration','diagnosis updates preserve graph coordinates and zoom','teacher/student conversation isolation','student cannot use demo update button','390px drawer/no overflow','no page errors']},null,2));
  console.log('Agent browser checks passed');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
