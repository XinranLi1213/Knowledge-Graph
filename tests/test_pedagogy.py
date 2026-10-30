import copy
import json
import tempfile
import unittest
import threading
import time
from pathlib import Path
from agent.engine import Engine
from agent.provider import Provider,ProviderError,GenerationError
from agent.pedagogy import instructions,intent,PROMPT_VERSION,clean_display,check_presentation
from agent.batches import Batches

ROOT=Path(__file__).resolve().parents[1]

def output(node='C02'):
    return {'explanation':'先检查小信号等效电路的分析过程。','sections':{'conclusion':'应通过短测检查本课重点概念的运用。','actions':['请独立完成一题工作点分析，画出等效电路并标出参数。'],'verification':'改变一个偏置条件复做，比较波形与计算并记录差异。'},'cited_node_ids':[node],'cited_evidence_ids':[],'resource_ids':[],'limitations':['现有分数不能证明具体错因。']}
def completion(value,reason='stop'):
    return {'choices':[{'finish_reason':reason,'message':{'role':'assistant','content':json.dumps(value,ensure_ascii=False)}}],'usage':{'prompt_tokens':100,'completion_tokens':50}}

class PedagogyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.engine=Engine(ROOT,Path(self.tmp.name)/'agent.sqlite',Provider('rules'),False,load_seed=False)
        self.scope=self.engine.scope({'type':'student','id':'DEMO001'},'mixed_evidence')
    def tearDown(self):self.engine.close();self.tmp.cleanup()
    def ctx(self,node='C02',role='teacher'):return self.engine.context(self.scope,role,node)
    def test_all_nodes_have_authored_tasks_and_context_budget(self):
        self.assertEqual(set(self.engine.teaching['nodes']),set(self.engine.nodes))
        for nid in self.engine.nodes:
            ctx=self.ctx(nid);self.assertLess(len(json.dumps(ctx.model_payload(),ensure_ascii=False)),48000)
            self.assertIn(nid,ctx.teaching_context()['items'])
        ctx=self.ctx('C02');self.assertLess(len(json.dumps(ctx.model_payload(),ensure_ascii=False)),len(json.dumps(ctx.payload(),ensure_ascii=False)))
    def test_role_level_state_and_question_routing(self):
        self.assertEqual(intent('给我出一道自测题'),'assessment');self.assertEqual(intent('解释第二步'),'explain')
        self.assertIn('课程节点',instructions(self.ctx(),None));self.assertIn('学生学习辅导',instructions(self.ctx(role='student'),'怎么复习'))
        self.assertIn('知识点',instructions(self.ctx('C02.K03'),None));self.assertIn('能力节点',instructions(self.ctx('A01'),None))
    def test_truncation_has_one_repair_and_attempt_log(self):
        calls=[]
        def transport(p):calls.append(copy.deepcopy(p));return completion(output(),'length' if len(calls)==1 else 'stop')
        ctx=self.ctx();value,usage=Provider('deepseek','test-key','test-model',transport).generate(ctx)
        self.assertEqual(usage['model_calls'],2);self.assertEqual(ctx.attempts[0]['error_code'],'truncated');self.assertEqual(calls[1]['tool_choice'],'none')
        self.assertIn('actions',value['sections']);self.assertGreaterEqual(calls[1]['max_tokens'],calls[0]['max_tokens'])
    def test_invalid_output_repair_is_bounded(self):
        ctx=self.ctx();calls=[]
        def transport(p):calls.append(p);return completion({'wrong':'shape'})
        with self.assertRaises(GenerationError):Provider('deepseek','test-key','test-model',transport).generate(ctx)
        self.assertEqual(len(calls),2);self.assertEqual(ctx.attempts[-1]['error_code'],'invalid_output')
    def test_transient_retry_but_no_balance_retry(self):
        calls=[]
        def transport(p):
            calls.append(p)
            if len(calls)==1:raise ProviderError('network','temporary')
            return completion(output())
        ctx=self.ctx();Provider('deepseek','test-key','test-model',transport).generate(ctx);self.assertEqual(len(calls),2)
        count=[]
        def no_balance(p):count.append(p);raise ProviderError('insufficient_balance','余额不足')
        with self.assertRaises(ProviderError):Provider('deepseek','test-key','test-model',no_balance).generate(self.ctx())
        self.assertEqual(len(count),1)
    def test_cross_node_history_stays_same_subject_and_role(self):
        seen=[]
        def transport(p):
            value=json.loads(p['messages'][1]['content']);seen.append(value)
            return completion(output(value['context']['target_node_id']))
        self.engine.provider=Provider('deepseek','test-key','test-model',transport)
        a=self.engine.ask(self.scope,'teacher','C02','请给一道题');self.engine.process_one(a['run']['run_id'])
        b=self.engine.ask(self.scope,'teacher','C02.K03','再解释第二步');self.engine.process_one(b['run']['run_id'])
        self.assertEqual(seen[-1]['history'][0]['target_node_id'],'C02')
        c=self.engine.ask(self.scope,'student','C02.K03','再解释第二步');self.engine.process_one(c['run']['run_id'])
        self.assertEqual(seen[-1]['history'],[])
    def test_read_teaching_and_dependency_version_change(self):
        ctx=self.ctx();self.assertIn('practice',ctx.call('read_teaching',{'node_id':'C02.K03'})['reference'])
        old=ctx.fingerprint(None,True);self.engine.teaching['version']='new';self.assertNotEqual(old,self.ctx().fingerprint(None,True))
    def test_batch_scope_and_quality_gate(self):
        b=Batches(self.engine);self.assertEqual(len(b.tasks('sample',self.scope,'teacher')),24)
        self.assertEqual(len(b.tasks('first_release',self.scope,'teacher')),417)
        self.engine.provider=Provider('deepseek','test-key','test-model',lambda p:completion(output()))
        with self.assertRaises(ValueError):b.start('first_release',self.scope,'teacher',8)
        with self.assertRaises(ValueError):b.start('sample',self.scope,'teacher',0)
    def test_generation_facts_include_teaching_reference(self):
        self.engine.provider=Provider('deepseek','test-key','test-model',lambda p:completion(output()))
        job=self.engine.ensure_diagnosis(self.scope,'teacher','C02','retry');self.engine.process_one(job['run']['run_id'])
        artifact=self.engine.fresh_artifact(self.scope,'teacher','C02');self.assertEqual(artifact['context_version'],3)
        self.assertEqual(artifact['generation']['prompt_version'],PROMPT_VERSION)
        self.engine.teaching['nodes']['C02']['practice']='新版教学任务'
        self.assertIsNone(self.engine.fresh_artifact(self.scope,'teacher','C02'))
    def test_omitted_evidence_is_visible_and_not_treated_as_absent(self):
        ctx=self.ctx('A01');data=ctx.model_payload()
        self.assertIsNone(data['nodes']['A01']['child_knowledge_evaluated'])
        self.assertGreater(data['nodes']['A01']['omitted_evidence_count'],0)
        value=output('A01');value['sections']['conclusion']='唯一证据来自一门课程。'
        with self.assertRaises(ValueError):check_presentation(value,None,ctx)
    def test_display_ids_are_labels_and_question_code_is_untouched(self):
        value=output();value['sections']['conclusion']='C02模拟电子技术应关注C02.K03。'
        clean=clean_display(value,self.ctx(),None)
        self.assertEqual(clean['sections']['conclusion'],'模拟电子技术应关注小信号放大。')
        self.assertEqual(clean_display(value,self.ctx(),'解释代码'),value)
    def test_batch_two_workers_no_duplicate_cursor_and_bounded_pause(self):
        counts={'active':0,'maximum':0};lock=threading.Lock()
        def transport(p):
            with lock:counts['active']+=1;counts['maximum']=max(counts['maximum'],counts['active'])
            time.sleep(.15)
            context=json.loads(p['messages'][1]['content'])['context'];node=context['target_node_id'] or next(iter(context['nodes']))
            with lock:counts['active']-=1
            return completion(output(node))
        self.engine.provider=Provider('deepseek','test-key','test-model',transport)
        manager=Batches(self.engine);b=manager.start('sample',self.scope,'teacher',max_tasks=2)
        manager.thread.join(5);value=manager.get(b['batch_id'])
        self.assertEqual(value['cursor'],2);self.assertEqual(value['state'],'paused')
        self.assertEqual(len(value['results']),2);self.assertEqual(counts['maximum'],2)
    def test_verified_examples_have_consistent_active_region_and_variant(self):
        from agent.exercises import examples
        reference=examples(self.ctx('C02.K03'));solution=next(e['solution'] for e in reference if e['id']=='common-emitter-v1')
        self.assertGreater(solution['VCEQ_V'],7);self.assertTrue(solution['variant_DC_unchanged'])
        self.assertLess(abs(solution['variant_Av']),abs(solution['Av']))
        self.assertAlmostEqual(solution['ICQ_A'],.002017857142857143)
    def test_explanation_omits_unneeded_grades_and_hidden_answer(self):
        seen=[]
        def transport(p):seen.append(json.loads(p['messages'][1]['content'])['context']);return completion(output('C09.K01'))
        Provider('deepseek','test-key','test-model',transport).generate(self.ctx('C09.K01'),'给我出一道自测题，先不给答案')
        self.assertEqual(seen[0]['evidence'],[]);self.assertTrue(all('status' not in n for n in seen[0]['nodes'].values()))
        self.assertTrue(all('solution' not in e for e in seen[0]['verified_examples']))
    def test_exercise_guard_rejects_known_bad_rule_and_answer_leak(self):
        from agent.exercises import check_answer
        value=output();value['explanation']='RB只出现在直流通路。'
        with self.assertRaises(ValueError):check_answer(value,self.ctx('C02.K03'),'解释这个例子')
        value['explanation']='p=2，q=2.00。'
        with self.assertRaises(ValueError):check_answer(value,self.ctx('C09.K01'),'先不给答案')
        value['explanation']='二极管截止、电流为零。'
        with self.assertRaises(ValueError):check_answer(value,self.ctx('C02'),'不提供完整答案')
        value['explanation']='能力层下已评价知识点数为0。'
        with self.assertRaises(ValueError):check_answer(value,self.ctx('A04'),'现在能判断吗')

if __name__=='__main__':unittest.main()
