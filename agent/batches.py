"""Bounded, resumable model generation using the service's in-memory provider."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from .engine import now,uid,Conflict
from .pedagogy import PROMPT_VERSION
from .context import ref

class Batches:
    def __init__(self,engine):
        self.engine=engine;engine.batch_manager=self;self.lock=threading.RLock();self.thread=None
        for batch in engine.store.all('batch'):
            if batch['state']=='running':batch.update(state='paused',reason='服务重启，等待显式继续');self.save(batch)
    def save(self,batch):self.engine.store.put('batch',batch['batch_id'],batch)
    def get(self,id):
        batch=self.engine.store.get('batch',id)
        if not batch:raise ValueError('批次不存在')
        return batch
    def scopes(self):
        e=self.engine
        return [(e.scope({'type':'class','id':'COMM-DEMO-40'},'mixed_evidence'),'teacher'),(e.scope({'type':'student','id':'DEMO001'},'mixed_evidence'),'teacher'),(e.scope({'type':'student','id':'DEMO001'},'mixed_evidence'),'student')]
    def tasks(self,mode,scope,audience):
        scopes=self.scopes() if mode in ('sample','first_release') else [(scope,audience)]
        tasks=[]
        for s,role in scopes:
            ids=[None,'A01','C01','C02','C05','C02.K03','C05.K04','C09.K01'] if mode=='sample' else [None]+list(self.engine.nodes)
            for nid in ids:
                self.engine.context(s,role,nid)
                tasks.append({'scope':s,'audience':role,'node_id':nid,'snapshot_ref':ref(self.engine.ensure(s))})
        return tasks
    def start(self,mode,scope,audience,max_tasks=8,token_budget=200000):
        if mode not in ('sample','scope','first_release'):raise ValueError('生成范围无效')
        if type(max_tasks) is not int or not 1<=max_tasks<=417:raise ValueError('单批任务预算为1–417')
        if type(token_budget) is not int or not 1000<=token_budget<=6000000:raise ValueError('token停止阈值为1000–6000000')
        if self.engine.provider.origin!='model':raise PermissionError('请先配置真实API')
        if mode!='sample' and not any(b.get('review',{}).get('accepted') and b['mode']=='sample' and b.get('prompt_version')==PROMPT_VERSION and b.get('provider')==self.engine.provider.identity for b in self.engine.store.all('batch')):raise ValueError('请先完成当前模型的代表性样本验证与质量审核')
        tasks=self.tasks(mode,scope,audience)
        with self.lock:
            if any(b['state']=='running' for b in self.engine.store.all('batch')):raise Conflict('已有生成批次正在执行')
            batch={'batch_id':uid('batch'),'mode':mode,'state':'running','prompt_version':PROMPT_VERSION,'provider':self.engine.provider.identity,'tasks':tasks,'cursor':0,'results':[],'max_tasks':max_tasks,'token_budget':token_budget,'tokens_used':0,'calls_used':0,'reason':None,'created_at':now(),'updated_at':now()}
            self.save(batch);self.launch(batch['batch_id']);return self.summary(batch)
    def launch(self,id):self.thread=threading.Thread(target=self.work,args=(id,),daemon=True,name='diagnosis-batch');self.thread.start()
    def summary(self,b):return {k:v for k,v in b.items() if k!='tasks'}|{'total_tasks':len(b['tasks']),'total_tokens_used':sum(r['usage']['input_tokens']+r['usage']['output_tokens'] for r in b['results']),'total_calls_used':sum(r['usage']['model_calls'] for r in b['results'])}
    def resume(self,id):
        with self.lock:
            b=self.get(id)
            if b['state']=='running':return self.summary(b)
            if self.engine.provider.origin!='model' or b['provider']!=self.engine.provider.identity:raise ValueError('请恢复该批次原模型配置')
            if any(x['state']=='running' for x in self.engine.store.all('batch')):raise Conflict('已有运行批次')
            if b['cursor']>=len(b['tasks']):raise ValueError('该批次已完成')
            if b['reason']=='本批预算到达；可继续剩余任务':b.update(tokens_used=0,calls_used=0)
            b.update(state='running',reason=None,updated_at=now());self.save(b);self.launch(id);return self.summary(b)
    def cancel(self,id):
        with self.lock:
            b=self.get(id);b.update(state='paused',reason='用户暂停；已在运行的单项仍保留结果',updated_at=now());self.save(b);return self.summary(b)
    def review(self,id,value):
        with self.lock:
            b=self.get(id)
            if b['mode']!='sample' or b['cursor']<len(b['tasks']):raise ValueError('样本批次尚未完成')
            success=[r for r in b['results'] if r['state'] in ('succeeded','reused')]
            if len(success)/len(b['tasks'])<.95:raise ValueError('样本最终成功率未达95%，请先修复失败')
            if not isinstance(value,dict) or value.get('reviewer_type') not in ('teacher','assistant_manual_review') or not isinstance(value.get('notes'),str) or len(value['notes'])<20:raise ValueError('需要明确审核者与具体审核依据')
            scores=value.get('scores',[])
            if len(scores)!=len(success) or any(type(x) not in (int,float) or not 1<=x<=5 for x in scores) or sum(scores)/len(scores)<4:raise ValueError('需要逐项评分且平均至少4/5')
            if value.get('critical_errors')!=0:raise ValueError('关键事实错误未清零')
            b['review']={**value,'accepted':True,'reviewed_at':now()};self.save(b);return self.summary(b)
    def work(self,id):
        processed=0
        try:
            while True:
                with self.lock:
                    b=self.get(id)
                    if b['state']!='running':return
                    if b['cursor']>=len(b['tasks']):b.update(state='completed',reason=None);self.save(b);return
                    if processed>=b['max_tasks'] or b['tokens_used']>=b['token_budget']:b.update(state='paused',reason='本批预算到达；可继续剩余任务');self.save(b);return
                    tasks=b['tasks'][b['cursor']:b['cursor']+min(2,b['max_tasks']-processed)]
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(lambda task:self.execute(task,b['provider']),tasks))
                for result in results:
                    with self.lock:
                        b=self.get(id);b['results'].append(result);b['cursor']+=1;b['tokens_used']+=result['usage']['input_tokens']+result['usage']['output_tokens'];b['calls_used']+=result['usage']['model_calls'];b['updated_at']=now();processed+=1
                        if result.get('error_code') in ('authentication','insufficient_balance','permission'):b.update(state='paused',reason=result['error'])
                        if len(b['results'])>=3 and all(r.get('error_code') in ('network','timeout','invalid_response','rate_limit') for r in b['results'][-3:]):b.update(state='paused',reason='连续3项连接或响应失败，已自动暂停；检查连接后可继续')
                        self.save(b)
        except Exception as error:
            with self.lock:
                b=self.get(id);b.update(state='paused',reason=str(error)[:160],updated_at=now());self.save(b)
    def execute(self,task,provider):
        if self.engine.provider.identity!=provider or self.engine.provider.origin!='model':raise ValueError('模型配置已变化，批次暂停')
        if ref(self.engine.ensure(task['scope']))!=task['snapshot_ref']:raise ValueError('评价已更新，停止旧版批次；请创建新批次')
        artifact=self.engine.fresh_artifact(task['scope'],task['audience'],task['node_id'])
        if artifact and artifact.get('generation',{}).get('prompt_version')==PROMPT_VERSION and artifact.get('output',{}).get('sections'):
            return {**task,'state':'reused','artifact_id':artifact['artifact_id'],'usage':{'model_calls':0,'input_tokens':0,'output_tokens':0}}
        request=self.engine.ensure_diagnosis(task['scope'],task['audience'],task['node_id'],'retry');run=request['run']
        while run['state'] in ('queued','running'):
            self.engine.process_one(run['run_id'])
            time.sleep(.1);run=self.engine.store.get('agent_run',run['run_id'])
        return {**task,'state':run['state'],'artifact_id':run.get('artifact_id'),'run_id':run['run_id'],'usage':run['usage'],'error_code':run.get('error_code'),'error':run.get('error')}
