from pathlib import Path
import copy
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from agent.engine import Engine,Conflict
from agent.provider import Provider
from agent.context import ref,digest
from agent.http_server import create_server

ROOT=Path(__file__).resolve().parents[1]
def completion(output):return {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(output,ensure_ascii=False)}}],'usage':{'prompt_tokens':50,'completion_tokens':30}}
def output():return {'explanation':'依据当前对象与指定版本的评价解释。','sections':{'conclusion':'当前需要结合评价覆盖判断。','actions':['安排一次针对本课程知识点的短测并记录步骤。'],'verification':'通过独立复做与教师核验比较改善情况。'},'cited_node_ids':['C05'],'cited_evidence_ids':[],'resource_ids':[],'limitations':[]}

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'agent.sqlite'
        self.engine=Engine(ROOT,self.path,Provider('rules'),False,allow_rules=True,load_seed=False);self.scope=self.engine.scope({'type':'student','id':'DEMO001'},'mixed_evidence')
    def tearDown(self):self.engine.close();self.tmp.cleanup()
    def drain(self):
        for _ in range(50):
            if not self.engine.process_one():return
        self.fail('任务未在预算内完成')
    def test_contracts_queue_and_persistence(self):
        run=self.engine.ensure_diagnosis(self.scope,'teacher','C05')['run'];self.drain()
        artifact=self.engine.state(self.scope,'teacher','C05')['artifact'];self.assertEqual(artifact['origin'],'rules_demo')
        self.assertEqual(self.engine.store.get('agent_run',run['run_id'])['state'],'succeeded')
        self.engine.close();self.engine=Engine(ROOT,self.path,Provider('rules'),False,allow_rules=True,load_seed=False)
        self.assertEqual(self.engine.state(self.scope,'teacher','C05')['artifact']['artifact_id'],artifact['artifact_id'])
    def test_javascript_numeric_round_trip_does_not_invalidate_dependencies(self):
        self.assertEqual(digest({'score':74.0,'coverage':1.0}),digest({'coverage':1,'score':74}))
        self.assertNotEqual(digest({'score':0}),digest({'score':None}))
        self.engine.demo_update(self.scope,1,'round-first');self.drain()
        old=self.engine.artifact(self.scope,'teacher','C05')
        def js(v):
            if isinstance(v,float) and v.is_integer():return int(v)
            if isinstance(v,dict):return {k:js(x) for k,x in v.items()}
            if isinstance(v,list):return [js(x) for x in v]
            return v
        snap=js(copy.deepcopy(self.engine.ensure(self.scope)));snap['revision']=3
        next(e for e in snap['evidence'] if e['node_id']=='C09.K01')['title']='外部描述修订'
        self.engine.submit(self.scope,snap,2,'round-second')
        new=self.engine.state(self.scope,'teacher','C05')['artifact']
        self.assertEqual(old['generated_against'],new['generated_against']);self.assertEqual(new['validated_against']['revision'],3)
    def test_dedupe_diagnosis_and_update_event(self):
        a=self.engine.ensure_diagnosis(self.scope,'teacher','C05');b=self.engine.ensure_diagnosis(self.scope,'teacher','C05')
        self.assertEqual(a['run']['run_id'],b['run']['run_id'])
        update=self.engine.demo_update(self.scope,1,'event1');duplicate=self.engine.demo_update(self.scope,1,'event1')
        self.assertTrue(duplicate['duplicate']);self.assertEqual(update['snapshot_ref'],duplicate['snapshot_ref'])
        self.assertEqual(self.engine.ensure(self.scope)['revision'],2)
        with self.assertRaises(Conflict):self.engine.demo_update(self.scope,2,'event1')
    def test_timestamp_only_update_has_no_new_revision(self):
        snap=copy.deepcopy(self.engine.ensure(self.scope));snap['revision']=2;snap['evaluation_context']['as_of']='2026-10-30'
        result=self.engine.submit(self.scope,snap,1,'clock-only');self.assertFalse(result['changed'])
        self.assertEqual(self.engine.ensure(self.scope)['revision'],1)
        self.assertTrue(self.engine.submit(self.scope,snap,1,'clock-only')['duplicate'])
    def test_deterministic_demo_aggregation_and_facts_before_diagnosis(self):
        for i in range(1,4):self.engine.demo_update(self.scope,i,'grade-'+str(i))
        snap=self.engine.ensure(self.scope);course=snap['node_results']['C05']['status']
        self.assertEqual(snap['revision'],4);self.assertEqual(course['coverage_rate'],1);self.assertEqual(course['learning_progress'],1)
        self.assertEqual(course['learning_state'],'completed');self.assertGreater(course['achievement_rate'],60)
        self.assertIsNone(self.engine.artifact(self.scope,'teacher','C05'))
        self.drain();self.assertEqual(self.engine.state(self.scope,'teacher','C05')['artifact']['validated_against']['revision'],4)
    def test_unrelated_explanation_revalidated_without_model(self):
        self.engine.ensure_diagnosis(self.scope,'teacher','C09.K01');self.drain()
        old=self.engine.artifact(self.scope,'teacher','C09.K01');self.engine.demo_update(self.scope,1,'update-unrelated')
        new=self.engine.state(self.scope,'teacher','C09.K01')['artifact']
        self.assertIsNotNone(new);self.assertEqual(old['generated_against'],new['generated_against']);self.assertEqual(new['validated_against']['revision'],2)
        self.assertNotEqual(old['artifact_id'],new['artifact_id'])
    def test_evidence_change_with_same_score_invalidates_explanation(self):
        self.engine.ensure_diagnosis(self.scope,'teacher','C05');self.drain()
        snap=copy.deepcopy(self.engine.ensure(self.scope));snap['revision']=2
        e=next(e for e in snap['evidence'] if e['node_id']=='C05.K01');e['title']='评分依据已修正'
        self.engine.submit(self.scope,snap,1,'evidence-update')
        self.assertIsNone(self.engine.state(self.scope,'teacher','C05')['artifact']);self.drain()
        self.assertEqual(self.engine.state(self.scope,'teacher','C05')['artifact']['generated_against']['revision'],2)
    def test_foreign_snapshot_and_forged_summary_rejected(self):
        snap=copy.deepcopy(self.engine.ensure(self.scope));snap['revision']=2;snap['subject']['id']='DEMO002'
        with self.assertRaises(ValueError):self.engine.submit(self.scope,snap,1,'foreign')
        snap=copy.deepcopy(self.engine.ensure(self.scope));snap['revision']=2;snap['summary']['weak_node_ids']=[]
        with self.assertRaises(ValueError):self.engine.submit(self.scope,snap,1,'wrong-summary')
    def test_read_tools_cannot_change_student_or_escape_scope(self):
        ctx=self.engine.context(self.scope,'teacher','C05')
        with self.assertRaises(ValueError):ctx.call('read_node',{'node_id':'C05','subject_id':'DEMO002'})
        with self.assertRaises(ValueError):ctx.call('read_node',{'node_id':'C17'})
        self.assertEqual(len(ctx.seen),11)
    def test_structured_tool_loop_uses_bound_facts(self):
        calls=[]
        def transport(payload):
            calls.append(payload)
            if len(calls)==1:return {'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':'read_evidence','arguments':'{"node_id":"C05"}'}}]}}]}
            return completion(output())
        p=Provider('openai','unit-test-key','unit-model',transport);ctx=self.engine.context(self.scope,'teacher','C05')
        result,usage=p.generate(ctx,'为什么？');self.assertEqual(usage['model_calls'],2);self.assertEqual(ctx.trace[0]['tool'],'read_evidence')
        self.assertEqual(calls[0]['response_format']['type'],'json_schema');self.assertEqual(calls[1]['messages'][-1]['role'],'tool')
        self.assertEqual(result,output())
    def test_followup_includes_discussed_diagnosis_with_version(self):
        self.engine.ensure_diagnosis(self.scope,'teacher','C05');self.drain()
        artifact=self.engine.artifact(self.scope,'teacher','C05');payloads=[]
        def transport(payload):
            payloads.append(json.loads(payload['messages'][1]['content']));return completion(output())
        self.engine.provider=Provider('openai','unit-test-key','unit-model',transport)
        self.engine.ask(self.scope,'teacher','C05','你刚才的解释是什么意思？');self.drain()
        discussion=payloads[0]['context']['discussed_diagnosis']
        self.assertEqual(discussion['artifact_id'],artifact['artifact_id'])
        self.assertTrue(discussion['matches_answer_version']);self.assertEqual(discussion['origin'],'rules_demo')
    def test_unknown_citations_and_refusals_rejected_without_fallback(self):
        bad=output();bad['cited_node_ids']=['C17']
        p=Provider('openai','unit-test-key','unit-model',lambda _:completion(bad))
        with self.assertRaises(ValueError):p.generate(self.engine.context(self.scope,'teacher','C05'))
        p=Provider('openai','unit-test-key','unit-model',lambda _:{'choices':[{'finish_reason':'stop','message':{'refusal':'拒绝'}}]})
        with self.assertRaises(ValueError):p.generate(self.engine.context(self.scope,'teacher','C05'))
    def test_model_failure_is_visible_and_does_not_block_facts(self):
        self.engine.provider=Provider('openai','unit-test-key','unit-model',lambda _:completion({'bad':'shape'}))
        run=self.engine.ensure_diagnosis(self.scope,'teacher','C05')['run'];self.drain()
        self.assertEqual(self.engine.store.get('agent_run',run['run_id'])['state'],'failed')
        self.assertIsNotNone(self.engine.ensure(self.scope)['node_results']['C05']['status']['achievement_rate'])
        self.assertIsNone(self.engine.state(self.scope,'teacher','C05')['artifact'])
    def test_old_model_run_cannot_replace_new_diagnosis(self):
        gate=threading.Event();started=threading.Event()
        def transport(_):started.set();gate.wait(5);return completion(output())
        self.engine.provider=Provider('openai','unit-test-key','unit-model',transport)
        run=self.engine.ensure_diagnosis(self.scope,'teacher','C05')['run'];thread=threading.Thread(target=self.engine.process_one)
        thread.start();self.assertTrue(started.wait(3));self.engine.demo_update(self.scope,1,'while-generating');gate.set();thread.join(5)
        self.assertEqual(self.engine.store.get('agent_run',run['run_id'])['state'],'superseded')
        self.assertIsNone(self.engine.artifact(self.scope,'teacher','C05'));self.drain()
        self.assertEqual(self.engine.state(self.scope,'teacher','C05')['artifact']['validated_against']['revision'],2)
    def test_question_during_update_stays_on_old_revision(self):
        gate=threading.Event();started=threading.Event();versions=[]
        def transport(payload):
            versions.append(json.loads(payload['messages'][1]['content'])['context']['snapshot_ref']['revision']);started.set();gate.wait(5);return completion(output())
        self.engine.provider=Provider('openai','unit-test-key','unit-model',transport)
        result=self.engine.ask(self.scope,'teacher','C05','为什么这门课低？');thread=threading.Thread(target=self.engine.process_one)
        thread.start();self.assertTrue(started.wait(3));self.engine.demo_update(self.scope,1,'while-answering');gate.set();thread.join(5)
        state=self.engine.state(self.scope,'teacher','C05');turn=next(t for t in state['turns'] if t['turn_id']==result['turn']['turn_id'])
        self.assertEqual(versions[0],1);self.assertEqual(turn['snapshot_ref']['revision'],1);self.assertTrue(turn['historical'])
        self.engine.ask(self.scope,'teacher','C05','现在有什么变化？');self.drain()
        self.assertEqual(self.engine.state(self.scope,'teacher','C05')['turns'][-1]['snapshot_ref']['revision'],2)
    def test_sessions_do_not_mix_students_or_audiences(self):
        self.engine.ask(self.scope,'teacher','C05','这门课？');self.drain()
        other=self.engine.scope({'type':'student','id':'DEMO002'},'mixed_evidence')
        self.assertEqual(self.engine.state(other,'teacher','C05')['turns'],[])
        self.assertEqual(self.engine.state(self.scope,'student','C05')['turns'],[])
    def test_queued_work_recovers_after_restart(self):
        run=self.engine.ensure_diagnosis(self.scope,'teacher','C05')['run'];run['state']='running';self.engine.store.put('agent_run',run['run_id'],run)
        self.engine.close();self.engine=Engine(ROOT,self.path,Provider('rules'),False,allow_rules=True,load_seed=False);self.drain()
        self.assertEqual(self.engine.store.get('agent_run',run['run_id'])['state'],'succeeded')

class HTTPTests(unittest.TestCase):
    def test_api_and_static_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=create_server(ROOT,Path(tmp)/'http.sqlite',0,Provider('rules'),load_seed=False);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_address[1])
            try:
                with urllib.request.urlopen(base+'/api/agent/health') as r:self.assertEqual(json.load(r)['provider'],'rules_demo')
                for target in ['/.git/config','/.env','/.runtime/agent.sqlite3','/agent/provider.py']:
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+target)
                    self.assertEqual(error.exception.code,403)
                req=urllib.request.Request(base+'/api/agent/ask',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://foreign.example'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
                self.assertEqual(error.exception.code,400)
            finally:server.shutdown();server.server_close();server.engine.close();thread.join(2)

if __name__=='__main__':unittest.main()
