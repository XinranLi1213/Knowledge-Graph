from pathlib import Path
import copy
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from agent.engine import Engine
from agent.provider import Provider,ProviderError
from agent.settings import Settings
from agent.bundles import export_bundle,load_bundle

ROOT=Path(__file__).resolve().parents[1]

def transport(payload):
    context=json.loads(payload['messages'][1]['content'])['context']
    node=context['target_node_id'] or next(iter(context['nodes']))
    output={'explanation':'测试传输生成的诊断：仅用于自动化测试。','cited_node_ids':[node],'cited_evidence_ids':[],'resource_ids':[],'limitations':['自动化测试数据，不是真实外部模型成果。']}
    return {'_request_id':'mock-request-1','choices':[{'finish_reason':'stop','message':{'content':json.dumps(output,ensure_ascii=False)}}],'usage':{'prompt_tokens':100,'completion_tokens':30}}

def factory(key,model):
    if key=='bad-key':
        def fail(_):raise ProviderError('authentication','密钥无效，请检查API Key。')
        return Provider('openai',key,model,fail)
    return Provider('openai',key,model,transport)

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.engine=Engine(ROOT,Path(self.tmp.name)/'agent.sqlite',Provider('rules'),False)
        self.scope=self.engine.scope({'type':'student','id':'DEMO001'},'mixed_evidence');self.settings=Settings(self.engine,factory)
    def tearDown(self):self.engine.close();self.tmp.cleanup()
    def generate(self):
        self.settings.test_and_enable({'api_key':'test-key','model':'test-model'})
        run=self.engine.ensure_diagnosis(self.scope,'teacher','C05','retry')['run']
        self.engine.process_one()
        return self.engine.store.get('agent_run',run['run_id'])
    def test_readonly_backend_forbids_ask_and_retry_without_creating_jobs(self):
        self.assertFalse(self.engine.capabilities()['can_ask'])
        with self.assertRaises(PermissionError):self.engine.ask(self.scope,'teacher','C05','为什么？')
        with self.assertRaises(PermissionError):self.engine.ensure_diagnosis(self.scope,'teacher','C05','retry')
        self.engine.ensure_diagnosis(self.scope,'teacher','C05')
        self.assertEqual(self.engine.store.all('agent_run'),[])
    def test_bad_configuration_preserves_working_provider_and_never_exposes_key(self):
        result=self.settings.test_and_enable({'api_key':'test-key','model':'test-model'})
        self.assertTrue(result['verified']);self.assertNotIn('test-key',json.dumps(result))
        with self.assertRaises(ProviderError):self.settings.test_and_enable({'api_key':'bad-key','model':'other-model'})
        self.assertEqual(self.engine.provider.model,'test-model')
    def test_disconnect_during_test_prevents_late_activation(self):
        gate=threading.Event();started=threading.Event();failures=[]
        def delayed_factory(key,model):
            def delayed(payload):started.set();gate.wait(3);return transport(payload)
            return Provider('openai',key,model,delayed)
        self.settings.factory=delayed_factory
        def work():
            try:self.settings.test_and_enable({'api_key':'test-key','model':'test-model'})
            except ValueError as error:failures.append(str(error))
        thread=threading.Thread(target=work);thread.start();self.assertTrue(started.wait(2))
        self.settings.disconnect();gate.set();thread.join(3)
        self.assertFalse(self.engine.capabilities()['configured']);self.assertEqual(len(failures),1)
    def test_model_changes_and_disconnect_preserve_fact_validity(self):
        run=self.generate();self.assertEqual(run['state'],'succeeded');self.assertEqual(run['generation']['request_ids'],['mock-request-1'])
        old=self.engine.fresh_artifact(self.scope,'teacher','C05')
        self.settings.disconnect();new=self.engine.fresh_artifact(self.scope,'teacher','C05')
        self.assertEqual(new['artifact_id'],old['artifact_id']);self.assertFalse(self.engine.capabilities()['can_ask'])
        self.settings.test_and_enable({'api_key':'test-key','model':'second-model'})
        self.assertEqual(self.engine.fresh_artifact(self.scope,'teacher','C05')['artifact_id'],old['artifact_id'])
        # Viewing cached or absent nodes creates no new paid runs.
        before=len(self.engine.store.all('agent_run'));self.engine.ensure_diagnosis(self.scope,'teacher','C09')
        self.assertEqual(len(self.engine.store.all('agent_run')),before)
    def test_bundle_roundtrip_then_evidence_change_invalidates(self):
        self.generate();path=Path(self.tmp.name)/'bundle.json'
        self.assertEqual(export_bundle(self.engine,path),1);self.assertEqual(len(load_bundle(self.engine,path)),1)
        self.settings.disconnect();other=Engine(ROOT,Path(self.tmp.name)/'viewer.sqlite',Provider('rules'),False)
        try:
            other.seed_artifacts=load_bundle(other,path)
            self.assertIsNotNone(other.state(self.scope,'teacher','C05')['artifact'])
            self.assertEqual(export_bundle(other,path),1) # Empty runtime cannot erase existing results.
            received=[]
            def followup(payload):received.append(json.loads(payload['messages'][1]['content']));return transport(payload)
            other.provider=Provider('openai','test-key','test-model',followup)
            question=other.ask(self.scope,'teacher','C05','刚才的解释是什么意思？');other.process_one(question['run']['run_id'])
            self.assertIsNotNone(received[0]['context']['discussed_diagnosis'])
            other.provider=Provider('rules')
            other.demo_update(self.scope,1,'new-assessment')
            state=other.state(self.scope,'teacher','C05');self.assertIsNone(state['artifact']);self.assertEqual(state['historical_artifact']['validity'],'historical')
        finally:other.close()
        value=json.loads(path.read_text(encoding='utf-8'));value['entries'][0]['artifact']['output']['cited_node_ids']=['not-in-graph'];path.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(ValueError):load_bundle(self.engine,path)
    def test_revalidated_export_preserves_original_generation_run(self):
        run=self.generate();snap=copy.deepcopy(self.engine.ensure(self.scope));snap['revision']=2
        next(e for e in snap['evidence'] if e['node_id']=='C09.K01')['title']='无关修订'
        self.engine.submit(self.scope,snap,1,'independent')
        path=Path(self.tmp.name)/'bundle.json';self.assertEqual(export_bundle(self.engine,path),1)
        entry=json.loads(path.read_text(encoding='utf-8'))['entries'][0]
        self.assertEqual(entry['run']['artifact_id'],run['artifact_id'])
        self.assertNotEqual(entry['artifact']['artifact_id'],run['artifact_id']);self.assertEqual(len(load_bundle(self.engine,path)),1)
    def test_fresh_viewer_imports_packaged_facts_without_overwriting_local_scope(self):
        self.engine.demo_update(self.scope,1,'packaged-assessment');self.generate()
        path=Path(self.tmp.name)/'bundle.json';self.assertEqual(export_bundle(self.engine,path),1)
        viewer=Engine(ROOT,Path(self.tmp.name)/'fresh.sqlite',Provider('rules'),False)
        existing=Engine(ROOT,Path(self.tmp.name)/'existing.sqlite',Provider('rules'),False)
        try:
            viewer.seed_artifacts=load_bundle(viewer,path,bootstrap=True)
            self.assertEqual(viewer.ensure(self.scope)['revision'],2);self.assertIsNotNone(viewer.state(self.scope,'teacher','C05')['artifact'])
            existing.ensure(self.scope)
            existing.seed_artifacts=load_bundle(existing,path,bootstrap=True)
            self.assertEqual(existing.ensure(self.scope)['revision'],1);self.assertIsNone(existing.state(self.scope,'teacher','C05')['artifact'])
        finally:viewer.close();existing.close()

