from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy
import json
import math
import threading
import uuid
from jsonschema import Draft202012Validator
from .storage import Store
from .context import Context,digest,ref
from .provider import Provider

def now():return datetime.now(timezone.utc).isoformat()
def uid(prefix):return prefix+'-'+uuid.uuid4().hex
def record(kind,**values):return {'schema_version':'3.0.0','record_type':kind,**values}
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

class Conflict(ValueError):pass

class Engine:
    def __init__(self,root,db_path,provider=None,start_worker=True):
        self.root=Path(root);self.data=self.root/'review'/'personalization-v2';self.provider=provider or Provider()
        self.graph=read(self.data/'data/graph.json');self.registry=read(self.data/'data/students.json');self.resources=read(self.data/'data/resources.json');self.policy=read(self.data/'data/evaluation-policy.json')
        self.manifest=read(self.data/'manifest.json');self.nodes={n['id']:n for n in self.graph['nodes']}
        self.profiles={p['student_id']:p for p in self.registry['students'] if p['student_id'] in self.manifest['demo_student_ids']}
        self.incoming={k:[e for e in self.graph['edges'] if e['target']==k and e['aggregation_weight'] is not None] for k in self.nodes}
        self.snapshot_schema=read(self.data/'contracts/contract.schema.json');self.snapshot_validator=Draft202012Validator({'$ref':'#/$defs/snapshot','$defs':self.snapshot_schema['$defs']})
        self.store=Store(db_path);self.lock=self.store.lock;self.wake=threading.Event();self.stopping=False
        for run in self.store.all('agent_run'):
            if run['state']=='running':run['state']='queued';run['updated_at']=now();self.store.put('agent_run',run['run_id'],run)
        self.worker=threading.Thread(target=self._worker,daemon=True,name='teaching-agent')
        if start_worker:self.worker.start()
    def scope(self,subject,scenario):
        if not isinstance(subject,dict) or set(subject)!={'type','id'}:raise ValueError('对象格式无效')
        if not any(e['subject']==subject and e['scenario_id']==scenario for e in self.manifest['snapshot_entries']):raise ValueError('对象或场景不存在')
        if subject['type']=='student' and subject['id'] not in self.profiles:raise ValueError('仅开放3名模拟学生')
        return {'subject':subject,'scenario_id':scenario}
    def key(self,scope):return digest(scope)
    def ensure(self,scope):
        with self.lock:
            pointer=self.store.pointer('snapshot:'+self.key(scope))
            if not pointer:
                entry=next(e for e in self.manifest['snapshot_entries'] if e['subject']==scope['subject'] and e['scenario_id']==scope['scenario_id'])
                snap=read(self.data/entry['path'])
                with self.store.transaction():
                    self.store.put('snapshot',snap['snapshot_id'],snap,snap['revision']);self.store.pointer('snapshot:'+self.key(scope),ref(snap))
            else:snap=self.store.get('snapshot',pointer['snapshot_id'],pointer['revision'])
            return snap
    def context(self,scope,audience,target,snapshot=None,dependencies=None):
        if audience not in ('teacher','student') or (scope['subject']['type']=='class' and audience!='teacher'):raise ValueError('角色无效')
        if target is not None and target not in self.nodes:raise ValueError('节点不存在')
        snap=snapshot or self.ensure(scope);previous=self.store.get('snapshot',snap['snapshot_id'],snap['revision']-1) if snap['revision']>1 else None
        return Context(self.graph,snap,self.profiles.get(scope['subject']['id'],{}),self.resources,self.policy,audience,target,previous,dependencies)
    def dkey(self,scope,audience,target):return 'diagnosis:'+self.key(scope)+':'+audience+':'+(target or '@overview')
    def artifact(self,scope,audience,target):
        pointer=self.store.pointer(self.dkey(scope,audience,target));return self.store.get('diagnostic_artifact',pointer['id']) if pointer else None
    def fresh_artifact(self,scope,audience,target,snapshot=None):
        snap=snapshot or self.ensure(scope);old=self.artifact(scope,audience,target)
        if not old:return None
        try:ctx=self.context(scope,audience,target,snap,old['dependencies']);same=ctx.fingerprint(self.provider.identity)==old['fingerprint']
        except ValueError:same=False
        if not same:return None
        if old['validated_against']!=ref(snap):
            old={**old,'artifact_id':uid('diag'),'validated_against':ref(snap),'created_at':now(),'validity':'fresh'}
            self.store.put('diagnostic_artifact',old['artifact_id'],old);self.store.pointer(self.dkey(scope,audience,target),{'id':old['artifact_id']})
        return old
    def ensure_diagnosis(self,scope,audience,target,trigger='view'):
        with self.lock:
            snap=self.ensure(scope);fresh=self.fresh_artifact(scope,audience,target,snap)
            if fresh and trigger!='retry':return {'artifact':fresh,'run':None}
            jobkey='job:'+self.dkey(scope,audience,target)+':'+str(snap['revision'])
            existing=self.store.pointer(jobkey)
            if existing:
                run=self.store.get('agent_run',existing['id'])
                if run and (run['state'] in ('queued','running') or (run['state']=='failed' and trigger!='retry')):
                    if run['state']=='queued' and trigger in ('view','retry') and run['trigger']=='evaluation_changed':run.update(trigger=trigger,updated_at=now());self.store.put('agent_run',run['run_id'],run)
                    return {'artifact':None,'run':run}
            # Validate target/scope before a persisted job is created.
            self.context(scope,audience,target,snap)
            run=self._new_run(scope,audience,target,snap,trigger,'diagnosis',None)
            self.store.pointer(jobkey,{'id':run['run_id']});self.wake.set();return {'artifact':None,'run':run}
    def _new_run(self,scope,audience,target,snapshot,trigger,mode,turn_id):
        run=record('agent_run',run_id=uid('run'),scope=scope,audience=audience,target_node_id=target,snapshot_ref=ref(snapshot),trigger=trigger,state='queued',mode=mode,artifact_id=None,turn_id=turn_id,error=None,tool_trace=[],usage={'model_calls':0,'input_tokens':0,'output_tokens':0},created_at=now(),updated_at=now())
        self.store.put('agent_run',run['run_id'],run);return run
    def ask(self,scope,audience,target,question,requested_ref=None):
        if not isinstance(question,str) or not question.strip() or len(question)>2000:raise ValueError('问题长度须为1–2000字符')
        with self.lock:
            latest=self.ensure(scope);snap=latest
            if requested_ref:
                if requested_ref.get('snapshot_id')!=latest['snapshot_id']:raise ValueError('问题评价不属于当前对象')
                snap=self.store.get('snapshot',latest['snapshot_id'],requested_ref.get('revision'))
                if not snap:raise ValueError('指定评价版本不存在')
            self.context(scope,audience,target,snap)
            session=digest({'scope':scope,'audience':audience,'target':target});old=self.artifact(scope,audience,target)
            turn=record('conversation_turn',turn_id=uid('turn'),session_id=session,scope=scope,audience=audience,target_node_id=target,snapshot_ref=ref(snap),discussed_artifact_id=old['artifact_id'] if old else None,question=question.strip(),state='queued',answer=None,origin=self.provider.origin,created_at=now())
            with self.store.transaction():
                self.store.put('conversation_turn',turn['turn_id'],turn);run=self._new_run(scope,audience,target,snap,'question','question',turn['turn_id'])
            self.wake.set();return {'turn':turn,'run':run}
    def state(self,scope,audience,target):
        with self.lock:
            snap=self.ensure(scope);self.context(scope,audience,target,snap)
            artifact=self.fresh_artifact(scope,audience,target,snap);old=self.artifact(scope,audience,target)
            runs=[r for r in self.store.all('agent_run') if r['scope']==scope and r['audience']==audience and r['target_node_id']==target]
            turns=[t for t in self.store.all('conversation_turn') if t['scope']==scope and t['audience']==audience and t['target_node_id']==target]
            return {'snapshot_ref':ref(snap),'artifact':artifact,'historical_artifact':{**old,'validity':'historical'} if old and not artifact else None,
                'runs':runs[-8:],'turns':[{**t,'historical':t['snapshot_ref']!=ref(snap)} for t in turns[-12:]],
                'provider':self.provider.origin,'model':self.provider.model if self.provider.mode=='openai' else None,
                'events':[{k:e[k] for k in ['event_id','before','after','affected_node_ids','created_at']} for e in self.store.all('evaluation_changed') if e['scope']==scope][-6:]}
    def _validate_snapshot(self,new,current):
        self.snapshot_validator.validate(new)
        for k in ['snapshot_id','subject','graph_ref','registry_version','policy_id','policy_version']:
            if new[k]!=current[k]:raise ValueError('评价绑定或策略版本不一致：'+k)
        if new['evaluation_context']['scenario_id']!=current['evaluation_context']['scenario_id'] or new['evaluation_context']['period_id']!=current['evaluation_context']['period_id']:raise ValueError('评价阶段不一致')
        if new['revision']!=current['revision']+1:raise Conflict('评价版本已更新，请刷新后重试')
        if set(new['node_results'])!=set(self.nodes):raise ValueError('必须提交完整节点结果')
        evidence={e['evidence_id']:e for e in new['evidence']}
        if len(evidence)!=len(new['evidence']) or any(e['subject']!=new['subject'] or e['node_id'] not in self.nodes for e in evidence.values()):raise ValueError('评价证据对象无效')
        for nid,r in new['node_results'].items():
            s=r['status'];val=s['achievement_rate'];cov=s['coverage_rate']
            if not math.isfinite(cov) or val is not None and not math.isfinite(val):raise ValueError('评价数值无效')
            if not set(r['evidence_refs'])<=set(evidence):raise ValueError('评价证据引用无效')
            if (val is None and r['evidence_refs']) or (val is not None and not r['evidence_refs']):raise ValueError('分数与评价依据不一致')
            expected='grey' if val is None or cov<self.policy['min_coverage'] else 'green' if val>=self.policy['green_min'] else 'yellow' if val>=self.policy['yellow_min'] else 'red'
            if s['health_color']!=expected or s['score_is_provisional']!=(0<cov<1):raise ValueError('成绩与状态不一致')
            if (s['grey_reason'] is not None)!=(expected=='grey') or val is None and cov!=0:raise ValueError('缺失评价语义无效')
            if s['aggregation_basis']=='weighted_inputs':
                es=self.incoming[nid]
                c=sum(e['aggregation_weight']*new['node_results'][e['source']]['status']['coverage_rate'] for e in es)
                score=sum(e['aggregation_weight']*new['node_results'][e['source']]['status']['coverage_rate']*(new['node_results'][e['source']]['status']['achievement_rate'] or 0) for e in es)/c if c else None
                if abs(c-cov)>2e-6 or (score is None)!=(val is None) or score is not None and abs(score-val)>2e-6:raise ValueError('加权结果不一致')
            if val is not None and s['aggregation_basis'] in ('knowledge_assessment','course_total'):
                if not any(evidence[i]['node_id']==nid and abs(evidence[i]['score']-val)<2e-6 for i in r['evidence_refs']):raise ValueError('直接得分与考核来源不一致')
        from collections import Counter
        results=new['node_results'];counts=Counter(r['status']['health_color'] for r in results.values())
        if new['summary']['health_counts']!={c:counts[c] for c in ['green','yellow','red','grey']}:raise ValueError('画像统计与节点不一致')
        expected_abilities={k for k,n in self.nodes.items() if n['level']=='L1_Ability'}
        if {a['node_id'] for a in new['summary']['ability_profile']}!=expected_abilities:raise ValueError('能力画像缺失')
        for a in new['summary']['ability_profile']:
            s=results[a['node_id']]['status']
            if a['score']!=s['achievement_rate'] or a['coverage']!=s['coverage_rate']:raise ValueError('能力画像数值不一致')
        for field,color,limit,reverse in [('weak_node_ids','red',6,False),('strength_node_ids','green',5,True)]:
            ordered=sorted([k for k,r in results.items() if r['status']['health_color']==color],key=lambda k:results[k]['status']['achievement_rate'],reverse=reverse)
            actual=new['summary'][field]
            if len(actual)!=min(limit,len(ordered)) or len(set(actual))!=len(actual) or any(k not in ordered for k in actual):raise ValueError('强弱项画像不一致')
            if [results[k]['status']['achievement_rate'] for k in actual]!=[results[k]['status']['achievement_rate'] for k in ordered[:limit]]:raise ValueError('强弱项排序不一致')
        provisional={k for k,r in results.items() if r['status']['score_is_provisional'] and r['status']['achievement_rate'] is not None and r['status']['achievement_rate']<60}
        if set(new['summary']['provisional_low_node_ids'])!=provisional:raise ValueError('阶段风险画像不一致')
    def submit(self,scope,new,base_revision,event_id,request_hash=None):
        if not isinstance(event_id,str) or not 1<=len(event_id)<=128:raise ValueError('event_id无效')
        request_hash=request_hash or digest({'scope':scope,'snapshot':new,'base_revision':base_revision})
        with self.lock:
            receipt=self.store.get('receipt',event_id)
            if receipt:
                if receipt['request_hash']!=request_hash or receipt['scope']!=scope:raise Conflict('事件ID已用于不同内容')
                return {**receipt['response'],'duplicate':True}
            existing=self.store.get('evaluation_changed',event_id)
            if existing:
                if existing['scope']!=scope or existing['request_hash']!=request_hash:raise Conflict('事件ID已用于不同内容')
                return {'changed':True,'duplicate':True,'event':existing,'snapshot_ref':existing['after']}
            current=self.ensure(scope)
            if base_revision!=current['revision']:raise Conflict('评价版本已更新，请刷新后重试')
            self._validate_snapshot(new,current);changes=[]
            for nid in self.nodes:
                a=current['node_results'][nid];b=new['node_results'][nid]
                for field in ('status','progress_source','evidence_refs','input_node_ids'):
                    if field=='status':
                        for key in a[field]:
                            if a[field][key]!=b[field][key]:changes.append({'node_id':nid,'field':'status.'+key,'before':a[field][key],'after':b[field][key]})
                    elif a[field]!=b[field]:changes.append({'node_id':nid,'field':field,'before':a[field],'after':b[field]})
            before_ev={e['evidence_id']:e for e in current['evidence']};after_ev={e['evidence_id']:e for e in new['evidence']}
            for eid in sorted(set(before_ev)|set(after_ev)):
                if before_ev.get(eid)!=after_ev.get(eid):changes.append({'node_id':(after_ev.get(eid) or before_ev[eid])['node_id'],'field':'evidence','before':before_ev.get(eid),'after':after_ev.get(eid)})
            if not changes:
                response={'changed':False,'duplicate':False,'event':None,'snapshot_ref':ref(current)}
                self.store.put('receipt',event_id,{'scope':scope,'request_hash':request_hash,'response':response});return response
            affected={c['node_id'] for c in changes}
            while True:
                parents={e['target'] for e in self.graph['edges'] if e['source'] in affected and e['relation_type'] in ('belongs_to','supports')}
                if parents<=affected:break
                affected|=parents
            event=record('evaluation_changed',event_id=event_id,scope=scope,before=ref(current),after=ref(new),request_hash=request_hash,changes=changes,affected_node_ids=sorted(affected),created_at=now())
            with self.store.transaction():
                self.store.put('snapshot',new['snapshot_id'],new,new['revision']);self.store.put('evaluation_changed',event_id,event)
                self.store.pointer('snapshot:'+self.key(scope),ref(new))
            # Recheck all subscribed diagnoses, plus the current demonstration course and overview.
            targets={(a['audience'],a['target_node_id']) for a in self.store.all('diagnostic_artifact') if a['scope']==scope}
            targets|={(role,t) for role in (['teacher','student'] if scope['subject']['type']=='student' else ['teacher']) for t in [None]+([ 'C05'] if 'C05' in affected else [])}
            for audience,target in sorted(targets,key=lambda x:(x[1]!='C05',x[1] is None,x[0]!='teacher',x[1] or '')):self.ensure_diagnosis(scope,audience,target,'evaluation_changed')
            return {'changed':True,'duplicate':False,'event':event,'snapshot_ref':ref(new)}
    def demo_update(self,scope,base_revision,event_id):
        if not isinstance(event_id,str) or not 1<=len(event_id)<=128:raise ValueError('event_id无效')
        request_hash=digest({'scope':scope,'base_revision':base_revision,'kind':'demo_update'})
        with self.lock:
            receipt=self.store.get('receipt',event_id)
            if receipt:
                if receipt['request_hash']!=request_hash or receipt['scope']!=scope:raise Conflict('事件ID冲突')
                return {**receipt['response'],'duplicate':True}
            old_event=self.store.get('evaluation_changed',event_id)
            if old_event:
                if old_event['request_hash']!=request_hash or old_event['scope']!=scope:raise Conflict('事件ID冲突')
                return {'changed':True,'duplicate':True,'event':old_event,'snapshot_ref':old_event['after']}
            old=self.ensure(scope)
            if old['revision']!=base_revision:raise Conflict('评价版本已更新，请刷新后重试')
            if scope['subject']['type']!='student' or scope['scenario_id']!='mixed_evidence':raise ValueError('模拟补测仅适用于学生阶段性评价')
            new=copy.deepcopy(old);target=next((f'C05.K{k:02}' for k in range(4,7) if new['node_results'][f'C05.K{k:02}']['status']['achievement_rate'] is None),None)
            if target is None:
                response={'changed':False,'duplicate':False,'event':None,'snapshot_ref':ref(old)}
                self.store.put('receipt',event_id,{'scope':scope,'request_hash':request_hash,'response':response});return response
            new['revision']+=1;r=new['node_results'][target];k=int(target[-2:]);value={4:74.,5:82.,6:88.}[k]
            new['evaluation_context']['as_of']=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            r['status'].update(achievement_rate=value,health_color='yellow' if value<80 else 'green',coverage_rate=1.,learning_state='completed',learning_progress=1.,grey_reason=None,evidence_granularity='knowledge_assessment',aggregation_basis='knowledge_assessment',sample_count=1,score_is_provisional=False)
            eid=uid('demo-assessment');r['evidence_refs']=[eid]
            new['evidence'].append({'evidence_id':eid,'node_id':target,'subject':scope['subject'],'kind':'knowledge_assessment','title':'模拟补测','score':value,'sample_count':1,'source':'synthetic_demo','original_record_ref':'runtime-demo:'+event_id})
            for level in ['L2_Course','L1_Ability']:
                for nid,n in self.nodes.items():
                    result=new['node_results'][nid];s=result['status']
                    if n['level']!=level or s['aggregation_basis']!='weighted_inputs':continue
                    es=self.incoming[nid];cov=round(sum(e['aggregation_weight']*new['node_results'][e['source']]['status']['coverage_rate'] for e in es),6)
                    value=round(sum(e['aggregation_weight']*new['node_results'][e['source']]['status']['coverage_rate']*(new['node_results'][e['source']]['status']['achievement_rate'] or 0) for e in es)/cov,6) if cov else None
                    states=[new['node_results'][e['source']]['status']['learning_state'] for e in es]
                    learning='completed' if all(v=='completed' for v in states) else 'not_started' if all(v=='not_started' for v in states) else 'in_progress'
                    color='grey' if value is None or cov<.8 else 'green' if value>=80 else 'yellow' if value>=60 else 'red'
                    s.update(achievement_rate=value,coverage_rate=cov,health_color=color,learning_state=learning,
                        grey_reason=None if color!='grey' else 'not_started' if learning=='not_started' else 'insufficient_coverage' if cov else 'no_evidence',score_is_provisional=0<cov<1,sample_count=int(value is not None))
                    if level=='L2_Course':s['learning_progress']=round(sum(e['aggregation_weight']*(new['node_results'][e['source']]['status']['learning_progress'] or 0) for e in es),6)
                    result['evidence_refs']=sorted({i for e in es for i in new['node_results'][e['source']]['evidence_refs']})
            from collections import Counter
            counts=Counter(r['status']['health_color'] for r in new['node_results'].values());summary=new['summary']
            summary['health_counts']={c:counts[c] for c in ['green','yellow','red','grey']}
            summary['ability_profile']=[{'node_id':nid,'score':new['node_results'][nid]['status']['achievement_rate'],'coverage':new['node_results'][nid]['status']['coverage_rate']} for nid,n in self.nodes.items() if n['level']=='L1_Ability']
            known=[nid for nid,r in new['node_results'].items() if r['status']['achievement_rate'] is not None]
            summary['weak_node_ids']=sorted([nid for nid in known if new['node_results'][nid]['status']['health_color']=='red'],key=lambda k:new['node_results'][k]['status']['achievement_rate'])[:6]
            summary['strength_node_ids']=sorted([nid for nid in known if new['node_results'][nid]['status']['health_color']=='green'],key=lambda k:-new['node_results'][k]['status']['achievement_rate'])[:5]
            summary['provisional_low_node_ids']=[nid for nid in known if new['node_results'][nid]['status']['score_is_provisional'] and new['node_results'][nid]['status']['achievement_rate']<60]
            return self.submit(scope,new,base_revision,event_id,request_hash)
    def process_one(self):
        with self.lock:
            queued=[r for r in self.store.all('agent_run') if r['state']=='queued']
            run=min(queued,key=lambda r:({'question':0,'view':1,'retry':1,'evaluation_changed':2}[r['trigger']],r['created_at'])) if queued else None
            if not run:return False
            latest=self.ensure(run['scope'])
            if run['mode']=='diagnosis' and run['snapshot_ref']!=ref(latest):
                run.update(state='superseded',updated_at=now());self.store.put('agent_run',run['run_id'],run);return True
            snap=self.store.get('snapshot',run['snapshot_ref']['snapshot_id'],run['snapshot_ref']['revision'])
            ctx=self.context(run['scope'],run['audience'],run['target_node_id'],snap)
            turn=self.store.get('conversation_turn',run['turn_id']) if run['turn_id'] else None
            if turn and turn['discussed_artifact_id']:
                discussed=self.store.get('diagnostic_artifact',turn['discussed_artifact_id'])
                if discussed and discussed['scope']==run['scope'] and discussed['audience']==run['audience'] and discussed['target_node_id']==run['target_node_id']:
                    ctx.discussion={'artifact_id':discussed['artifact_id'],'generated_against':discussed['generated_against'],'validated_against':discussed['validated_against'],
                        'matches_answer_version':discussed['validated_against']==ref(snap),'origin':discussed['origin'],'explanation':discussed['output']['explanation'][:2000]}
            history=[{'question':t['question'][:400],'answer':t['answer']['explanation'][:800],'snapshot_ref':t['snapshot_ref']} for t in self.store.all('conversation_turn') if turn and t['session_id']==turn['session_id'] and t['state']=='succeeded'][-4:]
            run.update(state='running',updated_at=now());self.store.put('agent_run',run['run_id'],run)
            if turn:turn['state']='running';self.store.put('conversation_turn',turn['turn_id'],turn)
        try:
            output,usage=self.provider.generate(ctx,turn['question'] if turn else None,history)
            ctx.validate_output(output)
            with self.lock:
                if self.stopping:return True
                latest=self.ensure(run['scope']);current_ctx=self.context(run['scope'],run['audience'],run['target_node_id'],latest,ctx.dependencies())
                valid=ctx.fingerprint(self.provider.identity)==current_ctx.fingerprint(self.provider.identity)
                run.update(state='succeeded' if turn or valid else 'superseded',usage=usage,tool_trace=ctx.trace,updated_at=now())
                if turn:
                    turn.update(state='succeeded',answer=output);self.store.put('conversation_turn',turn['turn_id'],turn)
                else:
                    artifact=record('diagnostic_artifact',artifact_id=uid('diag'),scope=run['scope'],audience=run['audience'],target_node_id=run['target_node_id'],generated_against=ref(snap),validated_against=ref(latest) if valid else ref(snap),fingerprint=ctx.fingerprint(self.provider.identity),dependencies=ctx.dependencies(),validity='fresh' if valid else 'historical',publication='active',origin=self.provider.origin,output=output,created_at=now())
                    self.store.put('diagnostic_artifact',artifact['artifact_id'],artifact);run['artifact_id']=artifact['artifact_id']
                    if valid:self.store.pointer(self.dkey(run['scope'],run['audience'],run['target_node_id']),{'id':artifact['artifact_id']})
                self.store.put('agent_run',run['run_id'],run)
        except Exception as error:
            with self.lock:
                if self.stopping:return True
                run.update(state='failed',error=str(error)[:240],tool_trace=ctx.trace,usage=getattr(ctx,'usage',run['usage']),updated_at=now());self.store.put('agent_run',run['run_id'],run)
                if turn:turn.update(state='failed');self.store.put('conversation_turn',turn['turn_id'],turn)
        return True
    def _worker(self):
        while not self.stopping:
            if not self.process_one():self.wake.wait(.25);self.wake.clear()
    def close(self):
        self.stopping=True;self.wake.set()
        if self.worker.is_alive():self.worker.join(timeout=2)
        if not self.worker.is_alive():self.store.close()
