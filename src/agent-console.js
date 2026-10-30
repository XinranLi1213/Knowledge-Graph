import {esc} from './sidebar.js';
const $=s=>document.querySelector(s);
const equal=(a,b)=>a?.snapshot_id===b?.snapshot_id&&a?.revision===b?.revision;
export class AgentConsole{
 constructor({refresh,choose}){
  this.refresh=refresh;this.choose=choose;this.key=null;this.state=null;this.polling=false;this.refreshing=false;
  document.body.insertAdjacentHTML('beforeend',`<button id="agent-toggle" aria-expanded="false">✦ 智能助手</button><section id="agent-console" hidden aria-label="智能助手"><div class="agent-head"><strong>智能助手</strong><span id="agent-mode"></span><button id="agent-close" aria-label="收起智能助手">×</button></div><div id="agent-context"></div><div class="agent-scroll"><div id="agent-diagnostic"></div><div id="agent-messages" aria-live="polite"></div></div><div id="agent-error" role="status"></div><div class="agent-controls"><button id="agent-demo" hidden>模拟 C05 补测</button><button id="agent-retry">重新诊断</button></div><form id="agent-form"><label class="sr-only" for="agent-question">继续追问</label><textarea id="agent-question" maxlength="2000" rows="2" placeholder="例如：为什么这门课需要关注？"></textarea><button id="agent-send" type="submit">发送</button></form><details id="agent-log"><summary>运行详情</summary><div id="agent-runs"></div></details></section>`);
  $('#agent-toggle').onclick=()=>{const open=$('#agent-console').hidden;$('#agent-console').hidden=!open;$('#agent-toggle').setAttribute('aria-expanded',String(open));};
  $('#agent-close').onclick=()=>{$('#agent-console').hidden=true;$('#agent-toggle').setAttribute('aria-expanded','false');};
  $('.agent-head').insertAdjacentHTML('beforeend','<button id="agent-settings-open" aria-label="API设置">API 设置</button>');
  $('#agent-console').insertAdjacentHTML('beforeend',`<section id="agent-settings" hidden><button id="agent-settings-back">← 返回诊断</button><h3>API 设置</h3><p class="subtle">用于当前本机服务 · OpenAI</p><form id="agent-settings-form"><label>模型名称<input id="agent-model-input" required maxlength="120" placeholder="填写账户可用的模型名称" autocomplete="off"></label><label>API Key<input id="agent-key-input" type="password" maxlength="1024" placeholder="输入密钥，或留空沿用当前配置" autocomplete="new-password" spellcheck="false"></label><p class="subtle">密钥仅保存在服务内存，重启后清除；不写入浏览器存储。连接测试会发送演示上下文并产生少量API用量。</p><p id="agent-settings-status" role="status"></p><div class="agent-settings-actions"><button id="agent-test-enable" type="submit">测试并启用</button><button id="agent-disconnect" type="button">断开 API</button></div></form></section>`);
  $('#agent-settings-open').onclick=()=>this.openSettings();
  $('#agent-settings-back').onclick=()=>{$('#agent-settings').hidden=true;$('#agent-console').classList.remove('settings-open');};
  $('#agent-settings-form').onsubmit=e=>{e.preventDefault();this.configure();};$('#agent-disconnect').onclick=()=>this.disconnect();
  $('#agent-settings').insertAdjacentHTML('beforeend','<button id="agent-export-bundle">保存为静态成果</button>');
  $('#agent-export-bundle').onclick=async()=>{try{const r=await this.api('bundle/export',{});$('#agent-settings-status').textContent=`已保存 ${r.exported_model_diagnoses} 条模型诊断；不包含私人对话。`;}catch(e){$('#agent-settings-status').textContent=e.message;}};
  $('#agent-retry').onclick=()=>this.diagnose(true);
  $('#agent-demo').onclick=()=>this.demo();$('#agent-form').onsubmit=e=>{e.preventDefault();this.ask();};
  $('#agent-console').onclick=e=>{const button=e.target.closest('[data-agent-node]');if(button)this.choose(button.dataset.agentNode);};
  this.timer=setInterval(()=>this.poll(),1500);
 }
 async openSettings(){
  $('#agent-settings').hidden=false;$('#agent-console').classList.add('settings-open');$('#agent-key-input').value='';
  try{const value=await this.api('config');$('#agent-model-input').value=value.model||'';$('#agent-settings-status').textContent=value.configured?`已配置 ${value.model}${value.verified?' · 连接已验证':' · 尚未测试'}`:'未配置 · 可浏览已保存诊断';}
  catch(e){$('#agent-settings-status').textContent=e.message;}
 }
 async configure(){
  $('#agent-test-enable').disabled=true;$('#agent-disconnect').disabled=true;
  const body={model:$('#agent-model-input').value.trim(),api_key:$('#agent-key-input').value.trim()};$('#agent-key-input').value='';
  $('#agent-settings-status').textContent='正在验证连接与结构化输出…';
  try{const value=await this.api('config/test',body);$('#agent-settings-status').textContent=`连接成功 · ${value.model} · 可继续追问`;await this.poll();}
  catch(e){$('#agent-settings-status').textContent=e.message;}finally{body.api_key='';$('#agent-test-enable').disabled=false;$('#agent-disconnect').disabled=false;}
 }
 async disconnect(){try{await this.api('config/disconnect',{});$('#agent-key-input').value='';$('#agent-settings-status').textContent='已断开 · 已保存诊断仍可浏览';await this.poll();}catch(e){$('#agent-settings-status').textContent=e.message;}}
 binding(){const b=this.bound;return {subject_type:b.view.subject.type,subject_id:b.view.subject.id,scenario:b.view.scenario,audience:b.view.role,node_id:b.node||''};}
 async api(path,body){const r=await fetch('/api/agent/'+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store'}:{cache:'no-store'});const value=await r.json();if(!r.ok)throw Error(value.error||'智能体请求失败');return value;}
 update(view,node,mode){
  const key=JSON.stringify([view.subject,view.scenario,view.role,node]);const version={snapshot_id:view.snapshot.snapshot_id,revision:view.snapshot.revision};
  const contextChanged=key!==this.key;const changed=contextChanged||!equal(version,this.bound?.version);
  this.bound={view,node,mode,version};
  if(changed){this.key=key;if(contextChanged){this.state=null;this.waiting=false;$('#agent-question').value='';}$('#agent-error').textContent='';this.paint();clearTimeout(this.debounce);this.debounce=setTimeout(()=>this.diagnose(),100);}
  else this.paintSide();
 }
 async diagnose(retry=false){if(!this.bound)return;if(!this.bound.view.agentAvailable){$('#agent-error').textContent='请用 python tools/serve.py 启动智能体服务。';return;}
  const key=this.key;try{await this.api('diagnose',{...this.binding(),retry});if(key===this.key)await this.poll();}catch(e){if(key===this.key)$('#agent-error').textContent=e.message;}
 }
 async poll(){if(!this.bound?.view.agentAvailable||this.polling)return;this.polling=true;const key=this.key;
  try{const value=await this.api('state?'+new URLSearchParams(this.binding()));if(key!==this.key)return;this.state=value;this.paint();
   if(!equal(value.snapshot_ref,this.bound.version)&&!this.refreshing){this.refreshing=true;try{await this.refresh();}finally{this.refreshing=false;}}
  }catch(e){if(key===this.key)$('#agent-error').textContent=e.message;}finally{this.polling=false;}
 }
 paint(){if(!this.bound)return;const {view,node,version}=this.bound;
  $('#agent-context').textContent=`${view.profile?.display_name||view.displayName} · ${node?view.nodes.find(n=>n.id===node)?.label:'总体画像'} · 评价 r${version.revision}`;
  const canAsk=this.state?.capabilities?.can_ask===true;
  $('#agent-mode').textContent=canAsk?'API 已配置':view.agentAvailable?'只读浏览':'服务未连接';
  const artifact=this.state?.artifact;const ready=artifact&&equal(artifact.validated_against,version);
  const failed=this.state?.runs.filter(r=>r.mode==='diagnosis').at(-1)?.state==='failed';
  const historical=this.state?.historical_artifact;
  $('#agent-diagnostic').innerHTML=ready?`<div class="agent-result"><small>${artifact.origin==='rules_demo'?'规则演示':'模型解释'} · r${artifact.validated_against.revision}${artifact.generated_against.revision!==artifact.validated_against.revision?' · 依赖未变，已重新验证':''}</small><p>${esc(artifact.output.explanation)}</p>${this.citations(artifact.output)}</div>`:historical?`<div class="agent-result historical"><small>历史诊断 · r${historical.validated_against.revision} · 当前依据已变化</small><p>${esc(historical.output.explanation)}</p></div>`:`<p class="subtle">${failed?'诊断生成失败，最新评价不受影响。':canAsk?'暂无当前模型诊断，可点击生成。':'暂无已保存的模型诊断。'}</p>`;
  $('#agent-messages').innerHTML=(this.state?.turns||[]).map(t=>`<article class="agent-turn"><p class="agent-question-text">${esc(t.question)}</p><small>依据 r${t.snapshot_ref.revision}${!equal(t.snapshot_ref,version)?' · 历史评价，当前为 r'+version.revision:''}</small><p>${t.answer?esc(t.answer.explanation):t.state==='failed'?'本次回答失败，请重新提问。':'正在查阅依据…'}</p>${t.answer?this.citations(t.answer):''}</article>`).join('');
  const pending=this.waiting||(this.state?.turns||[]).some(t=>['queued','running'].includes(t.state));
  $('#agent-send').disabled=!view.agentAvailable||!canAsk||pending;
  $('#agent-question').disabled=!canAsk;$('#agent-question').placeholder=canAsk?'例如：为什么这门课需要关注？':'配置 API 后可继续追问';
  $('#agent-retry').disabled=!canAsk;$('#agent-retry').textContent=ready?'重新诊断':'生成诊断';
  $('#agent-demo').hidden=!(view.role==='teacher'&&view.subject.type==='student'&&view.scenario==='mixed_evidence'&&node==='C05');
  $('#agent-runs').innerHTML=(this.state?.runs||[]).slice(-4).map(r=>`<p>${esc({queued:'排队',running:'执行中',succeeded:'完成',failed:'失败',superseded:'已被新评价替代'}[r.state])} · r${r.snapshot_ref.revision} · 工具 ${r.tool_trace.length} 次 · 模型 ${r.usage.model_calls} 次${r.error?' · '+esc(r.error):''}</p>`).join('');
  this.paintSide();
 }
 citations(output){const resources=output.resource_ids.map(id=>this.bound.view.resourceMap.get(id)).filter(Boolean);
  return `<div class="agent-citations">${output.cited_node_ids.slice(0,4).map(id=>`<button data-agent-node="${esc(id)}">${esc(this.bound.view.nodes.find(n=>n.id===id)?.label||id)}</button>`).join('')}</div>${resources.length?`<div class="agent-resources">${resources.slice(0,2).map(r=>`<a href="${esc(r.url)}" target="_blank" rel="noopener">↗ ${esc(r.title)}</a>`).join('')}</div>`:''}${output.limitations.length?`<details class="agent-limits"><summary>局限说明</summary>${output.limitations.map(t=>`<p>${esc(t)}</p>`).join('')}</details>`:''}`;}
 paintSide(){document.querySelector('.agent-node-diagnosis')?.remove();if(!this.bound?.node||this.bound.mode!=='diagnosis')return;
  const body=$('#sidebar .panel-body');if(!body)return;const box=document.createElement('section');box.className='agent-node-diagnosis';
  const artifact=this.state?.artifact;const valid=artifact&&equal(artifact.validated_against,this.bound.version);
  const failed=this.state?.runs.filter(r=>r.mode==='diagnosis'&&equal(r.snapshot_ref,this.bound.version)).at(-1)?.state==='failed';
  box.innerHTML=`<small>智能诊断 · ${valid?(artifact.origin==='model'?'模型解释':'规则演示'):'待生成'}</small><p>${valid?esc(artifact.output.explanation):failed?'诊断暂未生成，可在智能助手中重试。':'暂无当前模型诊断，分数与进度独立显示。'}</p>`;body.prepend(box);
 }
 async ask(){const question=$('#agent-question').value.trim();if(!question||!this.bound||this.waiting||!this.state?.capabilities?.can_ask)return;
  const key=this.key,body={...this.binding(),question,snapshot_ref:this.bound.version};this.waiting=true;this.paint();
  try{await this.api('ask',body);if(key===this.key){$('#agent-question').value='';this.waiting=false;await this.poll();}}
  catch(e){if(key===this.key){this.waiting=false;$('#agent-error').textContent=e.message;this.paint();}}
 }
 async demo(){const key=this.key;$('#agent-demo').disabled=true;
  try{const result=await this.api('demo-update',{...this.binding(),base_revision:this.bound.version.revision,event_id:crypto.randomUUID()});if(key!==this.key)return;
   if(result.changed){await this.refresh();await this.poll();}else $('#agent-error').textContent='三次预设补测均已完成。';
  }catch(e){if(key===this.key)$('#agent-error').textContent=e.message;}finally{$('#agent-demo').disabled=false;}
 }
}