class ConfigurationHTTPTests(unittest.TestCase):
    def test_config_api_errors_capabilities_and_secret_boundaries(self):
        from agent.http_server import create_server
        with tempfile.TemporaryDirectory() as tmp:
            server=create_server(ROOT,Path(tmp)/'http.sqlite',0,Provider('rules'),factory)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_address[1])
            def post(path,value,headers=None):
                req=urllib.request.Request(base+'/api/agent/'+path,data=json.dumps(value).encode(),headers={'Content-Type':'application/json',**(headers or {})})
                with urllib.request.urlopen(req) as response:return json.load(response)
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:post('ask',{'question':'为什么？'})
                self.assertEqual(error.exception.code,403)
                result=post('config/test',{'api_key':'test-key','model':'test-model'})
                self.assertTrue(result['can_ask']);self.assertNotIn('test-key',json.dumps(result))
                with self.assertRaises(urllib.error.HTTPError) as error:post('config/test',{'api_key':'bad-key','model':'other'})
                self.assertEqual(error.exception.code,502);self.assertNotIn('bad-key',error.exception.read().decode())
                self.assertFalse(post('config/disconnect',{})['can_ask'])
                for headers in [{'Origin':'https://foreign.example'},{'Host':'foreign.example'}]:
                    with self.assertRaises(urllib.error.HTTPError):post('config/test',{'api_key':'test-key','model':'test-model'},headers)
            finally:server.shutdown();server.server_close();server.engine.close();thread.join(2)

if __name__=='__main__':unittest.main()
